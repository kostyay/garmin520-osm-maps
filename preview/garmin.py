"""Local classic Garmin IMG/TYP decoding, shared by the viewer and captures."""
import base64
from collections import OrderedDict
from io import BytesIO
import json
from pathlib import Path
import subprocess
import tempfile

import jpype
from PIL import Image
from shapely.geometry import box
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]


def bitmap(icon):
    pixels = base64.b64decode(icon['pixels'])
    if len(pixels) != icon['width'] * icon['height']:
        raise ValueError('Invalid TYP bitmap dimensions')
    palette = icon.get('palette', [])
    rgba = []
    for pixel in pixels:
        if palette and pixel > len(palette):
            raise ValueError('Invalid TYP palette index')
        colour = palette[pixel] if pixel < len(palette) else 'none'
        rgba.append(tuple(bytes.fromhex(colour[1:])) + (255,) if colour.startswith('#') else (0, 0, 0, 0))
    img = Image.new('RGBA', (icon['width'], icon['height']))
    img.putdata(rgba)
    output = BytesIO()
    img.save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()


def start_java():
    if not jpype.isJVMStarted():
        jpype.startJVM(jpype.getDefaultJVMPath(), '-Xmx1g',
                      classpath=[str(ROOT / '.tools/mkgmap-r4924/mkgmap.jar')])


class GarminMap:
    def __init__(self, image, typconv):
        self.directory = tempfile.TemporaryDirectory(prefix='garmin-viewer-')
        self.readers = []
        self.cache = OrderedDict()
        try:
            self._open(Path(image), typconv)
        except Exception:
            self.close()
            raise

    def _open(self, image, typconv):
        with image.open('rb') as stream:
            header = stream.read(512)
        if len(header) < 512 or header[0] != 0 or header[16:22] != b'DSKIMG':
            raise ValueError('Choose an unlocked classic Garmin IMG (mkgmap/OpenMTBMap). Encrypted and NT maps are unsupported.')
        start_java()
        fsclass = jpype.JClass('uk.me.parabola.imgfmt.sys.ImgFS')
        fs = fsclass.openFs(str(image))
        root = Path(self.directory.name)
        try:
            entries = {str(e.getFullName()): e for e in fs.list() if not e.isSpecial()}
            types = [name for name in entries if name.endswith('.TYP')]
            trees = [name for name in entries if name.endswith('.TRE')]
            if len(trees) > 500:
                raise ValueError('Choose an IMG with at most 500 map tiles.')
            if len(types) != 1 or not trees:
                raise ValueError('This viewer requires classic TRE/LBL/RGN tiles and exactly one embedded TYP. NT/GMP and multiple-style containers are unsupported.')
            channel = fs.open(types[0], 'r')
            try:
                buffer = jpype.JClass('java.nio.ByteBuffer').allocate(entries[types[0]].getSize())
                while buffer.hasRemaining():
                    if channel.read(buffer) <= 0:
                        raise ValueError('Incomplete TYP file')
                (root/'map.typ').write_bytes(bytes(buffer.array()))
            finally:
                channel.close()
            subprocess.run([str(typconv), 'bin2txt', str(root/'map.typ'), '--format', 'json', '-o', str(root/'typ.json')],
                           check=True, capture_output=True, timeout=30)
            typ = json.loads((root/'typ.json').read_text())
            self.styles = {}
            for kind in ('lines', 'polygons', 'points'):
                for item in typ[kind]:
                    code = item['type']
                    if kind != 'points' and code < 0x10000:
                        code >>= 8
                    item['kind'] = kind
                    item['code'] = code
                    item['name'] = item.get('labels', {}).get('00', '').strip() or f'{kind[:-1].title()} {code:#x}'
                    if kind == 'lines' and code in (0x20, 0x21, 0x22):
                        # TYP labels describe the original contour interval, not a filtered build's interval.
                        item['name'] = {0x20: 'Minor contours', 0x21: 'Index contours', 0x22: 'Major contours'}[code]
                    for field in ('dayIcon', 'nightIcon', 'dayPattern', 'nightPattern'):
                        if field in item:
                            item[field]['url'] = bitmap(item[field])
                            del item[field]['pixels']
                    self.styles[f'{kind}:{code}'] = item
            buffer = jpype.JClass('java.nio.ByteBuffer').allocate(65536)
            Reader = jpype.JClass('uk.me.parabola.imgfmt.app.map.MapReader')
            for tree in trees:
                stem = tree.rsplit('.', 1)[0]
                if any(f'{stem}.{ext}' not in entries for ext in ('LBL', 'RGN')):
                    raise ValueError('A TRE tile is missing its LBL or RGN data')
                params = jpype.JClass('uk.me.parabola.imgfmt.FileSystemParam')()
                params.setBlockSize(512)
                target = root/f'{len(self.readers)}.img'
                out = fsclass.createFs(str(target), params)
                try:
                    for ext in ('TRE', 'LBL', 'RGN', 'NET', 'NOD'):
                        name = f'{stem}.{ext}'
                        if name not in entries:
                            continue
                        source = fs.open(name, 'r')
                        destination = jpype.JClass('uk.me.parabola.imgfmt.app.BufferedImgFileWriter')(out.create(name), str(target))
                        try:
                            remaining = entries[name].getSize()
                            while remaining:
                                buffer.clear()
                                buffer.limit(min(remaining, buffer.capacity()))
                                n = source.read(buffer)
                                if n <= 0:
                                    raise ValueError('Incomplete IMG subfile')
                                remaining -= n
                                buffer.flip()
                                destination.put(buffer)
                        finally:
                            source.close()
                            # ImgFS allocates/finalizes destination channels together on close.
                finally:
                    out.close()
                reader = Reader(str(target))
                bounds = reader.getTreBounds()
                scale = 360 / 2**24
                bounds = [bounds.getMinLong()*scale, bounds.getMinLat()*scale,
                          bounds.getMaxLong()*scale, bounds.getMaxLat()*scale]
                levels = [(int(z.getResolution()), int(z.getLevel())) for z in reader.getLevels()]
                self.readers.append((reader, bounds, levels))
        finally:
            fs.close()
        bounds = [min(r[1][i] for r in self.readers) if i < 2 else max(r[1][i] for r in self.readers) for i in range(4)]
        self.metadata = {'name': image.name, 'bytes': image.stat().st_size, 'bounds': bounds,
                         'tiles': len(self.readers), 'styles': self.styles, 'typ': typ['header']}

    def features(self, bounds, zoom):
        requested = box(*bounds)
        bits = 24 if zoom >= 14 else 22 if zoom >= 12 else 20 if zoom >= 10 else 18
        result, unknown = [], set()
        for index, (reader, extent, levels) in enumerate(self.readers):
            if not requested.intersects(box(*extent)):
                continue
            _, level = min(levels, key=lambda pair: (abs(pair[0]-bits), -pair[0]))
            key = (index, level)
            if key not in self.cache:
                features, boxes = [], []
                for kind, objects in [('polygons', reader.shapesForLevel(level, True)),
                                      ('lines', reader.linesForLevel(level)),
                                      ('points', reader.pointsForLevel(level, True))]:
                    for obj in objects:
                        code = int(obj.getType())
                        if kind == 'polygons' and code in (0x4a, 0x4b):
                            continue
                        values = [obj.getLocation()] if kind == 'points' else obj.getPoints()
                        coords = [[p.getLongitude()*360/2**24, p.getLatitude()*360/2**24] for p in values]
                        if not coords:
                            continue
                        xs, ys = zip(*coords)
                        label = obj.getLabel()
                        text = str(label.getText()) if label else ''
                        text = ''.join(c for c in text if ord(c) >= 32)
                        features.append([f'{kind}:{code}', coords, text])
                        boxes.append(box(min(xs), min(ys), max(xs), max(ys)))
                self.cache[key] = (features, STRtree(boxes))
                # shortcut: four decoded tile-levels; increase only if repeat pans need more caching.
                while len(self.cache) > 4:
                    self.cache.popitem(last=False)
            self.cache.move_to_end(key)
            features, tree = self.cache[key]
            for index in tree.query(requested):
                feature = features[int(index)]
                result.append(feature)
                if feature[0] not in self.styles:
                    unknown.add(feature[0])
            if len(result) > 60000:
                raise ValueError('This view contains over 60,000 features. Zoom in to inspect it.')
        return {'features': result, 'unknownTypes': sorted(unknown), 'resolution': bits}

    def close(self):
        for reader, _, _ in self.readers:
            reader.close()
        self.readers.clear()
        self.cache.clear()
        self.directory.cleanup()

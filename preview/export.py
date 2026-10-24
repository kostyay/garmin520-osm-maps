# /// script
# requires-python = ">=3.10"
# dependencies = ["jpype1==1.7.1"]
# ///
"""Export the actual compiled Garmin geometry into small browser map tiles."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import shutil

import jpype

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'preview/dist'
IMAGE = ROOT / 'quiet/build/gmapsupp.img'
names = {
    0x16: ('MTB trails', 'MTB-tagged paths and mountain-bike route members.'),
    0x0d: ('Hiking paths', 'Other paths, footways and bridleways useful for orientation.'),
    0x0a: ('Tracks', 'Tracks, including forest and farm access tracks.'),
    0x06: ('Unpaved access roads', 'Unpaved service, unclassified and residential access roads.'),
    0x03: ('Major roads', 'Motorways through tertiary roads for geographic context.'),
    0x1f: ('Rivers', 'Main rivers; smaller streams are omitted.'),
    0x3c: ('Lakes and water', 'Lakes, reservoirs and riverbank polygons.'),
}


def tile_xy(lon, lat, zoom):
    scale = 2**zoom
    return ((lon + 180) / 360 * scale,
            (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * scale)


assert tile_xy(0, 0, 1) == (1, 1)
jpype.startJVM(jpype.getDefaultJVMPath(), '-Xmx1g', classpath=[str(ROOT / '.tools/mkgmap-r4924/mkgmap.jar')])
reader = jpype.JClass('uk.me.parabola.imgfmt.app.map.MapReader')(str(IMAGE))
shutil.rmtree(DEST / 'data', ignore_errors=True)
summary = {'imageBytes': IMAGE.stat().st_size,
           'imageSHA256': hashlib.file_digest(IMAGE.open('rb'), 'sha256').hexdigest(),
           'sourceDate': '2026-10-22', 'layers': {}, 'levels': {}}
for section in re.findall(r'\[_(line|polygon)\]\n(.*?)\[end\]', (ROOT / 'quiet/quiet.txt').read_text(), re.S):
    kind, body = section
    code = int(re.search(r'Type=(0x[0-9a-f]+)', body).group(1), 16)
    if code not in names:
        continue
    colours = re.findall(r'c (#[0-9A-Fa-f]{6})', body)
    pixels = re.findall(r'^"([a.]{32})"$', body, re.M)
    summary['layers'][code] = {'name': names[code][0], 'description': names[code][1],
                               'day': colours[0], 'night': colours[-1],
                               'pattern': pixels[0] if pixels else None,
                               'polygon': kind == 'polygon'}
assert set(map(int, summary['layers'])) == set(names)

demo = None
for level, zoom in [(3, 8), (2, 9), (1, 11), (0, 12)]:
    buckets = defaultdict(list)
    counts = Counter()
    assert len(reader.pointsForLevel(level, True)) == 0, 'Unexpected Garmin POIs'
    for objects in [reader.shapesForLevel(level, True), reader.linesForLevel(level)]:
        for obj in objects:
            code = int(obj.getType())
            if code == 0x4b:
                continue
            assert code in names, code
            coords = [[round(p.getLongitude() * 360 / 2**24, 6),
                       round(p.getLatitude() * 360 / 2**24, 6)] for p in obj.getPoints()]
            if len(coords) < 2:
                continue
            if code == 0x3c and coords[-1] != coords[0]:
                coords.append(coords[0])
            counts[code] += 1
            if level == 0 and code in (0x16, 0x0d, 0x0a) and len(coords) > 10:
                lon, lat = coords[len(coords) // 2]
                if abs(lon - 1.426) < .06 and abs(lat - 42.34) < .04:
                    if demo is None or len(coords) > len(demo):
                        demo = coords
            xs, ys = zip(*(tile_xy(lon, lat, zoom) for lon, lat in coords))
            feature = [code, coords]
            for x in range(math.floor(min(xs)), math.floor(max(xs)) + 1):
                for y in range(math.floor(min(ys)), math.floor(max(ys)) + 1):
                    buckets[x, y].append(feature)
    for (x, y), features in buckets.items():
        path = DEST / f'data/{level}/{x}/{y}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(features, separators=(',', ':')))
    summary['levels'][level] = {'tileZoom': zoom, 'counts': dict(counts),
                                'tiles': [f'{x}/{y}' for x, y in buckets]}
    print(f'Garmin level {level}: {sum(counts.values()):,} features, {len(buckets)} tiles', flush=True)
reader.close()
assert demo, 'No example trail near Arfa'
(DEST / 'demo-course.json').write_text(json.dumps(demo, separators=(',', ':')))
shutil.copy(ROOT / 'region.geojson', DEST / 'region.geojson')
shutil.copy(IMAGE, DEST / 'gmapsupp.img')
(DEST / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print('Exported actual Garmin geometry; demo is an illustrative trail overlay, not a planned route.')

# /// script
# requires-python = ">=3.10"
# dependencies = ["jpype1==1.7.1", "pillow==12.0.0"]
# ///
"""Make local SVG captures from compiled Easy tiles and decoded original TYP.

Usage: uv run preview/render-easy.py /path/to/typconv
Outputs are private/generated in preview/easy-captures/. Browser SVG rendering
approximates firmware: bitmap strokes, polygon ordering and label placement differ.
"""
import base64
from collections import Counter
import hashlib
from html import escape
from io import BytesIO
import json
import math
from pathlib import Path
import subprocess
import sys

import jpype
from PIL import Image

if len(sys.argv) != 2:
    raise SystemExit('Usage: uv run preview/render-easy.py /path/to/typconv')

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'preview/easy-captures'
BUILD = ROOT / 'replica/optimized/build'
OUT.mkdir(exist_ok=True)
validation = json.loads((BUILD / 'validation.json').read_text())
image = BUILD / 'gmapsupp.img'
assert hashlib.file_digest(image.open('rb'), 'sha256').hexdigest() == validation['sha256']
assert validation['originalTYPIdentical']
selection = json.loads((ROOT / 'sources/selection.json').read_text())
assert hashlib.sha256((ROOT / 'sources/legacy/easy.typ').read_bytes()).hexdigest() == selection['typSHA256']
subprocess.run([sys.argv[1], 'bin2txt', str(ROOT / 'sources/legacy/easy.typ'),
                '--format', 'json', '-o', str(OUT / 'typ.json')], check=True)
typ = json.loads((OUT / 'typ.json').read_text())
styles = {}
for kind in ('lines', 'polygons', 'points'):
    for item in typ[kind]:
        code = item['type']
        if kind != 'points' and code < 0x10000:
            code >>= 8
        assert (kind, code) not in styles
        styles[kind, code] = item


def bitmap(icon):
    pixels = base64.b64decode(icon['pixels'])
    assert len(pixels) == icon['width'] * icon['height']
    palette = icon.get('palette', [])
    rgba = []
    for pixel in pixels:
        assert not palette or pixel <= len(palette), 'Unexpected bitmap palette index'
        # typconv uses the extra palette index for transparent pixels.
        colour = palette[pixel] if pixel < len(palette) else 'none'
        rgba.append(tuple(bytes.fromhex(colour[1:])) + (255,) if colour.startswith('#') else (0, 0, 0, 0))
    img = Image.new('RGBA', (icon['width'], icon['height']))
    img.putdata(rgba)
    output = BytesIO()
    img.save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()


def mercator(lat):
    return math.degrees(math.asinh(math.tan(math.radians(lat))))


assert abs(mercator(0)) < 1e-10
for item in styles.values():
    for key in ('dayIcon', 'dayPattern'):
        if key in item:
            bitmap(item[key])
jpype.startJVM(jpype.getDefaultJVMPath(), '-Xmx1g',
              classpath=[str(ROOT / '.tools/mkgmap-r4924/mkgmap.jar')])
Reader = jpype.JClass('uk.me.parabola.imgfmt.app.map.MapReader')
places = {'arfa': (1.426, 42.340), 'andorra': (1.522, 42.506), 'la-seu': (1.456, 42.358)}
features = {name: [] for name in places}
counts = Counter()
# Read only tiles packaged in the deliverable, not mkgmap's desktop overview.
for tile_id in sorted(Path(item['path']).stem for item in selection['maps']):
    path = BUILD / f'{tile_id}.img'
    reader = Reader(str(path))
    level = min(reader.getLevels(), key=lambda z: -int(z.getResolution())).getLevel()
    for kind, objects in [('polygons', reader.shapesForLevel(level, True)),
                          ('lines', reader.linesForLevel(level)),
                          ('points', reader.pointsForLevel(level, True))]:
        for obj in objects:
            code = int(obj.getType())
            if kind == 'polygons' and code == 0x4b:
                continue  # Garmin's map-coverage rectangle, not a land-use feature.
            values = [obj.getLocation()] if kind == 'points' else obj.getPoints()
            coords = [(p.getLongitude() * 360 / 2**24, p.getLatitude() * 360 / 2**24) for p in values]
            if not coords:
                continue
            xs, ys = zip(*coords)
            for name, (lon, lat) in places.items():
                if max(xs) < lon-.018 or min(xs) > lon+.018 or max(ys) < lat-.012 or min(ys) > lat+.012:
                    continue
                assert (kind, code) in styles, f'Unstyled Easy type: {kind} {code:#x}'
                label = obj.getLabel()
                text = str(label.getText()) if label else ''
                text = ''.join(c for c in text if ord(c) >= 32)
                features[name].append((kind, code, coords, text))
                counts[kind, code] += 1
    reader.close()
    print(path.name, flush=True)

(OUT / 'features.json').write_text(json.dumps(features, separators=(',', ':')))
for name, (lon, lat) in places.items():
    scale = 940/.036
    def xy(p):
        return (250 + (p[0]-lon+.018)*scale, 420 - (mercator(p[1])-mercator(lat))*scale)
    defs, polygons, lines, points, labels = [], [], [], [], []
    occupied = []
    local = Counter()
    # Large land-cover polygons first; firmware has additional TYP draw-order rules.
    def area(feature):
        c=feature[2]
        return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(c,c[1:]+c[:1])))
    for kind, code, coords, text in sorted(features[name], key=lambda f: -area(f) if f[0]=='polygons' else 1):
        item = styles[kind, code]
        local[kind, code] += 1
        colour = item.get('dayColor', '#777777')
        icon = item.get('dayPattern')
        identifier = f'{kind}-{code}'
        if icon:
            if not any(f'id="{identifier}"' in d for d in defs):
                defs.append(f'<pattern id="{identifier}" patternUnits="userSpaceOnUse" width="{icon["width"]}" height="{icon["height"]}"><image width="{icon["width"]}" height="{icon["height"]}" href="{bitmap(icon)}"/></pattern>')
            colour = f'url(#{identifier})'
        projected = [xy(p) for p in coords]
        path = 'M'+' L'.join(f'{x:.1f},{y:.1f}' for x,y in projected)
        if kind == 'polygons':
            polygons.append(f'<path d="{path} Z" fill="{colour}"/>')
        elif kind == 'lines':
            width = icon['height'] if icon else item.get('lineWidth', 1)
            border = item.get('borderWidth', 0)
            if border:
                lines.append(f'<path d="{path}" stroke="{item.get("dayBorderColor", "#777")}" stroke-width="{border}"/>')
            if icon:
                distance = 0
                for a,b in zip(projected,projected[1:]):
                    angle = math.degrees(math.atan2(b[1]-a[1], b[0]-a[0]))
                    segment = f'segment-{len(defs)}'
                    defs.append(f'<pattern id="{segment}" href="#{identifier}" patternTransform="translate({a[0]:.1f} {a[1]:.1f}) rotate({angle:.2f}) translate({-distance:.1f} {-width/2:.1f})"/>')
                    lines.append(f'<path d="M{a[0]:.1f},{a[1]:.1f} L{b[0]:.1f},{b[1]:.1f}" stroke="url(#{segment})" stroke-width="{width}"/>')
                    distance += math.hypot(b[0]-a[0], b[1]-a[1])
            else:
                lines.append(f'<path d="{path}" stroke="{colour}" stroke-width="{max(width,1)}"/>')
        else:
            icon = item.get('dayIcon')
            x,y = projected[0]
            if icon:
                points.append(f'<image x="{x-icon["width"]/2:.1f}" y="{y-icon["height"]/2:.1f}" width="{icon["width"]}" height="{icon["height"]}" href="{bitmap(icon)}"/>')
        if text and kind != 'polygons' and not (kind == 'lines' and code in (0x20,0x21,0x22)):
            x,y = projected[len(projected)//2]
            rect = (x+4, y-19, x+14+len(text[:36])*6, y)
            if 275<x and rect[2]<1180 and 100<y<740 and not any(rect[0]<b[2] and rect[2]>b[0] and rect[1]<b[3] and rect[3]>b[1] for b in occupied):
                occupied.append(rect)
                labels.append(f'<text x="{x+7:.1f}" y="{y-5:.1f}" font-size="11" paint-order="stroke" stroke="white" stroke-width="2" fill="#394435">{escape(text[:36])}</text>')
    legend=[]
    for i,kind in enumerate(('polygons','lines','points')):
        n=sum(v for (k,c),v in local.items() if k==kind)
        types=sum(1 for (k,c) in local if k==kind)
        legend.append(f'<text x="24" y="{230+i*60}" font-size="14">{kind.title()}: {n:,}</text><text x="24" y="{250+i*60}" font-size="12" fill="#667782">{types} Easy types rendered</text>')
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="850" viewBox="0 0 1200 850">
<defs>{''.join(defs)}<clipPath id="map"><rect x="250" y="65" width="940" height="720"/></clipPath></defs>
<rect width="1200" height="850" fill="#f3f6f8"/><g font-family="sans-serif" fill="#293d48">
<text x="24" y="45" font-size="12">GARMIN EDGE 520 / EASY</text><text x="24" y="105" font-size="28">Andorra MTB</text>
<text x="24" y="140" font-size="18">{escape(name.replace('-', ' ').title())}</text>
<text x="24" y="175" font-size="12">{validation['MB']} MB optimized build</text>{''.join(legend)}
<text x="24" y="480" font-size="13">Actual compiled map geometry</text><text x="24" y="505" font-size="13">Original Easy TYP colours</text><text x="24" y="530" font-size="13">Backgrounds, paths and POIs</text>
<text x="270" y="40" font-size="15">Easy-style map · local browser capture</text>
<rect x="250" y="65" width="940" height="720" fill="#eeeeee"/>
<g clip-path="url(#map)">{''.join(polygons)}<g fill="none" stroke-linejoin="round">{''.join(lines)}</g>{''.join(points)}{''.join(labels)}</g>
<text x="24" y="815" font-size="12">Browser approximation: line patterns, polygon order and label placement can differ from Garmin firmware.</text>
<text x="24" y="837" font-size="11">Map data © OpenStreetMap contributors · OpenMTBMap Easy style · contours: OpenTopoMap / original Andorra map</text></g></svg>'''
    (OUT / f'{name}.svg').write_text(svg)
report={'imageSHA256':validation['sha256'], 'originalTYPIdentical':True,
        'renderedTypes': {kind:sorted(hex(code) for k,code in counts if k==kind) for kind in ('lines','polygons','points')},
        'unhandledTypes': [], 'places':list(places),
        'limitations':['Browser approximation, not firmware emulation','Bitmap line patterns approximate each straight path segment','Polygon order uses area, not Garmin draw-order rules','Labels use simple collision avoidance']}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
(OUT / 'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><title>Easy map captures</title><style>body{margin:0;background:#f3f6f8;font-family:sans-serif}nav{padding:12px}button{padding:8px 20px;margin-right:10px}img{display:block;width:100%;max-width:1200px}</style><nav><button onclick="document.querySelector('img').src='arfa.svg'">Arfa</button><button onclick="document.querySelector('img').src='la-seu.svg'">La Seu</button><button onclick="document.querySelector('img').src='andorra.svg'">Andorra</button></nav><img src="arfa.svg" alt="Actual Easy-style map geometry, rendered approximately in a browser"></html>''')
print('All visible types have Easy TYP definitions; captures exported to',OUT)

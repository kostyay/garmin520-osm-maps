# /// script
# requires-python = ">=3.10"
# dependencies = ["jpype1==1.7.1", "shapely==2.1.2"]
# ///
"""Clip decoded OpenMTBMap features, preserving their type, label and detail level."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import jpype
from shapely import make_valid, constrained_delaunay_triangles
from shapely.geometry import LineString, Point, Polygon, box, shape
from shapely.ops import unary_union
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'replica/maps'
OUT.mkdir(exist_ok=True)
region = unary_union([shape(f['geometry']) for f in json.loads((ROOT / 'region.geojson').read_text())['features']])
prepared = prep(region)
# The legacy/current Andorra tile rectangle is reserved for its own data.
old_coverage = None
jpype.startJVM(jpype.getDefaultJVMPath(), '-Xmx1g',
              classpath=[str(ROOT / '.tools/mkgmap-r4924/mkgmap.jar')])
Reader = jpype.JClass('uk.me.parabola.imgfmt.app.map.MapReader')
selection = json.loads((ROOT / 'sources/selection.json').read_text())
for item in selection['maps']:
    with (ROOT / item['path']).open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest() == item['sha256'], f"Source changed: {item['path']}"
assert hashlib.sha256((ROOT / 'sources/legacy/easy.typ').read_bytes()).hexdigest() == selection['typSHA256']
paths = [ROOT / item['path'] for item in selection['maps']]
kinds = {str(ROOT / item['path']): item['kind'] for item in selection['maps']}
old_coverage = box(*selection['andorraBounds'])
if len(sys.argv) > 1:
    paths = [Path(p).resolve() for p in sys.argv[1:]]
else:
    for stale in OUT.glob('*.mp'):
        stale.unlink()
counts = {}


def parts(geometry, kind):
    if geometry.is_empty:
        return []
    if geometry.geom_type == kind:
        return [geometry]
    if hasattr(geometry, 'geoms'):
        return [part for geom in geometry.geoms for part in parts(geom, kind)]
    return []


def label_text(obj):
    label = obj.getLabel()
    text = str(label.getText()) if label else ''
    return ''.join(f'~[0x{ord(c):02x}]' if ord(c) < 32 and c not in '\r\n' else c for c in text).replace('\n', ' ').replace('\r', ' ')


def coordinates(obj, point=False):
    values = [obj.getLocation()] if point else obj.getPoints()
    return [(p.getLongitude() * 360 / 2**24, p.getLatitude() * 360 / 2**24) for p in values]


assert parts(LineString([(0, 0), (1, 1)]).intersection(box(.25, .25, .75, .75)), 'LineString')[0].length > 0
for path in paths:
    reader = Reader(str(path))
    kind_of_map = kinds[str(path)]
    is_spanish_contour = kind_of_map == 'spain-contour'
    clip_region = region.difference(old_coverage) if kind_of_map in ('spain-base', 'spain-contour') else region
    prepared = prep(clip_region)
    highest_bits = max(int(z.getResolution()) for z in reader.getLevels())
    stats = Counter()
    with (OUT / (path.stem + '.mp')).open('w', encoding='cp1252', errors='replace') as out:
        out.write(f'[IMG ID]\nID={path.stem}\nName=Andorra MTB Easy\nCodePage=1252\nLevels=8\n')
        out.write(''.join(f'Level{i}={24-i}\n' for i in range(8)))
        out.write('Copyright=' + ' | '.join(str(s) for s in reader.getCopyrights()) + '\n[END-IMG ID]\n')
        for zoom in reader.getLevels():
            bits = int(zoom.getResolution())
            if bits < 17:
                continue
            level = 24 - bits
            groups = [('POLYLINE', reader.linesForLevel(zoom.getLevel())),
                      ('POLYGON', reader.shapesForLevel(zoom.getLevel(), True)),
                      ('POI', reader.pointsForLevel(zoom.getLevel(), True))]
            for kind, objects in groups:
                for obj in objects:
                    code = int(obj.getType())
                    if is_spanish_contour:
                        if kind != 'POLYLINE' or code not in (0x20, 0x21, 0x22):
                            continue
                        elevation = round(float(str(obj.getLabel().getText())) * .3048 / 10) * 10
                        if elevation % 20:
                            continue
                        code = 0x22 if elevation % 500 == 0 else 0x21 if elevation % 100 == 0 else 0x20
                    if code == 0x4b and kind == 'POLYGON':
                        continue
                    coords = coordinates(obj, kind == 'POI')
                    if not coords or (kind != 'POI' and len(coords) < 2):
                        continue
                    if kind == 'POI':
                        geom = Point(coords[0]); target = 'Point'
                    elif kind == 'POLYLINE':
                        geom = LineString(coords); target = 'LineString'
                    else:
                        if len(coords) < 3:
                            continue
                        geom = Polygon(coords); target = 'Polygon'
                    if not prepared.intersects(geom):
                        continue
                    if not geom.is_valid:
                        geom = make_valid(geom)
                    clipped = geom if prepared.covers(geom) else geom.intersection(clip_region)
                    for part in parts(clipped, target):
                        if kind == 'POLYGON' and part.interiors:
                            # Garmin polygons are simple rings; a clipped boundary hole is removed by splitting.
                            simple = list(constrained_delaunay_triangles(part).geoms)
                        else:
                            simple = [part]
                        for geom_part in simple:
                            points = list(geom_part.exterior.coords if kind == 'POLYGON' else geom_part.coords)
                            if kind != 'POI' and len(points) < (4 if kind == 'POLYGON' else 2):
                                continue
                            out.write(f'[{kind}]\nType=0x{code:x}\n')
                            text = label_text(obj)
                            if text:
                                out.write('Label=' + text + '\n')
                            data_level = 0 if bits == highest_bits else level
                            out.write(f'EndLevel={level}\nData{data_level}=' + ','.join(f'({lat:.7f},{lon:.7f})' for lon, lat in points) + '\n[END]\n')
                            stats[kind] += 1
    reader.close()
    counts[path.stem] = dict(stats)
    print(path.stem, dict(stats), flush=True)
(ROOT / 'replica/clipped-counts.json').write_text(json.dumps(counts, indent=2) + '\n')

"""Check the compiled IMG and exercise the actual mkgmap style engine."""
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
image = (ROOT / 'build/gmapsupp.img').read_bytes()
assert 0 < len(image) < 60_000_000, 'Device map must be smaller than 60 MB'
assert image[0] == 0 and image[16:22] == b'DSKIMG', 'Invalid Garmin IMG'
block_size = 1 << (image[0x61] + image[0x62])
fat_start = image[0x40] * 512
data_start = struct.unpack_from('<I', image, fat_start + 12)[0]
files = {}
sizes = {}
for offset in range(fat_start + 512, data_start, 512):
    entry = image[offset:offset + 512]
    if entry[0] != 1:
        continue
    name = entry[1:12].decode('ascii')
    files.setdefault(name, bytearray())
    sizes[name] = max(sizes.get(name, 0), struct.unpack_from('<I', entry, 12)[0])
    for block in struct.unpack_from('<240H', entry, 32):
        if block != 0xffff:
            files[name].extend(image[block * block_size:(block + 1) * block_size])
files = {name: bytes(data[:sizes[name]]) for name, data in files.items()}
extensions = {name[-3:] for name in files}
assert {'RGN', 'TRE', 'LBL', 'TYP', 'MPS'} <= extensions, extensions
assert not extensions & {'NET', 'NOD', 'MDR', 'MDX', 'DEM'}, extensions
tree = files['52371001TRE']
assert tree[2:12] == b'GARMIN TRE'
north, east, south, west = [
    int.from_bytes(tree[o:o + 3], 'little', signed=True) * 360 / 2**24
    for o in (21, 24, 27, 30)
]
for name, lat, lon in [('Andorra', 42.5063, 1.5218), ('La Seu', 42.3576, 1.456), ('Arfa', 42.34, 1.426)]:
    assert south <= lat <= north and west <= lon <= east, name
start, length, record_size = struct.unpack_from('<IIH', tree, 0x4a)
line_types = set(tree[start:start + length:record_size])
assert line_types == {0x03, 0x06, 0x0a, 0x0d, 0x16, 0x1f}, line_types
start, length, record_size = struct.unpack_from('<IIH', tree, 0x58)
assert set(tree[start:start + length:record_size]) == {0x3c, 0x4b}, 'Unexpected polygons'
assert struct.unpack_from('<I', tree, 0x6a)[0] == 0, 'Unexpected point features'
labels = files['52371001LBL']
start, length = struct.unpack_from('<II', labels, 21)
assert set(filter(None, labels[start:start + length].split(b'\0'))) == {
    b'PROGRAM LICENCED UNDER GPL V2',
    b'OPENSTREETMAP.ORG CONTRIBUTORS. SEE: HTTP://WIKI.OPENSTREETMAP.ORG/INDEX.PHP/ATTRIBUTION',
}, 'Unexpected feature labels in compiled map'

# Test rendering choices, including cases which must disappear, against mkgmap itself.
cases = [
    ('highway=path\nmtb:scale=3\nname=HiddenName', 0x16),
    ('highway=path\nquiet:mtb=yes', 0x16),
    ('highway=footway', 0x0d),
    ('highway=bridleway', 0x0d),
    ('highway=track\nname=HiddenName\nref=HiddenRef', 0x0a),
    ('highway=service\nsurface=gravel', 0x06),
    ('highway=primary\nname=HiddenName\nref=HiddenRef', 0x03),
    ('waterway=river\nname=HiddenName', 0x1f),
    ('highway=cycleway\nbicycle=designated\nmtb:scale=1', None),
    ('highway=path\nbicycle=designated\nsurface=asphalt', None),
    ('highway=footway\nbicycle=designated\nsurface=paving_stones', None),
    ('highway=path\nbicycle=designated\nsurface=ground', 0x0d),
    ('shop=bicycle', None),
    ('shop=supermarket', None),
    ('amenity=bicycle_repair_station', None),
    ('highway=residential\nsurface=asphalt', None),
    ('highway=service\nsurface=asphalt', None),
    ('highway=footway\narea=yes', None),
    ('contour=elevation\nele=1000', None),
]
with tempfile.TemporaryDirectory() as tmp:
    fixture = ''.join(f'WAY {i}\n{tags}\n\n' for i, (tags, _) in enumerate(cases, 1))
    for part in ('version', 'options', 'lines', 'polygons', 'points', 'relations'):
        fixture += f'<<<{part}>>>\n' + (ROOT / 'style' / part).read_text() + '\n'
    testfile = Path(tmp) / 'cases.test'
    testfile.write_text(fixture)
    result = subprocess.run([
        os.environ.get('JAVA', 'java'), '-cp', str(ROOT.parent / '.tools/mkgmap-r4924/mkgmap.jar'),
        'uk.me.parabola.mkgmap.main.StyleTester', str(testfile),
    ], cwd=tmp, capture_output=True, text=True, check=True)
    output = result.stdout
    assert 'ERROR' not in output, output + result.stderr
    assert 'HiddenName' not in output and 'HiddenRef' not in output, output
    actual = [(int(i), int(t, 16)) for i, t in re.findall(r'^WAY (\d+): Line 0x([0-9a-f]+)', output, re.M)]
    expected = [(i, t) for i, (_, t) in enumerate(cases, 1) if t is not None]
    assert actual == expected, output + result.stderr

print(f'PASS: {len(image):,} bytes; Andorra, La Seu and Arfa within map bounds')
print('PASS: required line types present; no POIs, contours, routing, search indexes or DEM')
print('PASS: compiled labels contain only copyright notices')
print(f'PASS: {len(cases)} style cases; street names and references suppressed')
print('PENDING: Edge 520 zoom, GPX contrast and firmware acceptance')

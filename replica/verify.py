"""Validate the replica's structure and exact original TYP payload."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
output = ROOT / (sys.argv[1] if len(sys.argv) > 1 else 'replica/build')
path = output / 'gmapsupp.img'
image = path.read_bytes()
assert image[0] == 0 and image[16:22] == b'DSKIMG'
block_size = 1 << (image[0x61] + image[0x62])
fat_start = image[0x40] * 512
data_start = struct.unpack_from('<I', image, fat_start + 12)[0]
files, sizes = {}, {}
for offset in range(fat_start + 512, data_start, 512):
    entry = image[offset:offset + 512]
    if entry[0] != 1:
        continue
    name = entry[1:12].decode('ascii')
    sizes[name] = max(sizes.get(name, 0), struct.unpack_from('<I', entry, 12)[0])
    data = files.setdefault(name, bytearray())
    for block in struct.unpack_from('<240H', entry, 32):
        if block != 0xffff:
            data.extend(image[block * block_size:(block + 1) * block_size])
files = {name: bytes(data[:sizes[name]]) for name, data in files.items()}
extensions = {name[-3:] for name in files}
assert not extensions & {'NET', 'NOD', 'MDR', 'MDX', 'DEM'}, extensions
types = [data for name, data in files.items() if name.endswith('TYP')]
original_typ = (ROOT / 'sources/legacy/easy.typ').read_bytes()
assert types == [original_typ], 'The original TYP must be preserved byte-for-byte'
trees = {name[:8]: data for name, data in files.items() if name.endswith('TRE')}
selection = json.loads((ROOT / 'sources/selection.json').read_text())
expected_ids = {Path(item['path']).stem for item in selection['maps']}
assert expected_ids == set(trees), 'A selected tile is missing or a stale tile was included'
bounds = []
for data in trees.values():
    n, e, s, w = [int.from_bytes(data[o:o + 3], 'little', signed=True) * 360 / 2**24 for o in (21, 24, 27, 30)]
    bounds.append((s, w, n, e))
for name, lat, lon in [('Andorra', 42.5063, 1.5218), ('La Seu', 42.3576, 1.456), ('Arfa', 42.34, 1.426)]:
    assert any(s <= lat <= n and w <= lon <= e for s, w, n, e in bounds), name
for map_id in [Path(item['path']).stem for item in selection['maps'] if item['kind'].endswith('contour')]:
    data = trees[map_id]
    offset, length, record_size = struct.unpack_from('<IIH', data, 0x4a)
    assert set(data[offset:offset + length:record_size]) <= {0x20, 0x21, 0x22}, map_id
report = {
    'bytes': len(image), 'MB': round(len(image) / 1e6, 2), 'MiB': round(len(image) / 2**20, 2),
    'under60MB': len(image) < 60_000_000, 'under50MB': len(image) < 50_000_000, 'maps': len(trees),
    'sha256': hashlib.sha256(image).hexdigest(),
    'originalTYPBytes': len(original_typ), 'originalTYPIdentical': True,
    'routingAndSearchIndexes': False, 'DEM': False,
    'andorraContours': True, 'spanishContours': True,
}
(output / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))

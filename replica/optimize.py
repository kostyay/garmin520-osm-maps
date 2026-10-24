"""Remove background clutter while retaining every navigation line feature."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'optimized/maps'
OUT.mkdir(parents=True, exist_ok=True)
for stale in OUT.glob('*.mp'):
    stale.unlink()

# Generic forest fill remains; species hatch overlays repeat the same geometry.
POLYGONS = {
    0x11, 0x16, 0x33, 0x3c, 0x3e, 0x3f, 0x50,
    0x1100d, 0x1100e, 0x1100f, 0x11014, 0x11015, 0x11016,
    0x11017, 0x1101c,
}
POINTS = {
    0x2b03, 0x2b05, 0x2b07, 0x2f0b, 0x4c01, 0x4c02, 0x5000,
    0x6404, 0x640c, 0x6500, 0x6501, 0x6508, 0x650c,
    0x6612, 0x6613, 0x6614, 0x6615, 0x6616,
    0x10c05, 0x10c07, 0x11001, 0x11005, 0x11508, 0x11517,
    0x11600, 0x11601, 0x11602, 0x11603, 0x11604, 0x11605, 0x11606,
    0x1190a, 0x11914, 0x11916, 0x1860a,
}


def keep(kind, code, label=''):
    if kind == 'POLYLINE' and code == 0x20 and label:
        try:
            elevation = round(float(label) * .3048 / 20) * 20
            return elevation % 40 == 0
        except ValueError:
            return True
    return (kind == 'POLYLINE' or kind == 'POLYGON' and code in POLYGONS
            or kind == 'POI' and (code in POINTS or code <= 0x1100 and code % 0x100 == 0))


assert keep('POLYLINE', 0x16) and keep('POLYLINE', 0x20)
assert keep('POLYLINE', 0x20, '1312') and not keep('POLYLINE', 0x20, '1378')
assert keep('POLYGON', 0x50) and not keep('POLYGON', 0x13)
assert keep('POI', 0x5000) and not keep('POI', 0x2e00)
report = {'kept': Counter(), 'removed': Counter(), 'files': {}}
for path in sorted((ROOT / 'maps').glob('*.mp')):
    original_lines, filtered_lines = hashlib.sha256(), hashlib.sha256()
    block, kind, code, label = [], None, None, ''
    with path.open(encoding='cp1252') as src, (OUT / path.name).open('w', encoding='cp1252') as dest:
        for line in src:
            if line.strip() in ('[POLYLINE]', '[POLYGON]', '[POI]'):
                kind, block, code, label = line.strip()[1:-1], [], None, ''
            if kind:
                block.append(line)
                if line.startswith('Type='):
                    code = int(line.split('=', 1)[1], 16)
                if line.startswith('Label='):
                    label = line.strip()[6:]
                if line.strip() == '[END]':
                    text = ''.join(block)
                    retained = keep(kind, code, label)
                    report['kept' if retained else 'removed'][kind] += 1
                    if kind == 'POLYLINE' and code not in (0x20, 0x21, 0x22):
                        original_lines.update(text.encode('cp1252'))
                    if retained:
                        dest.write(text)
                        if kind == 'POLYLINE' and code not in (0x20, 0x21, 0x22):
                            filtered_lines.update(text.encode('cp1252'))
                    kind = None
            else:
                dest.write(line)
    assert kind is None, f'Incomplete feature in {path}'
    assert original_lines.digest() == filtered_lines.digest(), f'Line data changed in {path}'
    report['files'][path.name] = {'allNavigationLineFeaturesIdentical': True, 'lineSHA256': original_lines.hexdigest()}
(ROOT / 'optimized/filter-report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k != 'files'}, indent=2))

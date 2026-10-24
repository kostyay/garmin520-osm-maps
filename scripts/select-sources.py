# /// script
# requires-python = ">=3.10"
# dependencies = ["shapely==2.1.2"]
# ///
"""Select source tiles intersecting the stored region and record exact inputs."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
from shapely.geometry import box, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
region = unary_union([shape(f['geometry']) for f in json.loads((ROOT/'region.geojson').read_text())['features']])

def bounds(path):
    data = path.read_bytes()
    i = data.find(b'GARMIN TRE')
    if i < 2:return None
    h=i-2
    n,e,s,w=[int.from_bytes(data[h+o:h+o+3],'little',signed=True)*360/2**24 for o in (21,24,27,30)]
    assert -90 <= s < n <= 90 and -180 <= w < e <= 180,path
    return s,w,n,e

selection={'maps':[]}
andorra=[]
for directory,pattern,kind in [('sources/spain','6*.img','spain-base'),('sources/legacy','6*.img','andorra-base'),('sources/legacy','7*.img','andorra-contour'),('sources/contours/tiles','*.img','spain-contour')]:
    for path in sorted((ROOT/directory).glob(pattern)):
        b=bounds(path)
        if not b:continue
        s,w,n,e=b
        if not region.intersects(box(w,s,e,n)):continue
        selection['maps'].append({'path':str(path.relative_to(ROOT)),'kind':kind,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        if kind.startswith('andorra-'):andorra.append(b)
assert andorra,'Andorra source tiles missing'
assert all(any(m['kind']==k for m in selection['maps']) for k in ['spain-base','andorra-base','andorra-contour','spain-contour'])
selection['andorraBounds']=[min(b[1] for b in andorra),min(b[0] for b in andorra),max(b[3] for b in andorra),max(b[2] for b in andorra)]
styles=list((ROOT/'sources/legacy').glob('*EASY*.TYP'))+list((ROOT/'sources/legacy').glob('easy*.TYP'))
assert styles,'Easy TYP not found in legacy map or current Andorra package'
typ=styles[0].read_bytes()
assert typ[2:12]==b'GARMIN TYP' and struct.unpack_from('<HH',typ,0x2f)==(6373,1),'Unexpected TYP family/product ID'
shutil.copyfile(styles[0],ROOT/'sources/legacy/easy.typ')
selection['typSHA256']=hashlib.sha256(typ).hexdigest()
selection['downloads']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'sources/downloads').glob('*') if p.is_file()}
(ROOT/'sources/selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print('Selected',len(selection['maps']),'tiles; TYP SHA256',selection['typSHA256'])

# /// script
# requires-python = ">=3.10"
# dependencies = ["jpype1==1.7.1"]
# ///
"""Inventory map tiles split by GMapTool; report features actually present."""
from collections import Counter
import json
from pathlib import Path
import sys
import jpype

ROOT=Path(__file__).resolve().parents[1]
jpype.startJVM(jpype.getDefaultJVMPath(),'-Xmx1g',classpath=[str(ROOT/'.tools/mkgmap-r4924/mkgmap.jar')])
Reader=jpype.JClass('uk.me.parabola.imgfmt.app.map.MapReader')
result={}
for path in Path(sys.argv[1]).glob('*.img'):
    if b'GARMIN TRE' not in path.read_bytes():continue
    r=Reader(str(path));levels=[]
    for z in r.getLevels():
        groups={'lines':r.linesForLevel(z.getLevel()),'polygons':r.shapesForLevel(z.getLevel(),True),'points':r.pointsForLevel(z.getLevel(),True)}
        levels.append({'level':int(z.getLevel()),'resolution':int(z.getResolution()),'types':{kind:{hex(k):v for k,v in Counter(int(obj.getType()) for obj in objects).items()} for kind,objects in groups.items()}})
    result[path.name]={'levels':levels,'labels':len(r.getLabels()),'routingRoads':len(r.getRoads())}
    r.close()
print(json.dumps(result,indent=2))

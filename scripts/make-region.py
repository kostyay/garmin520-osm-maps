# /// script
# requires-python = ">=3.10"
# dependencies = ["shapely==2.1.2", "pyproj==3.7.2"]
# ///
"""Print a 100 km Andorra/Spanish-side extraction polygon as GeoJSON."""
import json
from urllib.request import urlopen
from shapely.geometry import Polygon,Point,shape,mapping
from shapely.ops import transform,unary_union
from pyproj import Transformer

COUNTRIES='https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson'
ANDORRA='https://download.geofabrik.de/europe/andorra.poly'
with urlopen(COUNTRIES) as r:data=json.load(r)
land=unary_union([shape(f['geometry']) for f in data['features'] if f['properties']['name'] in ('Spain','Andorra')])
crs='+proj=aeqd +lat_0=42.5063 +lon_0=1.5218 +datum=WGS84'
forward=Transformer.from_crs(4326,crs,always_xy=True).transform
back=Transformer.from_crs(crs,4326,always_xy=True).transform
region=transform(back,transform(forward,land).intersection(Point(0,0).buffer(100000,resolution=180)))
with urlopen(ANDORRA) as r:lines=r.read().decode().splitlines()
coords=[tuple(map(float,v)) for line in lines if len(v:=line.split())==2]
outline=Polygon(coords);assert outline.is_valid
region=region.union(outline);assert region.is_valid
assert region.covers(Point(1.456,42.3576)) and region.covers(Point(1.426,42.34))
print(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{'name':'100 km from Andorra la Vella, Andorra and Spain only','center':[1.5218,42.5063],'radius_m':100000,'boundary_source':COUNTRIES,'andorra_boundary_source':ANDORRA},'geometry':mapping(region)}]},indent=2))

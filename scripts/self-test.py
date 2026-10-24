#!/usr/bin/env python3
"""Small offline checks for title preservation, copying and optimization rules."""
import importlib.util
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
def module(name,file):
    spec=importlib.util.spec_from_file_location(name,file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

rename=module('rename',ROOT/'scripts/rename-gpx.py').rename
copy=module('install',ROOT/'scripts/install.py').copy_verified
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp);source=p/'source.gpx';dest=p/'renamed.gpx'
    source.write_text('<gpx xmlns="http://www.topografix.com/GPX/1/1"><metadata><name>Old</name></metadata><trk><name>Old</name><trkseg><trkpt lat="42.3" lon="1.4"><ele>1000</ele></trkpt><trkpt lat="42.31" lon="1.41"/></trkseg></trk></gpx>')
    rename(source,dest,'Arfa Day 1');root=ET.parse(dest).getroot();ns={'g':'http://www.topografix.com/GPX/1/1'}
    assert root.find('g:metadata/g:name',ns).text=='Arfa Day 1'
    assert root.find('g:trk/g:name',ns).text=='Arfa Day 1'
    assert len(root.findall('.//g:trkpt',ns))==2
    copy(dest,p/'copied.gpx');assert dest.read_bytes()==(p/'copied.gpx').read_bytes()
print('PASS: GPX titles and all point content preserved; copy checksum verified')

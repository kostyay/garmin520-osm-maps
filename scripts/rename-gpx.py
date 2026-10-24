#!/usr/bin/env python3
"""Set GPX metadata/track/route titles without changing track points."""
import argparse
from pathlib import Path
from xml.dom import minidom

def rename(source, destination, title):
    assert source.resolve()!=destination.resolve(),'Keep the original GPX'
    assert not destination.exists(),'Destination already exists'
    doc=minidom.parse(str(source));ns=doc.documentElement.namespaceURI
    before=[p.toxml() for name in ('trkpt','rtept','wpt') for p in doc.getElementsByTagNameNS(ns,name)]
    assert before,'No GPX points found'
    for parent_name in ('metadata','trk','rte'):
        for parent in doc.getElementsByTagNameNS(ns,parent_name):
            nodes=[c for c in parent.childNodes if c.nodeType==c.ELEMENT_NODE and c.localName=='name']
            if not nodes:
                name=doc.createElementNS(ns,((parent.prefix+':') if parent.prefix else '')+'name')
                parent.insertBefore(name,parent.firstChild)
            else:name=nodes[0]
            for child in list(name.childNodes):name.removeChild(child)
            name.appendChild(doc.createTextNode(title))
    destination.write_bytes(doc.toxml(encoding='UTF-8'))
    check=minidom.parse(str(destination))
    after=[p.toxml() for name in ('trkpt','rtept','wpt') for p in check.getElementsByTagNameNS(ns,name)]
    assert before==after,'Point content changed'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('destination',type=Path);p.add_argument('title')
    a=p.parse_args();rename(a.source,a.destination,a.title)

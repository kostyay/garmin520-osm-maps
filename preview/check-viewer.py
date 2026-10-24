# /// script
# requires-python = ">=3.10"
# dependencies = ["jpype1==1.7.1", "pillow==12.0.0", "shapely==2.1.2"]
# ///
"""Regression check with a locally built Andorra/Arfa IMG; never writes the input."""
import argparse
import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image
from garmin import bitmap
from serve import MAX_BYTES, Viewer, parse_view

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('image', type=Path)
parser.add_argument('--typconv', required=True)
args = parser.parse_args()
for bounds, zoom in [('nan,42,2,43', '15'), ('2,42,1,43', '15'), ('1,42,2,43', '19'), ('1,42,2', '15')]:
    try:
        parse_view({'bbox': [bounds], 'zoom': [zoom]})
    except ValueError:
        pass
    else:
        raise AssertionError('An invalid viewport was accepted')
icon = {'width': 2, 'height': 1, 'pixels': base64.b64encode(bytes([0, 1])).decode(), 'palette': ['#123456']}
rgba = Image.open(BytesIO(base64.b64decode(bitmap(icon).split(',')[1]))).convert('RGBA')
assert list(rgba.getdata()) == [(18, 52, 86, 255), (0, 0, 0, 0)]
original = hashlib.file_digest(args.image.open('rb'), 'sha256').hexdigest()
with Viewer(('127.0.0.1', 0), args.typconv, args.image.resolve()) as server:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    root = f'http://127.0.0.1:{server.server_port}'
    def get(path):
        with urlopen(root+path, timeout=120) as response:
            return json.load(response)
    for path in ('/', '/base.css', '/style.css', '/app.js', '/vendor/leaflet.js'):
        with urlopen(root+path, timeout=30) as response:
            assert response.status == 200
            response.read()
    try:
        urlopen(root+'/render-easy.py')
    except HTTPError as error:
        assert error.code == 404
    else:
        raise AssertionError('Server exposed a source file')
    before = get('/api/map')
    assert before['tiles'] > 1
    view = get('/api/features?map='+before['id']+'&bbox=1.408,42.328,1.444,42.352&zoom=15')
    assert len(view['features']) > 100 and not view['unknownTypes']
    assert {f[0].split(':')[0] for f in view['features']} == {'polygons', 'lines', 'points'}
    for body, headers, expected in [
        (bytes(512), {}, 422),
        (bytes(512), {'Origin': 'http://unrelated.example'}, 403),
        (b'', {'Content-Length': str(MAX_BYTES+1)}, 413),
    ]:
        try:
            urlopen(Request(root+'/api/map', data=body, headers=headers), timeout=120)
        except HTTPError as error:
            assert error.code == expected, error.code
        else:
            raise AssertionError('An invalid upload was accepted')
        assert get('/api/map')['id'] == before['id'], 'Rejected upload changed the current map'
    server.shutdown()
    thread.join()
assert hashlib.file_digest(args.image.open('rb'), 'sha256').hexdigest() == original
print('PASS: real IMG/TYP, all feature kinds, no missing Arfa styles, viewport validation, bitmap transparency, rejected uploads preserve map, input unchanged.')

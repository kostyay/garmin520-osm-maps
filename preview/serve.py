# /// script
# requires-python = ">=3.10"
# dependencies = ["jpype1==1.7.1", "pillow==12.0.0", "shapely==2.1.2"]
# ///
"""Local Easy/IMG viewer. Run with --help for options."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import shutil
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit, unquote
import uuid

from garmin import GarminMap, ROOT, start_java

MAX_BYTES = 256 * 1024**2


class Viewer(ThreadingHTTPServer):
    def __init__(self, address, typconv, image=None):
        self.typconv, self.map, self.map_id = typconv, None, None
        self.lock = threading.Lock()
        super().__init__(address, partial(Handler, directory=str(ROOT/'preview/easy')))
        if image:
            self.load(image)

    def load(self, image):
        candidate = GarminMap(image, self.typconv)
        old = self.map
        self.map, self.map_id = candidate, uuid.uuid4().hex
        if old:
            old.close()
        return self.metadata()

    def metadata(self):
        return dict(self.map.metadata, id=self.map_id) if self.map else {'id': None}

    def server_close(self):
        super().server_close()
        if self.map:
            self.map.close()


def parse_view(query):
    bounds = [float(v) for v in query['bbox'][0].split(',')]
    zoom = int(query['zoom'][0])
    if (len(bounds) != 4 or not all(math.isfinite(v) for v in bounds)
            or not -180 <= bounds[0] < bounds[2] <= 180
            or not -85 <= bounds[1] < bounds[3] <= 85 or not 7 <= zoom <= 18):
        raise ValueError('Invalid viewport coordinates or zoom')
    return bounds, zoom


class Handler(SimpleHTTPRequestHandler):
    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass  # Panning can cancel a response while a tile is still being decoded.

    def json(self, value, status=200):
        data = json.dumps(value, separators=(',', ':')).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/api/map':
            with self.server.lock:
                return self.json(self.server.metadata())
        if url.path == '/api/features':
            try:
                query = parse_qs(url.query)
                bounds, zoom = parse_view(query)
                with self.server.lock:
                    if not self.server.map or query.get('map', [''])[0] != self.server.map_id:
                        return self.json({'error': 'The map changed in another tab. Reload this page.'}, 409)
                    return self.json(self.server.map.features(bounds, zoom))
            except (ValueError, KeyError, IndexError) as error:
                return self.json({'error': str(error)}, 400)
            except Exception:
                return self.json({'error': 'This IMG tile could not be decoded. Use an unlocked classic mkgmap/OpenMTBMap IMG.'}, 422)
        if url.path == '/base.css':
            self.path = '/style.css'
            self.directory = str(ROOT/'preview/dist')
        elif url.path.startswith('/vendor/'):
            name = url.path.removeprefix('/vendor/')
            if name not in ('leaflet.js', 'leaflet.css', 'leaflet.LICENSE'):
                return self.send_error(404)
            self.path = '/vendor/'+name
            self.directory = str(ROOT/'preview/dist')
        elif url.path not in ('/', '/index.html', '/app.js', '/style.css'):
            return self.send_error(404)
        super().do_GET()

    def do_POST(self):
        if self.path != '/api/map':
            return self.send_error(404)
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            return self.json({'error': 'Load maps from this viewer’s own page.'}, 403)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 512 <= size <= MAX_BYTES:
                return self.json({'error': 'Choose an IMG between 512 bytes and 256 MiB.'}, 413)
            with tempfile.TemporaryDirectory(prefix='garmin-upload-') as directory:
                image = Path(directory)/'uploaded.img'
                with image.open('wb') as stream:
                    remaining = size
                    while remaining:
                        chunk = self.rfile.read(min(1024**2, remaining))
                        if not chunk:
                            raise ValueError('The upload was interrupted')
                        stream.write(chunk)
                        remaining -= len(chunk)
                with self.server.lock:
                    metadata = self.server.load(image)
                    metadata['name'] = Path(unquote(self.headers.get('X-Map-Name', 'uploaded.img'))).name[:120]
                    self.server.map.metadata['name'] = metadata['name']
                    return self.json(metadata)
        except ValueError as error:
            return self.json({'error': str(error)}, 422)
        except Exception:
            return self.json({'error': 'Cannot read this IMG/TYP. Use an unlocked classic IMG with one embedded TYP; NT/GMP maps are unsupported.'}, 422)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', nargs='?', type=Path, help='Optional IMG to open initially')
    parser.add_argument('--typconv', default=shutil.which('typconv') or str(ROOT/'.tools/typconv'))
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8768)
    args = parser.parse_args()
    if not Path(args.typconv).is_file():
        parser.error('typconv is missing. See docs/preview.md for the pinned installation command.')
    if not (ROOT/'.tools/mkgmap-r4924/mkgmap.jar').is_file():
        parser.error('mkgmap is missing. Run ./scripts/bootstrap.sh first.')
    try:
        start_java()
    except Exception:
        parser.error('Cannot start Java. Install Java 21 and set JAVA_HOME to its JRE directory.')
    with Viewer((args.host, args.port), args.typconv, args.image.resolve() if args.image else None) as server:
        print(f'IMG viewer: http://{args.host}:{args.port}/', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

# Map viewers

## Easy IMG viewer (recommended)

The repository includes a pan/zoom viewer for the **actual Easy IMG**, with
terrain polygons, road/trail patterns, contours, POI symbols, labels, night
colours, per-type toggles/search, feature identification and a local GPX overlay.
Use **Load IMG file** to open another map without rebuilding or exporting it.
The file is sent only to the local server you started, decoded into temporary
files, and removed when replaced or the server exits. GPX files stay entirely
in the browser. No external basemap or CDN is used.

Prerequisites: Python 3.10+, `uv`, Java 21 with `JAVA_HOME` pointing to the JRE,
Git, and Go (to build typconv once). Bootstrap the pinned mkgmap JAR, then build
the pinned MIT converter:

```sh
./scripts/bootstrap.sh
git clone https://github.com/dyuri/typconv .tools/typconv-src
git -C .tools/typconv-src checkout 5bd9e96a9ab7be2a5c5507a7bc60298be1bf46fc
(cd .tools/typconv-src && go build -o ../typconv ./cmd/typconv)
uv run preview/serve.py replica/optimized/build/gmapsupp.img
```

Open **http://127.0.0.1:8768/**. Omit the IMG argument to start with an empty
viewer and use the file picker. An IMG need not be inside this repository.
`uv` installs pinned Python dependencies in its cache; no npm build is needed.
Use `--typconv /absolute/path/to/typconv` for an existing converter.

```sh
uv run preview/serve.py /path/to/gmapsupp.img --port 8768
uv run preview/check-viewer.py replica/optimized/build/gmapsupp.img --typconv "$PWD/.tools/typconv"
```

The decoder uses mkgmap's IMG filesystem and MapReader APIs to read every
embedded tile, plus the map's own TYP; it does not substitute the seven quiet
map types. Visible types without a TYP entry are reported and drawn with a
magenta fallback rather than silently disappearing. Contour classes use generic
names because a TYP's original interval labels may be stale after filtering.

The first viewport in a tile can take 10–20 seconds to decode. Subsequent pans
reuse up to four decoded tile/detail combinations. A viewport over 60,000
features asks you to zoom in; this limit is reported instead of silently
truncating the map. The coverage button fits tile bounds, which can include
empty space outside the extraction polygon.

Supported: unlocked **classic TRE/LBL/RGN IMG containers with exactly one
embedded TYP**, including this project's Easy and quiet builds. File-picker
uploads are limited to 256 MiB and containers to 500 map tiles. Encrypted, Garmin NT/GMP, multiple-TYP and
missing-TYP maps are rejected with an explanation; this is not a universal
Garmin map reader. Inputs are read-only. SVG/canvas polygon ordering, segment
patterns, label placement and zoom/detail thresholds approximate firmware.
No routing/search/DEM rendering is implemented.

For tailnet access, keep the server bound to localhost and proxy its **HTTP
server**, including `/api/` (serving just the static files cannot decode IMG):

```sh
tailscale serve --bg --https=8445 http://127.0.0.1:8768
tailscale serve status
# Remove only this port when finished:
tailscale serve --https=8445 off
```

Use an unused port and preserve existing handlers. Open the hostname shown by
your own Tailscale installation. The map is uploaded to the machine running
this server; access should stay within your own trusted tailnet. A GitHub
Pages-only deployment cannot run the Java decoder. Stop the local server with
Ctrl-C when done. One server holds one active map; loading another replaces
it for all connected viewers.

## Earlier quiet-map viewer


Build `quiet/build/gmapsupp.img`, run `uv run preview/export.py`, and serve only
the generated `preview/dist` directory. Geometry is decoded from the actual IMG;
there is no unrelated online basemap. Leaflet 1.9.4 is vendored with its license.

```sh
python3 -m http.server 8767 --bind 127.0.0.1 --directory preview/dist
```

For a personal tailnet (not the public internet):

```sh
tailscale serve --bg --https=8444 --set-path=/garmin-maps "$PWD/preview/dist"
tailscale serve status
```

Use the hostname printed by your own Tailscale installation. Choose an unused
port/path and preserve existing handlers. Do not use Funnel unless you intend
public internet access. To remove only this handler:

```sh
tailscale serve --https=8444 --set-path=/garmin-maps off
```

The seven layers are MTB paths, other hiking paths, tracks, unpaved access,
major roads, rivers and water polygons. Quiet/inspection colours, night mode,
GPX uploads, example trail and optional place/boundary/screen helpers are
available. Personal GPX parsing stays client-side. Helpers are not embedded
in the base map; the example overlay is not a planned or validated ride.

Browser projection, dash alignment and zoom thresholds differ from firmware.
The 200×265 screen outline is a scale reference, not a device emulator. The
viewer shows the earlier quiet map, **not the optimized Easy-style map**.

The original session used Playwright with an existing local Chrome install to
check desktop/mobile interactions; browser binaries and local QA caches are
not committed. No Tailnet hostname, private address or personal track is stored
in this repository.

## Easy-map captures

The README GIF uses the optimized Easy build, not the seven-layer viewer above.
`render-easy.py` reads all compiled split tiles in `replica/optimized/build/`,
uses their highest-detail geometry, and decodes `sources/legacy/easy.typ` with
[typconv](https://github.com/dyuri/typconv). It checks the IMG SHA-256 against the
build validation report and the TYP against the source manifest, and fails if
any feature type visible in the three captured areas has no TYP definition.
Generated SVGs and decoded styling stay in ignored `preview/easy-captures/`.

Build the optimized map first and follow the one-time mkgmap/typconv setup
above. Then generate the capture views:

```sh
# JAVA_HOME must point to a JRE with lib/server/libjvm.so for JPype.
uv run preview/render-easy.py "$PWD/.tools/typconv"
python3 -m http.server 8897 --bind 127.0.0.1 --directory preview/easy-captures
```

Open `http://127.0.0.1:8897/` for the Arfa/La Seu/Andorra capture selector.
These are fixed-area SVG views, not a pan/zoom map or firmware emulator. SVG
patterns follow straight path segments, polygons are sorted by area, and labels use simple
collision avoidance. See generated `report.json` for input hash, rendered type
inventory and limitations. No personal GPX is used.

To reproduce the README images, open each generated SVG in a browser at
1200×850 pixels and save screenshots as `arfa.png`, `la-seu.png`, `andorra.png`.
With local Chrome/Chromium, for example:

```sh
for place in arfa la-seu andorra; do
  chromium --headless --hide-scrollbars --force-device-scale-factor=1 \
    --window-size=1200,850 --screenshot="$PWD/preview/easy-captures/$place.png" \
    "http://127.0.0.1:8897/$place.svg"
done
cp preview/easy-captures/arfa.png docs/assets/easy-map-preview.png
magick -delay 250 preview/easy-captures/arfa.png \
  preview/easy-captures/la-seu.png preview/easy-captures/andorra.png \
  -loop 0 -layers Optimize docs/assets/easy-map-preview.gif
```

The public screenshots are raster captures; decoded TYP data and map binaries
are not committed. The generated fixed views are intended for local use.

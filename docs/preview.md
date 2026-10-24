# Quiet-map browser preview

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

Build the optimized map first. Install Go and build the pinned converter:

```sh
git clone https://github.com/dyuri/typconv .tools/typconv-src
git -C .tools/typconv-src checkout 5bd9e96a9ab7be2a5c5507a7bc60298be1bf46fc
(cd .tools/typconv-src && go build -o ../typconv ./cmd/typconv)
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

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

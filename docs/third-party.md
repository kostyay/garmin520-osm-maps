# Inputs, attribution and redistribution

This repository publishes original scripts, the quiet style, documentation,
the fixed region and sanitized reference metadata. It does not bundle map
packages, legacy device maps, provider TYP binaries or personal GPX/FIT files.

- **OSM data:** © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright).
  Raw extracts are supplied by [Geofabrik](https://download.geofabrik.de/).
- **OpenMTBMap:** produced maps and Easy symbology originate from
  [OpenMTBMap/Outdoormaps](https://openmtbmap.org/download/odbl/). Acquire inputs
  from the provider or your own retained device backup, and observe its current
  terms. This project's MIT license does not apply to those assets. Provider
  copyright strings are retained in derived MP/map inputs.
- **Spanish contours:** [OpenTopoMap Garmin](https://garmin.opentopomap.org/)
  credits Viewfinderpanoramas and declares CC-BY-NC-SA 4.0. The reference archive
  is historical terrain, not a fresh OSM snapshot. Personal regeneration is
  separate from redistribution of generated map files.
- **mkgmap:** [project](https://www.mkgmap.org.uk/), GPLv2; r4924 ZIP is downloaded
  and hash checked, not vendored.
- **GMapTool:** [Linux download](https://www.gmaptool.eu/en/content/linux-version);
  downloaded separately to split IMG containers. Read its bundled license.
- **7-Zip:** [project](https://www.7-zip.org/); used to extract NSIS installers
  without running their Windows executables.
- **TYP inspection:** [typconv](https://github.com/dyuri/typconv), MIT. The
  exploratory revision was `5bd9e96a9ab7be2a5c5507a7bc60298be1bf46fc`.
  Optional: clone, check out that revision and `go build ./cmd/typconv`, then
  use `bin2txt` or `info`. The build does not require it or recompile its output.
- **Leaflet 1.9.4:** BSD-2-Clause; license in
  [preview/dist/vendor/leaflet.LICENSE](../preview/dist/vendor/leaflet.LICENSE).
- **Boundary:** country outlines from [geo-countries](https://github.com/datasets/geo-countries),
  based on Natural Earth public-domain data, combined with the
  [Geofabrik Andorra polygon](https://download.geofabrik.de/europe/andorra.poly).
  The exact polygon used is committed; regeneration against newer outlines can
  change it.

No compiled map is offered as a public GitHub release here. The README links
upstream downloads and explains how to generate maps locally. If distributing
derived maps elsewhere, check the licenses of every included input independently
of this repository's code license.

# Reconstruction and deployment history

This is a decision log, not a raw chat transcript. It deliberately excludes
personal track files, pasted local paths, device serials and network addresses.

## 1. Connect and inspect

The device was a Garmin Edge 520 with about 105 MiB of FAT storage. It initially
did not enumerate over USB; reconnecting exposed a `GARMIN` volume. Linux mount
operations required the user's own authentication. Later inspection confirmed
firmware 13.20.

All original map files were copied locally before analysis. `gmapbmap.img` and
`gmapsupp.img` were identical 3,550,208-byte maps named `Andorra_MTB_20251101`.
`gmaptz.img` was a time-zone map; `osmmap.img` was a tiny overview, not additional
regional coverage. Checksums established the basemap backup matched the device.

Decoding TRE bounds showed approximately 42.407227–42.670984 N,
1.406164–1.801758 E. La Seu and Arfa are south of that coverage. Downloaded GPX
courses cannot add missing background mapping.

## 2. Expand the region

The requested scope became the Spanish/Andorran side within roughly 100 km of
Andorra la Vella. France was not needed. Whole OpenMTBMap tiles were much larger
than the desired region, so the final pipeline clips actual features to a stored
polygon, rather than treating tile bounding boxes as an exact extraction.

Raw OSM downloads were also tried: Catalonia alone did not provide full Andorra
coverage, and Aragón was needed for the western part of the radius. The quiet
build merges all three PBF files and extracts the polygon before mkgmap.

## 3. The lean prompt did not describe the old map

A recovered brief requested thin low-contrast lines, no names, POIs, contours,
routing, search or urban data, and a small custom style. Implementing that brief
produced a valid 8,843,264-byte regional map, but the rider found it less detailed
and colourful than the original.

Binary analysis later established the original was an **OpenMTBMap Easy** map:

- Base tile 63730000: 117 distinct line types, 63 polygon types and 148 point
  types actually present at the finest detail; 14,306 line objects, 17,775
  polygons and 5,645 point objects. Counts are compiler objects, not unique
  real-world trails, and can include overlays.
- 6,116 labels and 4,207 routing-road records; actual street/trail names, track
  grades, MTB/hiking classifications and route overlays.
- Forests, meadows, scrub, scree/rock, water, buildings and urban land use.
  Outdoor POIs and also shops, hotels, restaurants, bus stops and ski features.
- A separate tile 73730000 with **20 m contours**, three contour line types,
  2,880 line objects at its finest level, and a DEM grid.
- A 72,911-byte `00EASYAD.TYP`, family 6373/product 1. The reconstruction's
  270-byte muted TYP was therefore intentionally very different.

The original TYP was recovered and reused as binary data, not reconstructed from
guessed colours or regenerated from exploratory decompiler output. Native TYP
headers and GMapTool were used for IDs; third-party JSON TYP conversion was not
treated as authoritative metadata.

## 4. Browser inspection

A buildless Leaflet viewer decoded the quiet IMG itself through mkgmap's Java
`MapReader`, exported four useful detail levels as small browser tiles, and
showed seven layer toggles. It included optional place labels, extraction
boundary, example course and screen-size outline, clearly distinguished from
map features. A local GPX loader never uploaded files.

Desktop/mobile browser checks passed for layer toggles, colours, GPX import and
invalid coordinates, location shortcuts, helper overlays and responsive layout.
It was served only over the user's tailnet. This viewer remains a comparison
for the quiet build; it does not reproduce the Easy map's icons or firmware.

## 5. Installation persistence failure

The first map installation wrote a temporary file, verified it immediately,
renamed it over `gmapbmap.img`, disabled the duplicate, synced and unmounted.
After restarting, the rider saw an almost blank Arfa course and only a northern
corner of the other course had a background map.

The corner matched the old map boundary exactly. Reading the device again found
both original 3.55 MB maps and an empty staging file. The initial write/rename
had not persisted despite checks from the mounted filesystem. **The cause was
not proven**; it should not be generalized to all FAT devices or all renames.
Raw filesystem diagnosis would have required administrator access.

The quiet map was then written **directly into the existing map files**, using
flush/fsync, followed by an actual unmount/remount and full SHA-256 checks of
both files. The rider confirmed that version worked. Immediate cache reads
alone were not sufficient evidence of persistent installation.

The original 520 basemap slot is `Garmin/gmapbmap.img`. A 75 MB map cannot be
duplicated on this device, so later installation uses one active copy and
verified local backups. An identical `gmapsupp.img` duplicate can be removed;
an unrelated supplemental map must be reviewed rather than silently deleted.

## 6. Course imports

Two GPX files were given Day 1/Day 2 names in metadata and track names, with all
track point XML verified unchanged. Their supplied order was reversed relative
to their embedded titles. The files were copied to `Garmin/NewFiles`, checked
and safely ejected; the device converted them to named FIT courses. Those
personal files are not part of this public project.

## 7. Recover the detailed appearance and optimize

The full Spain OpenMTBMap desktop package provided detailed Catalonia data.
Spain's contours were a separate OpenMTBMap download; public OpenTopoMap Spain
contours were used instead, clipped and reduced from 10 m to 20 m spacing with
the recovered contour type styling. Original Andorra content was retained.

With routing/index/DEM data omitted, whole tiles measured 111,304,704 bytes.
Clipping geometry before re-compiling reduced the detailed replica, including
Spanish contours, to **75,161,600 bytes**. Its embedded TYP matched the original
exactly. A requested deployment of this version was interrupted during backup
verification when the user asked for a map under 50 MB; no 75 MB write occurred.

Optimization measurements:

| Change | MB |
| --- | ---: |
| Full replica | 75.16 |
| Remove city/background clutter and forest-species overlays; 5 m polygon tolerance | 60.47 |
| 40 m minor contours; 15 m polygon tolerance | 53.08 |
| Remove crop-field shading; 20 m polygon tolerance | 50.83 |
| Remove town-park/orchard/vineyard fills | 50.06 |
| 21 m background polygon tolerance | **49.99** |

All non-contour line-feature inputs were preserved byte-for-byte throughout
filtering, with hashes per tile. This retained trails, junctions, road access,
labels and route overlays; reductions were concentrated in background and POIs.
The original TYP remained byte-identical. Background polygon precision changes
do not claim to preserve precise forest/shore boundaries at survey accuracy.

## Last confirmed deployment state

The 49,987,584-byte map was written directly to `Garmin/gmapbmap.img`, the
identical quiet-map duplicate was removed after backup verification, and an
immediate full checksum matched. Free space was approximately **39.7 MB**.
The device was safely unmounted. **Final remount verification was awaiting user
authentication, and this optimized map had not yet received a device/ride test.**

Do not change that statement into a success claim until the post-remount
checksum and actual display test have been completed.

## Public-repository portability check

The complete source-preparation/clipping pipeline was rerun in a new checkout,
not only recompiled from cached MP inputs. It uses constrained triangulation
for polygon holes; the earlier exploratory run had used unconstrained triangles
filtered by representative points. The corrected polygons and exact recovered
tile bounds changed the generated background slightly: at the historical 21 m
tolerance the fresh result was 50.10 MB, so the strict size assertion correctly
failed. The published build uses **24 m background-only tolerance** instead.
Navigation-line retention checks still apply. This does not change the already
written historical device file or claim a new device test.

That complete portable rebuild passed at **49,881,088 bytes (49.88 MB)**.
Its reference report is `results/portable-rebuild-validation.json`; the selected
TYP remained byte-identical and all per-tile navigation-line checks passed.

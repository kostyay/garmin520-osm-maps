#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
./scripts/bootstrap.sh
sevenzip=$(command -v 7zz || command -v 7z)
mkdir -p sources/downloads sources/spain sources/legacy sources/contours/tiles
download() {
    if [[ ! -f "$2" ]]; then
        curl -fL --retry 3 "$1" -o "$2.part"
        mv "$2.part" "$2"
    fi
}
if [[ -z ${GMT:-} ]]; then
    [[ $(uname -s) == Linux ]] || { echo 'Set GMT to your native GMapTool executable.' >&2; exit 1; }
    download https://www.gmaptool.eu/sites/default/files/lgmt08220.zip .tools/lgmt08220.zip
    echo '1bfb6cf8e3c13f841000fa025084c9c3d6f7a468a4a0d68753f01f8ab2069660  .tools/lgmt08220.zip' | sha256sum --check
    unzip -oq .tools/lgmt08220.zip -d .tools
    chmod +x .tools/gmt
    GMT="$PWD/.tools/gmt"
fi
download https://ftp5.gwdg.de/pub/misc/openstreetmap/openmtbmap/odbl/mtbspain.exe sources/downloads/mtbspain.exe
"$sevenzip" x -y -osources/spain sources/downloads/mtbspain.exe >/dev/null
if [[ $# == 1 ]]; then
    "$GMT" -s -o "$PWD/sources/legacy" "$1"
elif [[ $# == 0 ]]; then
    download https://ftp5.gwdg.de/pub/misc/openstreetmap/openmtbmap/odbl/mtbandorra.exe sources/downloads/mtbandorra.exe
    "$sevenzip" x -y -osources/legacy sources/downloads/mtbandorra.exe >/dev/null
else
    echo 'Usage: scripts/prepare-sources.sh [absolute-path-to-old-device-map.img]' >&2; exit 1
fi
download https://garmin.opentopomap.org/europe/spain/otm-spain-contours.zip sources/downloads/otm-spain-contours.zip
unzip -oq sources/downloads/otm-spain-contours.zip -d sources/contours
"$GMT" -s -o "$PWD/sources/contours/tiles" "$PWD/sources/contours/otm-spain-contours.img" >/dev/null
uv run scripts/select-sources.py

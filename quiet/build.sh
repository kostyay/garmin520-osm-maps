#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
../scripts/bootstrap.sh
JAVA=${JAVA:-java}
OSMIUM=${OSMIUM:-osmium}
MKGMAP=../.tools/mkgmap-r4924/mkgmap.jar
mkdir -p .tools data build

download() {
    if [[ ! -f "$2" ]]; then
        curl --fail --location --retry 3 "$1" --output "$2.part"
        mv -- "$2.part" "$2"
    fi
}

"$JAVA" -version
"$OSMIUM" --version
while read -r url filename; do
    download "$url" "data/$filename"
done < sources.txt
sha256sum --check sources.sha256

"$OSMIUM" merge data/andorra.osm.pbf data/cataluna.osm.pbf data/aragon.osm.pbf \
    --overwrite --output build/merged.osm.pbf
"$OSMIUM" extract --polygon ../region.geojson --strategy complete_ways \
    --overwrite --output build/region.osm.pbf build/merged.osm.pbf
"$JAVA" -Xmx2g -jar "$MKGMAP" --style-file=style --check-styles
rm -f build/gmapsupp.img build/52371001.img build/quiet.typ
"$JAVA" -Xmx2g -jar "$MKGMAP" \
    --style-file=style --gmapsupp --output-dir=build \
    --family-id=52371 --product-id=1 --mapname=52371001 \
    --family-name='Andorra MTB' --series-name='Andorra MTB' \
    --description='Andorra MTB - Spanish Pyrenees' \
    --latin1 --name-tag-list=quiet:unused-label --no-net \
    build/region.osm.pbf quiet.txt
python3 validate.py | tee build/validation.txt
sha256sum build/gmapsupp.img > build/gmapsupp.img.sha256

#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
./scripts/bootstrap.sh
uv run replica/clip_maps.py
mkdir -p replica/build
"${JAVA:-java}" -Xmx4g -jar .tools/mkgmap-r4924/mkgmap.jar \
    --max-jobs=2 --gmapsupp --latin1 --no-net \
    --family-id=6373 --product-id=1 --family-name='Andorra MTB Easy' \
    --series-name='Andorra MTB Easy' --description='Andorra MTB Easy - 100km Spanish Pyrenees' \
    --output-dir=replica/build replica/maps/*.mp sources/legacy/easy.typ
python3 replica/verify.py

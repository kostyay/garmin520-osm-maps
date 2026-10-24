#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
python3 replica/optimize.py
mkdir -p replica/optimized/build
"${JAVA:-java}" -Xmx4g -jar .tools/mkgmap-r4924/mkgmap.jar \
    --max-jobs=2 --gmapsupp --latin1 --no-net --simplify-polygons=24:24 \
    --family-id=6373 --product-id=1 --family-name='Andorra MTB Easy Trail' \
    --series-name='Andorra MTB Easy Trail' --description='Andorra MTB Easy Trail - 100km' \
    --output-dir=replica/optimized/build replica/optimized/maps/*.mp sources/legacy/easy.typ
python3 replica/verify.py replica/optimized/build
python3 -c 'from pathlib import Path; assert Path("replica/optimized/build/gmapsupp.img").stat().st_size < 50_000_000, "Map exceeds 50 MB target"'

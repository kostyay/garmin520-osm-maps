#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
mkdir -p .tools
archive=.tools/mkgmap-r4924.zip
if [[ ! -f "$archive" ]]; then
    curl -fL --retry 3 https://www.mkgmap.org.uk/download/mkgmap-r4924.zip -o "$archive.part"
    mv "$archive.part" "$archive"
fi
python3 - "$archive" <<'PY'
import hashlib,sys,zipfile
from pathlib import Path
p=Path(sys.argv[1])
assert hashlib.sha256(p.read_bytes()).hexdigest()=='b2170799b61a95d4fc258e8e4fb4e21396809e0390789178f94c77109f8e0d84','mkgmap download checksum mismatch'
if not Path('.tools/mkgmap-r4924/mkgmap.jar').exists():
    with zipfile.ZipFile(p) as z:z.extractall('.tools')
PY
"${JAVA:-java}" -version
[[ $("${JAVA:-java}" -jar .tools/mkgmap-r4924/mkgmap.jar --version 2>&1 | tail -n 1) == 4924 ]]

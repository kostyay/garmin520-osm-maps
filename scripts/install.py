#!/usr/bin/env python3
"""Back up device maps and overwrite the Edge 520 basemap in place."""
import argparse
from datetime import datetime,timezone
import hashlib
import os
from pathlib import Path
import shutil

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def copy_verified(source,destination):
    with source.open('rb') as inp,destination.open('wb') as out:
        shutil.copyfileobj(inp,out);out.flush();os.fsync(out.fileno())
    assert sha(source)==sha(destination),f'Copy mismatch: {destination}'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('image',type=Path);p.add_argument('mount',type=Path)
    p.add_argument('--verify-only',action='store_true',help='Run after a real unmount/remount')
    a=p.parse_args();image=a.image.resolve();mount=a.mount.resolve()
    assert os.path.ismount(mount),'The Garmin volume must be mounted'
    assert image.is_file() and mount not in image.parents,'Use a local map source outside the Garmin'
    with image.open('rb') as f:assert f.read(22)[16:22]==b'DSKIMG','Not a Garmin IMG'
    device=mount/'Garmin';target=device/'gmapbmap.img'
    assert target.is_file(),'Expected existing Edge 520 basemap not found'
    expected=sha(image)
    if a.verify_only:
        assert sha(target)==expected,'Installed map does not match local source'
        print('PASS: device checksum matches',expected)
    else:
        duplicate=device/'gmapsupp.img'
        current=sha(target)
        if duplicate.exists():assert sha(duplicate)==current,'A different supplemental map is present; review it first'
        available=shutil.disk_usage(mount).free+(duplicate.stat().st_size if duplicate.exists() else 0)
        needed=max(0,image.stat().st_size-target.stat().st_size)
        assert available>=needed+5_000_000,'Insufficient free space (including 5 MB reserve)'
        backup=Path(__file__).resolve().parents[1]/'backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup.mkdir(parents=True)
        for file in [target]+([duplicate] if duplicate.exists() else []):copy_verified(file,backup/file.name)
        print('Verified backup:',backup,flush=True)
        if duplicate.exists():duplicate.unlink();os.sync()
        # Preserve the existing directory entry; the staged rename failed to persist on this device.
        with image.open('rb') as inp,target.open('r+b') as out:
            shutil.copyfileobj(inp,out,1024*1024);out.truncate(image.stat().st_size)
            out.flush();print('Flushing Garmin flash storage; keep it connected…',flush=True);os.fsync(out.fileno())
        os.sync();assert sha(target)==expected,'Immediate checksum mismatch'
        print('Written and immediately verified. Unmount/remount, then rerun with --verify-only.')

# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
"""Download hash-verified sources without executing upstream setup.py."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def download(record,folder):
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/record['filename']
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==record['sha256']:return target
    temp=target.with_suffix('.part')
    with urllib.request.urlopen(record['url'],timeout=60) as stream,temp.open('wb') as output:
        shutil.copyfileobj(stream,output)
    if hashlib.sha256(temp.read_bytes()).hexdigest()!=record['sha256']:
        temp.unlink(missing_ok=True);raise RuntimeError('Source hash mismatch: '+record['filename'])
    temp.replace(target);return target

def prepare():
    records=json.loads((ROOT/'DEPENDENCY_SOURCES.json').read_text(encoding='utf-8'))
    downloaded={r['component']:download(r,ROOT/('.download_cache' if r['component']=='vgamepad' else 'corresponding_source')) for r in records}
    destination=ROOT/'.build_deps'
    if destination.exists():shutil.rmtree(destination)
    destination.mkdir()
    archive=downloaded['vgamepad']
    with tarfile.open(archive) as source:
        for item in source.getmembers():
            if not item.isfile():continue
            parts=Path(item.name).parts[1:]
            if not parts:continue
            relative=Path(*parts)
            if '..' in parts:raise RuntimeError('Unsafe archive member')
            keep=(parts[0]=='vgamepad' and relative.suffix=='.py' and not 'lin' in parts)
            keep|=relative.as_posix()=='vgamepad/win/vigem/client/x64/ViGEmClient.dll'
            if keep:
                target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
                with source.extractfile(item) as inp,target.open('wb') as out:shutil.copyfileobj(inp,out)
            if relative.as_posix()=='PKG-INFO':
                info=destination/'vgamepad-0.1.0.dist-info';info.mkdir(exist_ok=True)
                (info/'METADATA').write_bytes(source.extractfile(item).read())
    forbidden=list(destination.rglob('*.msi'))
    assert not forbidden
    dll=destination/'vgamepad/win/vigem/client/x64/ViGEmClient.dll'
    expected=json.loads((ROOT/'VENDOR_BINARY_HASHES.json').read_text())['ViGEmClient.dll']
    if hashlib.sha256(dll.read_bytes()).hexdigest()!=expected:raise RuntimeError('Unexpected ViGEmClient DLL')
    return downloaded

if __name__=='__main__':
    for name,path in prepare().items():print(name,path.name)

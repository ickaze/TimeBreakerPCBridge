# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
import ast
import hashlib
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
def check():
    for folder in ['source','tools']:
        for file in (ROOT/folder).rglob('*.py'):
            ast.parse(file.read_text(encoding='utf-8'),filename=str(file))
    license=(ROOT/'LICENSE.txt').read_text()
    assert 'Copyright (C) 2026 by I.C.KaZe' in license
    assert 'Permission to use, copy, modify, and/or distribute' in license
    origins=json.loads((ROOT/'docs/LICENSE_ORIGINS.json').read_text())
    for name,record in origins.items():
        assert hashlib.sha256((ROOT/'licenses'/name).read_bytes()).hexdigest()==record['sha256'],name
    records=json.loads((ROOT/'DEPENDENCY_SOURCES.json').read_text())
    for record in records:
        if record['component']=='vgamepad':continue
        file=ROOT/'corresponding_source'/record['filename']
        assert hashlib.sha256(file.read_bytes()).hexdigest()==record['sha256'],file.name
        with tarfile.open(file) as archive:
            assert not any(m.name.lower().endswith(('.dll','.exe','.msi','.pyd')) for m in archive.getmembers()),file.name
    assert 'Apache-2.0' in (ROOT/'DEPENDENCIES.txt').read_text()
    assert (ROOT/'THIRD_PARTY_NOTICES.txt').is_file()
    print('Source syntax, notices and corresponding-source hashes: PASS')
if __name__=='__main__':check()

# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
import hashlib
import json
from pathlib import Path
import sys
from PyInstaller.archive.readers import CArchiveReader
import pefile

DENIED_MODULES=('setuptools','pkg_resources','pip','wheel','importlib_metadata','vgamepad.lin','usb.backend.libusb0','usb.backend.openusb')
ALLOWED_METADATA={'pyusb','libusb_package','vgamepad','importlib_resources'}

def forbidden_path(name):
    p=name.replace('\\','/').lower()
    return p.endswith('.msi') or p.endswith('libusb0.dll') or '/vigem/install/' in p or '/client/x86/' in p or any('/'+m+'/' in '/'+p for m in ['setuptools','pkg_resources','pip'])

def audit(folder):
    folder=Path(folder);bad=[];inventory=[];metadata=[]
    for file in folder.rglob('*'):
        if not file.is_file():continue
        name=file.relative_to(folder).as_posix()
        if forbidden_path(name):bad.append(name)
        if file.name=='METADATA' and file.parent.name.endswith('.dist-info'):
            distribution=file.parent.name.split('-')[0].lower().replace('-','_')
            if distribution not in ALLOWED_METADATA:bad.append(name)
            metadata.append(name)
        if file.suffix.lower() in ['.dll','.pyd','.exe']:
            info={}
            pe=pefile.PE(str(file),fast_load=True)
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
            for block in getattr(pe,'FileInfo',[]):
                for entry in block:
                    for table in getattr(entry,'StringTable',[]):
                        info.update({k.decode(errors='replace'):v.decode(errors='replace') for k,v in table.entries.items()})
            inventory.append({'path':name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'size':file.stat().st_size,'pe':info})
    reader=CArchiveReader(str(folder/'TimeBreakerPCBridge.exe'))
    if 'pyi_rth_usb' in reader.toc:bad.append('EXE:pyi_rth_usb')
    pyz=reader.open_embedded_archive('PYZ.pyz')
    for module in pyz.toc:
        if any(module==prefix or module.startswith(prefix+'.') for prefix in DENIED_MODULES):bad.append('PYZ:'+module)
    if bad:raise RuntimeError('Forbidden bundled components: '+json.dumps(bad))
    for required in ['libusb_package/libusb-1.0.dll','vgamepad/win/vigem/client/x64/ViGEmClient.dll']:
        if not any(row['path'].replace('_internal/','')==required for row in inventory):raise RuntimeError('Missing binary: '+required)
    if len(metadata)!=4:raise RuntimeError('Expected exactly 4 runtime metadata records: '+str(metadata))
    return {'passed':True,'forbidden_components':[],'metadata':metadata,'pyz_modules':len(pyz.toc),'binaries':inventory}

if __name__=='__main__':
    report=audit(sys.argv[1]);Path(sys.argv[2]).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

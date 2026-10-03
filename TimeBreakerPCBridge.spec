# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata
import importlib.util
import sys

root=Path(SPECPATH)
sys.path.insert(0,str(root/'tools'))
from build_policy import filter_runtime_scripts
if sys.platform!='win32' or sys.maxsize<=2**32:
    raise RuntimeError('Release builds require 64-bit Windows Python 3.13.16')
libusb_dir=Path(importlib.util.find_spec('libusb_package').origin).parent
vendor=root/'.build_deps'
client=vendor/'vgamepad/win/vigem/client/x64/ViGEmClient.dll'
metadata=[(str(vendor/'vgamepad-0.1.0.dist-info'),'vgamepad-0.1.0.dist-info')]
metadata+=copy_metadata('pyusb')+copy_metadata('libusb-package')+copy_metadata('importlib_resources')
a=Analysis([str(root/'source/launcher.py')],pathex=[str(root/'source'),str(vendor)],
    binaries=[(str(libusb_dir/'libusb-1.0.dll'),'libusb_package'),(str(client),'vgamepad/win/vigem/client/x64')],
    datas=[(str(root/'manual_ja.html'),'.'),(str(root/'manual_en.html'),'.'),(str(root/'source/translations.json'),'.')]+metadata,
    hiddenimports=['bridge','smoke_test','setup_gui','usb_view','core','windows_output','diagnostics','i18n','vendor_path','vgamepad.win.virtual_gamepad','vgamepad.win.vigem_client','vgamepad.win.vigem_commons'],
    hookspath=[str(root/'tools/hooks')],
    runtime_hooks=[str(root/'tools/hooks/runtime_smoke_checkpoint.py')],
    excludes=['setuptools','pkg_resources','pip','wheel','importlib_metadata','usb.backend.libusb0','usb.backend.openusb','vgamepad.lin'],
    noarchive=False,optimize=0)
# The contributed USB runtime hook imports libusb0/openusb unconditionally.
# Our app always passes libusb_package's explicit finder to libusb1; no generic
# backend patch is needed. Remove this hook from both EXEs before packaging.
a.scripts=filter_runtime_scripts(a.scripts)
# Fail rather than silently ship an unintended installer or USB backend.
for name,_,_ in a.binaries+a.datas:
    normalized=name.replace('\\','/').lower()
    if normalized.endswith('libusb0.dll') or normalized.endswith('.msi') or '/vigem/install/' in normalized:
        raise RuntimeError('Forbidden build input: '+name)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='TimeBreakerPCBridge',debug=False,
        bootloader_ignore_signals=False,strip=False,upx=False,console=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='TimeBreakerPCBridge')

# Diagnostic console build uses the identical analysis and resources.
# It stays outside the public Release folder and runs only after a smoke failure.
diagnostic_exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='TimeBreakerPCBridge_diagnostic',debug=True,
        bootloader_ignore_signals=False,strip=False,upx=False,console=True)
diagnostic_coll=COLLECT(diagnostic_exe,a.binaries,a.datas,strip=False,upx=False,name='TimeBreakerPCBridge_diagnostic')

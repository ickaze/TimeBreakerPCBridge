# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
"""No driver installation/removal; no virtual device connection is requested."""
import ctypes
import importlib.util
import json
from pathlib import Path
import sys
import traceback
from datetime import datetime

class Version(ctypes.Structure):
    _fields_=[('major',ctypes.c_uint16),('minor',ctypes.c_uint16),('micro',ctypes.c_uint16),('nano',ctypes.c_uint16),('rc',ctypes.c_char_p),('description',ctypes.c_char_p)]

def run(destination,gui=False):
    result={'passed':False,'windows':sys.platform=='win32','python':sys.version,'hardware_tested':False,'driver_install_remove_tested':False}
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    def checkpoint(stage):
        result['stage']=stage
        result['updated_at']=datetime.now().isoformat()
        destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    checkpoint('self-test entered')
    try:
        if sys.platform!='win32':raise RuntimeError('Windows smoke test requires Windows')
        checkpoint('import libusb_package')
        import libusb_package
        checkpoint('load libusb backend')
        backend=libusb_package.get_libusb1_backend()
        if backend is None:raise RuntimeError('libusb1 backend unavailable')
        backend.lib.libusb_get_version.restype=ctypes.POINTER(Version)
        version=backend.lib.libusb_get_version().contents
        result['libusb_version']=[version.major,version.minor,version.micro,version.nano]
        if result['libusb_version']!=[1,0,30,12037]:raise RuntimeError('Unexpected libusb version')
        checkpoint('locate ViGEmClient')
        spec=importlib.util.find_spec('vgamepad')
        if spec is None:raise RuntimeError('vgamepad unavailable')
        client=Path(spec.origin).parent/'win/vigem/client/x64/ViGEmClient.dll'
        checkpoint('load ViGEmClient DLL (no bus connection)')
        dll=ctypes.CDLL(str(client))
        if not hasattr(dll,'vigem_alloc'):raise RuntimeError('ViGEmClient export unavailable')
        result['vigemclient_loaded']=True
        if gui:
            checkpoint('import GUI modules')
            import tkinter as tk
            import i18n
            from bridge import Bridge
            # Fail with a file traceback rather than wait for user response to a dialog.
            from tkinter import messagebox
            previous_show=messagebox._show
            def unexpected_dialog(*args,**kwargs):
                raise RuntimeError('Unexpected self-test dialog: '+repr((args,kwargs)))
            messagebox._show=unexpected_dialog
            root=None;app=None
            try:
                checkpoint('create Tk root')
                root=tk.Tk()
                def callback_error(exc,value,tb):raise value.with_traceback(tb)
                root.report_callback_exception=callback_error
                checkpoint('create Bridge widgets (USB/hotkeys/settings disabled)')
                app=Bridge(root,auto_setup=False,start_runtime=False)
                for lang in ['en','ja']:
                    checkpoint('GUI language: '+lang)
                    i18n.set_language(lang,persist=False);root.update_idletasks()
                    expected='Output OFF' if lang=='en' else '出力停止'
                    app.disable()
                    if app.outstatus.get()!=expected:raise RuntimeError('Language switch failed: '+lang)
                result['gui_created']=True;result['languages_tested']=['en','ja']
            finally:
                checkpoint('destroy GUI')
                try:
                    if app is not None:app.pause_usb()
                finally:
                    if root is not None:root.destroy()
                    messagebox._show=previous_show
        result['passed']=True
        checkpoint('complete')
    except Exception as error:
        result['error']=str(error);result['traceback']=traceback.format_exc()
    checkpoint('complete' if result['passed'] else 'failed: '+result.get('stage','unknown'))
    return 0 if result['passed'] else 1

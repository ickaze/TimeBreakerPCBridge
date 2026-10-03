# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
import runpy
import sys
from vendor_path import activate
activate()

if '--self-test' in sys.argv:
    import json
    from pathlib import Path
    import traceback
    destination=Path(sys.argv[sys.argv.index('--self-test')+1])
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps({'passed':False,'stage':'launcher entered'}),encoding='utf-8')
    try:
        from smoke_test import run
        exit_code=run(destination,gui='--gui' in sys.argv)
    except Exception:
        destination.write_text(json.dumps({'passed':False,'stage':'self-test startup failed','traceback':traceback.format_exc()},indent=2),encoding='utf-8')
        exit_code=1
    sys.exit(exit_code)
else:
    runpy.run_module('bridge',run_name='__main__')

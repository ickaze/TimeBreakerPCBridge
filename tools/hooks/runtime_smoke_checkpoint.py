# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
"""Record frozen Python bootstrap errors before the app entry point."""
import sys
if '--self-test' in sys.argv:
    import json
    from pathlib import Path
    import traceback
    destination=Path(sys.argv[sys.argv.index('--self-test')+1])
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps({'passed':False,'stage':'PyInstaller early runtime hook entered'}),encoding='utf-8')
    def record_exception(exc,value,tb):
        trace=''.join(traceback.format_exception(exc,value,tb))
        destination.write_text(json.dumps({'passed':False,'stage':'frozen Python startup exception','traceback':trace},indent=2),encoding='utf-8')
        if sys.stderr is not None:
            sys.stderr.write(trace);sys.stderr.flush()
    sys.excepthook=record_exception

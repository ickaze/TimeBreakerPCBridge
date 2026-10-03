# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
"""Source setup accepts installed x64 Python >=3.11; release build remains pinned."""
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import traceback
import venv
from prepare_dependencies import prepare
ROOT=Path(__file__).resolve().parents[1]

def supported(version,maximum):
    return tuple(version[:2]) >= (3,11) and maximum > 2**32

def setup():
    log_path=ROOT/'setup_windows.log'
    with log_path.open('w',encoding='utf-8') as log:
        def say(value):
            print(value,flush=True);log.write(str(value)+'\n');log.flush()
        def command(args):
            say('Running: '+subprocess.list2cmdline([str(x) for x in args]))
            process=subprocess.Popen(args,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
            for line in process.stdout:say(line.rstrip())
            if process.wait():raise RuntimeError('Command failed; see output above')
        try:
            say('Setup started: '+datetime.now().isoformat())
            say('Python: '+sys.version+' | '+sys.executable)
            if sys.platform!='win32':raise RuntimeError('This setup tool requires Windows')
            if not supported(sys.version_info,sys.maxsize):raise RuntimeError('Use 64-bit Python 3.11 or later')
            executable=ROOT/'.venv/Scripts/python.exe'
            if not executable.exists():venv.EnvBuilder(with_pip=True).create(ROOT/'.venv')
            # An existing virtual environment is preserved, but must be compatible.
            command([str(executable),'-c','import sys; assert sys.version_info >= (3,11) and sys.maxsize > 2**32, "Existing .venv is incompatible; rename .venv then retry"'])
            command([str(executable),'-m','pip','install','--only-binary=:all:','--require-hashes','-r','requirements-runtime.lock'])
            for name,path in prepare().items():say('Verified dependency: '+name+' / '+path.name)
            say('Setup complete. No OS drivers were installed or removed.')
            return 0
        except Exception:
            say(traceback.format_exc());return 1
if __name__=='__main__':sys.exit(setup())

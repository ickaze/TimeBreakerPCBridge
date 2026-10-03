# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from prepare_dependencies import prepare
from audit_bundle import audit

ROOT=Path(__file__).resolve().parents[1]

def command(args,**kwargs):subprocess.run(args,check=True,**kwargs)

def run_smoke(args,destination,timeout=120):
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    # Do not mistake evidence from an earlier build for this attempt.
    destination.unlink(missing_ok=True)
    console_log=destination.with_suffix('.console.log')
    try:
        with console_log.open('wb') as output:
            subprocess.run(args,check=True,cwd=ROOT,timeout=timeout,stdout=output,stderr=subprocess.STDOUT)
    except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
        try:evidence=json.loads(destination.read_text(encoding='utf-8'))
        except (OSError,ValueError):evidence={'stage':'No self-test checkpoint. Failure before launcher or process startup.'}
        details={'passed':False,'failure':type(error).__name__,'returncode':getattr(error,'returncode',None),'timeout_seconds':timeout if isinstance(error,subprocess.TimeoutExpired) else None,'console_log':console_log.name,'last_checkpoint':evidence}
        failure=destination.with_name(destination.stem+'-failure.json')
        failure.write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf-8')
        raise RuntimeError('EXE smoke test failed at '+str(evidence.get('stage'))+'. See '+str(failure)) from error

def build():
    if sys.platform!='win32' or sys.version_info[:3]!=(3,13,16) or sys.maxsize<=2**32:
        raise RuntimeError('Install official Windows x64 Python 3.13.16 for the pinned release build')
    version=(ROOT/'VERSION').read_text().strip()
    prepare()
    command([sys.executable,'-m','unittest','discover','-s','source','-p','test_*.py','-v'],cwd=ROOT)
    command([sys.executable,'-m','PyInstaller','--clean','--noconfirm','TimeBreakerPCBridge.spec'],cwd=ROOT)
    folder=ROOT/'dist/TimeBreakerPCBridge'
    report=audit(folder)
    evidence=ROOT/'build/evidence';evidence.mkdir(parents=True,exist_ok=True)
    try:
        run_smoke([str(folder/'TimeBreakerPCBridge.exe'),'--self-test',str(evidence/'runtime-smoke.json'),'--gui'],evidence/'runtime-smoke.json')
    except RuntimeError:
        print('Running diagnostic console EXE; see build/evidence/runtime-smoke-diagnostic.console.log',flush=True)
        diagnostic=ROOT/'dist/TimeBreakerPCBridge_diagnostic/TimeBreakerPCBridge_diagnostic.exe'
        try:
            run_smoke([str(diagnostic),'--self-test',str(evidence/'runtime-smoke-diagnostic.json'),'--gui'],evidence/'runtime-smoke-diagnostic.json')
        except RuntimeError:
            pass
        # A successful diagnostic run does not waive a failed windowed release test.
        raise
    smoke=json.loads((evidence/'runtime-smoke.json').read_text(encoding='utf-8'))
    if not smoke.get('passed'):raise RuntimeError('Runtime smoke test failed: '+json.dumps(smoke))
    command([sys.executable,str(ROOT/'tools/check_source.py')],cwd=ROOT)
    for name in ['LICENSE.txt','DEPENDENCIES.txt','THIRD_PARTY_NOTICES.txt','README.md','manual_ja.html','manual_en.html']:
        shutil.copy2(ROOT/name,folder/name)
    for directory in ['licenses','docs']:
        shutil.copytree(ROOT/directory,folder/directory,dirs_exist_ok=True)
    corresponding=folder/'corresponding_source';corresponding.mkdir(exist_ok=True)
    for file in (ROOT/'corresponding_source').glob('*'):
        if file.name.startswith(('libusb-1.0.30-','libusb-package-1.0.30.0-')):shutil.copy2(file,corresponding/file.name)
    # Also provide build recipes and app source for replacement/relinking of the LGPL library.
    source=folder/'source_package'
    for name in ['source','tools','docs','.github']:
        shutil.copytree(ROOT/name,source/name,ignore=shutil.ignore_patterns('__pycache__'),dirs_exist_ok=True)
    for name in ['TimeBreakerPCBridge.spec','DEPENDENCY_SOURCES.json','VENDOR_BINARY_HASHES.json','requirements-build.lock','requirements-runtime.lock','VERSION','build_exe_windows.bat','setup_windows.bat','start_windows.bat']:
        shutil.copy2(ROOT/name,source/name)
    for name in ['LICENSE.txt','DEPENDENCIES.txt','THIRD_PARTY_NOTICES.txt','README.md','manual_ja.html','manual_en.html']:
        shutil.copy2(ROOT/name,source/name)
    shutil.copytree(ROOT/'licenses',source/'licenses',dirs_exist_ok=True)
    shutil.copytree(ROOT/'corresponding_source',source/'corresponding_source',dirs_exist_ok=True,ignore=shutil.ignore_patterns('*vgamepad*'))
    packages={name:importlib.metadata.version(name) for name in ['pyusb','libusb-package','importlib_resources','PyInstaller','pyinstaller-hooks-contrib','setuptools','wheel','packaging','pefile','pywin32-ctypes','altgraph']}
    manifest={'app_version':version,'source_commit':os.environ.get('GITHUB_SHA','local/uncommitted'),'runner':os.environ.get('RUNNER_OS','local Windows'),
              'python':sys.version,'python_executable':Path(sys.executable).name,'build_packages':packages,'vgamepad':'0.1.0 (verified extracted source)',
              'dependency_sources':json.loads((ROOT/'DEPENDENCY_SOURCES.json').read_text()),'bundle_audit':report,'runtime_smoke':smoke,
              'hardware_tested':False,'driver_install_remove_tested':False,'binary_determinism_claimed':False}
    (folder/'BUILD_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    # The app may create diagnostics during smoke tests; do not publish local machine paths/logs.
    for generated in ['diagnostics','error_gui.txt','settings.json','language.json']:
        path=folder/generated
        if path.is_dir():shutil.rmtree(path)
        elif path.exists():path.unlink()
    release=ROOT/'release';release.mkdir(exist_ok=True)
    archive=release/f'TimeBreakerPCBridge_v{version}_Windows_x64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as zipped:
        for file in sorted(folder.rglob('*')):
            if file.is_file() and '__pycache__' not in file.parts:zipped.write(file,Path(folder.name)/file.relative_to(folder))
    (release/'SHA256SUMS.txt').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n',encoding='ascii')
    print(archive)

if __name__=='__main__':build()

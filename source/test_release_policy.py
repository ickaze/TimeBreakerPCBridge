# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
import hashlib
import json
from pathlib import Path
import sys
import unittest
import tempfile
from unittest.mock import patch
import subprocess
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from check_source import check
from audit_bundle import forbidden_path
from setup_source import supported
from build_release import run_smoke
from build_policy import filter_runtime_scripts
from setup_gui import removal_script,removal_bootstrap,trusted_signature,find_manual
class ReleasePolicyTests(unittest.TestCase):
    def test_timeout_preserves_last_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            destination=Path(directory)/'runtime-smoke.json'
            def stall(*args,**kwargs):
                destination.write_text(json.dumps({'passed':False,'stage':'create Tk root'}))
                raise subprocess.TimeoutExpired(args[0],120)
            with patch('build_release.subprocess.run',side_effect=stall):
                with self.assertRaisesRegex(RuntimeError,'create Tk root'):
                    run_smoke(['dummy.exe'],destination)
            evidence=json.loads(destination.with_name('runtime-smoke-failure.json').read_text())
            self.assertEqual(evidence['last_checkpoint']['stage'],'create Tk root')
            self.assertFalse(evidence['passed'])
    def test_early_exit_captures_console_and_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            destination=Path(directory)/'runtime-smoke.json'
            def crash(*args,**kwargs):
                kwargs['stdout'].write(b'Bootloader: simulated startup failure')
                raise subprocess.CalledProcessError(17,args[0])
            with patch('build_release.subprocess.run',side_effect=crash):
                with self.assertRaises(RuntimeError):run_smoke(['dummy.exe'],destination)
            evidence=json.loads(destination.with_name('runtime-smoke-failure.json').read_text())
            self.assertEqual(evidence['returncode'],17)
            self.assertIn('simulated startup failure',destination.with_suffix('.console.log').read_text())
    def test_smoke_test_does_not_start_device_loop(self):
        import ast
        tree=ast.parse((ROOT/'source/smoke_test.py').read_text())
        constructors=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='Bridge']
        self.assertEqual(len(constructors),1)
        self.assertTrue(any(k.arg=='start_runtime' and isinstance(k.value,ast.Constant) and k.value.value is False for k in constructors[0].keywords))
        # update() could run live callbacks/hotkeys while attempting a widget-only test.
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='update' for n in ast.walk(tree)))
    def test_generic_usb_hook_is_removed_without_removing_required_hooks(self):
        scripts=[('runtime_smoke_checkpoint','/hooks/runtime_smoke_checkpoint.py','PYSOURCE'),('pyi_rth_usb','/hooks/pyi_rth_usb.py','PYSOURCE'),('pyi_rth__tkinter','/hooks/pyi_rth__tkinter.py','PYSOURCE'),('launcher','/source/launcher.py','PYSOURCE')]
        filtered=filter_runtime_scripts(scripts)
        self.assertEqual([entry[0] for entry in filtered],['runtime_smoke_checkpoint','pyi_rth__tkinter','launcher'])
        self.assertEqual(len(scripts),4)
        self.assertEqual(filter_runtime_scripts(filtered),filtered)
    def test_uninstall_logs_startup_and_progress(self):
        script=removal_script(True,False,'C:/local/log.txt')
        self.assertLess(script.index('Set-Content -LiteralPath $logPath'),script.index('$all=@(RegistryRemovalRows)'))
        self.assertIn('Add-Content -LiteralPath $logPath',script)
        self.assertIn('Write-Host $text',script)
        self.assertNotIn('Get-WindowsDriver -Online -All',script)
        self.assertNotIn('Get-PnpDeviceProperty',script)
        self.assertIn('Driver bindings read:',script)
        self.assertIn('Shared package $inf',script)
        bootstrap=removal_bootstrap("C:/user's folder/remove.ps1",'C:/log.txt')
        self.assertIn("& 'C:/user''s folder/remove.ps1'",bootstrap)
        self.assertIn('exit 1',bootstrap)
    def test_signature_requires_exact_publisher(self):
        self.assertTrue(trusted_signature({'status':'Valid','publisher':'Akeo Consulting'},'Akeo Consulting'))
        for status,publisher in [('Valid','Fake Akeo Consulting'),('Valid','Akeo Consulting malicious'),('NotSigned','Akeo Consulting'),('Valid','akeo consulting')]:
            self.assertFalse(trusted_signature({'status':status,'publisher':publisher},'Akeo Consulting'))
    def test_manual_selection_follows_language(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for language in ['en','ja']:(root/('manual_'+language+'.html')).write_text(language)
            self.assertEqual(find_manual('en',[root]).name,'manual_en.html')
            self.assertEqual(find_manual('ja',[root]).name,'manual_ja.html')
            (root/'manual_en.html').unlink()
            self.assertIsNone(find_manual('en',[root]))
    def test_source_python_requirements(self):
        self.assertTrue(supported((3,12,4),2**63-1))
        self.assertTrue(supported((3,13,16),2**63-1))
        self.assertFalse(supported((3,10,9),2**63-1))
        self.assertFalse(supported((3,12,4),2**31-1))
    def test_source_notices_and_corresponding_source(self):check()
    def test_forbidden_artifacts(self):
        for name in ['_internal/libusb0.dll','vgamepad/win/vigem/install/old.msi','vgamepad/win/vigem/client/x86/ViGEmClient.dll','_internal/setuptools/test.py']:
            self.assertTrue(forbidden_path(name),name)
        self.assertFalse(forbidden_path('_internal/vgamepad/win/vigem/client/x64/ViGEmClient.dll'))
        self.assertFalse(forbidden_path('_internal/libusb_package/libusb-1.0.dll'))
    def test_vendor_selection(self):
        vendor=ROOT/'.build_deps'
        files=[p.relative_to(vendor).as_posix() for p in vendor.rglob('*') if p.is_file()]
        self.assertTrue(files,'Run tools/prepare_dependencies.py before testing')
        self.assertFalse(any(forbidden_path(p) or p.endswith('setup.py') for p in files))
        binaries=[p for p in files if p.endswith(('.dll','.pyd','.exe','.msi'))]
        self.assertEqual(binaries,['vgamepad/win/vigem/client/x64/ViGEmClient.dll'])
        expected=json.loads((ROOT/'VENDOR_BINARY_HASHES.json').read_text())['ViGEmClient.dll']
        self.assertEqual(hashlib.sha256((vendor/binaries[0]).read_bytes()).hexdigest(),expected)

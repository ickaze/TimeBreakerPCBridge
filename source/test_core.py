# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
import unittest
from core import *
from windows_output import Mouse

class Tests(unittest.TestCase):
    def test_packet(self):
        packet=(0xffff & ~(1<<13) & ~(1<<3)).to_bytes(2,'little')+b'\x34\x12\x78\x56'
        x,y,s=decode(packet)
        self.assertEqual((x,y),(0x1234,0x5678));self.assertTrue(s['Trigger']);self.assertTrue(s['A']);self.assertFalse(s['B'])
        with self.assertRaises(ValueError):decode(b'123')
    def test_fire(self):
        f=Fire()
        self.assertFalse(f.step(True,0,True,100,40,20))
        self.assertTrue(f.step(True,.025,True,100,40,20))
        self.assertFalse(f.step(True,.080,True,100,40,20))
        self.assertTrue(f.step(True,.125,True,100,40,20))
        self.assertFalse(f.step(False,.130,True))
        self.assertFalse(f.step(True,.135,True,100,40,20))
        self.assertTrue(f.step(True,.136,False))
    def test_mapping_collision(self):
        self.assertEqual(report({'A':True,'B':True,'Trigger':True},{'A':'A','B':'A','Trigger':'RT'}),(0x1000,0,255))
        self.assertEqual(report({'A':False},{'A':'A'}),(0,0,0))
    def test_calibration(self):
        cal={'x':fit_axis([100,900,900,100],[.1,.9,.9,.1]),'y':fit_axis([900,900,100,100],[.1,.1,.9,.9])}
        u,v=transform(500,500,cal)
        self.assertAlmostEqual(u,.5);self.assertAlmostEqual(v,.5)
        with self.assertRaises(ValueError):fit_axis([1]*4,[0,1,1,0])
    def test_mouse_state_and_failure(self):
        m=Mouse.__new__(Mouse);m.held=set();calls=[];m.send=lambda flag,*args:calls.append(flag)
        m.update(None,{'LEFT':True});m.update(None,{'LEFT':True});m.release()
        self.assertEqual(calls,[2,4]);self.assertFalse(m.held)
        m.held={'LEFT','RIGHT'}
        def send(flag,*args):
            if flag==16:raise RuntimeError('failure')
        m.send=send
        with self.assertRaises(RuntimeError):m.release()
        self.assertIn('RIGHT',m.held)

class NewBehaviorTests(unittest.TestCase):
    def test_offscreen_pad_and_mouse_are_independent(self):
        self.assertEqual(output_permissions(True,True,False,False,False,True,True),(True,False,True))
        self.assertEqual(output_permissions(True,True,False,False,False,True,False),(True,False,False))
        self.assertEqual(output_permissions(True,True,False,False,False,False,False,True),(True,True,False))
        self.assertEqual(output_permissions(True,False,False,False,False,True,True),(False,False,False))
        self.assertEqual(output_permissions(True,True,True,False,False,False,True),(False,False,False))
    def test_calibration_trigger_edges(self):
        from bridge import Bridge
        from types import SimpleNamespace
        b=Bridge.__new__(Bridge)
        b.bitvars={'Trigger':SimpleNamespace(get=lambda:'13')}
        b.cal_trigger=True;b.calibrating=True;b.cal_pending=False
        hits=[];b.capture=lambda:hits.append(1)
        def packet(on):return (0xffff & ~(1<<13) if on else 0xffff).to_bytes(2,'little')+bytes([1,0,2,0])
        b.on_packet(0,1,2,True,packet(True)) # trigger held at start: ignored
        b.on_packet(1,1,2,False,packet(False))
        b.on_packet(2,1,2,True,packet(True))
        b.on_packet(3,1,2,True,packet(True)) # hold: one capture only
        self.assertEqual(len(hits),1)
        b.on_packet(4,1,2,False,packet(False));b.on_packet(5,1,2,True,packet(True))
        self.assertEqual(len(hits),2)
    def test_capture_uses_trigger_packet_coordinates(self):
        from usb_view import App
        from types import SimpleNamespace
        import time
        from collections import deque
        b=App.__new__(App)
        b.last=(time.perf_counter(),1000,2000,True,b'')
        b.samples=deque([(time.perf_counter(),100,200)]*30)
        b.corners=[];b.guide=SimpleNamespace(set=lambda value:None)
        App.capture(b)
        self.assertEqual(b.corners,[(1000,2000)])

    def test_removal_scope(self):
        from setup_gui import classify_device,removal_script
        self.assertEqual(classify_device({'id':'USB\\VID_0B9A&PID_016A\\123'}),'usb')
        self.assertIsNone(classify_device({'id':'USB\\VID_0B9A&PID_016AB\\123'}))
        self.assertEqual(classify_device({'id':'ROOT\\VIGEMBUS\\0000'}),'vigem')
        self.assertIsNone(classify_device({'id':'USB\\VID_1234&PID_5678\\123'}))
        script=removal_script(True,False,"C:/test/log.txt")
        self.assertIn('$usb=$true; $vigem=$false',script)
        self.assertNotIn('/force',script)
        self.assertIn('refusing removal',script)

class DiagnosticsAndLanguageTests(unittest.TestCase):
    def test_clixml_error_is_readable(self):
        from diagnostics import clean_ps_error
        sample='#< CLIXML\n<Objs xmlns="http://schemas.microsoft.com/powershell/2004/04"><S S="Error">Invalid class_x000D__x000A_0x80041010</S><S S="progress">IGNORE</S></Objs>'
        text=clean_ps_error(sample)
        self.assertEqual(text,'Invalid class\r\n0x80041010');self.assertNotIn('IGNORE',text)
    def test_log_file_is_written(self):
        import diagnostics,tempfile
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder,patch.object(diagnostics,'ROOT',Path(folder)):
            path=diagnostics.log_error('test-logging','test error',details='raw details',trace='test trace')
            self.assertTrue(path.exists())
            text=path.read_text(encoding='utf-8')
            self.assertIn('raw details',text);self.assertIn('test trace',text)
            self.assertTrue((Path(folder)/'diagnostics/error_latest.txt').exists())
    def test_language_translation_and_variables(self):
        import i18n,tkinter as tk
        self.assertEqual(i18n.translate('状態を再確認','en'),'Refresh status')
        self.assertEqual(i18n.translate('Refresh status','ja'),'状態を再確認')
        text=i18n.translate('測定中 12.3 / 30秒 — トリガーを離す。照準は中央に保持。','en')
        self.assertFalse(any('\u3040'<=c<='\u9fff' for c in text))
        i18n.install();interp=tk.Tcl();old=i18n.LANG
        try:
            i18n.LANG='en';v=tk.StringVar(interp,value='状態を再確認')
            self.assertEqual(v.get(),'Refresh status')
            i18n.set_language('ja',persist=False);self.assertEqual(v.get(),'状態を再確認')
            choice=tk.StringVar(interp,value='RT');self.assertEqual(choice.get(),'RT')
        finally:i18n.set_language(old,persist=False)
    def test_diagnostics_does_not_require_signeddriver_class(self):
        from setup_gui import QUERY,removal_script
        self.assertNotIn('Win32_PnPSignedDriver',QUERY)
        self.assertIn('Get-PnpDeviceProperty',QUERY)
        self.assertIn('warnings',QUERY)
        self.assertNotIn('Win32_PnPSignedDriver',removal_script(True,True,'log.txt'))

if __name__=='__main__':unittest.main()

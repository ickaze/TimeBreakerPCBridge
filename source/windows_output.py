# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
import ctypes as c
from ctypes import wintypes as w

class MOUSEINPUT(c.Structure):
    _fields_=[('dx',w.LONG),('dy',w.LONG),('mouseData',w.DWORD),('dwFlags',w.DWORD),('time',w.DWORD),('dwExtraInfo',c.c_size_t)]
class KEYBDINPUT(c.Structure):
    _fields_=[('wVk',w.WORD),('wScan',w.WORD),('dwFlags',w.DWORD),('time',w.DWORD),('dwExtraInfo',c.c_size_t)]
class HARDWAREINPUT(c.Structure):
    _fields_=[('uMsg',w.DWORD),('wParamL',w.WORD),('wParamH',w.WORD)]
class UNION(c.Union):
    _fields_=[('mi',MOUSEINPUT),('ki',KEYBDINPUT),('hi',HARDWAREINPUT)]
class INPUT(c.Structure):
    _anonymous_=('u',)
    _fields_=[('type',w.DWORD),('u',UNION)]

class Mouse:
    def __init__(self):
        self.user=c.WinDLL('user32',use_last_error=True)
        self.user.SendInput.argtypes=[w.UINT,c.POINTER(INPUT),c.c_int]
        self.user.SendInput.restype=w.UINT
        self.user.GetForegroundWindow.restype=w.HWND
        self.user.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
        self.user.GetWindowThreadProcessId.restype=w.DWORD
        self.user.GetAsyncKeyState.argtypes=[c.c_int]
        self.user.GetAsyncKeyState.restype=c.c_short
        self.held=set()
    def send(self,flags,x=0,y=0):
        item=INPUT(type=0,mi=MOUSEINPUT(dx=x,dy=y,dwFlags=flags))
        if self.user.SendInput(1,c.byref(item),c.sizeof(item))!=1:
            raise RuntimeError('SendInput failed (権限の高いゲームには同じ権限が必要な場合があります)')
    def update(self,uv,buttons):
        if uv is not None:
            u,v=uv
            # Absolute coordinates on primary desktop, normalized to 0..65535.
            self.send(0x8001,round(min(max(u,0),1)*65535),round(min(max(v,0),1)*65535))
        wanted={b for b,on in buttons.items() if on}
        flags={'LEFT':(2,4),'RIGHT':(8,16),'MIDDLE':(32,64)}
        for b in list(self.held-wanted):
            self.send(flags[b][1]);self.held.remove(b)
        for b in wanted-self.held:
            self.send(flags[b][0]);self.held.add(b)
    def release(self):self.update(None,{})

class Pad:
    def __init__(self):
        from vendor_path import activate
        activate()
        import vgamepad as vg
        self.vg=vg;self.pad=vg.VX360Gamepad()
    def update(self,report):
        buttons,lt,rt=report
        self.pad.reset()
        if buttons:self.pad.press_button(button=self.vg.XUSB_BUTTON(buttons))
        self.pad.left_trigger(value=lt);self.pad.right_trigger(value=rt)
        self.pad.update()
    def release(self):self.pad.reset();self.pad.update()

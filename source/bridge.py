# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
import i18n
i18n.install()
from diagnostics import current_exception,log_error
import sys
import ctypes
import json
import time
import threading
from usb_view import reader
from setup_gui import SetupWindow
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox
from core import BITS,DEFAULT_MAP,TARGETS,Fire,decode,report,fit_axis,transform,output_permissions
from windows_output import Mouse,Pad
from usb_view import App

ROOT=Path(sys.executable if getattr(sys,'frozen',False) else __file__).resolve().parent

class Bridge(App):
    def __init__(self,win,auto_setup=False,start_runtime=True):
        self.ready=False
        super().__init__(win,start_runtime=start_runtime)
        win.title('TimeBreaker PC Bridge v0.2.2')
        win.geometry('1060x800')
        self.mouse=Mouse();self.pad=None;self.fire=Fire();self.enabled=False
        self.outputcal=None;self.targets=[];self.last_report=None;self.cal_trigger=True;self.cal_pending=False
        self.panel=tk.Toplevel(win);self.panel.title('出力設定 / F8で開始・停止 / F9で緊急停止')
        self.panel.geometry('610x760');self.panel.protocol('WM_DELETE_WINDOW',self.panel.withdraw)
        f=ttk.Frame(self.panel,padding=12);f.pack(fill='both',expand=True)
        self.mousevar=tk.BooleanVar(value=True);self.padvar=tk.BooleanVar(value=True)
        self.autovar=tk.BooleanVar(value=False);self.suppress=tk.BooleanVar(value=True)
        self.padoffscreen=tk.BooleanVar(value=True)
        ttk.Checkbutton(f,text='マウス移動・ボタン出力（主画面）',variable=self.mousevar).pack(anchor='w')
        ttk.Checkbutton(f,text='仮想Xbox 360 / XInput出力',variable=self.padvar).pack(anchor='w')
        ttk.Checkbutton(f,text='PC側トリガー連射（ガン本体は単発に）',variable=self.autovar).pack(anchor='w')
        ttk.Checkbutton(f,text='照準未取得・画面外ではマウスボタンを離す',variable=self.suppress).pack(anchor='w')
        ttk.Checkbutton(f,text='画面外・照準なしでもXInputボタンを有効（標準）',variable=self.padoffscreen).pack(anchor='w')
        self.numbers={}
        for key,label,default in [('period','連射周期 ms',100),('pulse','押下時間 ms',40),('delay','連射開始遅延 ms',0)]:
            row=ttk.Frame(f);row.pack(fill='x',pady=3)
            ttk.Label(row,text=label,width=25).pack(side='left')
            v=tk.StringVar(value=str(default));self.numbers[key]=v
            ttk.Entry(row,textvariable=v,width=10).pack(side='left')
        ttk.Label(f,text='入力 / 生ビット番号 / XInput割当 / マウス割当').pack(anchor='w',pady=8)
        self.bitvars={};self.mapvars={};self.mvars={};self.states={}
        defaultmouse={'Trigger':'LEFT','A':'RIGHT','B':'MIDDLE'}
        for name,bit in BITS.items():
            row=ttk.Frame(f);row.pack(fill='x',pady=2)
            state=tk.StringVar(value=name+' OFF');self.states[name]=state
            ttk.Label(row,textvariable=state,width=14).pack(side='left')
            bv=tk.StringVar(value=str(bit));self.bitvars[name]=bv
            ttk.Spinbox(row,from_=0,to=15,textvariable=bv,width=3).pack(side='left',padx=5)
            mv=tk.StringVar(value=DEFAULT_MAP[name]);self.mapvars[name]=mv
            ttk.Combobox(row,textvariable=mv,values=TARGETS,state='readonly',width=9).pack(side='left',padx=5)
            mm=tk.StringVar(value=defaultmouse.get(name,'NONE'));self.mvars[name]=mm
            ttk.Combobox(row,textvariable=mm,values=['NONE','LEFT','RIGHT','MIDDLE'],state='readonly',width=9).pack(side='left')
        ttk.Button(f,text='設定を保存',command=self.save).pack(fill='x',pady=5)
        ttk.Button(f,text='出力開始 / 停止 (F8)',command=self.toggle).pack(fill='x',pady=5)
        ttk.Button(f,text='緊急停止 (F9)',command=self.disable).pack(fill='x')
        self.outstatus=tk.StringVar(value='出力停止。主画面で四隅を校正してください。')
        ttk.Label(f,textvariable=self.outstatus,wraplength=520).pack(anchor='w',pady=8)
        ttk.Label(f,text='起動時は出力OFF。校正中・測定中・本アプリ操作中は出力停止。\nボタンビット番号はGunCon2標準値。異なる場合は変更可能。').pack(anchor='w')
        ttk.Button(win,text='出力設定ウィンドウを表示',command=self.panel.deiconify).pack()
        ttk.Button(win,text='導入状況・インストール・アンインストール / HTML説明書',command=self.open_setup).pack()
        i18n.attach(win)
        if start_runtime:self.load()
        self.ready=True;self.hotkeys=set()
        if auto_setup and start_runtime:self.win.after(250,self.open_setup)
        if start_runtime:win.after(8,self.output_tick)

    def config(self):
        p=int(self.numbers['period'].get());q=int(self.numbers['pulse'].get());d=int(self.numbers['delay'].get())
        if not (32<=p<=5000 and 16<=q<=p-16 and 0<=d<=10000):
            raise ValueError('周期32～5000ms、押下16～周期-16ms、遅延0～10000msで指定してください。')
        bits={k:int(v.get()) for k,v in self.bitvars.items()}
        if any(not 0<=v<=15 for v in bits.values()):raise ValueError('ビット番号は0～15です。')
        return {'period':p,'pulse':q,'delay':d,'bits':bits,'mapping':{k:v.get() for k,v in self.mapvars.items()},
                'mousemap':{k:v.get() for k,v in self.mvars.items()},'mouse':self.mousevar.get(),
                'pad':self.padvar.get(),'auto':self.autovar.get(),'suppress':self.suppress.get(),'pad_offscreen':self.padoffscreen.get(),'calibration':self.outputcal}

    def save(self):
        try:
            cfg=self.config();cfg['view_calibration']=self.cal
            path=ROOT/'settings.json';temp=ROOT/'settings.tmp'
            temp.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
            self.outstatus.set('設定を保存しました。')
        except Exception as e:messagebox.showerror('保存',str(e))

    def load(self):
        try:
            p=ROOT/'settings.json'
            if not p.exists():return
            cfg=json.loads(p.read_text(encoding='utf-8'))
            for key,var in self.numbers.items():var.set(str(cfg[key]))
            for key,var in self.bitvars.items():var.set(str(cfg['bits'][key]))
            for key,var in self.mapvars.items():var.set(cfg['mapping'][key] if cfg['mapping'][key] in TARGETS else 'NONE')
            for key,var in self.mvars.items():var.set(cfg['mousemap'][key])
            for key,var in [('mouse',self.mousevar),('pad',self.padvar),('auto',self.autovar),('suppress',self.suppress)]:var.set(cfg.get(key,True) if key=='pad' else cfg[key])
            self.padoffscreen.set(cfg.get('pad_offscreen',True))
            self.outputcal=cfg.get('calibration');self.cal=cfg.get('view_calibration')
            self.config()
        except Exception as e:
            current_exception('Settings load',e)
            self.outputcal=None;self.cal=None
            self.outstatus.set('設定読込エラー: '+str(e))

    def release(self):
        try:self.mouse.release()
        finally:
            if self.pad and self.last_report!=(0,0,0):self.pad.release()
        self.last_report=(0,0,0)
        self.fire=Fire()

    def disable(self):
        self.enabled=False
        try:self.release()
        except Exception as e:current_exception('Release output',e)
        if self.ready:self.outstatus.set('出力停止')

    def toggle(self):
        if self.enabled:self.disable();return
        try:
            cfg=self.config()
            if cfg['mouse'] and not self.outputcal:raise ValueError('マウス出力には主画面での四隅校正が必要です。')
            if cfg['pad'] and self.pad is None:self.pad=Pad()
            self.release();self.enabled=True;self.outstatus.set('出力ON。本アプリからゲームへ切り替えてください。F9で停止。')
        except Exception as e:self.disable();messagebox.showerror('出力開始',str(e))

    def begin_cal(self):
        self.disable();self.outputcal=None;self.targets=[]
        self.cal_trigger=True;self.cal_pending=False
        super().begin_cal()
        self.guide.set("左上の黄色ターゲットを狙い、トリガーを離してから1回引いてください。")

    def on_packet(self,t,x,y,on,data):
        try:
            bit=int(self.bitvars['Trigger'].get())
            on=not bool(int.from_bytes(data[:2],'little') & (1<<bit))
        except (AttributeError,ValueError):return
        previous=self.cal_trigger;self.cal_trigger=on
        if self.calibrating and on and not previous and not self.cal_pending:
            self.cal_pending=True
            try:self.capture()
            except Exception as e:
                self.reset_cal();messagebox.showerror('校正エラー',str(e))
            finally:self.cal_pending=False

    def open_setup(self):
        self.disable()
        if getattr(self,'setup_window',None) and self.setup_window.win.winfo_exists():
            self.setup_window.win.lift();return
        self.setup_window=SetupWindow(self)

    def pause_usb(self):
        self.disable();self.stop.set()
        if self.reader_thread.is_alive():self.reader_thread.join(timeout=1)
        if self.reader_thread.is_alive():raise RuntimeError('USB読取停止待ちです。再度操作してください。')
        self.last=None;self.descriptors=None;self.samples.clear()
        while not self.events.empty():
            try:self.events.get_nowait()
            except Exception:break

    def reconnect_usb(self):
        try:self.pause_usb()
        except Exception as e:messagebox.showerror('USB再接続',str(e));return
        self.stop=threading.Event()
        self.reader_thread=threading.Thread(target=reader,args=(self.events,self.stop),daemon=True)
        self.reader_thread.start();self.status.set('USB再接続中…')

    def capture(self):
        if not self.calibrating:return
        i=len(self.corners)
        u,v=[(.12,.12),(.88,.12),(.88,.88),(.12,.88)][i]
        target=((self.canvas.winfo_rootx()+u*self.canvas.winfo_width())/self.win.winfo_screenwidth(),
                (self.canvas.winfo_rooty()+v*self.canvas.winfo_height())/self.win.winfo_screenheight())
        before=len(self.corners);super().capture()
        if len(self.corners)>before:self.targets.append(target)
        if self.cal and len(self.targets)==4:
            self.outputcal={'x':fit_axis([p[0] for p in self.corners],[p[0] for p in self.targets]),
                            'y':fit_axis([p[1] for p in self.corners],[p[1] for p in self.targets]),
                            'screen':[self.win.winfo_screenwidth(),self.win.winfo_screenheight()]}
            self.save()

    def reset_cal(self):
        if self.ready:self.disable()
        self.outputcal=None;super().reset_cal()

    def start_record(self):
        self.disable();super().start_record()

    def output_tick(self):
        try:
            down={key for key in (0x77,0x78) if self.mouse.user.GetAsyncKeyState(key)&0x8000}
            if 0x78 in down:self.disable()
            elif 0x77 in down-self.hotkeys:self.toggle()
            self.hotkeys=down
            cfg=self.config();now=time.perf_counter();fresh=self.last and now-self.last[0]<.25
            states={k:False for k in BITS};uv=None
            if fresh:
                _,x,y,_,data=self.last;x,y,states=decode(data,cfg['bits'])
                if self.outputcal and x!=0:uv=transform(x,y,self.outputcal)
            for key,var in self.states.items():var.set(key+(' ON' if states[key] else ' OFF'))
            # Keep UI operable: foreground application windows suspend output.
            hwnd=self.mouse.user.GetForegroundWindow();pid=ctypes.c_ulong()
            self.mouse.user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            import os
            own=pid.value==os.getpid()
            aim_invalid=not self.last or self.last[1]==0 or (uv is not None and not all(0<=n<=1 for n in uv))
            invalid=not fresh or (cfg['suppress'] and aim_invalid)
            active,mouse_active,pad_active=output_permissions(self.enabled,fresh,own,self.calibrating,self.record,invalid,cfg['pad_offscreen'],aim_invalid)
            if mouse_active and cfg['mouse']:
                if not self.outputcal or self.outputcal.get('screen')!=[self.win.winfo_screenwidth(),self.win.winfo_screenheight()]:
                    raise ValueError('画面サイズに合った四隅校正が必要です。')
            if active:
                if cfg['pad'] and self.pad is None:self.pad=Pad()
                states['Trigger']=self.fire.step(states['Trigger'],now,cfg['auto'],cfg['period'],cfg['pulse'],cfg['delay'])
                if cfg['mouse'] and mouse_active:
                    mb={b:False for b in ['LEFT','RIGHT','MIDDLE']}
                    for name,on in states.items():
                        dest=cfg['mousemap'][name]
                        if dest in mb:mb[dest]|=on
                    self.mouse.update(uv,mb)
                else:self.mouse.release()
                if self.pad:
                    rpt=report(states,cfg['mapping']) if cfg['pad'] and pad_active else (0,0,0)
                    if rpt!=self.last_report:self.pad.update(rpt);self.last_report=rpt
            else:
                self.release()
        except Exception as e:
            current_exception("Output",e)
            self.disable();self.outstatus.set('出力エラー: '+str(e))
        self.win.after(8,self.output_tick)

    def close(self):
        if getattr(self,'setup_window',None) and self.setup_window.busy:
            messagebox.showinfo('処理中','インストーラー・診断・削除処理が終わるまでお待ちください。');return
        self.disable();super().close()

if __name__=='__main__':
    ctypes.windll.user32.SetProcessDPIAware()
    win=tk.Tk()
    def callback_error(exc,value,tb):
        import traceback
        path=log_error('Tk callback',value,trace=''.join(traceback.format_exception(exc,value,tb)))
        messagebox.showerror('Error',str(value)+'\n\nLog: '+str(path))
    win.report_callback_exception=callback_error
    try:Bridge(win);win.mainloop()
    except Exception as e:
        path=current_exception('Startup',e)
        messagebox.showerror('Startup error',str(e)+'\n\nLog: '+str(path))

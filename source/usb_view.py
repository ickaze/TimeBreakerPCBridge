# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
from diagnostics import current_exception
import sys
import csv
import json
import queue
import statistics
import threading
import time
import traceback
from collections import deque
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

ROOT = Path(sys.executable if getattr(sys,'frozen',False) else __file__).resolve().parent

def reader(events, stop):
    dev = None
    claimed = False
    try:
        import usb.core
        import usb.util
        import libusb_package
        dev = usb.core.find(idVendor=0x0B9A, idProduct=0x016A,
                            backend=libusb_package.get_libusb1_backend())
        if dev is None:
            raise RuntimeError('0B9A:016A が見つかりません。接続とWinUSBを確認してください。')
        info = {'vid': dev.idVendor, 'pid': dev.idProduct, 'bcdDevice': dev.bcdDevice,
                'deviceClass': dev.bDeviceClass, 'configurations': []}
        for cfg in dev:
            ci = {'value': cfg.bConfigurationValue, 'interfaces': []}
            for i in cfg:
                ci['interfaces'].append({'number': i.bInterfaceNumber, 'alternate': i.bAlternateSetting,
                    'class': i.bInterfaceClass, 'subclass': i.bInterfaceSubClass,
                    'protocol': i.bInterfaceProtocol,
                    'endpoints': [{'address': e.bEndpointAddress, 'attributes': e.bmAttributes,
                                  'maxPacketSize': e.wMaxPacketSize, 'interval': e.bInterval} for e in i]})
            info['configurations'].append(ci)
        events.put(('descriptors', info))
        try:
            cfg = dev.get_active_configuration()
        except usb.core.USBError:
            dev.set_configuration()
            cfg = dev.get_active_configuration()
        eps = [(i, e) for i in cfg if i.bAlternateSetting == 0 for e in i
               if usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
               and usb.util.endpoint_type(e.bmAttributes) in (2, 3)]
        if len(eps) != 1:
            raise RuntimeError('INエンドポイントが1個ではありません。記述子を確認する必要があります。')
        intf, ep = eps[0]
        usb.util.claim_interface(dev, intf.bInterfaceNumber)
        claimed = True
        events.put(('status', '接続済み / IN 0x%02X' % ep.bEndpointAddress))
        while not stop.is_set():
            try:
                data = bytes(ep.read(ep.wMaxPacketSize, timeout=250))
                events.put(('packet', (time.perf_counter(), data)))
            except usb.core.USBTimeoutError:
                pass
    except Exception as e:
        current_exception("USB reader",e)
        err = traceback.format_exc()
        (ROOT / 'error_gui.txt').write_text(err, encoding='utf-8')
        events.put(('error', err))
    finally:
        if dev is not None:
            if claimed:
                try:
                    usb.util.release_interface(dev, intf.bInterfaceNumber)
                except Exception:
                    pass
            usb.util.dispose_resources(dev)

class App:
    def __init__(self, win, start_runtime=True):
        self.win = win
        win.title('Time Breaker USB — 照準確認・キャリブレーション・測定')
        win.geometry('1060x820')
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.samples = deque(maxlen=250)
        self.last = None
        self.descriptors = None
        self.cal = None
        self.corners = []
        self.calibrating = False
        self.record = None
        self.bounds = None
        self.status = tk.StringVar(value='接続中…')
        self.values = tk.StringVar(value='受信待ち')
        self.guide = tk.StringVar(value='センサーバーをPC画面の上などへ置き、ガンを向けてください。')
        ttk.Label(win, textvariable=self.status).pack(anchor='w', padx=12, pady=5)
        ttk.Label(win, textvariable=self.values).pack(anchor='w', padx=12)
        ttk.Label(win, textvariable=self.guide, wraplength=1000).pack(anchor='w', padx=12, pady=8)
        bar = ttk.Frame(win)
        bar.pack(fill='x', padx=12)
        self.calbtn = ttk.Button(bar, text='① キャリブレーション開始', command=self.begin_cal)
        self.calbtn.pack(side='left', padx=3)
        # Calibration capture uses the gun trigger; no capture button is shown.
        ttk.Button(bar, text='位置合わせ解除', command=self.reset_cal).pack(side='left', padx=3)
        ttk.Button(bar, text='表示範囲リセット', command=self.reset_bounds).pack(side='left', padx=3)
        bar2 = ttk.Frame(win)
        bar2.pack(fill='x', padx=12, pady=8)
        self.mode = tk.StringVar(value='single')
        ttk.Radiobutton(bar2, text='単発モードを測定', variable=self.mode, value='single').pack(side='left')
        ttk.Radiobutton(bar2, text='連射モードを測定', variable=self.mode, value='auto').pack(side='left')
        self.recbtn = ttk.Button(bar2, text='② 30秒測定開始', command=self.start_record)
        self.recbtn.pack(side='left', padx=12)
        ttk.Button(bar2, text='測定中止', command=self.cancel_record).pack(side='left')
        self.canvas = tk.Canvas(win, background='#101b2a', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True, padx=12, pady=5)
        ttk.Label(win, text='黄色：合わせるターゲット　水色：受信位置　赤：トリガーON / X=0では点を非表示\n'
                  '未校正表示は受信範囲に自動拡大。校正はPC内の表示変換のみ。PS2用の校正や本体設定は変更しません。').pack(pady=5)
        win.protocol('WM_DELETE_WINDOW', self.close)
        self.reader_thread=threading.Thread(target=reader, args=(self.events,self.stop),daemon=True)
        if start_runtime:
            self.reader_thread.start()
            win.after(16, self.tick)

    def reset_bounds(self):
        self.bounds = None

    def reset_cal(self):
        self.cal = None
        self.corners = []
        self.calibrating = False
        self.guide.set('位置合わせ解除。受信範囲に自動拡大して表示します。')

    def begin_cal(self):
        if self.record:
            return
        self.cal = None
        self.corners = []
        self.calibrating = True
        self.guide.set('左上の黄色ターゲットに照準を合わせ1秒ほど保持し、トリガーを1回引いて確定してください。')

    def capture(self):
        now = time.perf_counter()
        pts = [(self.last[1],self.last[2])] if self.last else []
        if not self.last or now-self.last[0] > .25 or self.last[1] == 0:
            messagebox.showwarning('座標不足', '照準を合わせ、Xが0以外の座標が受信されている状態でトリガーを引いてください。センサーバーの位置・距離を調整してください。')
            return
        self.corners.append((statistics.median(p[0] for p in pts), statistics.median(p[1] for p in pts)))
        names = ['左上', '右上', '右下', '左下']
        if len(self.corners) < 4:
            self.guide.set(names[len(self.corners)]+'の黄色ターゲットに合わせ照準を合わせ、トリガーを1回引いて確定してください。')
            self.samples.clear()
            return
        tl, tr, br, bl = self.corners
        xmin, xmax = (tl[0]+bl[0])/2, (tr[0]+br[0])/2
        ymin, ymax = (tl[1]+tr[1])/2, (bl[1]+br[1])/2
        if abs(xmax-xmin) < 10 or abs(ymax-ymin) < 10:
            self.reset_cal()
            messagebox.showwarning('校正できません', '四隅の座標差が不足しています。特にYが固定の場合、PC接続では縦座標を取得できていない可能性があります。\n校正なしでも生データの測定はできます。')
            return
        self.cal = {'left': xmin, 'right': xmax, 'top': ymin, 'bottom': ymax, 'corners': self.corners,
                    'target_margin': .12, 'method': 'four-corner axis scaling; local display only'}
        self.calibrating = False
        self.guide.set('位置合わせ完了。中央を狙って点が中央に来るか確認してください。実機のモードを切り替えて測定できます。')

    def start_record(self):
        if self.record or self.calibrating or self.descriptors is None:
            messagebox.showinfo('測定', '接続完了を待ち、キャリブレーションを完了または解除してください。')
            return
        out = ROOT / ('log_gui_'+time.strftime('%Y%m%d_%H%M%S')+'_'+self.mode.get())
        out.mkdir(exist_ok=False)
        (out/'descriptors.json').write_text(json.dumps(self.descriptors, indent=2), encoding='utf-8')
        (out/'calibration.json').write_text(json.dumps({'calibration': self.cal,
            'coordinate_interpretation': 'tentative GunCon2 layout; x=0 hidden, no validity guarantee'}, indent=2), encoding='utf-8')
        f = (out/(self.mode.get()+'.csv')).open('w', newline='', encoding='utf-8')
        writer = csv.writer(f)
        writer.writerow(['elapsed_ms', 'phase', 'length', 'hex', 'x', 'y', 'trigger_on'])
        self.record = (time.perf_counter(), f, writer, out, self.mode.get())
        self.recbtn.config(state='disabled')
        self.calbtn.config(state='disabled')

    def cancel_record(self):
        if self.record:
            self.finish_record(True)

    def finish_record(self, aborted=False):
        start, f, writer, out, mode = self.record
        f.close()
        (out/'session.json').write_text(json.dumps({'mode_label':mode, 'aborted':aborted,
            'duration_seconds':time.perf_counter()-start}, indent=2), encoding='utf-8')
        self.record = None
        self.recbtn.config(state='normal')
        self.calbtn.config(state='normal')
        self.guide.set(('測定中止。' if aborted else '測定完了。')+'ログ: '+str(out))

    def tick(self):
        for _ in range(1000):
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'descriptors':
                self.descriptors = payload
            elif kind in ('status', 'error'):
                self.status.set(payload if kind=='status' else 'USBエラー。error_gui.txtを送ってください。')
                # Keep setup accessible even when no driver/device is present.
            elif kind == 'packet':
                t, data = payload
                if len(data) < 6:
                    self.status.set('6バイト未満のデータを受信。解析対象外。')
                    continue
                x, y = int.from_bytes(data[2:4], 'little'), int.from_bytes(data[4:6], 'little')
                on = not bool(data[1]&32)
                self.last = (t, x, y, on, data)
                self.samples.append((t, x, y))
                if hasattr(self,"on_packet"):self.on_packet(t,x,y,on,data)
                if x != 0:
                    if self.bounds is None:
                        self.bounds = [x-20, x+20, y-20, y+20]
                    else:
                        b = self.bounds
                        b[:] = [min(b[0],x-5), max(b[1],x+5), min(b[2],y-5), max(b[3],y+5)]
                if self.record:
                    start, f, writer, out, mode = self.record
                    elapsed = t-start
                    if 0 <= elapsed < 30:
                        phase = 'release' if elapsed<5 else 'hold' if elapsed<15 else 'release2' if elapsed<20 else 'tap'
                        writer.writerow([round(elapsed*1000,3), phase, len(data), data.hex(' '), x,y,int(on)])
        now = time.perf_counter()
        if self.record:
            elapsed = now-self.record[0]
            if elapsed >= 30:
                self.finish_record()
            else:
                action = '離す' if elapsed<5 else '引き続ける' if elapsed<15 else '離す' if elapsed<20 else '繰り返し引く'
                self.guide.set('測定中 %.1f / 30秒 — トリガーを%s。照準は中央に保持。' % (elapsed,action))
        self.draw(now)
        self.win.after(16, self.tick)

    def draw(self, now):
        c = self.canvas
        c.delete('all')
        w, h = max(c.winfo_width(),1), max(c.winfo_height(),1)
        for i in range(1, 10):
            c.create_line(w*i/10,0,w*i/10,h, fill='#23344b')
            c.create_line(0,h*i/10,w,h*i/10, fill='#23344b')
        c.create_line(w/2-20,h/2,w/2+20,h/2,fill='white')
        c.create_line(w/2,h/2-20,w/2,h/2+20,fill='white')
        if self.calibrating:
            u,v = [( .12,.12),(.88,.12),(.88,.88),(.12,.88)][len(self.corners)]
            cx, cy = u*w, v*h
            c.create_oval(cx-20,cy-20,cx+20,cy+20,outline='#ffdd44',width=4)
            c.create_line(cx-30,cy,cx+30,cy,fill='#ffdd44',width=2)
            c.create_line(cx,cy-30,cx,cy+30,fill='#ffdd44',width=2)
        if self.last:
            t,x,y,on,data = self.last
            fresh = now-t < .5
            self.values.set('X=%d  Y=%d  トリガー=%s  RAW: %s  / %s' %
                (x,y,'ON' if on else 'OFF',data.hex(' '),'校正済み' if self.cal else '未校正・自動範囲'))
            if fresh and x != 0:
                b = self.cal
                if b:
                    u = .12+.76*(x-b['left'])/(b['right']-b['left'])
                    v = .12+.76*(y-b['top'])/(b['bottom']-b['top'])
                else:
                    b=self.bounds
                    u,v=(x-b[0])/(b[1]-b[0]),(y-b[2])/(b[3]-b[2])
                outside = not (0<=u<=1 and 0<=v<=1)
                cx,cy=min(max(u,0),1)*w,min(max(v,0),1)*h
                color='#ff6666' if on else '#44ddff'
                c.create_oval(cx-12,cy-12,cx+12,cy+12,outline=color,width=3)
                c.create_line(cx-20,cy,cx+20,cy,fill=color,width=2)
                c.create_line(cx,cy-20,cx,cy+20,fill=color,width=2)
                if outside:
                    c.create_text(w/2,25,text='校正範囲外（点は画面端に表示）',fill='#ffdd44')
            else:
                c.create_text(w/2,h/2+45,text='X=0：照準未取得の可能性' if fresh else 'USBデータ受信待ち',fill='#ffdd44',font=('',16))
        if self.record:
            e=now-self.record[0]
            act='離す' if e<5 else '引き続ける' if e<15 else '離す' if e<20 else '繰り返し引く'
            c.create_text(w/2,h-32,text='%.1f秒：%s' % (e,act),fill='white',font=('',22,'bold'))

    def close(self):
        self.cancel_record()
        self.stop.set()
        self.win.destroy()

if __name__ == '__main__':
    window = tk.Tk()
    App(window)
    window.mainloop()

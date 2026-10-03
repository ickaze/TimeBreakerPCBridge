# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
"""Windows diagnostics and explicit, scoped installation/removal actions."""
import base64
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
from diagnostics import clean_ps_error,log_error,current_exception,last_log
import tkinter as tk
from tkinter import ttk,messagebox,filedialog

ROOT=Path(sys.executable if getattr(sys,'frozen',False) else __file__).resolve().parent
RESOURCE=Path(__file__).resolve().parent
OFFICIAL={
    'Zadig':('https://github.com/pbatard/libwdi/releases/download/v1.5.1/zadig-2.9.exe','Akeo Consulting'),
    'ViGEmBus':('https://github.com/nefarius/ViGEmBus/releases/download/v1.22.0/ViGEmBus_1.22.0_x64_x86_arm64.exe','Nefarius Software Solutions e.U.'),
}

def quote(value):return "'"+str(value).replace("'","''")+"'"

def powershell(script,timeout=60):
    prefix="$ProgressPreference='SilentlyContinue'; $ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); "
    encoded=base64.b64encode((prefix+script).encode('utf-16le')).decode('ascii')
    r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],
        capture_output=True,encoding='utf-8',errors='replace',timeout=timeout,creationflags=0x08000000)
    if r.returncode:
        error=clean_ps_error(r.stderr or r.stdout) or 'PowerShell failed'
        path=log_error('PowerShell',error,details=f'Exit code: {r.returncode}\nSCRIPT:\n{script}\nRAW STDOUT:\n{r.stdout}\nRAW STDERR:\n{r.stderr}')
        raise RuntimeError(error+'\nPowerShell log: '+str(path))
    return r.stdout.strip().lstrip('\ufeff')

PNP_FUNCTIONS=r'''
function PnpPropertyValue($props,$key) {
  $property=$props | Where-Object { $_.KeyName -eq $key } | Select-Object -First 1
  if($null -eq $property){return $null}
  $data=$property.PSObject.Properties['Data']
  if($null -eq $data){return $null}
  return $data.Value
}
function DeviceProp($id,$key) {
  try { (Get-PnpDeviceProperty -InstanceId $id -KeyName $key -ErrorAction Stop).Data }
  catch { $null }
}
function PnpRows {
  param([switch]$Removal)
  foreach($d in @(Get-PnpDevice -ErrorAction Stop)) {
    $id=$d.InstanceId
    if($Removal) {
      # One batched property query per device; avoid seven calls per device.
      $props=@(Get-PnpDeviceProperty -InstanceId $id -KeyName 'DEVPKEY_Device_DriverInfPath','DEVPKEY_Device_ProblemCode' -ErrorAction Stop)
      [pscustomobject]@{DeviceID=$id;PNPDeviceID=$id;
        InfName=(PnpPropertyValue $props 'DEVPKEY_Device_DriverInfPath');
        ConfigManagerErrorCode=(PnpPropertyValue $props 'DEVPKEY_Device_ProblemCode')}
      continue
    }
    [pscustomobject]@{DeviceID=$id;PNPDeviceID=$id;Name=$d.FriendlyName;
      Service=(DeviceProp $id 'DEVPKEY_Device_Service');
      ConfigManagerErrorCode=(DeviceProp $id 'DEVPKEY_Device_ProblemCode');
      Present=(DeviceProp $id 'DEVPKEY_Device_IsPresent');Status=$d.Status;
      InfName=(DeviceProp $id 'DEVPKEY_Device_DriverInfPath');
      DriverVersion=(DeviceProp $id 'DEVPKEY_Device_DriverVersion');
      DriverProviderName=(DeviceProp $id 'DEVPKEY_Device_DriverProvider')}
  }
}
'''
QUERY=r'''
$warnings=[System.Collections.Generic.List[string]]::new()
$wanted=@()
try {
  $wanted=@(Get-PnpDevice -ErrorAction Stop | Where-Object { $_.InstanceId -match '^USB\\VID_0B9A&PID_016A(?:&|\\)' -or $_.InstanceId -match '^ROOT\\VIGEMBUS(?:\\|$)' })
} catch { $warnings.Add('Get-PnpDevice: '+$_.Exception.Message) }
$rows=@(foreach($d in $wanted) {
  $id=$d.InstanceId
  [pscustomobject]@{id=$id;name=$d.FriendlyName;
    service=(DeviceProp $id 'DEVPKEY_Device_Service');
    problem=(DeviceProp $id 'DEVPKEY_Device_ProblemCode');
    present=(DeviceProp $id 'DEVPKEY_Device_IsPresent');status=$d.Status;
    inf=(DeviceProp $id 'DEVPKEY_Device_DriverInfPath');
    version=(DeviceProp $id 'DEVPKEY_Device_DriverVersion');
    provider=(DeviceProp $id 'DEVPKEY_Device_DriverProvider')}
})
$svc=Get-Service -Name ViGEmBus -ErrorAction SilentlyContinue
$apps=@(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match 'ViGEm Bus|ViGEmBus|Virtual Gamepad Emulation Bus' } | Select-Object DisplayName,DisplayVersion,PSChildName)
[pscustomobject]@{devices=$rows;warnings=@($warnings);vigem_service=$(if($svc){[string]$svc.Status}else{'Missing'});apps=$apps} | ConvertTo-Json -Depth 6 -Compress
'''
QUERY=PNP_FUNCTIONS+QUERY

def classify_device(row):
    ident=str(row.get('id','')).upper()
    if re.match(r'^USB\\VID_0B9A&PID_016A(?:&|\\)',ident):return 'usb'
    if ident.startswith('ROOT\\VIGEMBUS\\') or ident=='ROOT\\VIGEMBUS' or str(row.get('service','')).lower()=='vigembus':return 'vigem'
    return None

REMOVAL_BINDINGS=r"""
function RegistryRemovalRows {
  # One device enumeration; registry reads replace slow per-device PnP properties.
  $devices=@(Get-PnpDevice -ErrorAction Stop)
  $count=0
  foreach($d in $devices) {
    $id=$d.InstanceId
    $deviceKey='HKLM:\SYSTEM\CurrentControlSet\Enum\'+$id
    try {$properties=Get-ItemProperty -LiteralPath $deviceKey -ErrorAction Stop}
    catch {throw "Cannot verify driver binding for $id : $($_.Exception.Message)"}
    $driverMember=$properties.PSObject.Properties['Driver']
    $inf=$null
    if($null -ne $driverMember -and ![string]::IsNullOrWhiteSpace([string]$driverMember.Value)) {
      $driverKey='HKLM:\SYSTEM\CurrentControlSet\Control\Class\'+[string]$driverMember.Value
      try {$driver=Get-ItemProperty -LiteralPath $driverKey -ErrorAction Stop}
      catch {throw "Cannot read driver class for $id : $($_.Exception.Message)"}
      $infMember=$driver.PSObject.Properties['InfPath']
      if($null -eq $infMember -or [string]::IsNullOrWhiteSpace([string]$infMember.Value)) {
        throw "Driver INF could not be verified for $id; refusing package removal."
      }
      $inf=[string]$infMember.Value
    }
    [pscustomobject]@{DeviceID=$id;PNPDeviceID=$id;InfName=$inf;BindingVerified=$true}
    $count++
    if($count % 25 -eq 0 -or $count -eq $devices.Count) {
      Note("Driver bindings read: $count / $($devices.Count)")
    }
  }
}
"""

def removal_script(usb,vigem,log):
    # Re-discover candidates inside the elevated process; do not trust GUI snapshots.
    return REMOVAL_BINDINGS+r'''
$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new()
$lines=[System.Collections.Generic.List[string]]::new()
$fail=$false
$logPath=LOG_PATH
Set-Content -LiteralPath $logPath -Value 'TimeBreaker driver uninstall started' -Encoding UTF8
function Note($s) {
  $text=([DateTime]::Now.ToString('HH:mm:ss')+' '+[string]$s)
  $lines.Add($text)
  Add-Content -LiteralPath $logPath -Value $text -Encoding UTF8
  Write-Host $text
}
try {
  $usb=USB_CHOICE; $vigem=VIGEM_CHOICE
  Note('Reading device driver bindings from registry; please wait...')
  $all=@(RegistryRemovalRows)
  Note('Device bindings checked: '+$all.Count)
  $entities=$all
  if(@($all | Where-Object { $_.BindingVerified -ne $true }).Count){
    throw "Device properties could not be read. Refusing uninstall because package sharing cannot be verified."
  }
  Note('Scanning OEM INF files (no DISM driver enumeration)...')
  $drivers=@(Get-ChildItem -LiteralPath "$env:windir\INF" -Filter 'oem*.inf' -File | Select-Object @{Name='Driver';Expression={$_.Name}})
  $infs=[System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
  foreach($d in $all) {
    $isUsb=$d.DeviceID -match '^USB\\VID_0B9A&PID_016A(?:&|\\)'
    $isVigem=$d.DeviceID -match '^ROOT\\VIGEMBUS(?:\\|$)'
    if(($usb -and $isUsb) -or ($vigem -and $isVigem)) { if($d.InfName -match '^oem\d+\.inf$'){[void]$infs.Add($d.InfName)} }
  }
  # Include disconnected/stored packages only if their INF explicitly names this hardware.
  foreach($d in $drivers) {
    if($d.Driver -notmatch '^oem\d+\.inf$'){continue}
    $path=Join-Path "$env:windir\INF" $d.Driver
    if(!(Test-Path -LiteralPath $path)){continue}
    $text=Get-Content -LiteralPath $path -Raw
    if(($usb -and $text -match 'USB\\VID_0B9A&PID_016A(?:&|[\s"\r\n,]|$)') -or ($vigem -and $text -match 'ROOT\\VIGEMBUS(?:[\s"\r\n,]|$)')) {
      [void]$infs.Add($d.Driver)
    }
  }
  # Refuse packages also attached to another physical USB device.
  foreach($inf in $infs) {
    $other=@($all | Where-Object { $_.InfName -eq $inf -and $_.DeviceID -notmatch '^USB\\VID_0B9A&PID_016A(?:&|\\)' -and $_.DeviceID -notmatch '^ROOT\\VIGEMBUS(?:\\|$)' })
    if($other.Count){throw "Shared package $inf also serves other devices; refusing removal."}
  }
  if($vigem) {
    $apps=@(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match 'ViGEm Bus|ViGEmBus|Virtual Gamepad Emulation Bus' })
    foreach($a in $apps) {
      if($a.PSChildName -match '^\{[0-9A-Fa-f-]{36}\}$' -and $a.WindowsInstaller -eq 1) {
        Note("MSI uninstall: "+$a.DisplayName)
        $p=Start-Process msiexec.exe -ArgumentList @('/x',$a.PSChildName,'/passive','/norestart') -Wait -PassThru
        Note("MSI exit: "+$p.ExitCode)
        if($p.ExitCode -notin @(0,1605,3010)){ $fail=$true }
      } elseif($a.UninstallString -match '^"([^"\r\n]+\.exe)"(?:\s|$)') {
        $exe=$Matches[1]
        $sig=Get-AuthenticodeSignature -LiteralPath $exe
        if($sig.Status -eq 'Valid' -and $sig.SignerCertificate.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName,$false) -ceq 'Nefarius Software Solutions e.U.') {
          Note("Official ViGEm uninstaller: "+$exe)
          $p=Start-Process -FilePath $exe -ArgumentList @('/uninstall','/passive','/norestart') -Wait -PassThru
          Note("Uninstaller exit: "+$p.ExitCode)
          if($p.ExitCode -notin @(0,1605,3010)){$fail=$true}
        } else {Note('ViGEm uninstaller signature not verified. Use Windows Installed Apps.');$fail=$true}
      } else { Note('Unsupported ViGEm uninstall entry remains. Remove through Windows Installed Apps.');$fail=$true }
    }
  }
  foreach($inf in $infs) {
    $path=Join-Path "$env:windir\INF" $inf
    if(!(Test-Path -LiteralPath $path)){Note("Already removed: $inf");continue}
    Note("Driver removal: $inf")
    $output=& "$env:windir\System32\pnputil.exe" /delete-driver $inf /uninstall 2>&1
    $code=$LASTEXITCODE;Note(($output -join "`r`n"));Note("PnPUtil exit: $code")
    if($code -notin @(0,3010)){$fail=$true}
  }
  foreach($d in $entities) {
    $match=($usb -and $d.PNPDeviceID -match '^USB\\VID_0B9A&PID_016A(?:&|\\)') -or ($vigem -and $d.PNPDeviceID -match '^ROOT\\VIGEMBUS(?:\\|$)')
    if($match) {
      Note("Remove instance: "+$d.PNPDeviceID)
      $output=& "$env:windir\System32\pnputil.exe" /remove-device $d.PNPDeviceID 2>&1
      Note(($output -join "`r`n"));Note("PnPUtil exit: "+$LASTEXITCODE)
      if($LASTEXITCODE -notin @(0,3010)){$fail=$true}
    }
  }
  if(!$infs.Count){Note('No matching OEM driver package found.')}
  Note('Restart Windows, reconnect the dongle, and refresh diagnostics before reinstalling.')
} catch {Note(($_ | Out-String));Note($_.ScriptStackTrace);$fail=$true}
if($fail){Note('RESULT: PARTIAL/FAILED')}else{Note('RESULT: COMPLETED; REBOOT AND RECHECK')}

if($fail){exit 1}else{exit 0}
'''.replace('USB_CHOICE','$true' if usb else '$false').replace('VIGEM_CHOICE','$true' if vigem else '$false').replace('LOG_PATH',quote(log))

def removal_bootstrap(script,launch_log):
    return r"""
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new()
$launchLog=LAUNCH_LOG
Set-Content -LiteralPath $launchLog -Value 'Elevated PowerShell started' -Encoding UTF8
Write-Host 'TimeBreaker: checking and removing selected drivers. Progress is saved to logs.'
try {
  & SCRIPT_PATH
} catch {
  $detail=($_ | Out-String)
  Add-Content -LiteralPath $launchLog -Value $detail -Encoding UTF8
  Write-Host $detail
  exit 1
}
""".replace('LAUNCH_LOG',quote(launch_log)).replace('SCRIPT_PATH',quote(script))

def trusted_signature(signature,publisher):
    return signature.get('status')=='Valid' and signature.get('publisher')==publisher

def find_manual(language,roots):
    filename='manual_en.html' if language=='en' else 'manual_ja.html'
    for root in roots:
        path=Path(root)/filename
        if path.is_file():return path.resolve()
    return None

class SetupWindow:
    def __init__(self,bridge):
        self.bridge=bridge;self.win=tk.Toplevel(bridge.win);self.win.title('TimeBreaker 導入・診断・ドライバー削除')
        self.win.geometry('880x720');self.events=queue.Queue();self.busy=False;self.snapshot={}
        self.win.protocol('WM_DELETE_WINDOW',self.close)
        outer=ttk.Frame(self.win,padding=12);outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='1 状態確認 → 2 WinUSB導入 → 3 XInput導入（必要時） → 4 USB再接続 → 校正・出力設定',wraplength=820).pack(anchor='w')
        bar=ttk.Frame(outer);bar.pack(fill='x',pady=8)
        for label,cmd in [('状態を再確認',self.refresh),('HTML説明書',self.help),('デバイスマネージャー',lambda:subprocess.Popen(['mmc.exe','devmgmt.msc'])),('コントローラー確認',lambda:subprocess.Popen(['control.exe','joy.cpl']))]:
            ttk.Button(bar,text=label,command=cmd).pack(side='left',padx=3)
        frame=ttk.Frame(outer);frame.pack(fill='both',expand=True)
        self.text=tk.Text(frame,wrap='word',height=18);self.text.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(frame,command=self.text.yview);scroll.pack(side='right',fill='y');self.text.config(yscrollcommand=scroll.set)
        row=ttk.Frame(outer);row.pack(fill='x',pady=6)
        ttk.Button(row,text='Zadigを取得して起動',command=lambda:self.install('Zadig')).pack(side='left',padx=3)
        ttk.Button(row,text='ViGEmBusを取得して導入',command=lambda:self.install('ViGEmBus')).pack(side='left',padx=3)
        ttk.Button(row,text='保存済インストーラーを選択',command=self.local_installer).pack(side='left',padx=3)
        ttk.Label(outer,text='Zadigでは USB ID 0B9A:016A を選び、WinUSB をInstall/Replaceしてください。\n取得時はネット接続が必要です。署名確認後、公式インストーラーとWindowsのUAC画面を表示します。',wraplength=820).pack(anchor='w')
        row=ttk.Frame(outer);row.pack(fill='x',pady=8)
        ttk.Button(row,text='USB再接続（導入後に押す）',command=self.reconnect).pack(side='left',padx=3)
        ttk.Button(row,text='出力設定ウィンドウを表示',command=self.output_settings).pack(side='left',padx=3)
        ttk.Button(row,text='Windowsのインストール済アプリ',command=lambda:os.startfile('ms-settings:appsfeatures')).pack(side='left',padx=3)
        box=ttk.LabelFrame(outer,text='まとめてアンインストール / 管理者権限・再起動が必要',padding=8);box.pack(fill='x')
        self.removeusb=tk.BooleanVar(value=True);self.removevigem=tk.BooleanVar(value=False)
        ttk.Checkbutton(box,text='対象ドングル 0B9A:016A のOEMドライバー・デバイス登録',variable=self.removeusb).pack(anchor='w')
        ttk.Checkbutton(box,text='ViGEmBus（DS4Windowsなど他アプリからも使われる共有ドライバー）',variable=self.removevigem).pack(anchor='w')
        ttk.Label(box,text='Windows内蔵WinUSB自体、他USBデバイス、Zadigの証明書、Python環境は削除しません。\nViGEmBusを使う他アプリも終了してください。削除対象は管理者処理で再検出します。',wraplength=800).pack(anchor='w')
        ttk.Button(box,text='選択したドライバー類をまとめてアンインストール',command=self.uninstall).pack(fill='x',pady=4)
        self.status=tk.StringVar(value='未確認。「状態を再確認」を押すと診断します。');ttk.Label(outer,textvariable=self.status,wraplength=820).pack(anchor='w',pady=5)
        ttk.Button(outer,text='エラーログの場所を開く',command=self.open_logs).pack(anchor='w')
        self.win.after(100,self.poll)

    def open_logs(self):
        path=last_log()
        folder=path.parent if path else ROOT/"diagnostics"
        folder.mkdir(parents=True,exist_ok=True);os.startfile(str(folder))

    def close(self):
        if self.busy:
            messagebox.showinfo("処理中","処理が終わるまでこの画面を開いたままにしてください。",parent=self.win);return
        self.win.destroy()

    def output_settings(self):self.bridge.panel.deiconify();self.bridge.panel.lift()
    def help(self):
        import i18n
        path=find_manual(i18n.LANG,[ROOT,RESOURCE,ROOT.parent])
        if path is not None:webbrowser.open(path.as_uri())
        else:messagebox.showerror('説明書','Manual file missing: manual_'+i18n.LANG+'.html')
    def reconnect(self):
        if self.busy:return
        self.bridge.reconnect_usb()
    def worker(self,task,callback):
        if self.busy:return
        self.busy=True;self.status.set('処理中。インストーラーやUAC画面の操作を完了してください。')
        def run():
            try:self.events.put((callback,task(),None))
            except Exception as e:
                path=current_exception('Setup worker',e)
                self.events.put((callback,None,(str(e),path)))
        threading.Thread(target=run,daemon=True).start()
    def poll(self):
        if not self.win.winfo_exists():return
        while not self.events.empty():
            cb,result,error=self.events.get();self.busy=False
            if error:
                error,path=error
                self.text.delete('1.0','end');self.text.insert('1.0',error+'\n\nLog: '+str(path))
                self.status.set('失敗: '+error.splitlines()[0]+' | Log: '+str(path))
                messagebox.showerror('導入・診断',error[:1000]+'\n\nLog: '+str(path),parent=self.win)
            else:cb(result)
        self.win.after(100,self.poll)
    def refresh(self):
        def task():
            output=powershell(QUERY)
            try:result=json.loads(output)
            except ValueError as e:
                path=log_error('Diagnostics JSON',e,details=output)
                raise RuntimeError('Invalid diagnostics response. Log: '+str(path)) from e
            result['libraries']={m:importlib.util.find_spec(m) is not None for m in ['usb','libusb_package','vgamepad']}
            return result
        self.worker(task,self.show_status)
    def show_status(self,result):
        self.snapshot=result
        warnings=result.get('warnings',[])
        if warnings:log_error('Device diagnostics warnings','; '.join(warnings),details=json.dumps(result,ensure_ascii=False,indent=2))
        rows=['TimeBreaker PC Bridge v0.2.2','起動形態: '+('EXE / Python導入不要' if getattr(sys,'frozen',False) else 'Pythonソース実行'),
              '管理者権限: '+str(bool(ctypes.windll.shell32.IsUserAnAdmin())),
              'ライブラリー: '+json.dumps(result['libraries'],ensure_ascii=False),
              'ViGEmBusサービス: '+result['vigem_service'],'']
        usb=False
        for d in result.get('devices',[]):
            usb|=classify_device(d)=='usb'
            rows += [str(d.get('name')),str(d.get('id')),'Service=%s  Problem=%s  Present=%s  Status=%s'%(d.get('service'),d.get('problem'),d.get('present'),d.get('status')),
                     'INF=%s  Version=%s  Provider=%s'%(d.get('inf'),d.get('version'),d.get('provider')),'']
        if not usb:rows.append('0B9A:016A の登録が見つかりません。接続／USBポート／ハードウェアIDを確認してください。')
        rows+=['Warnings: '+str(result.get('warnings',[])), 'ViGEmBusアプリ登録: '+json.dumps(result.get('apps',[]),ensure_ascii=False),
               'USB受信: '+('受信あり' if self.bridge.last and time.perf_counter()-self.bridge.last[0]<.25 else '受信なし'),
               'サービス／登録があっても動作成功とは限りません。USB再接続とjoy.cplで確認してください。']
        self.text.delete('1.0','end');self.text.insert('1.0','\n'.join(rows));self.status.set('一部の情報を取得できません。エラーログを確認してください。' if warnings else '確認完了。導入後はUSB再接続・状態再確認を実行してください。')
    def install(self,kind):
        if self.busy:return
        detail='対象はUSB ID 0B9A:016Aだけを選んでください。' if kind=='Zadig' else 'ViGEmBusは開発終了しています。XInput利用に必要な共有ドライバーです。'
        if not messagebox.askokcancel('公式インストーラーの起動',kind+'を公式配布から取得・署名確認し起動します。\n'+detail,parent=self.win):return
        try:self.prepare_action()
        except Exception as e:messagebox.showerror("USB停止",str(e));return
        def task():
            url,subject=OFFICIAL[kind]
            folder=ROOT/'installers';folder.mkdir(exist_ok=True)
            target=folder/url.rsplit('/',1)[-1];temp=target.with_suffix('.download')
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'TimeBreakerPCBridge/0.2.2'}),timeout=30) as src, temp.open('wb') as dst:
                total=0
                while True:
                    part=src.read(1024*1024)
                    if not part:break
                    total+=len(part)
                    if total>100*1024*1024:raise RuntimeError('インストーラーのサイズが想定を超えました。')
                    dst.write(part)
            temp.replace(target)
            return self.run_installer(target,subject)
        self.worker(task,self.install_done)
    def prepare_action(self):
        self.bridge.pause_usb()
        if self.bridge.pad:
            self.bridge.pad.release();self.bridge.pad=None;self.bridge.last_report=None
    def run_installer(self,path,subject):
        sig=json.loads(powershell('$s=Get-AuthenticodeSignature -LiteralPath '+quote(path)+"; [pscustomobject]@{status=[string]$s.Status;subject=$s.SignerCertificate.Subject;publisher=$(if($s.SignerCertificate){$s.SignerCertificate.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName,$false)}else{''})}|ConvertTo-Json -Compress"))
        if not trusted_signature(sig,subject):
            raise RuntimeError('公式発行者の有効な署名を確認できません。起動を中止しました。'+str(sig))
        return powershell('$p=Start-Process -FilePath '+quote(path)+' -Verb RunAs -Wait -PassThru; $p.ExitCode',timeout=1800)
    def install_done(self,result):
        self.status.set('インストーラー終了コード: '+str(result)+'。USB再接続／状態再確認を押してください。')
        self.text.insert('end','\nインストーラー終了コード: '+str(result))
    def local_installer(self):
        if self.busy:return
        path=filedialog.askopenfilename(parent=self.win,title='公式ZadigまたはViGEmBusのEXEを選択',filetypes=[('EXE','*.exe')])
        if not path:return
        kind='Zadig' if 'zadig' in Path(path).name.lower() else 'ViGEmBus' if 'vigem' in Path(path).name.lower() else None
        if not kind:messagebox.showerror('選択','名前がZadigまたはViGEmの公式EXEを指定してください。');return
        if not messagebox.askokcancel('起動',str(path)+'\n公式発行者の署名を検証して起動します。',parent=self.win):return
        try:self.prepare_action()
        except Exception as e:messagebox.showerror('USB停止',str(e));return
        self.worker(lambda:self.run_installer(Path(path),OFFICIAL[kind][1]),self.install_done)
    def uninstall(self):
        if self.busy:return
        usb=self.removeusb.get();vigem=self.removevigem.get()
        if not usb and not vigem:return
        targets=('ドングル用OEMドライバー\n' if usb else '')+('ViGEmBus（他アプリも使用不能になります）\n' if vigem else '')
        if not messagebox.askyesno('削除対象の確認',targets+'\n出力とUSB読取を停止して削除します。\n処理後はWindows再起動が必要です。続行しますか？',parent=self.win):return
        try:self.prepare_action()
        except Exception as e:messagebox.showerror('USB停止',str(e));return
        def task():
            # Elevated processes may not see mapped drives used for the application.
            folder=Path(os.environ.get('LOCALAPPDATA') or tempfile.gettempdir())/'TimeBreakerPCBridge/diagnostics'
            folder.mkdir(parents=True,exist_ok=True)
            stamp=time.strftime('%Y%m%d_%H%M%S')+'_'+str(time.time_ns())
            log=folder/('uninstall_'+stamp+'.txt')
            script=folder/('uninstall_'+stamp+'.ps1')
            launch_log=folder/('uninstall_'+stamp+'_launch.txt')
            script.write_text(removal_script(usb,vigem,log),encoding='utf-8-sig')
            # A short encoded bootstrap avoids nested -File path quoting and records
            # parse/startup errors before the removal script can create its log.
            bootstrap=removal_bootstrap(script,launch_log)
            encoded=base64.b64encode(bootstrap.encode('utf-16le')).decode('ascii')
            args='-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand '+encoded
            result=powershell('$p=Start-Process powershell.exe -Verb RunAs -ArgumentList '+quote(args)+' -Wait -PassThru; $p.ExitCode',timeout=1800)
            if not log.exists():
                detail=launch_log.read_text(encoding='utf-8-sig') if launch_log.exists() else 'No elevated startup log. Check UAC response.'
                raise RuntimeError('Uninstall did not start. Exit code: '+result+'\n'+detail+'\nStartup log: '+str(launch_log))
            output=log.read_text(encoding='utf-8-sig')+'\nLog: '+str(log)+'\nStartup log: '+str(launch_log)
            if result.strip() not in ('0','3010'):
                raise RuntimeError('Uninstall incomplete. Exit code: '+result+'\n'+output)
            return output
        def done(result):
            self.text.delete('1.0','end');self.text.insert('1.0',result)
            self.status.set('ログを確認してWindowsを再起動してください。「状態を再確認」で残存を確認できます。')
        self.worker(task,done)

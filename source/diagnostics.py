# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
import datetime
import os
from pathlib import Path
import platform
import sys
import threading
import time
import traceback
import xml.etree.ElementTree as ET
import re

ROOT=Path(sys.executable if getattr(sys,'frozen',False) else __file__).resolve().parent
_lock=threading.Lock()
_last=None
_recent={}

def clean_ps_error(value):
    text=value.strip().lstrip('\ufeff')
    if text.startswith('#< CLIXML'):
        try:
            root=ET.fromstring(text[text.index('<Objs'):])
            chunks=[node.text or '' for node in root.iter() if node.tag.rsplit('}',1)[-1]=='S' and node.attrib.get('S')=='Error']
            text='\n'.join(chunks) or text
            text=re.sub(r'_x([0-9A-Fa-f]{4})_',lambda m:chr(int(m[1],16)),text)
        except (ValueError,ET.ParseError):pass
    return text.strip()

def log_error(context,error,details='',trace=None):
    global _last
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    body=(f'TimeBreaker PC Bridge v0.2.2\nTime: {datetime.datetime.now().isoformat()}\n'
          f'Context: {context}\nOS: {platform.platform()}\nPython: {sys.version}\n'
          f'Executable: {sys.executable}\nError: {error}\n\n{details}\n\n{trace or ""}\n')
    candidates=[ROOT/'diagnostics',Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'TimeBreakerPCBridge'/'diagnostics']
    with _lock:
        token=(str(context),str(error))
        cached=_recent.get(token)
        if cached and time.monotonic()-cached[0]<10:return cached[1]
        for folder in candidates:
            try:
                folder.mkdir(parents=True,exist_ok=True)
                path=folder/('error_'+stamp+'.txt');path.write_text(body,encoding='utf-8')
                (folder/'error_latest.txt').write_text(body,encoding='utf-8')
                _last=path;_recent[token]=(time.monotonic(),path);return path
            except OSError:continue
    return None

def last_log():return _last

def current_exception(context,error):return log_error(context,error,trace=traceback.format_exc())

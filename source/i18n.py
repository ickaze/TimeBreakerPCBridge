# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
"""Runtime Japanese/English GUI text catalog and locale selection."""
import ctypes
import json
import locale
import re
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox
import weakref

ROOT=Path(sys.executable if getattr(sys,'frozen',False) else __file__).resolve().parent
RESOURCE=Path(__file__).resolve().parent
CATALOG=json.loads((RESOURCE/'translations.json').read_text(encoding='utf-8'))
_tables={'en':CATALOG,'ja':{v:k for k,v in CATALOG.items()}}
_patterns={lang:re.compile('|'.join(re.escape(k) for k in sorted(table,key=len,reverse=True))) for lang,table in _tables.items()}
_variables=[]
_roots=[]
LANG='ja'

def os_language():
    try:return 'ja' if ctypes.windll.kernel32.GetUserDefaultUILanguage()&0x3ff==0x11 else 'en'
    except (AttributeError,OSError):return 'ja' if (locale.getlocale()[0] or '').lower().startswith('ja') else 'en'

def translate(value,language=None):
    if not isinstance(value,str):return value
    lang=language or LANG
    table=_tables[lang]
    if value in table:return table[value]
    if lang=='en' and not any('\u3040'<=c<='\u9fff' for c in value):return value
    return _patterns[lang].sub(lambda m:table[m.group()],value)

def set_language(language,persist=True):
    global LANG
    if language not in ('ja','en'):raise ValueError('Unknown language')
    LANG=language
    for ref in list(_variables):
        var=ref()
        if var is None:continue
        try:var.set(translate(var.get()))
        except tk.TclError:pass
    def walk(widget):
        try:
            if isinstance(widget,(tk.Tk,tk.Toplevel)):widget.title(translate(widget.title()))
            if 'text' in widget.keys():widget.configure(text=translate(widget.cget('text')))
            if isinstance(widget,tk.Text):
                content=widget.get('1.0','end-1c');widget.delete('1.0','end');widget.insert('1.0',translate(content))
            for child in widget.winfo_children():walk(child)
        except tk.TclError:pass
    for root in _roots:walk(root)
    if persist:
        try:(ROOT/'language.json').write_text(json.dumps({'language':LANG}),encoding='utf-8')
        except OSError as e:
            from diagnostics import current_exception
            current_exception('Language preference save',e)

_installed=False

def install():
    global LANG,_installed
    if _installed:return
    _installed=True;LANG=os_language()
    try:
        saved=json.loads((ROOT/'language.json').read_text(encoding='utf-8')).get('language')
        if saved in ('ja','en'):LANG=saved
    except (OSError,ValueError):pass
    original_options=tk.Misc._options
    def options(self,cnf,kw=None):
        def convert(data):
            if isinstance(data,dict):return {k:translate(v) if k in ('text','title','message') else v for k,v in data.items()}
            return data
        return original_options(self,convert(cnf),convert(kw))
    tk.Misc._options=options
    original_title=tk.Wm.wm_title
    def title(self,string=None):return original_title(self,translate(string) if string is not None else None)
    tk.Wm.wm_title=tk.Wm.title=title
    original_set=tk.Variable.set
    def setvar(self,value):
        if not getattr(self,"_language_registered",False):
            _variables.append(weakref.ref(self));self._language_registered=True
        return original_set(self,translate(value))
    tk.Variable.set=tk.Variable.initialize=setvar
    original_insert=tk.Text.insert
    def insert(self,index,chars,*args):return original_insert(self,index,translate(chars),*args)
    tk.Text.insert=insert
    original_show=messagebox._show
    def show(title=None,message=None,*args,**kwargs):
        icon=args[0] if args else kwargs.get('_icon')
        if icon=='error' and message and 'Log: ' not in str(message):
            from diagnostics import log_error
            path=log_error(str(title),str(message))
            message=str(message)+'\n\nLog: '+str(path)
        return original_show(translate(title),translate(message),*args,**kwargs)
    messagebox._show=show

def attach(root):
    from tkinter import ttk
    _roots.append(root)
    bar=ttk.Frame(root,padding=(12,4));bar.pack(fill='x',before=root.winfo_children()[0] if root.winfo_children() else None)
    ttk.Label(bar,text='Language / 言語').pack(side='left')
    chosen=tk.StringVar(value='日本語' if LANG=='ja' else 'English')
    combo=ttk.Combobox(bar,values=['日本語','English'],state='readonly',textvariable=chosen,width=12)
    combo.pack(side='left',padx=8)
    combo.bind('<<ComboboxSelected>>',lambda e:set_language('ja' if chosen.get()=='日本語' else 'en'))

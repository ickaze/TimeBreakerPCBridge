# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
BITS = {'Trigger':13,'A':3,'B':2,'C':1,'Start':15,'Select':14,
        'Up':4,'Right':5,'Down':6,'Left':7}
DEFAULT_MAP = {'Trigger':'RT','A':'A','B':'B','C':'X','Start':'START','Select':'BACK',
               'Up':'UP','Right':'RIGHT','Down':'DOWN','Left':'LEFT'}
TARGETS = ['NONE','A','B','X','Y','START','BACK','LB','RB','LT','RT','UP','DOWN','LEFT','RIGHT']
MASKS = {'A':0x1000,'B':0x2000,'X':0x4000,'Y':0x8000,'START':0x10,'BACK':0x20,
         'LB':0x100,'RB':0x200,'UP':1,'DOWN':2,'LEFT':4,'RIGHT':8}

def decode(data, bits=BITS):
    if len(data)<6:raise ValueError('Packet needs 6 bytes')
    word=int.from_bytes(data[:2],'little')
    return int.from_bytes(data[2:4],'little'),int.from_bytes(data[4:6],'little'),{k:not bool(word&(1<<v)) for k,v in bits.items()}

class Fire:
    def __init__(self):self.start=None
    def step(self, held, now, enabled=False, period=100, pulse=40, delay=0):
        if not held:self.start=None;return False
        if self.start is None:self.start=now
        if not enabled:return True
        age=(now-self.start)*1000-delay
        return age>=0 and age%period<pulse

def fit_axis(raw, target):
    mr=sum(raw)/len(raw);mt=sum(target)/len(target)
    den=sum((x-mr)**2 for x in raw)
    if den<100:raise ValueError('四隅の座標差が不足しています。')
    a=sum((x-mr)*(y-mt) for x,y in zip(raw,target))/den
    return [a,mt-a*mr]

def transform(x,y,cal):
    return cal['x'][0]*x+cal['x'][1],cal['y'][0]*y+cal['y'][1]

def report(states,mapping):
    buttons=lt=rt=0
    for name,on in states.items():
        if not on:continue
        target=mapping.get(name,'NONE')
        buttons|=MASKS.get(target,0)
        if target=='LT':lt=255
        if target=='RT':rt=255
    return buttons,lt,rt


def output_permissions(enabled,fresh,own,calibrating,record,invalid,pad_offscreen,pad_invalid=None):
    active=bool(enabled and fresh and not own and not calibrating and not record)
    pad_invalid=invalid if pad_invalid is None else pad_invalid
    return active,active and not invalid,active and (pad_offscreen or not pad_invalid)

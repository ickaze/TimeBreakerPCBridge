# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
from pathlib import Path
import sys

def activate():
    if not getattr(sys,'frozen',False):
        vendor=Path(__file__).resolve().parents[1]/'.build_deps'
        if vendor.exists() and str(vendor) not in sys.path:sys.path.insert(0,str(vendor))

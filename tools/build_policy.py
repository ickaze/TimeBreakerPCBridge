# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
from pathlib import Path

def filter_runtime_scripts(scripts):
    """libusb-package supplies an explicit finder; the generic USB hook is incompatible."""
    return [entry for entry in scripts if entry[0]!='pyi_rth_usb' and Path(entry[1]).name!='pyi_rth_usb.py']

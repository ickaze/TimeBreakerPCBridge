# Copyright (C) 2026 by I.C.KaZe
# SPDX-License-Identifier: 0BSD
# The app explicitly uses libusb_package's libusb1 backend. Do not probe other DLLs.
hiddenimports=['usb.backend.libusb1']
binaries=[]

# -*- coding: utf-8 -*-
"""Funções do Windows: administrador e reabertura elevada."""
import os
import subprocess
import sys


def is_admin():
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


def reabrir_como_admin():
    """Pede elevação (UAC) e abre uma nova instância. Devolve True se o Windows aceitou o pedido."""
    if sys.platform != "win32":
        return False
    import ctypes
    if getattr(sys, "frozen", False):
        params = subprocess.list2cmdline(sys.argv[1:])
    else:
        params = subprocess.list2cmdline([os.path.abspath(sys.argv[0])] + sys.argv[1:])
    try:
        return ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1) > 32
    except Exception:  # noqa: BLE001
        return False

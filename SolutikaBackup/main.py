# -*- coding: utf-8 -*-
"""Solutika Backup: ponto de entrada."""
import sys


def _windows_preparar():
    if sys.platform != "win32":
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # tela nítida em monitores com escala
    except Exception:  # noqa: BLE001
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Solutika.Backup")
    except Exception:  # noqa: BLE001
        pass


def main():
    _windows_preparar()
    from solutika.app import App
    App().mainloop()


if __name__ == "__main__":
    main()

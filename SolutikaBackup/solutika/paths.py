# -*- coding: utf-8 -*-
"""Caminhos, recursos embutidos e configurações do técnico."""
import json
import os
import sys


def resource_path(rel):
    """Caminho de um recurso (funciona no .py e dentro do executável do PyInstaller)."""
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def data_dir():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, "SolutikaBackup")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


class Settings:
    """Preferências simples gravadas em JSON (nome do técnico, últimas pastas...)."""

    def __init__(self):
        self.path = os.path.join(data_dir(), "settings.json")
        self.data = {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            self.data = {}

    def get(self, key, default=""):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

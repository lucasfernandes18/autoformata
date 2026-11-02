# -*- coding: utf-8 -*-
"""Registro das operações feitas nesta execução (alimenta a ficha do técnico)."""
from datetime import datetime


class Sessao:
    def __init__(self):
        self.inicio = datetime.now()
        self.eventos = []
        self._ouvintes = []

    def ao_mudar(self, func):
        self._ouvintes.append(func)

    def add(self, ev):
        chave = (ev.get("tipo"), ev.get("inicio"), ev.get("usuario"))
        if any((e.get("tipo"), e.get("inicio"), e.get("usuario")) == chave for e in self.eventos):
            return False
        self.eventos.append(ev)
        for f in self._ouvintes:
            f(ev)
        return True

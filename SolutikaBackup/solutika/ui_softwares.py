# -*- coding: utf-8 -*-
"""Janela com a lista de softwares e impressoras do backup, para o técnico reinstalar."""
import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import engine
from .theme import COR, Botao, combo, entrada, fonte, px, rotulo

MARCADO, DESMARCADO = "\u2611", "\u2610"
FILTROS = ["Programas", "Drivers e hardware", "Componentes do sistema", "Todos"]


def tipo_porta(porta):
    """Traduz o nome da porta da impressora para algo que o técnico entenda."""
    p = (porta or "").upper()
    if p.startswith("USB"):
        return "USB"
    if p.startswith("WSD"):
        return "Rede (WSD)"
    if p.startswith("IP_") or p.replace(".", "").replace(":", "").isdigit():
        return "Rede (IP)"
    if p.startswith("\\\\"):
        return "Compartilhada"
    if p.startswith(("LPT", "COM")):
        return "Porta física (LPT/COM)"
    if p in ("PORTPROMPT:", "NUL:", "FILE:") or p.startswith("PORTPROMPT") or ".PDF" in p or "XPSPORT" in p:
        return "Virtual (PDF/arquivo)"
    return "Outra"


class DialogoSoftwares(tk.Toplevel):
    def __init__(self, app, pasta_backup):
        super().__init__(app)
        self.app = app
        self.title("Softwares e impressoras do computador antigo")
        self.configure(bg=COR["surface"])
        self.transient(app)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(px(1000), sw - 80), min(px(720), sh - 100)
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}")
        self.minsize(min(px(860), w), min(px(560), h))
        softs, imps = engine.ler_inventario(pasta_backup)
        self.dados = [{"nome": n, "versao": v, "editor": e, "tipo": engine.classificar_software(n)}
                      for n, v, e in softs]
        self.imps = imps
        self.marcados = set()
        self.visiveis = []
        self.tv = None
        self.tv_imp = None

        # --- cabeçalho ---
        topo = tk.Frame(self, bg=COR["surface"])
        topo.pack(fill="x", padx=px(24), pady=(px(18), px(8)))
        rotulo(topo, "Programas do computador antigo", 18, "bold", "navy").pack(anchor="w")
        rotulo(topo, "Esta é a lista do que estava instalado quando o backup foi feito. Os programas NÃO voltam "
                     "sozinhos: use a lista como guia e marque (clique na caixinha) o que você for reinstalando.",
               10, "normal", "muted", wraplength=px(900)).pack(anchor="w", pady=(px(2), 0))
        cont = {t: sum(1 for d in self.dados if d["tipo"] == t) for t in FILTROS[:3]}
        rotulo(topo, f"{cont['Programas']} programas  ·  {cont['Drivers e hardware']} drivers e hardware  ·  "
                     f"{cont['Componentes do sistema']} componentes do sistema (Visual C++, .NET, atualizações)  ·  "
                     f"{len(self.imps)} impressoras", 9, "bold", "accent").pack(anchor="w", pady=(px(6), 0))

        # --- abas ---
        abas = tk.Frame(self, bg=COR["surface"])
        abas.pack(fill="x", padx=px(24), pady=(px(6), px(8)))
        self.bt_prog = Botao(abas, "Softwares", lambda: self._aba("prog"), "primario")
        self.bt_prog.pack(side="left")
        self.bt_imp = Botao(abas, f"Impressoras ({len(self.imps)})", lambda: self._aba("imp"), "secundario")
        self.bt_imp.pack(side="left", padx=px(8))

        self.area = tk.Frame(self, bg=COR["surface"])
        self.area.pack(fill="both", expand=True, padx=px(24))
        self._montar_programas()
        self._montar_impressoras()
        self._aba("prog")
        self.bind("<Escape>", lambda e: self.destroy())

    # ------------------------------------------------------------------
    def _tabela(self, pai, colunas):
        moldura = tk.Frame(pai, bg=COR["bg"], highlightthickness=1, highlightbackground=COR["border"])
        tv = ttk.Treeview(moldura, columns=[c[0] for c in colunas], show="headings", style="S.Treeview",
                          selectmode="browse")
        for cid, titulo, larg, estica in colunas:
            tv.heading(cid, text=titulo, anchor="w")
            tv.column(cid, width=px(larg), anchor="w", stretch=estica)
        sb = ttk.Scrollbar(moldura, orient="vertical", command=tv.yview, style="S.Vertical.TScrollbar")
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)
        return moldura, tv

    def _tags(self):
        for tv in (self.tv, self.tv_imp):
            if tv is not None:
                tv.tag_configure("par", background=COR["bg"])
                tv.tag_configure("impar", background=COR["surface"])

    def _tema(self):
        self._tags()
        self.configure(bg=COR["surface"])

    def _montar_programas(self):
        self.f_prog = tk.Frame(self.area, bg=COR["surface"])
        barra = tk.Frame(self.f_prog, bg=COR["surface"])
        barra.pack(fill="x", pady=(0, px(8)))
        rotulo(barra, "Buscar", 9, "normal", "muted", bg=COR["surface"]).pack(side="left")
        self.var_busca = tk.StringVar()
        entrada(barra, self.var_busca, width=30).pack(side="left", padx=(px(8), px(18)))
        rotulo(barra, "Mostrar", 9, "normal", "muted", bg=COR["surface"]).pack(side="left")
        self.var_filtro = tk.StringVar(value=FILTROS[0])
        cb = combo(barra, FILTROS, self.var_filtro, width=24)
        cb.pack(side="left", padx=(px(8), 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self._preencher())
        self.var_busca.trace_add("write", lambda *a: self._preencher())
        self.lbl_contagem = rotulo(barra, "", 9, "bold", "navy", bg=COR["surface"])
        self.lbl_contagem.pack(side="right")

        moldura, self.tv = self._tabela(self.f_prog, [("marca", "Reinstalado", 90, False), ("nome", "Programa", 380, True),
                                                      ("versao", "Versão", 120, False), ("editor", "Fabricante", 200, False),
                                                      ("tipo", "Tipo", 150, False)])
        moldura.pack(fill="both", expand=True)
        self.tv.bind("<Button-1>", self._clique)
        self.tv.bind("<Double-1>", self._duplo)
        self.tv.bind("<space>", self._espaco)
        self._tags()

        rotulo(self.f_prog, "Dica: Office, antivírus e programas pagos precisam de licença ou conta para serem "
                            "reativados. Confira o e-mail do cliente ou o gerenciador de senhas antes de formatar.",
               9, "normal", "muted", bg=COR["surface"], wraplength=px(900)).pack(fill="x", pady=(px(8), 0))
        acoes = tk.Frame(self.f_prog, bg=COR["surface"])
        acoes.pack(fill="x", pady=(px(10), px(16)))
        Botao(acoes, "Marcar todos os exibidos", self._marcar_exibidos, "secundario").pack(side="left")
        Botao(acoes, "Limpar marcação", self._limpar, "secundario").pack(side="left", padx=px(8))
        Botao(acoes, "Registrar na ficha", self._registrar, "primario").pack(side="right")
        Botao(acoes, "Salvar em CSV", self._salvar_csv, "secundario").pack(side="right", padx=px(8))
        Botao(acoes, "Copiar marcados", self._copiar, "secundario").pack(side="right")

    def _montar_impressoras(self):
        self.f_imp = tk.Frame(self.area, bg=COR["surface"])
        rotulo(self.f_imp, "Reinstale estas impressoras no Windows novo. A coluna Conexão mostra se ela era USB, de "
                           "rede (IP ou WSD), compartilhada ou virtual (PDF). Para as de rede, anote o IP antes de "
                           "formatar; o driver aparece na coluna Driver.", 10, "normal", "muted", bg=COR["surface"],
               wraplength=px(900)).pack(fill="x", pady=(0, px(8)))
        moldura, self.tv_imp = self._tabela(self.f_imp, [("nome", "Impressora", 340, True), ("driver", "Driver", 300, False),
                                                         ("porta", "Porta", 150, False), ("conexao", "Conexão", 170, False)])
        moldura.pack(fill="both", expand=True, pady=(0, px(16)))
        for i, (nome, driver, porta) in enumerate(self.imps):
            self.tv_imp.insert("", "end", values=(nome, driver, porta, tipo_porta(porta)),
                               tags=("par" if i % 2 == 0 else "impar",))
        self._tags()

    def _aba(self, qual):
        self.f_prog.pack_forget()
        self.f_imp.pack_forget()
        if qual == "prog":
            self.f_prog.pack(fill="both", expand=True)
            self._preencher()
        else:
            self.f_imp.pack(fill="both", expand=True)
        for bt, nome in ((self.bt_prog, "prog"), (self.bt_imp, "imp")):
            bt.estilo = "primario" if nome == qual else "secundario"
            bt._pintar(False)

    # ------------------------------------------------------------------
    def _preencher(self):
        filtro, busca = self.var_filtro.get(), self.var_busca.get().strip().lower()
        self.tv.delete(*self.tv.get_children())
        self.visiveis = []
        for i, d in enumerate(self.dados):
            if filtro != "Todos" and d["tipo"] != filtro:
                continue
            if busca and busca not in d["nome"].lower() and busca not in d["editor"].lower():
                continue
            self.visiveis.append(i)
            self.tv.insert("", "end", iid=str(i), tags=("par" if len(self.visiveis) % 2 else "impar",),
                           values=(MARCADO if i in self.marcados else DESMARCADO, d["nome"], d["versao"], d["editor"],
                                   d["tipo"]))
        self._contagem()

    def _contagem(self):
        self.lbl_contagem.configure(text=f"{len(self.visiveis)} exibidos  ·  {len(self.marcados)} marcados")

    def _alternar(self, iid):
        if not iid:
            return
        i = int(iid)
        if i in self.marcados:
            self.marcados.discard(i)
        else:
            self.marcados.add(i)
        self.tv.set(iid, "marca", MARCADO if i in self.marcados else DESMARCADO)
        self._contagem()

    def _clique(self, e):
        if self.tv.identify_region(e.x, e.y) == "cell" and self.tv.identify_column(e.x) == "#1":
            self._alternar(self.tv.identify_row(e.y))

    def _duplo(self, e):
        if self.tv.identify_region(e.x, e.y) == "cell" and self.tv.identify_column(e.x) != "#1":
            self._alternar(self.tv.identify_row(e.y))

    def _espaco(self, _e):
        sel = self.tv.selection()
        if sel:
            self._alternar(sel[0])

    def _marcar_exibidos(self):
        self.marcados.update(self.visiveis)
        self._preencher()

    def _limpar(self):
        self.marcados.clear()
        self._preencher()

    def _lista_marcada(self):
        return [self.dados[i] for i in sorted(self.marcados, key=lambda k: self.dados[k]["nome"].lower())]

    def _copiar(self):
        itens = self._lista_marcada()
        if not itens:
            messagebox.showinfo("Copiar", "Marque ao menos um programa.", parent=self)
            return
        texto = "\n".join(f"- {d['nome']}" + (f" ({d['versao']})" if d["versao"] else "") for d in itens)
        self.clipboard_clear()
        self.clipboard_append(texto)
        messagebox.showinfo("Copiar", f"{len(itens)} programa(s) copiado(s) para a área de transferência.", parent=self)

    def _salvar_csv(self):
        itens = self._lista_marcada() or [self.dados[i] for i in self.visiveis]
        caminho = filedialog.asksaveasfilename(parent=self, defaultextension=".csv", initialfile="programas.csv",
                                               filetypes=[("CSV (Excel)", "*.csv")])
        if not caminho:
            return
        with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["Programa", "Versão", "Fabricante", "Tipo"])
            w.writerows((d["nome"], d["versao"], d["editor"], d["tipo"]) for d in itens)
        messagebox.showinfo("Salvar", f"{len(itens)} linha(s) salva(s) em:\n{caminho}", parent=self)

    def _registrar(self):
        itens = self._lista_marcada()
        if not itens:
            messagebox.showinfo("Ficha", "Marque os programas que foram reinstalados.", parent=self)
            return
        self.app.paginas["ficha"].registrar_programas([d["nome"] for d in itens])
        messagebox.showinfo("Ficha", f"{len(itens)} programa(s) registrado(s) na ficha do técnico.", parent=self)

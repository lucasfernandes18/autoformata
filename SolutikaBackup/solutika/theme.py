# -*- coding: utf-8 -*-
"""Tema claro e escuro (nas cores da Solutika) + componentes visuais reutilizáveis."""
import math
import queue
import sys
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

PALETAS = {
    "claro": {
        "bg": "#FFFFFF", "surface": "#F5F7FB", "border": "#E1E7F0", "text": "#1B2340", "muted": "#6A7491",
        "navy": "#2B2F80", "accent": "#1E7FD8", "accent_hover": "#1769B8", "accent_soft": "#E8F2FC",
        "ok": "#1E9E6A", "warn": "#C98A00", "err": "#D64545", "log_bg": "#F8FAFD", "disabled": "#B4BCCD",
        "ok_soft": "#E6F6EF", "warn_soft": "#FFF4DB", "err_soft": "#FCE9E9", "on_accent": "#FEFEFE",
        "track": "#E9EDF5",
    },
    "escuro": {
        "bg": "#171C2E", "surface": "#0F1320", "border": "#2A3150", "text": "#E6EAF5", "muted": "#98A2BF",
        "navy": "#A9B8F5", "accent": "#4DA3FF", "accent_hover": "#7DBBFF", "accent_soft": "#1F2B49",
        "ok": "#3DD598", "warn": "#F0B445", "err": "#FF6B6B", "log_bg": "#0C101D", "disabled": "#4A5272",
        "ok_soft": "#123329", "warn_soft": "#3A2E12", "err_soft": "#3B1C20", "on_accent": "#08101F",
        "track": "#232A45",
    },
}
COR = dict(PALETAS["claro"])      # dicionário único, atualizado no lugar quando o tema muda
TEMA = {"nome": "claro"}
FAMILIA = "Segoe UI"
ESCALA = 1.0


def definir_tema(nome):
    if nome not in PALETAS:
        nome = "claro"
    COR.update(PALETAS[nome])
    TEMA["nome"] = nome


def init(root):
    """Descobre a escala (DPI) e configura os estilos ttk. Chamar uma vez, logo após criar o Tk."""
    global ESCALA, FAMILIA
    try:
        ESCALA = max(1.0, root.winfo_fpixels("1i") / 96.0)
    except tk.TclError:
        ESCALA = 1.0
    try:
        if FAMILIA not in tkfont.families(root):
            FAMILIA = "Helvetica"
    except tk.TclError:
        pass
    _estilos(root)


def px(n):
    return int(round(n * ESCALA))


def fonte(tam=10, peso="normal"):
    return (FAMILIA, tam, peso)


def _estilos(root):
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    c = COR
    for nome in ("S.TEntry", "S.TSpinbox"):
        st.configure(nome, fieldbackground=c["bg"], foreground=c["text"], bordercolor=c["border"],
                     lightcolor=c["border"], darkcolor=c["border"], padding=px(6), insertcolor=c["text"],
                     arrowcolor=c["muted"], background=c["bg"])
        st.map(nome, bordercolor=[("focus", c["accent"])], lightcolor=[("focus", c["accent"])],
               darkcolor=[("focus", c["accent"])], fieldbackground=[("disabled", c["surface"])],
               foreground=[("disabled", c["disabled"])])
    st.configure("S.TCombobox", fieldbackground=c["bg"], background=c["bg"], foreground=c["text"],
                 bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"], arrowcolor=c["muted"],
                 padding=px(5), selectbackground=c["bg"], selectforeground=c["text"])
    st.map("S.TCombobox", fieldbackground=[("readonly", c["bg"]), ("disabled", c["surface"])],
           foreground=[("disabled", c["disabled"])], bordercolor=[("focus", c["accent"])],
           lightcolor=[("focus", c["accent"])], darkcolor=[("focus", c["accent"])],
           selectbackground=[("readonly", c["bg"])], selectforeground=[("readonly", c["text"])])
    root.option_add("*TCombobox*Listbox.background", c["bg"])
    root.option_add("*TCombobox*Listbox.foreground", c["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", c["accent_soft"])
    root.option_add("*TCombobox*Listbox.selectForeground", c["navy"])
    root.option_add("*TCombobox*Listbox.font", fonte(10))
    for nome, cor in (("S", c["accent"]), ("Ok", c["ok"]), ("Warn", c["warn"]), ("Err", c["err"])):
        st.configure(f"{nome}.Horizontal.TProgressbar", troughcolor=c["surface"], background=cor,
                     bordercolor=c["surface"], lightcolor=cor, darkcolor=cor, thickness=px(6))
    st.configure("S.Vertical.TScrollbar", background=c["border"], troughcolor=c["bg"], bordercolor=c["bg"],
                 arrowcolor=c["bg"], lightcolor=c["border"], darkcolor=c["border"], gripcount=0)
    st.map("S.Vertical.TScrollbar", background=[("active", c["disabled"])])
    st.configure("S.Treeview", background=c["bg"], fieldbackground=c["bg"], foreground=c["text"],
                 rowheight=px(26), borderwidth=0, font=fonte(10))
    st.map("S.Treeview", background=[("selected", c["accent_soft"])], foreground=[("selected", c["navy"])])
    st.configure("S.Treeview.Heading", background=c["surface"], foreground=c["navy"], relief="flat",
                 font=fonte(9, "bold"), padding=px(6), borderwidth=0)
    st.map("S.Treeview.Heading", background=[("active", c["border"])])


def entrada(parent, var=None, **kw):
    return ttk.Entry(parent, style="S.TEntry", textvariable=var, font=fonte(10), **kw)


def combo(parent, valores, var=None, somente_leitura=True, **kw):
    return ttk.Combobox(parent, style="S.TCombobox", values=valores, textvariable=var, font=fonte(10),
                        state="readonly" if somente_leitura else "normal", **kw)


def rotulo(parent, texto, tam=10, peso="normal", cor="text", bg=None, **kw):
    return tk.Label(parent, text=texto, font=fonte(tam, peso), fg=COR[cor], bg=bg or parent.cget("bg"), anchor="w",
                    justify="left", **kw)


# ---------------------------------------------------------------------------
# Troca de tema em tempo de execução
# ---------------------------------------------------------------------------
_OPCOES_COR = ("background", "foreground", "highlightbackground", "highlightcolor", "insertbackground",
               "activebackground", "activeforeground", "selectbackground", "selectforeground",
               "disabledforeground", "troughcolor")


def _recolorir(w, mapa):
    try:
        chaves = w.keys()
    except Exception:  # noqa: BLE001
        chaves = ()
    mud = {}
    for o in _OPCOES_COR:
        if o in chaves:
            try:
                v = str(w.cget(o)).lower()
            except Exception:  # noqa: BLE001
                continue
            if v in mapa:
                mud[o] = mapa[v]
    if mud:
        try:
            w.configure(**mud)
        except Exception:  # noqa: BLE001
            pass
    for filho in w.winfo_children():
        _recolorir(filho, mapa)


def _atualizar_custom(w):
    f = getattr(w, "_tema", None)
    if callable(f):
        try:
            f()
        except Exception:  # noqa: BLE001
            pass
    for filho in w.winfo_children():
        _atualizar_custom(filho)


def _popdown_combos(w, root):
    if w.winfo_class() == "TCombobox":
        try:
            pop = root.tk.call("ttk::combobox::PopdownWindow", str(w))
            root.tk.call(f"{pop}.f.l", "configure", "-background", COR["bg"], "-foreground", COR["text"],
                         "-selectbackground", COR["accent_soft"], "-selectforeground", COR["navy"])
        except Exception:  # noqa: BLE001
            pass
    for filho in w.winfo_children():
        _popdown_combos(filho, root)


def trocar_tema(root, nome):
    """Troca claro/escuro sem recriar a interface: remapeia as cores de todos os widgets."""
    antigo = dict(COR)
    definir_tema(nome)
    _estilos(root)
    mapa = {antigo[k].lower(): COR[k] for k in COR if antigo[k].lower() != COR[k].lower()}
    try:
        root.configure(bg=COR["surface"])
    except tk.TclError:
        pass
    _recolorir(root, mapa)
    _atualizar_custom(root)
    _popdown_combos(root, root)


def barra_titulo_escura(janela, escuro):
    """Barra de título escura no Windows 10/11 (se disponível)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        janela.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(janela.winfo_id())
        valor = ctypes.c_int(1 if escuro else 0)
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(valor),
                                                          ctypes.sizeof(valor)) == 0:
                break
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
class Botao(tk.Label):
    """Botão plano: estilos 'primario', 'secundario' e 'fantasma'."""

    def __init__(self, parent, texto, comando=None, estilo="primario", **kw):
        self.estilo = estilo
        self.comando = comando
        self._ativo = True
        self._pai_bg = parent.cget("bg")
        super().__init__(parent, text=texto, cursor="hand2", font=fonte(10, "bold"), padx=px(16), pady=px(8),
                         borderwidth=0, **kw)
        self._pintar(False)
        self.bind("<Enter>", lambda e: self._pintar(True))
        self.bind("<Leave>", lambda e: self._pintar(False))
        self.bind("<ButtonRelease-1>", self._soltou)

    def _pintar(self, hover):
        c = COR
        if not self._ativo:
            self.configure(bg=c["surface"], fg=c["disabled"], highlightthickness=1, highlightbackground=c["border"],
                           cursor="arrow")
            return
        self.configure(cursor="hand2")
        if self.estilo == "primario":
            self.configure(bg=c["accent_hover"] if hover else c["accent"], fg=c["on_accent"], highlightthickness=0)
        elif self.estilo == "secundario":
            self.configure(bg=c["accent_soft"] if hover else c["bg"], fg=c["navy"], highlightthickness=1,
                           highlightbackground=c["accent"] if hover else c["border"])
        else:
            self.configure(bg=c["accent_soft"] if hover else self._pai_bg, fg=c["navy"], highlightthickness=0)

    def _tema(self):
        try:
            self._pai_bg = self.master.cget("bg")
        except Exception:  # noqa: BLE001
            pass
        self._pintar(False)

    def _soltou(self, e):
        if not self._ativo:
            return
        if 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height() and self.comando:
            self.comando()

    def ativar(self, ligado):
        self._ativo = bool(ligado)
        self._pintar(False)

    def texto(self, t):
        self.configure(text=t)


class Cartao(tk.Frame):
    """Cartão com borda fina e título opcional."""

    def __init__(self, parent, titulo=None, **kw):
        super().__init__(parent, bg=COR["bg"], highlightthickness=1, highlightbackground=COR["border"], **kw)
        self.corpo = tk.Frame(self, bg=COR["bg"])
        self.corpo.pack(fill="both", expand=True, padx=px(16), pady=px(14))
        if titulo:
            tk.Label(self.corpo, text=titulo, font=fonte(10, "bold"), fg=COR["navy"], bg=COR["bg"],
                     anchor="w").pack(fill="x", pady=(0, px(8)))


class Caixa(tk.Frame):
    """Caixa de marcação própria (visual limpo), com descrição opcional."""

    def __init__(self, parent, texto="", var=None, descricao="", comando=None, largura=380, bg=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, bg=bg)
        self.var = var if var is not None else tk.BooleanVar(value=False)
        self.comando = comando
        self._ativo = True
        self.cv = tk.Canvas(self, width=px(18), height=px(18), bg=bg, highlightthickness=0, cursor="hand2")
        self.cv.grid(row=0, column=0, sticky="n", padx=(0, px(10)), pady=(px(1), 0))
        self.lbl = tk.Label(self, text=texto, font=fonte(10), fg=COR["text"], bg=bg, anchor="w", justify="left",
                            wraplength=px(largura), cursor="hand2")
        self.lbl.grid(row=0, column=1, sticky="w")
        self.desc = None
        if descricao:
            self.desc = tk.Label(self, text=descricao, font=fonte(9), fg=COR["muted"], bg=bg, anchor="w",
                                 justify="left", wraplength=px(largura), cursor="hand2")
            self.desc.grid(row=1, column=1, sticky="w")
        for w in (self.cv, self.lbl, self.desc):
            if w is not None:
                w.bind("<Button-1>", self._clique)
        self.var.trace_add("write", lambda *a: self._desenhar())
        self._desenhar()

    def _clique(self, _e=None):
        if not self._ativo:
            return
        self.var.set(not self.var.get())
        if self.comando:
            self.comando()

    def _desenhar(self):
        cv, s = self.cv, px(18)
        cv.delete("all")
        c = COR
        if self.var.get():
            cor = c["accent"] if self._ativo else c["disabled"]
            cv.create_rectangle(1, 1, s - 1, s - 1, fill=cor, outline=cor)
            cv.create_line(s * 0.24, s * 0.52, s * 0.44, s * 0.72, s * 0.78, s * 0.30, fill=c["on_accent"],
                           width=max(2, px(2)))
        else:
            cv.create_rectangle(1, 1, s - 1, s - 1, fill=c["bg"] if self._ativo else c["surface"],
                                outline=c["muted"] if self._ativo else c["disabled"], width=1)

    def _tema(self):
        self.ativar(self._ativo)

    def ativar(self, ligado):
        self._ativo = bool(ligado)
        cor = COR["text"] if ligado else COR["disabled"]
        self.lbl.configure(fg=cor, cursor="hand2" if ligado else "arrow")
        self.cv.configure(cursor="hand2" if ligado else "arrow")
        self._desenhar()

    def get(self):
        return bool(self.var.get())

    def set(self, v):
        self.var.set(bool(v))

    def texto(self, t):
        self.lbl.configure(text=t)


class Radio(tk.Frame):
    """Botão de opção (uma escolha entre várias) com título e descrição."""

    def __init__(self, parent, texto, var, valor, descricao="", comando=None, largura=380):
        bg = parent.cget("bg")
        super().__init__(parent, bg=bg)
        self.var, self.valor, self.comando, self._ativo = var, valor, comando, True
        self.cv = tk.Canvas(self, width=px(18), height=px(18), bg=bg, highlightthickness=0, cursor="hand2")
        self.cv.grid(row=0, column=0, sticky="n", padx=(0, px(10)), pady=(px(1), 0))
        self.lbl = tk.Label(self, text=texto, font=fonte(10, "bold"), fg=COR["text"], bg=bg, anchor="w",
                            justify="left", wraplength=px(largura), cursor="hand2")
        self.lbl.grid(row=0, column=1, sticky="w")
        self.desc = None
        if descricao:
            self.desc = tk.Label(self, text=descricao, font=fonte(9), fg=COR["muted"], bg=bg, anchor="w",
                                 justify="left", wraplength=px(largura), cursor="hand2")
            self.desc.grid(row=1, column=1, sticky="w")
        for w in (self.cv, self.lbl, self.desc):
            if w is not None:
                w.bind("<Button-1>", self._clique)
        var.trace_add("write", lambda *a: self._desenhar())
        self._desenhar()

    def _clique(self, _e=None):
        if not self._ativo:
            return
        self.var.set(self.valor)
        if self.comando:
            self.comando()

    def _desenhar(self):
        cv, s, c = self.cv, px(18), COR
        cv.delete("all")
        sel = self.var.get() == self.valor
        borda = (c["accent"] if sel else c["muted"]) if self._ativo else c["disabled"]
        cv.create_oval(1, 1, s - 1, s - 1, fill=c["bg"] if self._ativo else c["surface"], outline=borda,
                       width=2 if sel else 1)
        if sel:
            m = s * 0.3
            cv.create_oval(m, m, s - m, s - m, fill=c["accent"] if self._ativo else c["disabled"], outline="")

    def _tema(self):
        self.ativar(self._ativo)

    def ativar(self, ligado):
        self._ativo = bool(ligado)
        self.lbl.configure(fg=COR["text"] if ligado else COR["disabled"], cursor="hand2" if ligado else "arrow")
        self.cv.configure(cursor="hand2" if ligado else "arrow")
        self._desenhar()


class ToggleTema(tk.Canvas):
    """Chave pequena com sol e lua para alternar entre o tema claro e o escuro."""

    def __init__(self, parent, comando):
        self.w, self.h = px(68), px(30)
        super().__init__(parent, width=self.w, height=self.h, highlightthickness=0, bd=0, cursor="hand2",
                         bg=parent.cget("bg"))
        self.comando = comando
        self.bind("<Button-1>", lambda e: self.comando())
        self._desenhar()

    def _tema(self):
        try:
            self.configure(bg=self.master.cget("bg"))
        except Exception:  # noqa: BLE001
            pass
        self._desenhar()

    def _pilula(self, x0, y0, x1, y1, cor):
        r = (y1 - y0) / 2
        self.create_oval(x0, y0, x0 + 2 * r, y1, fill=cor, outline=cor)
        self.create_oval(x1 - 2 * r, y0, x1, y1, fill=cor, outline=cor)
        self.create_rectangle(x0 + r, y0, x1 - r, y1, fill=cor, outline=cor)

    def _sol(self, cx, cy, ativo):
        cor = "#F5A623" if ativo else COR["muted"]
        r = px(4.6)
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=cor, outline=cor)
        for i in range(8):
            a = math.radians(i * 45)
            self.create_line(cx + math.cos(a) * px(7), cy + math.sin(a) * px(7), cx + math.cos(a) * px(9.6),
                             cy + math.sin(a) * px(9.6), fill=cor, width=max(1, px(1.6)), capstyle="round")

    def _lua(self, cx, cy, ativo, fundo):
        cor = "#A9B8F5" if ativo else COR["muted"]
        r = px(6.4)
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=cor, outline=cor)
        d, r2 = px(3.4), px(5.2)
        self.create_oval(cx - r2 + d, cy - r2 - px(1.6), cx + r2 + d, cy + r2 - px(1.6), fill=fundo, outline=fundo)

    def _desenhar(self):
        self.delete("all")
        c, w, h = COR, self.w, self.h
        escuro = TEMA["nome"] == "escuro"
        self._pilula(0, 0, w, h, c["border"])
        self._pilula(1, 1, w - 1, h - 1, c["track"])
        d = h - px(6)
        kx = (w - d - px(3)) if escuro else px(3)
        knob = c["accent_soft"] if escuro else c["bg"]
        self.create_oval(kx, px(3), kx + d, px(3) + d, fill=knob, outline=c["border"])
        self._sol(h / 2 + px(1), h / 2, not escuro)
        self._lua(w - h / 2 - px(1), h / 2, escuro, knob if escuro else c["track"])


class Rolagem(tk.Frame):
    """Área com barra de rolagem vertical (a roda do mouse funciona sobre qualquer filho)."""

    def __init__(self, parent, bg=None):
        bg = bg or COR["surface"]
        super().__init__(parent, bg=bg)
        self.cv = tk.Canvas(self, bg=bg, highlightthickness=0, borderwidth=0)
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview, style="S.Vertical.TScrollbar")
        self.cv.configure(yscrollcommand=self.sb.set)
        self.interno = tk.Frame(self.cv, bg=bg)
        self._jan = self.cv.create_window((0, 0), window=self.interno, anchor="nw")
        self.interno.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(self._jan, width=e.width))
        self.sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.bind_all("<MouseWheel>", self._roda, add="+")

    def _roda(self, e):
        try:
            w = self.winfo_containing(e.x_root, e.y_root)
        except (KeyError, tk.TclError):
            return
        if w is None or w.winfo_class() in ("Text", "TCombobox", "Listbox", "Treeview"):
            return
        p = w
        while p is not None:
            if p is self:
                break
            p = p.master
        else:
            return
        if self.interno.winfo_height() > self.cv.winfo_height():
            self.cv.yview_scroll(int(-1 * (e.delta / 120)), "units")


ICONES = {"pend": ("\u25CB", "disabled"), "run": ("\u25BA", "accent"), "ok": ("\u2714", "ok"),
          "err": ("\u2716", "err"), "skip": ("\u2013", "disabled")}


class PainelAndamento(Cartao):
    """Etapas com ícone de estado, barra de progresso, status com tempo decorrido e registro colorido."""

    def __init__(self, parent, fases, titulo="Andamento"):
        super().__init__(parent, titulo)
        c = COR
        self.fases = {}
        self._nomes = dict(fases)
        self._estado = {}
        for fid, nome in fases:
            lin = tk.Frame(self.corpo, bg=c["bg"])
            lin.pack(fill="x", pady=px(1))
            ic = tk.Label(lin, text="", font=("Segoe UI Symbol", 10), bg=c["bg"], width=2, anchor="w")
            ic.pack(side="left")
            tx = tk.Label(lin, text=nome, font=fonte(10), bg=c["bg"], anchor="w")
            tx.pack(side="left", fill="x")
            self.fases[fid] = (ic, tx)
        self.barra = ttk.Progressbar(self.corpo, mode="determinate", style="S.Horizontal.TProgressbar", maximum=100)
        self.barra.pack(fill="x", pady=(px(12), px(4)))
        self.status = tk.Label(self.corpo, text="", font=fonte(9, "bold"), fg=c["muted"], bg=c["bg"], anchor="w",
                               justify="left", wraplength=px(420))
        self.status.pack(fill="x")
        caixa = tk.Frame(self.corpo, bg=c["log_bg"], highlightthickness=1, highlightbackground=c["border"])
        caixa.pack(fill="both", expand=True, pady=(px(8), 0))
        sb = ttk.Scrollbar(caixa, orient="vertical", style="S.Vertical.TScrollbar")
        self.txt = tk.Text(caixa, height=8, wrap="word", font=("Consolas", 9), bg=c["log_bg"], fg=c["text"],
                           relief="flat", borderwidth=0, padx=px(8), pady=px(6), state="disabled",
                           yscrollcommand=sb.set, cursor="arrow", selectbackground=c["accent_soft"],
                           selectforeground=c["navy"], insertbackground=c["text"])
        sb.configure(command=self.txt.yview)
        sb.pack(side="right", fill="y")
        self.txt.pack(side="left", fill="both", expand=True)
        Botao(self.corpo, "Copiar registro", self.copiar_registro, "fantasma").pack(anchor="e", pady=(px(4), 0))
        self._tags()
        self._t0 = None
        self._status_txt = ""
        self._rodando = False
        self.reset()

    def _tags(self):
        c = COR
        for nivel, cor in (("info", c["text"]), ("ok", c["ok"]), ("warn", c["warn"]), ("error", c["err"]),
                           ("muted", c["muted"]), ("accent", c["accent"])):
            self.txt.tag_configure(nivel, foreground=cor)

    def _tema(self):
        self._tags()
        for fid, st in list(self._estado.items()):
            self.fase(fid, st)

    # --- etapas ---
    def reset(self, pulados=()):
        for fid in self.fases:
            self.fase(fid, "skip" if fid in pulados else "pend")
        self._parar_barra("idle")
        self.set_status("")

    def fase(self, fid, estado):
        if fid not in self.fases:
            return
        ic, tx = self.fases[fid]
        simbolo, chave = ICONES.get(estado, ICONES["pend"])
        ic.configure(text=simbolo, fg=COR[chave])
        if estado == "run":
            tx.configure(fg=COR["navy"], font=fonte(10, "bold"))
        elif estado in ("pend", "skip"):
            tx.configure(fg=COR["muted"] if estado == "pend" else COR["disabled"], font=fonte(10))
        elif estado == "err":
            tx.configure(fg=COR["err"], font=fonte(10, "bold"))
        else:
            tx.configure(fg=COR["text"], font=fonte(10))
        self._estado[fid] = estado

    def fechar_pendentes_como_erro(self):
        for fid, st in list(self._estado.items()):
            if st == "run":
                self.fase(fid, "err")

    # --- status e barra ---
    def set_status(self, texto, cor="muted"):
        self._status_txt = texto
        self.status.configure(fg=COR[cor])
        self._atualizar_status()

    def _atualizar_status(self):
        t = self._status_txt
        if self._rodando and self._t0:
            seg = int(time.monotonic() - self._t0)
            t = f"{t}   ·   {seg // 3600:02d}:{(seg % 3600) // 60:02d}:{seg % 60:02d}"
        self.status.configure(text=t)

    def _tique(self):
        if self._rodando:
            self._atualizar_status()
            self.after(1000, self._tique)

    def executando(self, ligado):
        self._rodando = ligado
        if ligado:
            self._t0 = time.monotonic()
            self.barra.configure(style="S.Horizontal.TProgressbar", mode="indeterminate")
            self.barra.start(14)
            self.status.configure(fg=COR["accent"])
            self._tique()
        else:
            self.barra.stop()

    def _parar_barra(self, modo):
        self.barra.stop()
        estilo = {"ok": "Ok", "warn": "Warn", "err": "Err"}.get(modo, "S")
        self.barra.configure(style=f"{estilo}.Horizontal.TProgressbar", mode="determinate",
                             value=100 if modo in ("ok", "warn", "err") else 0)

    def resultado(self, tipo, texto):
        """tipo: ok | warn | fail | cancel | idle"""
        self._rodando = False
        modo = {"ok": "ok", "warn": "warn", "fail": "err", "cancel": "warn"}.get(tipo, "idle")
        self._parar_barra(modo)
        cor = {"ok": "ok", "warn": "warn", "fail": "err", "cancel": "warn"}.get(tipo, "muted")
        self.set_status(texto, cor)

    # --- registro ---
    def copiar_registro(self):
        self.clipboard_clear()
        self.clipboard_append(self.txt.get("1.0", "end"))
        self.set_status("Registro copiado para a área de transferência.", "ok")

    def log(self, texto, nivel="info"):
        self.txt.configure(state="normal")
        self.txt.insert("end", f"{time.strftime('%H:%M:%S')}  {texto}\n", nivel)
        if int(self.txt.index("end-1c").split(".")[0]) > 3000:
            self.txt.delete("1.0", "500.0")
        self.txt.see("end")
        self.txt.configure(state="disabled")


class Execucao:
    """Liga um Job do motor ao painel de andamento (consulta a fila a cada 100 ms)."""

    def __init__(self, widget, job, painel, ao_destino=None, ao_terminar=None):
        self.widget, self.job, self.painel = widget, job, painel
        self.ao_destino, self.ao_terminar = ao_destino, ao_terminar
        self.ativa = True

    def iniciar(self):
        self.painel.executando(True)
        self.job.start()
        self.widget.after(100, self._ler)

    def cancelar(self):
        self.job.cancel()

    def _ler(self):
        terminou = None
        try:
            while True:
                ev = self.job.q.get_nowait()
                tipo = ev[0]
                if tipo == "phase":
                    self.painel.fase(ev[1], ev[2])
                elif tipo == "status":
                    self.painel.set_status(ev[1], "accent")
                elif tipo == "log":
                    self.painel.log(ev[1], ev[2])
                elif tipo == "dest":
                    if self.ao_destino:
                        self.ao_destino(ev[1])
                elif tipo == "done":
                    terminou = (ev[1], ev[2])
                    break
        except queue.Empty:
            pass
        if terminou is not None:
            self.ativa = False
            self.painel.executando(False)
            if self.ao_terminar:
                self.ao_terminar(*terminou)
        else:
            self.widget.after(100, self._ler)

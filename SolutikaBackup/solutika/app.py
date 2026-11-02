# -*- coding: utf-8 -*-
"""Janela principal: barra lateral com as três seções."""
import os
import tkinter as tk
import traceback
from tkinter import messagebox

from . import APP_NAME, APP_VERSION, theme
from .paths import Settings, data_dir, resource_path
from .sessao import Sessao
from .sistema import is_admin, reabrir_como_admin
from .theme import COR, Botao, ToggleTema, fonte, px
from .ui_backup import BackupPage
from .ui_ficha import FichaPage
from .ui_restaurar import RestauracaoPage


class ItemNav(tk.Frame):
    def __init__(self, parent, titulo, sub, comando):
        super().__init__(parent, bg=COR["bg"], cursor="hand2")
        self.comando = comando
        self.sel = False
        self.barra = tk.Frame(self, width=px(3), bg=COR["bg"])
        self.barra.pack(side="left", fill="y")
        self.corpo = tk.Frame(self, bg=COR["bg"])
        self.corpo.pack(side="left", fill="x", expand=True, padx=px(16), pady=px(11))
        self.t = tk.Label(self.corpo, text=titulo, font=fonte(11, "bold"), anchor="w", bg=COR["bg"], fg=COR["text"])
        self.t.pack(fill="x")
        self.s = tk.Label(self.corpo, text=sub, font=fonte(9), anchor="w", bg=COR["bg"], fg=COR["muted"])
        self.s.pack(fill="x")
        for w in (self, self.barra, self.corpo, self.t, self.s):
            w.bind("<Button-1>", lambda e: self.comando())
            w.bind("<Enter>", lambda e: self._cor(True))
            w.bind("<Leave>", lambda e: self._cor(False))
        self._cor(False)

    def _cor(self, hover):
        if self.sel:
            fundo, barra, fg = COR["accent_soft"], COR["accent"], COR["navy"]
        else:
            fundo = COR["surface"] if hover else COR["bg"]
            barra, fg = fundo, COR["text"]
        for w in (self, self.corpo, self.t, self.s):
            w.configure(bg=fundo)
        self.barra.configure(bg=barra)
        self.t.configure(fg=fg)

    def marcar(self, sel):
        self.sel = sel
        self._cor(False)

    def _tema(self):
        self._cor(False)


class App(tk.Tk):
    def __init__(self):
        settings = Settings()
        theme.definir_tema(settings.get("tema", "claro"))
        super().__init__()
        self.settings = settings
        theme.init(self)
        self.title(f"{APP_NAME}  ·  Solutika Tecnologia")
        self.configure(bg=COR["surface"])
        try:
            self.iconbitmap(resource_path(os.path.join("assets", "icon.ico")))
        except tk.TclError:
            pass
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(px(1160), sw - 60), min(px(780), sh - 90)
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}")
        self.minsize(min(px(980), w), min(px(640), h))
        self.report_callback_exception = self._erro_interno

        self.sessao = Sessao()
        self.admin = is_admin()
        self.ocupado = None
        self._logo = None

        # --- barra lateral ---
        lateral = tk.Frame(self, bg=COR["bg"], width=px(260))
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)
        tk.Frame(self, bg=COR["border"], width=1).pack(side="left", fill="y")
        self._montar_logo(lateral)
        self.itens = {}
        self.paginas = {}
        self.area = tk.Frame(self, bg=COR["surface"])
        self.area.pack(side="left", fill="both", expand=True)
        for chave, titulo, sub, classe in (
                ("backup", "Backup de arquivos", "Salvar o perfil do usuário", BackupPage),
                ("restauracao", "Restauração", "Devolver dados ao usuário", RestauracaoPage),
                ("ficha", "Ficha do técnico", "Registro e PDF do chamado", FichaPage)):
            item = ItemNav(lateral, titulo, sub, lambda c=chave: self.mostrar(c))
            item.pack(fill="x")
            self.itens[chave] = item
            self.paginas[chave] = classe(self.area, self)

        rodape = tk.Frame(lateral, bg=COR["bg"])
        rodape.pack(side="bottom", fill="x", padx=px(18), pady=px(16))
        tk.Label(rodape, text=f"Versão {APP_VERSION}", font=fonte(8), fg=COR["disabled"], bg=COR["bg"],
                 anchor="w").pack(fill="x", pady=(px(10), 0))
        if not self.admin:
            Botao(rodape, "Reabrir como administrador", self.reabrir_admin, "secundario").pack(fill="x")
        chip = tk.Label(rodape, text=("\u25CF  Modo administrador" if self.admin else "\u25CF  Sem administrador"),
                        font=fonte(9, "bold"), anchor="w", padx=px(10), pady=px(6),
                        fg=COR["ok"] if self.admin else COR["warn"],
                        bg=COR["ok_soft"] if self.admin else COR["warn_soft"])
        chip.pack(fill="x", pady=(0, px(8)))
        # chave sol/lua no canto superior direito
        self.toggle = ToggleTema(self.area, self.alternar_tema)
        self.toggle.place(relx=1.0, x=-px(24), y=px(20), anchor="ne")
        self.protocol("WM_DELETE_WINDOW", self.fechar)
        self.mostrar("backup")
        self.after(150, lambda: theme.barra_titulo_escura(self, theme.TEMA["nome"] == "escuro"))

    def _carregar_logo(self):
        arquivo = "logo_dark.png" if theme.TEMA["nome"] == "escuro" else "logo.png"
        caminho = resource_path(os.path.join("assets", arquivo))
        try:
            from PIL import Image, ImageTk
            im = Image.open(caminho)
            larg = px(190)
            return ImageTk.PhotoImage(im.resize((larg, int(im.height * larg / im.width)), Image.LANCZOS))
        except Exception:  # noqa: BLE001 - sem Pillow usa o PNG original reduzido
            try:
                img = tk.PhotoImage(file=caminho)
                return img.subsample(max(1, round(img.width() / px(190))))
            except tk.TclError:
                return None

    def _montar_logo(self, pai):
        self._logo = self._carregar_logo()
        topo = tk.Frame(pai, bg=COR["bg"])
        topo.pack(fill="x", padx=px(18), pady=(px(24), px(22)))
        self._lbl_logo = tk.Label(topo, bg=COR["bg"])
        if self._logo:
            self._lbl_logo.configure(image=self._logo)
        else:
            self._lbl_logo.configure(text="SOLUTIKA", font=fonte(16, "bold"), fg=COR["navy"])
        self._lbl_logo.pack(anchor="w")
        tk.Label(topo, text="Backup e atendimento técnico", font=fonte(9), fg=COR["muted"], bg=COR["bg"],
                 anchor="w").pack(fill="x", pady=(px(8), 0))

    def alternar_tema(self):
        novo = "claro" if theme.TEMA["nome"] == "escuro" else "escuro"
        theme.trocar_tema(self, novo)
        self.settings.set("tema", novo)
        self._logo = self._carregar_logo()
        if self._logo:
            self._lbl_logo.configure(image=self._logo)
        theme.barra_titulo_escura(self, novo == "escuro")
        tk.Misc.lift(self.toggle)

    def mostrar(self, chave):
        for k, p in self.paginas.items():
            p.pack_forget()
            self.itens[k].marcar(k == chave)
        self.paginas[chave].pack(fill="both", expand=True)
        tk.Misc.lift(self.toggle)

    def set_ocupado(self, nome):
        self.ocupado = nome

    def reabrir_admin(self):
        if self.ocupado:
            messagebox.showinfo("Aguarde", "Termine ou cancele a operação em andamento antes de reabrir.")
            return
        if not messagebox.askyesno("Reabrir como administrador", "O programa será fechado e aberto de novo como "
                                   "administrador. O Windows vai pedir a sua confirmação.\n\nContinuar?"):
            return
        if reabrir_como_admin():
            self.destroy()
        else:
            messagebox.showwarning("Administrador", "Não foi possível reabrir como administrador (a confirmação foi "
                                   "cancelada ou está bloqueada).\n\nAlternativa: clique com o botão direito no "
                                   "programa e escolha \"Executar como administrador\". Se ele estiver em uma "
                                   "unidade de rede, copie-o antes para o Desktop.")

    def fechar(self):
        if self.ocupado:
            if not messagebox.askyesno("Atenção", "Há uma operação em andamento. Fechar agora vai interrompê-la e os "
                                       "dados ficarão INCOMPLETOS. Deseja fechar mesmo assim?"):
                return
            for p in self.paginas.values():
                ex = getattr(p, "exec", None)
                if ex is not None and getattr(ex, "ativa", False):
                    ex.cancelar()
        self.destroy()

    def _erro_interno(self, exc, val, tb):
        texto = "".join(traceback.format_exception(exc, val, tb))
        try:
            with open(os.path.join(data_dir(), "erro.log"), "a", encoding="utf-8") as f:
                f.write(texto + "\n")
        except OSError:
            pass
        messagebox.showerror("Erro inesperado", f"{val}\n\nO detalhe foi gravado em:\n{data_dir()}\\erro.log")

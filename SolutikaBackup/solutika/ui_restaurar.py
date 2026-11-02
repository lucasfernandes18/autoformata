# -*- coding: utf-8 -*-
"""Seção 2: Restauração do backup para um usuário."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import engine
from .theme import COR, Botao, Caixa, Cartao, Execucao, PainelAndamento, Rolagem, combo, entrada, px, rotulo
from .ui_backup import Pagina, grupo


class RestauracaoPage(Pagina):
    def __init__(self, parent, app):
        super().__init__(parent, app, "Restauração",
                         "Devolva arquivos, AppData e drivers de um backup para o usuário escolhido.")
        self.exec = None
        self.info = None
        self.lista_backups = []
        self._agenda = None
        self._ignorar_combo = False
        self.corpo.columnconfigure(0, weight=1, uniform="col")
        self.corpo.columnconfigure(1, weight=1, uniform="col")
        self.corpo.rowconfigure(0, weight=1)
        esq = Rolagem(self.corpo)
        esq.grid(row=0, column=0, sticky="nsew", padx=(0, px(14)))
        dire = tk.Frame(self.corpo, bg=COR["surface"])
        dire.grid(row=0, column=1, sticky="nsew")
        e = esq.interno

        # --- 1. backup ---
        f = grupo(e, "1 · Escolha o backup")
        f.columnconfigure(0, weight=1)
        rotulo(f, "Pasta do backup (COMPUTADOR_usuario_data)", 9, "normal", "muted").grid(row=0, column=0,
                                                                                         columnspan=2, sticky="w")
        self.var_bk = tk.StringVar()
        self.en_bk = entrada(f, self.var_bk)
        self.en_bk.grid(row=1, column=0, sticky="ew", pady=(px(3), px(8)))
        self.bt_abrir = Botao(f, "Procurar", self._procurar, "secundario")
        self.bt_abrir.configure(padx=px(12), pady=px(5))
        self.bt_abrir.grid(row=1, column=1, padx=(px(8), 0))
        rotulo(f, "Backups encontrados", 9, "normal", "muted").grid(row=2, column=0, columnspan=2, sticky="w")
        self.cb_bk = combo(f, [])
        self.cb_bk.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(px(3), 0))
        self.cb_bk.bind("<<ComboboxSelected>>", self._escolheu_lista)
        self.var_bk.trace_add("write", lambda *a: self._agendar_info())

        # --- conteúdo ---
        f = grupo(e, "Conteúdo do backup")
        self.lbl_nome = rotulo(f, "Selecione a pasta do backup.", 10, "bold", "text", wraplength=px(360))
        self.lbl_nome.pack(fill="x", pady=(0, px(6)))
        self.lbl_u = rotulo(f, "", 10, "normal", "muted")
        self.lbl_a = rotulo(f, "", 10, "normal", "muted")
        self.lbl_d = rotulo(f, "", 10, "normal", "muted")
        self.lbl_r = rotulo(f, "", 10, "normal", "muted", wraplength=px(360))
        self.lbl_p = rotulo(f, "", 9, "normal", "muted", wraplength=px(360))
        for l in (self.lbl_u, self.lbl_a, self.lbl_d, self.lbl_r, self.lbl_p):
            l.pack(fill="x", pady=px(1))

        # --- 2. usuário ---
        f = grupo(e, "2 · Usuário que vai receber os dados")
        f.columnconfigure(1, weight=1)
        rotulo(f, "Usuário").grid(row=0, column=0, sticky="w", padx=(0, px(12)))
        self.var_user = tk.StringVar()
        self.cb_user = combo(f, engine.listar_perfis(None if app.admin else os.environ.get("USERNAME")),
                             self.var_user)
        self.cb_user.grid(row=0, column=1, sticky="ew")
        self.lbl_dest = rotulo(f, "", 9, "bold", "accent")
        self.lbl_dest.grid(row=1, column=0, columnspan=2, sticky="w", pady=(px(6), 0))
        rotulo(f, "O usuário precisa ter entrado no Windows ao menos uma vez (para a pasta do perfil existir) e, de "
                  "preferência, estar deslogado durante a restauração.", 9, "normal", "muted",
               wraplength=px(360)).grid(row=2, column=0, columnspan=2, sticky="w", pady=(px(6), 0))
        self.cb_user.bind("<<ComboboxSelected>>", lambda _e: self._usuario_mudou())
        if self.cb_user["values"]:
            self.cb_user.current(0)
            self._usuario_mudou()

        # --- 3. o que restaurar ---
        f = grupo(e, "3 · O que restaurar")
        self.c_arq = Caixa(f, "Restaurar os arquivos do usuário", tk.BooleanVar(value=False),
                           "Desktop, Documentos, Downloads, Imagens etc. voltam para o perfil.", largura=330)
        self.c_app = Caixa(f, "Restaurar o AppData (configurações dos programas)", tk.BooleanVar(value=False),
                           "Extrai o AppData.zip. Arquivos que já existem são substituídos.", largura=330)
        self.c_drv = Caixa(f, "Instalar os drivers do backup", tk.BooleanVar(value=False),
                           "Vale para o computador todo. Use na mesma máquina do backup."
                           if app.admin else "Requer administrador (use o botão na barra lateral).", largura=330)
        self.c_fechar = Caixa(f, "Fechar navegadores, Outlook e Teams antes", tk.BooleanVar(value=True),
                              "Evita arquivos travados na hora de substituir as configurações.", largura=330)
        self.c_novos = Caixa(f, "Não sobrescrever arquivos mais novos", tk.BooleanVar(value=True),
                             "Arquivos do usuário: mantém os que já são mais novos que os do backup.", largura=330)
        for c in (self.c_arq, self.c_app, self.c_drv, self.c_fechar, self.c_novos):
            c.pack(fill="x", pady=px(5), anchor="w")
        for c in (self.c_arq, self.c_app, self.c_drv):
            c.ativar(False)

        # --- direita ---
        self.painel = PainelAndamento(dire, engine.RESTORE_FASES, "Andamento da restauração")
        self.painel.pack(fill="both", expand=True)
        self.painel.log("Escolha o backup (passo 1), o usuário (passo 2) e clique em \"Restaurar agora\".", "muted")
        if not app.admin:
            self.painel.log("Sem administrador: só é possível restaurar no seu próprio perfil e a instalação de drivers "
                            "fica desativada. Use \"Reabrir como administrador\" na barra lateral.", "warn")

        # --- rodapé ---
        self.bt_restaurar = Botao(self.rodape, "Restaurar agora", self._comecar, "primario")
        self.bt_restaurar.pack(side="left")
        self.bt_restaurar.ativar(False)
        self.bt_cancelar = Botao(self.rodape, "Cancelar", self._cancelar, "secundario")
        self.bt_softwares = Botao(self.rodape, "Ver lista de softwares", self._abrir_softwares, "secundario")
        self.bt_softwares.pack(side="right")
        self.bt_softwares.ativar(False)
        self.after(400, self._autodetectar)

    # ------------------------------------------------------------------
    def _usuario_mudou(self):
        self.lbl_dest.configure(text=f"Destino: {engine.pasta_usuario(self.var_user.get())}")

    def _procurar(self):
        pasta = filedialog.askdirectory(title="Escolha a pasta do backup (ou a pasta que contém os backups)")
        if pasta:
            self.var_bk.set(os.path.normpath(pasta))

    def _definir_lista(self, caminhos):
        self.lista_backups = list(caminhos)
        self._ignorar_combo = True
        self.cb_bk.configure(values=[os.path.basename(c.rstrip("\\/")) for c in self.lista_backups])
        self._ignorar_combo = False

    def _escolheu_lista(self, _e=None):
        if self._ignorar_combo:
            return
        i = self.cb_bk.current()
        if 0 <= i < len(self.lista_backups):
            self.var_bk.set(self.lista_backups[i])

    def _autodetectar(self):
        raizes = [os.path.join(engine.USERS_ROOT, u, "Documents", "BackupFormatacao") for u in engine.listar_perfis()]
        salvo = self.app.settings.get("destino_backup", "")
        if salvo:
            raizes.append(salvo)
        achados = engine.procurar_backups(raizes)
        if achados:
            self._definir_lista(achados)
            if not self.var_bk.get().strip():
                self.cb_bk.current(0)
                self.var_bk.set(achados[0])

    def _agendar_info(self):
        if self._agenda:
            self.after_cancel(self._agenda)
        self._agenda = self.after(350, self._atualizar_info)

    def _linha(self, lbl, estado, texto):
        simbolo, cor = {"ok": ("\u2714", "ok"), "warn": ("\u25B2", "warn"), "err": ("\u2716", "err")}.get(
            estado, ("\u2013", "muted"))
        lbl.configure(text=f"{simbolo}   {texto}", fg=COR[cor])

    def _atualizar_info(self):
        self._agenda = None
        pasta = self.var_bk.get().strip()
        self.info = None
        for l in (self.lbl_u, self.lbl_a, self.lbl_d, self.lbl_r, self.lbl_p):
            self._linha(l, "none", "")
            l.configure(text="")
        habilitar = {"arq": False, "app": False, "drv": False}
        if not pasta:
            self.lbl_nome.configure(text="Selecione a pasta do backup.")
        elif not os.path.isdir(pasta):
            self.lbl_nome.configure(text="Pasta não encontrada.")
        elif not engine.eh_backup(pasta):
            filhos = engine.procurar_backups([pasta])
            if filhos:
                self._definir_lista(filhos)
                self.lbl_nome.configure(text=f"Esta pasta contém {len(filhos)} backup(s). Escolha um na lista "
                                             "de backups encontrados.")
            else:
                self.lbl_nome.configure(text="Esta pasta não parece ser um backup (não tem Usuario, AppData.zip "
                                             "nem Drivers).")
        else:
            i = engine.descrever_backup(pasta)
            self.info = i
            nome = i["nome"]
            if i["usuario"] and i["data"]:
                nome = f"Backup de {i['usuario']}  •  {i['data']:%d/%m/%Y %H:%M}  •  PC {i['maquina']}"
            self.lbl_nome.configure(text=nome)
            self._linha(self.lbl_u, "ok" if i["tem_usuario"] else "none",
                        "Arquivos do usuário encontrados" if i["tem_usuario"]
                        else "Arquivos do usuário: não existem neste backup")
            self._linha(self.lbl_a, "ok" if i["tem_zip"] else "none",
                        f"AppData.zip encontrado ({engine.fmt_gb(i['zip_bytes'])})" if i["tem_zip"]
                        else "AppData.zip: não existe neste backup")
            self._linha(self.lbl_d, "ok" if i["tem_drivers"] else "none",
                        f"Drivers encontrados ({i['drivers']} pacotes .inf)" if i["tem_drivers"]
                        else "Drivers: não existem neste backup")
            if i["completo"] is True:
                self._linha(self.lbl_r, "ok", "Relatório: backup concluído e validado")
            elif i["completo"] is False:
                self._linha(self.lbl_r, "warn", "Relatório: este backup NÃO foi marcado como completo")
            else:
                self._linha(self.lbl_r, "none", "Relatório do backup não encontrado")
            if i["pastas"]:
                extra = ("  |  De fora do perfil: " + ", ".join(i["redirecionadas"])) if i["redirecionadas"] else ""
                self.lbl_p.configure(text="Pastas no backup: " + ", ".join(i["pastas"]) + extra, fg=COR["muted"])
            habilitar = {"arq": i["tem_usuario"], "app": i["tem_zip"], "drv": i["tem_drivers"] and self.app.admin}
            if i["usuario"] in self.cb_user["values"]:
                self.cb_user.set(i["usuario"])
                self._usuario_mudou()
        for caixa, chave in ((self.c_arq, "arq"), (self.c_app, "app"), (self.c_drv, "drv")):
            caixa.set(habilitar[chave])
            caixa.ativar(habilitar[chave])
        self.bt_restaurar.ativar(self.info is not None)
        self.bt_softwares.ativar(bool(self.info and self.info["tem_softwares"]))

    def _abrir_softwares(self):
        if self.info:
            from .ui_softwares import DialogoSoftwares
            DialogoSoftwares(self.app, self.info["pasta"])

    def _params(self):
        return {"backup": self.info["pasta"], "usuario": self.var_user.get(), "fechar": self.c_fechar.get(),
                "arquivos": self.c_arq.get(), "appdata": self.c_app.get(),
                "drivers": self.c_drv.get() and self.app.admin, "nao_sobrescrever_novos": self.c_novos.get(),
                "threads": 32}

    def _ocupado(self, b):
        self.app.set_ocupado("restauracao" if b else None)
        i = self.info or {}
        self.c_arq.ativar((not b) and bool(i.get("tem_usuario")))
        self.c_app.ativar((not b) and bool(i.get("tem_zip")))
        self.c_drv.ativar((not b) and bool(i.get("tem_drivers")) and self.app.admin)
        self.c_fechar.ativar(not b)
        self.c_novos.ativar(not b)
        self.en_bk.configure(state="disabled" if b else "normal")
        self.cb_bk.configure(state="disabled" if b else "readonly")
        self.cb_user.configure(state="disabled" if b else "readonly")
        self.bt_abrir.ativar(not b)
        self.bt_restaurar.ativar((not b) and self.info is not None)
        if b:
            self.bt_cancelar.pack(side="left", padx=px(10))
        else:
            self.bt_cancelar.pack_forget()

    def _comecar(self):
        if self.app.ocupado:
            messagebox.showinfo("Aguarde", "Já existe uma operação em andamento.")
            return
        if not self.info:
            messagebox.showwarning("Restauração", "Escolha a pasta de um backup válido.")
            return
        if not self.var_user.get():
            messagebox.showwarning("Restauração", "Escolha o usuário que vai receber os dados.")
            return
        p = self._params()
        if not (p["arquivos"] or p["appdata"] or p["drivers"]):
            messagebox.showwarning("Restauração", 'Marque ao menos uma opção em "O que restaurar".')
            return
        pt = "  •  "
        usuario = p["usuario"]
        t = [f"Backup:   {p['backup']}", f"Usuário de destino:   {usuario}   ({engine.pasta_usuario(usuario)})", "",
             "O que será feito:"]
        if p["arquivos"]:
            t.append(pt + "Copiar os arquivos do usuário para o perfil de destino")
            if p["nao_sobrescrever_novos"]:
                t.append(pt + "Arquivos mais novos que já existem no destino serão mantidos")
        if p["appdata"]:
            t.append(pt + "Extrair o AppData.zip no AppData do usuário (arquivos existentes serão SUBSTITUÍDOS)")
        if p["drivers"]:
            t.append(pt + "Instalar os drivers do backup (vale para o computador todo)")
        if p["fechar"]:
            t.append(pt + "ATENÇÃO: navegadores, Outlook e Teams abertos serão FECHADOS")
        t.append("")
        if engine.perfil_carregado(usuario):
            t += [f"ATENÇÃO: o usuário {usuario} está com a sessão aberta neste computador. Arquivos em uso podem não "
                  "ser substituídos. O ideal é ele estar deslogado.", ""]
        t.append("Deseja restaurar agora?")
        if not messagebox.askyesno("Confirmar restauração", "\n".join(t)):
            return
        self.painel.reset(pulados=[k for k, v in (("prog", p["fechar"]), ("arq", p["arquivos"]),
                                                  ("app", p["appdata"]), ("drv", p["drivers"])) if not v])
        self.painel.log(f"Iniciando a restauração em {usuario}", "accent")
        self._ocupado(True)
        self.exec = Execucao(self, engine.Job(engine.run_restore, p), self.painel, ao_terminar=self._fim)
        self.exec.iniciar()

    def _cancelar(self):
        if self.exec and messagebox.askyesno("Cancelar", "Interromper a restauração em andamento?"):
            self.exec.cancelar()

    def _fim(self, resultado, dados):
        self._ocupado(False)
        # registra a restauração e também o backup de origem (para a ficha descrever os dois)
        if self.info:
            for ev in engine.carregar_eventos(self.info["pasta"]):
                self.app.sessao.add(ev)
        if "evento" in dados:
            self.app.sessao.add(dados["evento"])
        extra = "\n\nReinicie o computador para concluir a instalação dos drivers." if dados.get("reiniciar") else ""
        if resultado == "ok":
            self.painel.resultado("ok", "Restauração concluída. Peça ao usuário para entrar na conta e conferir.")
            messagebox.showinfo("Restauração concluída", "Restauração concluída com sucesso.\n\nPeça ao usuário para "
                                "entrar na conta e conferir os arquivos e programas." + extra)
        elif resultado == "warn":
            self.painel.resultado("warn", "Restauração concluída com avisos. Revise o registro.")
            messagebox.showwarning("Restauração com avisos", "A restauração terminou, mas com avisos (arquivos em uso "
                                   "ou drivers não instalados).\n\nVeja o registro detalhado." + extra)
        elif resultado == "cancel":
            self.painel.fechar_pendentes_como_erro()
            self.painel.resultado("cancel", "Restauração cancelada. Os dados ficaram incompletos.")
        else:
            self.painel.fechar_pendentes_como_erro()
            self.painel.resultado("fail", "A restauração falhou ou ficou incompleta. Revise o registro.")
            messagebox.showerror("Atenção", "A restauração falhou ou ficou incompleta.\n\nVeja o registro detalhado, "
                                 "corrija o problema e tente de novo.")

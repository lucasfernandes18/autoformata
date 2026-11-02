# -*- coding: utf-8 -*-
"""Seção 1: Backup de arquivos."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import engine
from .theme import (COR, Botao, Caixa, Cartao, Execucao, PainelAndamento, Radio, Rolagem, combo, entrada, px,
                    rotulo)


class Pagina(tk.Frame):
    """Estrutura comum das seções: título, corpo e rodapé de ações."""

    def __init__(self, parent, app, titulo, subtitulo):
        super().__init__(parent, bg=COR["surface"])
        self.app = app
        cab = tk.Frame(self, bg=COR["surface"])
        cab.pack(fill="x", padx=px(28), pady=(px(22), px(14)))
        rotulo(cab, titulo, 20, "bold", "navy").pack(anchor="w")
        rotulo(cab, subtitulo, 10, "normal", "muted").pack(anchor="w", pady=(px(2), 0))
        self.corpo = tk.Frame(self, bg=COR["surface"])
        self.rodape = tk.Frame(self, bg=COR["surface"])
        self.rodape.pack(side="bottom", fill="x", padx=px(28), pady=(px(10), px(18)))
        self.corpo.pack(fill="both", expand=True, padx=px(28))


def grupo(pai, titulo):
    """Cartão com um frame interno livre para usar grid."""
    c = Cartao(pai, titulo)
    c.pack(fill="x", pady=(0, px(12)))
    f = tk.Frame(c.corpo, bg=COR["bg"])
    f.pack(fill="x")
    return f


class BackupPage(Pagina):
    def __init__(self, parent, app):
        super().__init__(parent, app, "Backup de arquivos",
                         "Salve o perfil do usuário (arquivos, AppData e drivers) antes de formatar o computador.")
        self.exec = None
        self.dest_final = None
        self.c_pastas = {}
        self.c_nav = {}
        self.corpo.columnconfigure(0, weight=1, uniform="col")
        self.corpo.columnconfigure(1, weight=1, uniform="col")
        self.corpo.rowconfigure(0, weight=1)
        esq = Rolagem(self.corpo)
        esq.grid(row=0, column=0, sticky="nsew", padx=(0, px(14)))
        dire = tk.Frame(self.corpo, bg=COR["surface"])
        dire.grid(row=0, column=1, sticky="nsew")
        e = esq.interno

        # --- origem e destino ---
        f = grupo(e, "Origem e destino")
        f.columnconfigure(1, weight=1)
        rotulo(f, "Usuário").grid(row=0, column=0, sticky="w", pady=px(4), padx=(0, px(12)))
        self.var_user = tk.StringVar()
        self.cb_user = combo(f, engine.listar_perfis(None if app.admin else os.environ.get("USERNAME")),
                             self.var_user)
        self.cb_user.grid(row=0, column=1, columnspan=2, sticky="ew", pady=px(4))
        rotulo(f, "Salvar em").grid(row=1, column=0, sticky="w", pady=px(4), padx=(0, px(12)))
        self.var_dest = tk.StringVar()
        self.en_dest = entrada(f, self.var_dest)
        self.en_dest.grid(row=1, column=1, sticky="ew", pady=px(4))
        self.bt_procurar = Botao(f, "Procurar", self._procurar, "secundario")
        self.bt_procurar.configure(padx=px(12), pady=px(5))
        self.bt_procurar.grid(row=1, column=2, padx=(px(8), 0))
        self.cb_user.bind("<<ComboboxSelected>>", lambda _e: self._usuario_mudou())

        # --- pastas do perfil ---
        f = grupo(e, "Pastas do perfil que serão salvas")
        rotulo(f, "Tudo o que está marcado entra no backup. Desmarque só o que realmente não precisa levar.", 9,
               "normal", "muted", wraplength=px(340)).pack(fill="x", pady=(0, px(6)))
        self.f_pastas = tk.Frame(f, bg=COR["bg"])
        self.f_pastas.pack(fill="x")
        self.lbl_onedrive = rotulo(f, "", 9, "normal", "warn", wraplength=px(340))
        self.lbl_onedrive.pack(fill="x", pady=(px(6), 0))

        # --- AppData (configurações dos programas) ---
        f = grupo(e, "Configurações dos programas (AppData)")
        rotulo(f, "O AppData é uma pasta oculta do usuário onde os programas guardam suas configurações: e-mail do "
                  "Outlook, Teams, Office, licenças e preferências. Ele tem duas partes: o Roaming (configurações "
                  "que acompanham o usuário) e o Local (dados pesados deste computador, como caches).",
               9, "normal", "muted", wraplength=px(340)).pack(fill="x", pady=(0, px(8)))
        self.var_appdata = tk.StringVar(value="completo")
        self.r_app = [
            Radio(f, "Completo (recomendado)", self.var_appdata, "completo",
                  "Leva Roaming e Local, sem as pastas de cache. É o mais seguro para o usuário não perder nenhuma "
                  "configuração, mas ocupa mais espaço.", largura=320),
            Radio(f, "Essencial", self.var_appdata, "essencial",
                  "Leva só o Roaming: configurações, perfis e licenças da maioria dos programas. Fica bem menor e "
                  "mais rápido. O Local não é levado (os navegadores têm escolha própria, logo abaixo).", largura=320),
            Radio(f, "Não levar o AppData", self.var_appdata, "nenhum",
                  "Leva só os arquivos pessoais. Os programas voltam com a configuração de fábrica.", largura=320),
        ]
        for r in self.r_app:
            r.pack(fill="x", pady=px(5), anchor="w")

        # --- navegadores ---
        f = grupo(e, "Navegadores")
        rotulo(f, "Chrome, Edge e Brave guardam histórico, favoritos, extensões e logins dentro do AppData\\Local. "
                  "Por isso a escolha dos navegadores é separada: eles entram no backup mesmo no modo Essencial.",
               9, "normal", "muted", wraplength=px(340)).pack(fill="x", pady=(0, px(8)))
        self.f_nav = tk.Frame(f, bg=COR["bg"])
        self.f_nav.pack(fill="x")
        self.c_fechar = Caixa(f, "Fechar os navegadores antes de copiar", tk.BooleanVar(value=True),
                              "Navegador aberto trava o histórico e as senhas. Salve o que estiver aberto!",
                              largura=320)
        self.c_fechar.pack(fill="x", pady=(px(8), px(2)), anchor="w")
        rotulo(f, "Atenção: as senhas salvas no Chrome e no Edge são protegidas pela conta do Windows e podem não "
                  "abrir depois de formatar. Confirme que a sincronização da conta do navegador está ativa.",
               9, "normal", "warn", wraplength=px(340)).pack(fill="x", pady=(px(6), 0))

        # --- como salvar ---
        f = grupo(e, "Como salvar")
        self.c_zip = Caixa(f, "Compactar o AppData em um único arquivo .zip", tk.BooleanVar(value=True),
                           "Bem mais rápido do que copiar milhares de arquivos pequenos.", largura=330)
        self.c_drv = Caixa(f, "Exportar os drivers do Windows", tk.BooleanVar(value=app.admin),
                           "Facilita reinstalar placas, rede e impressoras depois." if app.admin
                           else "Requer administrador (use o botão na barra lateral).", largura=330)
        if not app.admin:
            self.c_drv.ativar(False)
        self.c_zip.pack(fill="x", pady=px(5), anchor="w")
        self.c_drv.pack(fill="x", pady=px(5), anchor="w")
        lin = tk.Frame(f, bg=COR["bg"])
        lin.pack(fill="x", pady=(px(6), 0))
        rotulo(lin, "Threads da cópia").pack(side="left")
        self.var_threads = tk.IntVar(value=32)
        self.sp_threads = ttk.Spinbox(lin, from_=1, to=128, width=5, textvariable=self.var_threads, style="S.TSpinbox")
        self.sp_threads.pack(side="left", padx=px(10))
        rotulo(lin, "32 é um bom padrão; use 8 em HD lento ou rede.", 9, "normal", "muted").pack(side="left")

        # --- direita: espaço + andamento ---
        cart = Cartao(dire, "Espaço necessário")
        cart.pack(fill="x", pady=(0, px(12)))
        g = tk.Frame(cart.corpo, bg=COR["bg"])
        g.pack(fill="x")
        g.columnconfigure(0, weight=1)
        g.columnconfigure(1, weight=1)
        rotulo(g, "Tamanho a copiar", 9, "normal", "muted").grid(row=0, column=0, sticky="w")
        rotulo(g, "Espaço livre no destino", 9, "normal", "muted").grid(row=0, column=1, sticky="w")
        self.lbl_tam = rotulo(g, "—", 16, "bold", "text")
        self.lbl_tam.grid(row=1, column=0, sticky="w")
        self.lbl_livre = rotulo(g, "—", 16, "bold", "text")
        self.lbl_livre.grid(row=1, column=1, sticky="w")
        if self.cb_user["values"]:
            self.cb_user.current(0)
            self._usuario_mudou()
        self.painel = PainelAndamento(dire, engine.BACKUP_FASES, "Andamento do backup")
        self.painel.pack(fill="both", expand=True)
        self.painel.log('Pronto. Escolha o usuário e o destino, ajuste as opções e clique em "Iniciar backup".', "muted")
        if not app.admin:
            self.painel.log("Sem administrador: só o seu próprio perfil pode ser salvo e a exportação de drivers fica "
                            "desativada. Use \"Reabrir como administrador\" na barra lateral.", "warn")

        # --- rodapé ---
        self.bt_estimar = Botao(self.rodape, "Estimar tamanho", lambda: self._comecar("estimar"), "secundario")
        self.bt_estimar.pack(side="left")
        self.bt_iniciar = Botao(self.rodape, "Iniciar backup", lambda: self._comecar("backup"), "primario")
        self.bt_iniciar.pack(side="left", padx=px(10))
        self.bt_cancelar = Botao(self.rodape, "Cancelar", self._cancelar, "secundario")
        self.bt_pasta = Botao(self.rodape, "Abrir a pasta do backup", self._abrir_pasta, "secundario")
        self.bt_pasta.pack(side="right")
        self.bt_pasta.ativar(False)

    # ------------------------------------------------------------------
    def _usuario_mudou(self):
        self._destino_padrao()
        self._listar_pastas()
        self._listar_navegadores()

    def _listar_pastas(self):
        for w in self.f_pastas.winfo_children():
            w.destroy()
        self.c_pastas = {}
        usuario = self.var_user.get()
        nomes = engine.pastas_do_perfil(usuario) if usuario else []
        od = engine.onedrive_conteudo(usuario) if usuario else {}
        for i, nome in enumerate(nomes):
            texto = f"{nome}  (OneDrive: pode ser grande)" if nome in od else nome
            c = Caixa(self.f_pastas, texto, tk.BooleanVar(value=True), largura=320)
            c.grid(row=i, column=0, sticky="w", pady=px(2))
            self.c_pastas[nome] = c
        if not nomes:
            rotulo(self.f_pastas, "Nenhuma pasta encontrada para este usuário.", 9, "normal", "muted").grid(
                row=0, column=0, sticky="w")
        achados = [f"{pasta} ({', '.join(subs[:4])})" if subs else pasta for pasta, subs in od.items()]
        texto = ("O OneDrive deste usuário contém: " + "; ".join(achados) + ". Os arquivos dele ficam na nuvem, mas "
                 "só desmarque se tiver certeza de que a sincronização terminou.") if achados else ""
        try:
            fora = [k for k in engine.pastas_conhecidas(usuario) if k["existe"] and not k["dentro"]]
        except Exception:  # noqa: BLE001
            fora = []
        if fora:
            texto += ("\n" if texto else "") + "Pastas do Windows FORA do perfil (serão copiadas também): " + \
                "; ".join(f"{k['nome']} em {k['caminho']}" for k in fora)
        self.lbl_onedrive.configure(text=texto)

    def _listar_navegadores(self):
        for w in self.f_nav.winfo_children():
            w.destroy()
        self.c_nav = {}
        usuario = self.var_user.get()
        achados = engine.navegadores_do_usuario(usuario) if usuario else []
        for i, nv in enumerate(achados):
            perfis = f"{nv['perfis']} perfil" if nv["perfis"] == 1 else f"{nv['perfis']} perfis"
            c = Caixa(self.f_nav, f"{nv['titulo']}  ·  {perfis}", tk.BooleanVar(value=True),
                      "Histórico, favoritos, extensões e logins (sem arquivos de cache).", largura=320)
            c.grid(row=i, column=0, sticky="w", pady=px(4))
            self.c_nav[nv["nome"]] = c
        if not achados:
            rotulo(self.f_nav, "Nenhum navegador encontrado para este usuário.", 9, "normal", "muted").grid(
                row=0, column=0, sticky="w")
        self.c_fechar.ativar(bool(achados))

    def _destino_padrao(self):
        salvo = self.app.settings.get("destino_backup", "")
        if salvo:
            self.var_dest.set(salvo)
        else:
            self.var_dest.set(os.path.join(engine.USERS_ROOT, self.var_user.get(), "Documents", "BackupFormatacao"))

    def _procurar(self):
        pasta = filedialog.askdirectory(title="Escolha a pasta onde o backup será salvo")
        if pasta:
            self.var_dest.set(os.path.normpath(pasta))

    def _abrir_pasta(self):
        if self.dest_final and os.path.isdir(self.dest_final):
            os.startfile(self.dest_final)  # noqa: S606 - só existe no Windows, que é o alvo

    def _params(self):
        try:
            threads = int(self.var_threads.get())
        except (tk.TclError, ValueError):
            threads = 32
        nav = [n for n, c in self.c_nav.items() if c.get()]
        return {"usuario": self.var_user.get(), "destino": self.var_dest.get().strip(),
                "excluir_pastas": [n for n, c in self.c_pastas.items() if not c.get()],
                "appdata_modo": self.var_appdata.get(), "navegadores_lista": nav,
                "fechar_nav": bool(nav) and self.c_fechar.get(),
                "compactar": self.c_zip.get(), "drivers": self.c_drv.get() and self.app.admin,
                "threads": max(1, min(128, threads))}

    def _ocupado(self, b):
        self.app.set_ocupado("backup" if b else None)
        for c in (self.c_zip, *self.c_pastas.values(), *self.c_nav.values(), *self.r_app):
            c.ativar(not b)
        self.c_fechar.ativar((not b) and bool(self.c_nav))
        self.c_drv.ativar((not b) and self.app.admin)
        self.cb_user.configure(state="disabled" if b else "readonly")
        self.en_dest.configure(state="disabled" if b else "normal")
        self.sp_threads.configure(state="disabled" if b else "normal")
        self.bt_procurar.ativar(not b)
        self.bt_estimar.ativar(not b)
        self.bt_iniciar.ativar(not b)
        self.bt_pasta.ativar((not b) and bool(self.dest_final))
        if b:
            self.bt_cancelar.pack(side="left")
        else:
            self.bt_cancelar.pack_forget()

    def _resumo(self, p):
        pt = "  •  "
        t = [f"Usuário:  {p['usuario']}   ({engine.pasta_usuario(p['usuario'])})", f"Destino:  {p['destino']}", "",
             "O que será feito:", pt + "Copiar a pasta do usuário (Desktop, Documentos, Downloads, Imagens...)"]
        if p["excluir_pastas"]:
            t.append(pt + "Pastas NÃO incluídas: " + ", ".join(p["excluir_pastas"]))
            if any(n.lower().startswith("onedrive") for n in p["excluir_pastas"]):
                t.append(pt + "ATENÇÃO: o OneDrive foi desmarcado. Confirme que a sincronização terminou.")
        else:
            t.append(pt + "Todas as pastas do perfil serão incluídas")
        modo = {"completo": "AppData completo (Roaming e Local, sem caches)",
                "essencial": "AppData essencial (somente o Roaming)",
                "nenhum": "AppData NÃO será levado"}[p["appdata_modo"]]
        t.append(pt + modo + (", compactado em um único .zip" if p["compactar"] and p["appdata_modo"] != "nenhum"
                              else ""))
        if p["navegadores_lista"]:
            t.append(pt + "Navegadores: " + ", ".join(engine.TITULOS_NAV[n] for n in p["navegadores_lista"]) +
                     " (histórico, favoritos, extensões e logins, sem caches)")
            if p["fechar_nav"]:
                t.append(pt + "ATENÇÃO: navegadores abertos serão FECHADOS")
        else:
            t.append(pt + "Nenhum navegador será incluído")
        if p["drivers"]:
            t.append(pt + "Exportar os drivers do Windows")
        t += [pt + "Inventário de softwares e impressoras", pt + "Validação origem x destino e relatório final", "",
              "Deseja iniciar o backup agora?"]
        return "\n".join(t)

    def _comecar(self, modo):
        if self.app.ocupado:
            messagebox.showinfo("Aguarde", "Já existe uma operação em andamento.")
            return
        p = self._params()
        if not p["usuario"]:
            messagebox.showwarning("Backup", "Selecione o usuário.")
            return
        if not p["destino"]:
            messagebox.showwarning("Backup", "Informe a pasta de destino.")
            return
        if modo == "backup":
            disco = os.path.splitdrive(os.path.abspath(p["destino"]))[0].upper()
            if disco == os.environ.get("SystemDrive", "C:").upper() and not messagebox.askyesno(
                    "Atenção: mesmo disco do Windows",
                    f"O destino está no disco {disco}, o mesmo que será formatado. Se o disco for formatado, o "
                    "backup será APAGADO junto.\n\nRecomendado: salvar em disco externo ou no servidor.\n\n"
                    "Continuar mesmo assim?"):
                return
            if "onedrive" in p["destino"].lower() and not messagebox.askyesno(
                    "Atenção", "O destino está dentro do OneDrive: o backup será enviado para a nuvem. Continuar?"):
                return
            if not messagebox.askyesno("Confirmar backup", self._resumo(p)):
                return
            self.app.settings.set("destino_backup", p["destino"])
            self.dest_final = None
            self.painel.reset(pulados=self._pulados(p))
            job = engine.Job(engine.run_backup, p)
            fim = self._fim_backup
            self.painel.log(f"Iniciando o backup de {p['usuario']}", "accent")
        else:
            self.lbl_tam.configure(text="—", fg=COR["text"])
            self.lbl_livre.configure(text="—", fg=COR["text"])
            self.painel.reset()
            job = engine.Job(engine.run_estimate, p)
            fim = self._fim_estimativa
            self.painel.log(f"Estimando o tamanho do backup de {p['usuario']}", "accent")
        self._ocupado(True)
        self.exec = Execucao(self, job, self.painel, ao_destino=self._destino_recebido, ao_terminar=fim)
        self.exec.iniciar()

    @staticmethod
    def _pulados(p):
        pul = []
        if not p["fechar_nav"]:
            pul.append("nav")
        if not p["drivers"]:
            pul.append("drv")
        if not p["compactar"] or (p["appdata_modo"] == "nenhum" and not p["navegadores_lista"]):
            pul.append("zip")
        return pul

    def _cancelar(self):
        if self.exec and messagebox.askyesno("Cancelar", "Interromper a operação em andamento?"):
            self.exec.cancelar()

    def _destino_recebido(self, caminho):
        self.dest_final = caminho

    def _fim_estimativa(self, resultado, dados):
        self._ocupado(False)
        if resultado != "ok":
            self.painel.resultado("fail" if resultado == "fail" else "cancel",
                                  "Não foi possível calcular o tamanho. Veja o registro." if resultado == "fail"
                                  else "Estimativa cancelada.")
            return
        self.lbl_tam.configure(text=engine.fmt_gb(dados["bytes"]))
        livre = dados["livre"]
        if livre >= 0:
            self.lbl_livre.configure(text=engine.fmt_gb(livre),
                                     fg=COR["err"] if dados["bytes"] > livre * 0.9 else COR["ok"])
        else:
            self.lbl_livre.configure(text="não verificado", fg=COR["muted"])
        self.painel.resultado("ok", 'Estimativa concluída. Confira o espaço livre e clique em "Iniciar backup".')

    def _fim_backup(self, resultado, dados):
        self._ocupado(False)
        if "evento" in dados:
            self.app.sessao.add(dados["evento"])
        if resultado == "ok":
            self.painel.resultado("ok", "Backup concluído e validado. Copie a pasta para o servidor ou disco externo "
                                        "ANTES de formatar.")
            messagebox.showinfo("Backup concluído",
                                "Backup concluído e validado.\n\nIMPORTANTE: ele está nesta mesma máquina. Copie a "
                                f"pasta abaixo para o servidor (ou disco externo) ANTES de formatar:\n\n{self.dest_final}")
        elif resultado == "cancel":
            self.painel.fechar_pendentes_como_erro()
            self.painel.resultado("cancel", "Backup cancelado. A pasta de destino ficou incompleta.")
        else:
            self.painel.fechar_pendentes_como_erro()
            self.painel.resultado("fail", "NÃO FORMATAR: o backup tem pendências ou falhas. Revise o registro.")
            messagebox.showwarning("Atenção", "O backup terminou com pendências ou falhas.\n\nNÃO FORMATE a máquina "
                                              "antes de revisar o registro detalhado.")
        self.bt_pasta.ativar(bool(self.dest_final))

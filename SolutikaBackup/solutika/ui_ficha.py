# -*- coding: utf-8 -*-
"""Seção 3: Ficha do técnico (descrição do atendimento, serviços, peças e PDF)."""
import os
import platform
import re
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox

from . import engine
from .descricao import descrever_sessao
from .paths import resource_path
from .theme import COR, Botao, Caixa, Cartao, Rolagem, combo, entrada, fonte, px, rotulo
from .ui_backup import Pagina

SERVICOS = [
    ("Sistema operacional", ["Formatação / reinstalação do Windows", "Atualização do Windows",
                             "Ativação do Windows / Office", "Atualização de drivers"]),
    ("Dados do usuário", ["Backup dos arquivos do usuário", "Restauração dos arquivos do usuário"]),
    ("Programas e segurança", ["Instalação de programas", "Antivírus instalado / atualizado",
                              "Remoção de vírus / malware", "Configuração de e-mail / Outlook"]),
    ("Rede e periféricos", ["Configuração de rede / Wi-Fi", "Configuração de impressora"]),
    ("Manutenção", ["Limpeza e manutenção preventiva", "Troca de pasta térmica",
                    "Otimização do sistema (limpeza de disco e inicialização)"]),
]
PECAS = [
    ("Armazenamento e memória", ["HD / SSD", "Memória RAM"]),
    ("Energia", ["Fonte de alimentação", "Bateria", "Carregador / cabo de energia"]),
    ("Placa e processamento", ["Placa-mãe", "Processador", "Cooler / ventoinha", "Placa de vídeo"]),
    ("Tela e periféricos", ["Tela / display", "Teclado / touchpad", "Mouse", "Webcam / áudio"]),
]
ROT_SERVICO = {"feito": "Realizado", "nao": "Não necessário", "pend": "Pendente"}
ROT_PECA = {"feito": "Trocada", "nao": "Não necessária", "pend": "Aguardando peça"}
TIPOS = ["Notebook", "Desktop", "All-in-one", "Servidor", "Outro"]
STATUS = ["Resolvido", "Pendente", "Aguardando peça", "Aguardando cliente"]


def so_atual():
    try:
        rel, ver = platform.release(), platform.version()
        if platform.system() == "Windows":
            build = int(ver.split(".")[2]) if ver.count(".") >= 2 else 0
            if rel == "10" and build >= 22000:
                rel = "11"
            return f"Windows {rel} (build {build})"
        return f"{platform.system()} {rel}"
    except (ValueError, IndexError):
        return platform.platform()


class SeletorStatus(tk.Frame):
    """Três opções lado a lado (ex.: Realizado / Não necessário / Pendente). Clicar de novo desmarca."""

    def __init__(self, parent, rotulos):
        super().__init__(parent, bg=parent.cget("bg"))
        self.rotulos = rotulos
        self.valor = ""
        self.botoes = {}
        for cod in ("feito", "nao", "pend"):
            b = tk.Label(self, text=rotulos[cod], font=fonte(9), padx=px(9), pady=px(3), cursor="hand2", borderwidth=0,
                         highlightthickness=1)
            b.pack(side="left", padx=(0, px(4)))
            b.bind("<Button-1>", lambda e, c=cod: self._clicar(c))
            self.botoes[cod] = b
        self._pintar()

    def _clicar(self, cod):
        self.set("" if self.valor == cod else cod)

    def set(self, cod):
        self.valor = cod
        self._pintar()

    def get(self):
        return self.valor

    def _tema(self):
        try:
            self.configure(bg=self.master.cget("bg"))
        except Exception:  # noqa: BLE001
            pass
        self._pintar()

    def _pintar(self):
        c = COR
        sel = {"feito": (c["ok_soft"], c["ok"]), "nao": (c["border"], c["text"]), "pend": (c["warn_soft"], c["warn"])}
        for cod, b in self.botoes.items():
            if self.valor == cod:
                bg, fg = sel[cod]
                b.configure(bg=bg, fg=fg, highlightbackground=fg, font=fonte(9, "bold"))
            else:
                b.configure(bg=c["bg"], fg=c["muted"], highlightbackground=c["border"], font=fonte(9))


class ChecklistStatus(tk.Frame):
    """Lista agrupada: item | situação (3 opções) | observação, com linhas livres para outros itens."""

    def __init__(self, parent, grupos, rotulos, extras=2):
        super().__init__(parent, bg=COR["bg"])
        self.rotulos = rotulos
        self.linhas = []
        self.columnconfigure(0, minsize=px(250))
        self.columnconfigure(2, weight=1)
        for col, txt in enumerate(("Item", "Situação", "Observação")):
            rotulo(self, txt, 9, "normal", "muted").grid(row=0, column=col, sticky="w", padx=(0, px(10)))
        r = 1
        for titulo, itens in grupos:
            rotulo(self, titulo.upper(), 8, "bold", "accent").grid(row=r, column=0, columnspan=3, sticky="w",
                                                                   pady=(px(10), px(2)))
            r += 1
            for nome in itens:
                self._linha(r, nome, False)
                r += 1
        rotulo(self, "OUTROS", 8, "bold", "accent").grid(row=r, column=0, columnspan=3, sticky="w",
                                                         pady=(px(10), px(2)))
        r += 1
        for _ in range(extras):
            self._linha(r, "", True)
            r += 1

    def _linha(self, r, nome, extra):
        obs, nome_var = tk.StringVar(), tk.StringVar()
        if extra:
            entrada(self, nome_var).grid(row=r, column=0, sticky="ew", pady=px(3), padx=(0, px(10)))
        else:
            rotulo(self, nome, 10, "normal", "text", wraplength=px(240)).grid(row=r, column=0, sticky="w",
                                                                              pady=px(3), padx=(0, px(10)))
        sel = SeletorStatus(self, self.rotulos)
        sel.grid(row=r, column=1, sticky="w", pady=px(3), padx=(0, px(10)))
        entrada(self, obs).grid(row=r, column=2, sticky="ew", pady=px(3))
        self.linhas.append({"sel": sel, "obs": obs, "nome": nome, "nome_var": nome_var, "extra": extra})

    def valores(self):
        saida = []
        for l in self.linhas:
            item = l["nome"] or l["nome_var"].get().strip()
            obs, cod = l["obs"].get().strip(), l["sel"].get()
            if l["extra"] and not item and not obs and not cod:
                continue
            saida.append({"item": item or "(outro)", "status": cod, "status_txt": self.rotulos.get(cod, ""),
                          "obs": obs})
        return saida

    def marcar(self, inicio_nome, cod, obs=None):
        for l in self.linhas:
            if l["nome"].startswith(inicio_nome):
                l["sel"].set(cod)
                if obs and not l["obs"].get().strip():
                    l["obs"].set(obs)
                return

    def restante_nao_necessario(self):
        for l in self.linhas:
            if not l["extra"] and not l["sel"].get():
                l["sel"].set("nao")

    def limpar(self):
        for l in self.linhas:
            l["sel"].set("")
            l["obs"].set("")
            l["nome_var"].set("")


def texto_multilinha(parent, altura, somente_leitura=False):
    caixa = tk.Frame(parent, bg=COR["bg"], highlightthickness=1, highlightbackground=COR["border"])
    t = tk.Text(caixa, height=altura, wrap="word", font=fonte(10), bg=COR["bg"] if not somente_leitura else COR["log_bg"],
                fg=COR["text"], relief="flat", borderwidth=0, padx=px(8), pady=px(6), insertbackground=COR["text"],
                selectbackground=COR["accent_soft"], selectforeground=COR["navy"], undo=True)
    t.pack(fill="both", expand=True)
    return caixa, t


class FichaPage(Pagina):
    def __init__(self, parent, app):
        super().__init__(parent, app, "Ficha do técnico",
                         "Registre o atendimento e gere o PDF para anexar ao chamado.")
        self.pdf_gerado = None
        rol = Rolagem(self.corpo)
        rol.pack(fill="both", expand=True)
        e = rol.interno
        e.columnconfigure(0, weight=1)

        # --- atendimento ---
        f = self._secao(e, "Atendimento", colunas=4)
        self.v_chamado = self._campo(f, 0, 0, "Nº do chamado")
        self.v_cliente = self._campo(f, 0, 1, "Cliente / empresa", span=2)
        self.v_tecnico = self._campo(f, 0, 3, "Técnico responsável")
        self.v_tecnico.set(app.settings.get("tecnico", ""))
        self.v_data = self._campo(f, 1, 0, "Data")
        self.v_data.set(datetime.now().strftime("%d/%m/%Y"))
        self.v_inicio = self._campo(f, 1, 1, "Início (hh:mm)")
        self.v_inicio.set(app.sessao.inicio.strftime("%H:%M"))
        self.v_fim = self._campo(f, 1, 2, "Término (hh:mm)")
        self.v_status = self._campo(f, 1, 3, "Status do chamado", opcoes=STATUS, leitura=True)
        self.v_status.set(STATUS[0])
        self.v_usuario = self._campo(f, 2, 0, "Usuário atendido", span=2, opcoes=engine.listar_perfis(), leitura=False)

        # --- equipamento ---
        f = self._secao(e, "Equipamento", colunas=4)
        self.v_host = self._campo(f, 0, 0, "Nome do computador")
        self.v_host.set(engine.nome_computador())
        self.v_tipo = self._campo(f, 0, 1, "Tipo", opcoes=TIPOS, leitura=True)
        self.v_tipo.set(TIPOS[0])
        self.v_modelo = self._campo(f, 0, 2, "Marca / modelo", span=2)
        self.v_serial = self._campo(f, 1, 0, "Nº de série")
        self.v_patr = self._campo(f, 1, 1, "Patrimônio")
        self.v_so = self._campo(f, 1, 2, "Sistema operacional", span=2)
        self.v_so.set(so_atual())

        # --- serviços e peças ---
        self.ck_serv = self._lista(e, "Serviços realizados", SERVICOS, ROT_SERVICO,
                                   "Marque a situação de cada serviço. Itens sem marcação não aparecem no PDF.")
        self.ck_pecas = self._lista(e, "Peças e hardware", PECAS, ROT_PECA,
                                    "Marque o que foi trocado e o que foi avaliado como desnecessário. Use a "
                                    "observação para modelo, capacidade ou nº de série da peça nova.")

        # --- registro automático ---
        c = Cartao(e, "Registro automático (backup e restauração)")
        c.pack(fill="x", pady=(0, px(12)))
        rotulo(c.corpo, "Texto gerado a partir das operações feitas nesta ferramenta. Ele vai para o PDF.", 9, "normal",
               "muted").pack(fill="x", pady=(0, px(6)))
        caixa, self.t_auto = texto_multilinha(c.corpo, 9, somente_leitura=True)
        caixa.pack(fill="x")
        self.t_auto.configure(state="disabled")
        linha = tk.Frame(c.corpo, bg=COR["bg"])
        linha.pack(fill="x", pady=(px(8), 0))
        self.c_incluir = Caixa(linha, "Incluir no PDF", tk.BooleanVar(value=True))
        self.c_incluir.pack(side="left")
        Botao(linha, "Importar de um backup...", self._importar, "secundario").pack(side="right")
        Botao(linha, "Atualizar", self._atualizar_auto, "secundario").pack(side="right", padx=px(8))

        # --- descrição e observações ---
        c = Cartao(e, "Descrição do técnico")
        c.pack(fill="x", pady=(0, px(12)))
        rotulo(c.corpo, "O que foi feito, em suas palavras (complementa o registro automático).", 9, "normal",
               "muted").pack(fill="x", pady=(0, px(6)))
        caixa, self.t_desc = texto_multilinha(c.corpo, 5)
        caixa.pack(fill="x")
        c = Cartao(e, "Observações gerais e pendências")
        c.pack(fill="x", pady=(0, px(12)))
        caixa, self.t_obs = texto_multilinha(c.corpo, 4)
        caixa.pack(fill="x")

        # --- rodapé ---
        Botao(self.rodape, "Limpar ficha", self._limpar, "secundario").pack(side="left")
        self.bt_abrir = Botao(self.rodape, "Abrir o último PDF", self._abrir_pdf, "secundario")
        self.bt_abrir.pack(side="left", padx=px(10))
        self.bt_abrir.ativar(False)
        Botao(self.rodape, "Gerar PDF da ficha", self._gerar, "primario").pack(side="right")

        app.sessao.ao_mudar(self.on_evento)
        self._atualizar_auto()

    # ------------------------------------------------------------------
    def _lista(self, pai, titulo, grupos, rotulos, ajuda):
        c = Cartao(pai, titulo)
        c.pack(fill="x", pady=(0, px(12)))
        topo = tk.Frame(c.corpo, bg=COR["bg"])
        topo.pack(fill="x", pady=(0, px(8)))
        rotulo(topo, ajuda, 9, "normal", "muted", wraplength=px(430)).pack(side="left", fill="x", expand=True)
        ck = ChecklistStatus(c.corpo, grupos, rotulos, extras=2)
        Botao(topo, "Marcar o restante como não necessário", ck.restante_nao_necessario, "secundario").pack(
            side="right", padx=(px(10), 0))
        ck.pack(fill="x")
        return ck

    def _secao(self, pai, titulo, colunas):
        c = Cartao(pai, titulo)
        c.pack(fill="x", pady=(0, px(12)))
        f = tk.Frame(c.corpo, bg=COR["bg"])
        f.pack(fill="x")
        for i in range(colunas):
            f.columnconfigure(i, weight=1, uniform="campo")
        return f

    def _campo(self, grade, linha, coluna, nome, span=1, opcoes=None, leitura=True):
        var = tk.StringVar()
        fr = tk.Frame(grade, bg=COR["bg"])
        fr.grid(row=linha, column=coluna, columnspan=span, sticky="ew", padx=(0, px(10)), pady=px(4))
        rotulo(fr, nome, 9, "normal", "muted").pack(fill="x")
        w = combo(fr, opcoes, var, somente_leitura=leitura) if opcoes is not None else entrada(fr, var)
        w.pack(fill="x", pady=(px(2), 0))
        return var

    @staticmethod
    def _ler(t):
        return t.get("1.0", "end").strip()

    def _auto_texto(self):
        return descrever_sessao(self.app.sessao.eventos)

    def _atualizar_auto(self):
        texto = self._auto_texto() or ("Nenhuma operação registrada ainda. Faça um backup ou uma restauração, ou use "
                                       '"Importar de um backup..." para trazer o registro de um backup antigo.')
        self.t_auto.configure(state="normal")
        self.t_auto.delete("1.0", "end")
        self.t_auto.insert("1.0", texto)
        self.t_auto.configure(state="disabled")

    def on_evento(self, ev):
        """Chamado quando um backup/restauração termina (ou é importado)."""
        self._atualizar_auto()
        if not self.v_usuario.get().strip() and ev.get("usuario"):
            self.v_usuario.set(ev["usuario"])
        if ev.get("tipo") == "backup":
            self.ck_serv.marcar("Backup dos arquivos", "feito", f"Perfil {ev.get('usuario', '')}")
        elif ev.get("tipo") == "restauracao":
            self.ck_serv.marcar("Restauração dos arquivos", "feito", f"Perfil {ev.get('usuario', '')}")
            if ev.get("opcoes", {}).get("drivers"):
                self.ck_serv.marcar("Atualização de drivers", "feito", "Drivers do backup instalados")

    def registrar_programas(self, nomes):
        """Chamado pela janela de softwares: registra os programas reinstalados."""
        self.ck_serv.marcar("Instalação de programas", "feito", f"{len(nomes)} programa(s) da lista do backup")
        texto = "Programas reinstalados a partir da lista do backup: " + ", ".join(nomes) + "."
        atual = self._ler(self.t_desc)
        self.t_desc.insert("end", ("\n\n" if atual else "") + texto)

    def _importar(self):
        pasta = filedialog.askdirectory(title="Escolha a pasta de um backup (COMPUTADOR_usuario_data)")
        if not pasta:
            return
        evs = engine.carregar_eventos(pasta)
        if not evs:
            messagebox.showinfo("Importar", "Esta pasta não tem registro de operações (_meta\\eventos.json).")
            return
        novos = sum(1 for ev in evs if self.app.sessao.add(ev))
        messagebox.showinfo("Importar", f"{novos} operação(ões) importada(s)." if novos
                            else "Essas operações já estavam na ficha.")

    # ------------------------------------------------------------------
    def _coletar(self):
        fim = self.v_fim.get().strip() or datetime.now().strftime("%H:%M")
        return {
            "chamado": self.v_chamado.get().strip(), "cliente": self.v_cliente.get().strip(),
            "tecnico": self.v_tecnico.get().strip(), "data": self.v_data.get().strip(),
            "inicio": self.v_inicio.get().strip(), "fim": fim, "status": self.v_status.get(),
            "usuario_atendido": self.v_usuario.get().strip(),
            "equipamento": {"hostname": self.v_host.get().strip(), "tipo": self.v_tipo.get(),
                            "modelo": self.v_modelo.get().strip(), "serial": self.v_serial.get().strip(),
                            "patrimonio": self.v_patr.get().strip(), "so": self.v_so.get().strip()},
            "servicos": self.ck_serv.valores(), "pecas": self.ck_pecas.valores(),
            "registro_auto": self._auto_texto() if self.c_incluir.get() else "",
            "descricao": self._ler(self.t_desc), "obs_gerais": self._ler(self.t_obs),
        }

    def _gerar(self):
        ficha = self._coletar()
        if not ficha["chamado"] and not messagebox.askyesno("Ficha", "O número do chamado está vazio. Gerar o PDF "
                                                                   "mesmo assim?"):
            return
        base = re.sub(r"[^\w\-]+", "_", ficha["chamado"] or "sem_chamado")
        sugestao = f"Ficha_{base}_{ficha['equipamento']['hostname'] or 'PC'}_{datetime.now():%Y%m%d}.pdf"
        caminho = filedialog.asksaveasfilename(title="Salvar a ficha em PDF", defaultextension=".pdf",
                                               initialfile=sugestao, filetypes=[("PDF", "*.pdf")],
                                               initialdir=self.app.settings.get("pasta_pdf", "") or None)
        if not caminho:
            return
        try:
            from .pdf_ficha import gerar_pdf
            gerar_pdf(caminho, ficha, resource_path(os.path.join("assets", "logo.png")))
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Ficha", f"Não foi possível gerar o PDF:\n\n{e}")
            return
        self.pdf_gerado = caminho
        self.bt_abrir.ativar(True)
        self.app.settings.set("tecnico", ficha["tecnico"])
        self.app.settings.set("pasta_pdf", os.path.dirname(caminho))
        if messagebox.askyesno("Ficha gerada", f"PDF salvo em:\n{caminho}\n\nDeseja abri-lo agora?"):
            self._abrir_pdf()

    def _abrir_pdf(self):
        if self.pdf_gerado and os.path.isfile(self.pdf_gerado):
            os.startfile(self.pdf_gerado)  # noqa: S606

    def _limpar(self):
        if not messagebox.askyesno("Limpar ficha", "Apagar tudo o que foi preenchido nesta ficha?"):
            return
        for v in (self.v_chamado, self.v_cliente, self.v_fim, self.v_modelo, self.v_serial, self.v_patr,
                  self.v_usuario):
            v.set("")
        self.v_status.set(STATUS[0])
        for ck in (self.ck_serv, self.ck_pecas):
            ck.limpar()
        self.t_desc.delete("1.0", "end")
        self.t_obs.delete("1.0", "end")
        self.app.sessao.eventos.clear()
        self._atualizar_auto()

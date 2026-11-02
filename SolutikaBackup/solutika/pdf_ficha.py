# -*- coding: utf-8 -*-
"""Gera o PDF da ficha de atendimento técnico (para anexar ao chamado)."""
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from . import APP_NAME, APP_VERSION

NAVY = colors.HexColor("#2B2F80")
BLUE = colors.HexColor("#1E7FD8")
TEXT = colors.HexColor("#1B2340")
MUTED = colors.HexColor("#6A7491")
LINE = colors.HexColor("#DDE3EE")
SOFT = colors.HexColor("#F4F7FC")

ST_BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=9, leading=12.5, textColor=TEXT, alignment=TA_LEFT)
ST_SMALL = ParagraphStyle("small", parent=ST_BASE, fontSize=8, leading=10.5, textColor=MUTED)
ST_LABEL = ParagraphStyle("label", parent=ST_BASE, fontSize=7.5, leading=9.5, textColor=MUTED)
ST_VALUE = ParagraphStyle("value", parent=ST_BASE, fontSize=9.5, leading=12.5)
ST_H = ParagraphStyle("h", parent=ST_BASE, fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=NAVY)
ST_TITLE = ParagraphStyle("title", parent=ST_BASE, fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=NAVY, alignment=TA_RIGHT)
ST_SUB_R = ParagraphStyle("subr", parent=ST_BASE, fontSize=8, leading=10.5, textColor=MUTED, alignment=TA_RIGHT)


def _p(txt, style=ST_BASE):
    txt = escape(str(txt or "")).replace("\n", "<br/>")
    return Paragraph(txt, style)


def _titulo_secao(texto):
    t = Table([[_p(texto.upper(), ST_H)]], colWidths=[180 * mm])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 1.2, BLUE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _campos(pares, colunas=2):
    """Grade de campos (rótulo pequeno em cima, valor embaixo)."""
    larg = 180 * mm / colunas
    linhas, atual = [], []
    for rot, val in pares:
        atual.append([_p(rot, ST_LABEL), _p(val or "—", ST_VALUE)])
        if len(atual) == colunas:
            linhas.append(atual)
            atual = []
    if atual:
        while len(atual) < colunas:
            atual.append(["", ""])
        linhas.append(atual)
    dados = [[c for c in linha] for linha in linhas]
    t = Table(dados, colWidths=[larg] * colunas)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
    ]))
    return t


COR_STATUS = {"feito": colors.HexColor("#1E9E6A"), "nao": MUTED, "pend": colors.HexColor("#C98A00")}


def _checklist(titulo, linhas, rotulos):
    """linhas: dicts {item, status ('feito'|'nao'|'pend'|''), status_txt, obs}. Itens sem situação nem
    observação não aparecem. 'rotulos' são os nomes plurais usados no resumo."""
    uteis = [l for l in linhas if l.get("status") or l.get("obs")]
    cont = {k: sum(1 for l in uteis if l.get("status") == k) for k in ("feito", "nao", "pend")}
    resumo = "  •  ".join(f"{cont[k]} {rot}" for k, rot in zip(("feito", "nao", "pend"), rotulos) if cont[k])
    saida = [_titulo_secao(titulo), Spacer(1, 3)]
    if not uteis:
        return saida + [_p("Nenhum item registrado.", ST_SMALL)]
    if resumo:
        saida += [_p(resumo, ST_SMALL), Spacer(1, 3)]
    dados = [[_p("ITEM", ST_LABEL), _p("SITUAÇÃO", ST_LABEL), _p("OBSERVAÇÃO", ST_LABEL)]]
    for l in uteis:
        cor = COR_STATUS.get(l.get("status"), MUTED).hexval()[2:]
        txt = escape(l.get("status_txt") or "—")
        sit = Paragraph(f'<font color="#{cor}"><b>{txt}</b></font>', ST_BASE)
        dados.append([_p(l.get("item", ""), ST_BASE), sit, _p(l.get("obs", ""), ST_BASE)])
    t = Table(dados, colWidths=[62 * mm, 30 * mm, 88 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("BACKGROUND", (0, 0), (-1, 0), SOFT),
    ]))
    return saida + [t]


class _NumeradaCanvas(rl_canvas.Canvas):
    """Canvas que permite escrever 'Página X de Y' no rodapé."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for estado in self._saved:
            self.__dict__.update(estado)
            self._rodape(total)
            super().showPage()
        super().save()

    def _rodape(self, total):
        self.setStrokeColor(LINE)
        self.setLineWidth(0.5)
        self.line(15 * mm, 14 * mm, 195 * mm, 14 * mm)
        self.setFont("Helvetica", 7.5)
        self.setFillColor(MUTED)
        self.drawString(15 * mm, 9.5 * mm, f"Gerado por {APP_NAME} {APP_VERSION} em {datetime.now():%d/%m/%Y %H:%M}")
        self.drawRightString(195 * mm, 9.5 * mm, f"Página {self._pageNumber} de {total}")


def gerar_pdf(caminho, ficha, logo_path=None):
    """Cria o PDF. 'ficha' é o dicionário montado pela tela da ficha do técnico."""
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm,
                            bottomMargin=20 * mm, title=f"Ficha de atendimento {ficha.get('chamado', '')}",
                            author=ficha.get("tecnico", "") or "Solutika Tecnologia")
    el = []

    # Cabeçalho
    logo = ""
    if logo_path:
        try:
            logo = Image(logo_path, width=52 * mm, height=52 * mm * 224 / 788)
        except Exception:  # noqa: BLE001 - logo é opcional
            logo = ""
    titulo = [_p("Ficha de Atendimento Técnico", ST_TITLE),
              _p(f"Chamado nº {ficha.get('chamado') or '—'}  •  {ficha.get('data', '')}", ST_SUB_R)]
    cab = Table([[logo, titulo]], colWidths=[70 * mm, 110 * mm])
    cab.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, -1), 1.6, NAVY), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    el += [cab, Spacer(1, 8)]

    # Atendimento
    horario = ficha.get("inicio", "")
    if ficha.get("fim"):
        horario = f"{horario} – {ficha['fim']}" if horario else ficha["fim"]
    el += [_titulo_secao("Atendimento"), Spacer(1, 2), _campos([
        ("CLIENTE / EMPRESA", ficha.get("cliente")), ("TÉCNICO RESPONSÁVEL", ficha.get("tecnico")),
        ("DATA", ficha.get("data")), ("HORÁRIO", horario),
        ("USUÁRIO ATENDIDO", ficha.get("usuario_atendido")), ("STATUS DO CHAMADO", ficha.get("status")),
    ]), Spacer(1, 8)]

    # Equipamento
    eq = ficha.get("equipamento", {})
    el += [_titulo_secao("Equipamento"), Spacer(1, 2), _campos([
        ("NOME DO COMPUTADOR", eq.get("hostname")), ("TIPO", eq.get("tipo")),
        ("MARCA / MODELO", eq.get("modelo")), ("Nº DE SÉRIE", eq.get("serial")),
        ("PATRIMÔNIO", eq.get("patrimonio")), ("SISTEMA OPERACIONAL", eq.get("so")),
    ]), Spacer(1, 8)]

    # Registro automático + descrição
    auto = (ficha.get("registro_auto") or "").strip()
    if auto:
        blocos = [_titulo_secao("Registro automático (backup e restauração)"), Spacer(1, 3)]
        for par in auto.split("\n\n"):
            blocos += [_p(par, ST_BASE), Spacer(1, 4)]
        el += blocos + [Spacer(1, 4)]
    desc = (ficha.get("descricao") or "").strip()
    if desc:
        el += [_titulo_secao("Descrição do técnico"), Spacer(1, 3), _p(desc), Spacer(1, 8)]

    # Serviços e peças (com situação: realizado / não necessário / pendente)
    for chave, titulo_sec, rotulos in (
            ("servicos", "Serviços realizados", ("realizado(s)", "não necessário(s)", "pendente(s)")),
            ("pecas", "Peças e hardware", ("trocada(s)", "não necessária(s)", "aguardando peça"))):
        el += [KeepTogether(_checklist(titulo_sec, ficha.get(chave) or [], rotulos)), Spacer(1, 8)]

    obs = (ficha.get("obs_gerais") or "").strip()
    if obs:
        el += [_titulo_secao("Observações gerais e pendências"), Spacer(1, 3), _p(obs), Spacer(1, 8)]

    # Assinaturas
    ass = Table([[_p("Técnico responsável", ST_LABEL), "", _p("Cliente / usuário atendido", ST_LABEL)],
                 [_p(ficha.get("tecnico") or "", ST_SMALL), "", _p(ficha.get("usuario_atendido") or "", ST_SMALL)]],
                colWidths=[80 * mm, 20 * mm, 80 * mm], rowHeights=[None, None])
    ass.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (0, 0), 0.7, MUTED), ("LINEABOVE", (2, 0), (2, 0), 0.7, MUTED),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    el += [KeepTogether([Spacer(1, 26), ass])]

    doc.build(el, canvasmaker=_NumeradaCanvas)
    return caminho

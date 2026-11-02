# -*- coding: utf-8 -*-
"""Transforma os eventos de backup/restauração em texto para a ficha do técnico."""
from datetime import datetime


def _dt(iso):
    try:
        return datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None


def _quando(iso):
    d = _dt(iso)
    return f"{d:%d/%m/%Y} às {d:%H:%M}" if d else "data não registrada"


def _gb(nbytes):
    return f"{nbytes / (1024 ** 3):.2f}".replace(".", ",") + " GB"


def _int(n):
    return f"{int(n):,}".replace(",", ".")


def _dur(seg):
    seg = int(seg or 0)
    return f"{seg // 3600:02d}:{(seg % 3600) // 60:02d}:{seg % 60:02d}"


def _lista(itens):
    itens = [i for i in itens if i]
    if not itens:
        return ""
    if len(itens) == 1:
        return itens[0]
    return "; ".join(itens[:-1]) + " e " + itens[-1]


def descrever_backup(ev):
    op = ev.get("opcoes", {})
    inclui = ["arquivos do usuário (Desktop, Documentos, Downloads, Imagens e demais pastas)"]
    z = ev.get("appdata_zip")
    modo = ev.get("appdata_modo") or ("essencial" if op.get("so_roaming") else "completo")
    rotulo_modo = {"completo": "AppData completo (Roaming e Local, sem caches)",
                   "essencial": "AppData essencial (somente Roaming)"}.get(modo)
    if rotulo_modo:
        if z:
            inclui.append(f"{rotulo_modo}, compactado em AppData.zip ({_gb(z.get('zip_bytes', 0))}, "
                          f"{_int(z.get('arquivos', 0))} arquivos)")
        else:
            inclui.append(rotulo_modo + (", copiado pasta a pasta" if op.get("compactar") is False else ""))
    if ev.get("navegadores"):
        inclui.append("navegadores (" + "; ".join(ev["navegadores"]) + ") com histórico, favoritos, preenchimento e "
                      "logins, sem arquivos de cache")
    if "softwares" in ev:
        inclui.append(f"inventário de softwares ({_int(ev['softwares'])}) e impressoras ({ev.get('impressoras', 0)})")
    if "drivers" in ev:
        inclui.append(f"drivers do Windows exportados ({ev['drivers']} pacotes)")

    ignora = []
    pastas = ev.get("pastas") or {}
    if pastas.get("salvas"):
        inclui.append("pastas do perfil salvas: " + ", ".join(pastas["salvas"]))
    if pastas.get("ignoradas"):
        ignora.append("pastas do perfil desmarcadas: " + ", ".join(pastas["ignoradas"]))
    if op.get("so_roaming"):
        ignora.append("AppData\\Local (levado apenas o AppData\\Roaming)")
    if modo == "nenhum":
        ignora.append("AppData (configurações dos programas)")
    if not ev.get("navegadores"):
        ignora.append("dados dos navegadores")

    t = (f"BACKUP: em {_quando(ev.get('inicio'))} foi realizado o backup do perfil do usuário "
         f"{ev.get('usuario', '?')} ({ev.get('origem', '')}) no computador {ev.get('maquina', '?')}, "
         f"com destino em {ev.get('destino', '')}. ")
    t += "Itens incluídos: " + _lista(inclui) + ". "
    if ignora:
        t += "Itens ignorados: " + _lista(ignora) + ". "
    if ev.get("navegadores_fechados"):
        t += "Navegadores abertos foram fechados para copiar histórico e logins. "
    t += f"Duração: {_dur(ev.get('duracao_s'))}. "
    if ev.get("resultado") == "ok":
        t += "Resultado: backup concluído e validado, sem pendências entre origem e destino."
    else:
        t += (f"Resultado: backup INCOMPLETO ({ev.get('pendentes', 0)} item(ns) pendente(s) na validação); "
              "a formatação não deve ser feita antes de revisar.")
    for a in ev.get("avisos", []):
        t += f" Aviso: {a}."
    return t


def descrever_restauracao(ev):
    op = ev.get("opcoes", {})
    feito = []
    if op.get("arquivos"):
        s = "arquivos do usuário copiados de volta ao perfil"
        if op.get("nao_sobrescrever_novos"):
            s += " (arquivos mais novos no destino foram mantidos)"
        feito.append(s)
    if op.get("appdata"):
        feito.append(f"AppData restaurado ({_int(ev.get('appdata_arquivos', 0))} arquivos extraídos)")
    if op.get("drivers"):
        s = "drivers do backup instalados"
        if ev.get("reiniciar"):
            s += " (reinicialização necessária)"
        feito.append(s)
    t = (f"RESTAURAÇÃO: em {_quando(ev.get('inicio'))} foi realizada a restauração do backup "
         f"{ev.get('backup', '')} no perfil do usuário {ev.get('usuario', '?')} ({ev.get('destino', '')}), "
         f"no computador {ev.get('maquina', '?')}. ")
    t += "Itens restaurados: " + (_lista(feito) or "nenhum") + ". "
    if ev.get("programas_fechados"):
        t += "Navegadores/Outlook/Teams abertos foram fechados antes da restauração. "
    t += f"Duração: {_dur(ev.get('duracao_s'))}. "
    res = ev.get("resultado")
    if res == "ok":
        t += "Resultado: restauração concluída sem avisos."
    elif res == "warn":
        t += "Resultado: restauração concluída com avisos."
    else:
        t += "Resultado: restauração com FALHAS; necessário revisar."
    for a in ev.get("avisos", []):
        t += f" Aviso: {a}."
    t += " Programas instalados não são restaurados automaticamente."
    return t


def descrever_evento(ev):
    if ev.get("tipo") == "backup":
        return descrever_backup(ev)
    if ev.get("tipo") == "restauracao":
        return descrever_restauracao(ev)
    return ""


def descrever_sessao(eventos):
    """Texto completo (um parágrafo por operação, em ordem cronológica)."""
    ordenados = sorted(eventos, key=lambda e: e.get("inicio", ""))
    return "\n\n".join(t for t in (descrever_evento(e) for e in ordenados) if t)

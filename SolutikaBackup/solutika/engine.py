# -*- coding: utf-8 -*-
"""
Motor de backup e restauração (sem interface gráfica).

Tudo roda em uma thread separada (Job) e conversa com a interface por uma fila
de eventos:
    ("phase", id, estado)   estado: run | ok | err | skip | pend
    ("status", texto)
    ("log", texto, nivel)   nivel: info | ok | warn | error | muted | accent
    ("dest", caminho)
    ("done", resultado, dados)   resultado: ok | warn | fail | cancel
"""
import csv
import json
import os
import queue
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from datetime import datetime

IS_WIN = sys.platform == "win32"
OEM = "oem" if IS_WIN else "utf-8"
CREATE_NO_WINDOW = 0x08000000 if IS_WIN else 0

BACKUP_FASES = [
    ("prep", "Preparar as pastas de destino"),
    ("nav", "Fechar os navegadores"),
    ("drv", "Exportar os drivers"),
    ("inv", "Inventário de softwares e impressoras"),
    ("zip", "Compactar o AppData (.zip)"),
    ("cp", "Copiar os arquivos do usuário"),
    ("val", "Validar origem x destino"),
    ("rel", "Gerar o relatório final"),
]
RESTORE_FASES = [
    ("prep", "Verificar o backup e o perfil de destino"),
    ("prog", "Fechar navegadores, Outlook e Teams"),
    ("arq", "Copiar os arquivos do usuário"),
    ("app", "Restaurar o AppData"),
    ("drv", "Instalar os drivers"),
    ("fim", "Gerar o relatório da restauração"),
]

BROWSER_EXES = ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"]
RESTORE_EXES = BROWSER_EXES + ["outlook.exe", "olk.exe", "ms-teams.exe", "teams.exe"]

# Pastas de cache/lixo que não precisam ser migradas (relativas ao perfil)
REL_EXCLUDE = [
    r"AppData\Local\Temp", r"AppData\Local\CrashDumps", r"AppData\Local\Packages",
    r"AppData\Local\Microsoft\Windows\INetCache",
    r"AppData\Local\Google\Chrome\User Data\Default\Cache",
    r"AppData\Local\Google\Chrome\User Data\Default\Code Cache",
    r"AppData\Local\Google\Chrome\User Data\Default\GPUCache",
    r"AppData\Local\Microsoft\Edge\User Data\Default\Cache",
    r"AppData\Local\Microsoft\Edge\User Data\Default\Code Cache",
    r"AppData\Local\Microsoft\Edge\User Data\Default\GPUCache",
    r"AppData\Roaming\Microsoft\Teams\Cache",
    r"AppData\Roaming\Microsoft\Teams\Service Worker",
]
CHROMIUM = [
    ("Chrome", r"AppData\Local\Google\Chrome\User Data"),
    ("Edge", r"AppData\Local\Microsoft\Edge\User Data"),
    ("Brave", r"AppData\Local\BraveSoftware\Brave-Browser\User Data"),
]
CACHE_SUB = ["Cache", "Code Cache", "GPUCache", "DawnCache", r"Service Worker\CacheStorage",
             r"Service Worker\ScriptCache", "Media Cache"]
CACHE_RAIZ = ["ShaderCache", "GrShaderCache", "GraphiteDawnCache", "Crashpad", "component_crx_cache"]
EXCLUDE_FILES = ["*.ost", "*.tmp", "Thumbs.db", "NTUSER.DAT*", "UsrClass.dat*"]

USERS_ROOT = os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, "Users")
PERFIS_IGNORADOS = {"public", "default", "default user", "all users"}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
class Cancelado(Exception):
    pass


def agora_iso():
    return datetime.now().isoformat(timespec="seconds")


def fmt_int(n):
    return f"{int(n):,}".replace(",", ".")


def fmt_gb(nbytes):
    return f"{nbytes / (1024 ** 3):.2f}".replace(".", ",") + " GB"


def fmt_dur(seg):
    seg = int(seg)
    return f"{seg // 3600:02d}:{(seg % 3600) // 60:02d}:{seg % 60:02d}"


def nome_computador():
    return os.environ.get("COMPUTERNAME") or socket.gethostname()


def pasta_usuario(usuario):
    return os.path.join(USERS_ROOT, usuario)


def listar_perfis(somente=None):
    """Perfis em C:\\Users. Se 'somente' for informado, devolve só esse (usuário sem admin)."""
    try:
        nomes = [d for d in os.listdir(USERS_ROOT) if os.path.isdir(os.path.join(USERS_ROOT, d))]
    except OSError:
        nomes = []
    nomes = [n for n in nomes if n.lower() not in PERFIS_IGNORADOS]
    if somente:
        nomes = [n for n in nomes if n.lower() == somente.lower()]
    return sorted(nomes, key=str.lower)


def limpar_barra(path):
    p = path.rstrip("\\/")
    if re.fullmatch(r"[A-Za-z]:", p):
        p += "\\"
    return p or path


def sys32(exe):
    """Evita o redirecionamento do System32 quando o Python é 32 bits em Windows 64."""
    if IS_WIN and os.environ.get("PROCESSOR_ARCHITEW6432"):
        cand = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Sysnative", exe)
        if os.path.exists(cand):
            return cand
    return exe


def espaco_livre(path):
    p = os.path.abspath(path)
    while p and not os.path.exists(p):
        pai = os.path.dirname(p)
        if pai == p:
            break
        p = pai
    try:
        return shutil.disk_usage(p).free
    except OSError:
        return -1


def lp(path):
    """Prefixo \\\\?\\ para aceitar caminhos longos no Windows."""
    if not IS_WIN:
        return path
    p = os.path.abspath(path)
    if p.startswith("\\\\?\\"):
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p


if IS_WIN:
    import ctypes
    from ctypes import wintypes
    import msvcrt

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                 wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    _k32.CreateFileW.restype = wintypes.HANDLE
    _INVALID = ctypes.c_void_p(-1).value


def abrir_leitura(path):
    """Abre para leitura permitindo que outros programas continuem usando o arquivo."""
    if IS_WIN:
        h = _k32.CreateFileW(lp(path), 0x80000000, 0x7, None, 3, 0x80, None)
        if h is None or h == _INVALID:
            raise OSError(ctypes.get_last_error(), "arquivo em uso ou sem permissão", path)
        fd = msvcrt.open_osfhandle(h, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        return os.fdopen(fd, "rb")
    return open(path, "rb")


# ---------------------------------------------------------------------------
# Contexto de execução (thread de trabalho)
# ---------------------------------------------------------------------------
class Ctx:
    def __init__(self, q):
        self.q = q
        self.cancel_event = threading.Event()
        self._procs = []
        self._lock = threading.Lock()
        self._arquivo_log = None

    # --- mensagens para a interface ---
    def phase(self, pid, st):
        self.q.put(("phase", pid, st))

    def status(self, txt):
        self.q.put(("status", txt))

    def log(self, txt, nivel="info"):
        self.q.put(("log", txt, nivel))
        if self._arquivo_log:
            try:
                with open(self._arquivo_log, "a", encoding="utf-8-sig") as f:
                    f.write(f"{datetime.now():%H:%M:%S}  {txt}\n")
            except OSError:
                pass

    def arquivo_log(self, caminho):
        self._arquivo_log = caminho

    def dest(self, path):
        self.q.put(("dest", path))

    # --- controle ---
    def check(self):
        if self.cancel_event.is_set():
            raise Cancelado()

    def sleep(self, seg):
        fim = time.monotonic() + seg
        while time.monotonic() < fim:
            self.check()
            time.sleep(0.2)

    def cancel(self):
        self.cancel_event.set()
        with self._lock:
            procs = list(self._procs)
        for p in procs:
            try:
                p.terminate()
            except OSError:
                pass

    def run_lines(self, cmd, on_line=None):
        """Executa um programa, entrega cada linha de saída e devolve o código de retorno."""
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        with self._lock:
            self._procs.append(p)
        try:
            for raw in iter(p.stdout.readline, b""):
                linha = raw.decode(OEM, "replace").rstrip("\r\n")
                if on_line:
                    on_line(linha)
            p.wait()
            return p.returncode
        finally:
            with self._lock:
                if p in self._procs:
                    self._procs.remove(p)


class Job:
    """Executa uma função do motor em segundo plano."""

    def __init__(self, func, *args):
        self.q = queue.Queue()
        self.ctx = Ctx(self.q)
        self.func = func
        self.args = args
        self.thread = threading.Thread(target=self._main, daemon=True)

    def start(self):
        self.thread.start()

    def cancel(self):
        self.ctx.cancel()

    def _main(self):
        try:
            resultado, dados = self.func(self.ctx, *self.args)
        except Cancelado:
            resultado, dados = "cancel", {}
            self.ctx.log("Operação cancelada pelo técnico.", "warn")
        except Exception as e:  # noqa: BLE001 - qualquer falha vira mensagem na tela
            import traceback
            self.ctx.log(f"ERRO FATAL: {e}", "error")
            self.ctx.log(traceback.format_exc(), "muted")
            resultado, dados = "fail", {"erro": str(e)}
        self.q.put(("done", resultado, dados))


# ---------------------------------------------------------------------------
# Filtros de pastas/arquivos e varredura
# ---------------------------------------------------------------------------
def _norm(p):
    return os.path.normcase(os.path.normpath(p))


def _name_match(nome, pat):
    n, p = nome.lower(), pat.lower()
    if p.startswith("*"):
        return n.endswith(p[1:])
    if p.endswith("*"):
        return n.startswith(p[:-1])
    return n == p


class Filtro:
    def __init__(self, xd, xf):
        self.completos = set()
        self.nomes = []
        for x in xd:
            if "\\" in x or "/" in x:
                self.completos.add(_norm(x))
            else:
                self.nomes.append(x)
        self.xf = list(xf)

    def pasta_excluida(self, full, nome):
        if _norm(full) in self.completos:
            return True
        return any(_name_match(nome, n) for n in self.nomes)

    def arquivo_excluido(self, nome):
        return any(_name_match(nome, x) for x in self.xf)


def andar(raiz, filtro, ao_ignorar, check=None):
    """Percorre as pastas respeitando exclusões; ignora links e arquivos só-na-nuvem."""
    pilha = [raiz]
    while pilha:
        if check:
            check()
        d = pilha.pop()
        try:
            itens = list(os.scandir(lp(d)))
        except OSError:
            ao_ignorar(d)
            continue
        for e in itens:
            full = os.path.join(d, e.name)
            try:
                st = e.stat(follow_symlinks=False)
                eh_pasta = e.is_dir(follow_symlinks=False)
            except OSError:
                ao_ignorar(full)
                continue
            attrs = getattr(st, "st_file_attributes", 0)
            if eh_pasta:
                if attrs & 0x400 or stat.S_ISLNK(st.st_mode):
                    continue
                if filtro.pasta_excluida(full, e.name):
                    continue
                pilha.append(full)
            else:
                if filtro.arquivo_excluido(e.name):
                    continue
                if attrs & (0x400000 | 0x40000 | 0x400):  # placeholders de nuvem / links
                    continue
                yield full, st


def _subpastas(path):
    try:
        return [(e.name, os.path.join(path, e.name)) for e in os.scandir(path) if e.is_dir()]
    except OSError:
        return []


def _junta(base, rel):
    return os.path.join(base, *rel.split("\\"))


NAVEGADORES = ["Chrome", "Edge", "Brave", "Firefox"]
TITULOS_NAV = {"Chrome": "Google Chrome", "Edge": "Microsoft Edge", "Brave": "Brave", "Firefox": "Mozilla Firefox"}


def navegadores_do_usuario(usuario):
    """Navegadores encontrados no perfil, com a quantidade de perfis de cada um."""
    origem = pasta_usuario(usuario)
    res = []
    for nome, rel in CHROMIUM:
        raiz = _junta(origem, rel)
        if os.path.isdir(raiz):
            perfis = [f for _, f in _subpastas(raiz) if os.path.isfile(os.path.join(f, "Preferences"))]
            res.append({"nome": nome, "titulo": TITULOS_NAV[nome], "perfis": len(perfis)})
    ff = os.path.join(origem, "AppData", "Roaming", "Mozilla", "Firefox", "Profiles")
    if os.path.isdir(ff):
        res.append({"nome": "Firefox", "titulo": TITULOS_NAV["Firefox"], "perfis": len(_subpastas(ff))})
    return res


def navegadores_escolhidos(p):
    lista = p.get("navegadores_lista")
    if lista is None:  # compatibilidade com a versão antiga (um único "incluir navegadores")
        lista = NAVEGADORES if p.get("navegadores", True) else []
    return [n for n in lista if n in NAVEGADORES]


def modo_appdata(p):
    """completo = Roaming + Local | essencial = só Roaming | nenhum = sem AppData."""
    m = p.get("appdata_modo")
    if m in ("completo", "essencial", "nenhum"):
        return m
    return "essencial" if p.get("so_roaming") else "completo"


def montar_exclusoes(origem, base, p):
    """Devolve (pastas excluídas, arquivos excluídos, navegadores incluídos)."""
    xd = [_junta(origem, r) for r in REL_EXCLUDE]
    for nome in p.get("excluir_pastas") or []:  # pastas do perfil desmarcadas pelo técnico
        xd.append(os.path.join(origem, nome))
    modo = modo_appdata(p)
    nav = navegadores_escolhidos(p)
    roaming = os.path.join(origem, "AppData", "Roaming")
    local = os.path.join(origem, "AppData", "Local")
    if modo != "completo":
        # Local só entra quando um navegador Chromium escolhido precisa dele
        manter = set()
        if "Chrome" in nav:
            manter.add("Google")
        if "Brave" in nav:
            manter.add("BraveSoftware")
        if "Edge" in nav:
            manter.add("Microsoft")
        for nome, full in _subpastas(local):
            if nome not in manter:
                xd.append(full)
        if "Edge" in nav:
            for nome, full in _subpastas(os.path.join(local, "Microsoft")):
                if nome != "Edge":
                    xd.append(full)
    if modo == "nenhum":
        manter_r = {"Mozilla"} if "Firefox" in nav else set()
        for nome, full in _subpastas(roaming):
            if nome not in manter_r:
                xd.append(full)
        if not nav:
            xd.append(os.path.join(origem, "AppData"))
    nav_log = []
    for nome, rel in CHROMIUM:
        raiz = _junta(origem, rel)
        if not os.path.isdir(raiz):
            continue
        if nome not in nav:
            xd.append(raiz)
            continue
        perfis = [f for _, f in _subpastas(raiz) if os.path.isfile(os.path.join(f, "Preferences"))]
        nav_log.append(f"{nome}: {len(perfis)} perfil(is)")
        for pf in perfis:
            for c in CACHE_SUB:
                xd.append(_junta(pf, c))
        for c in CACHE_RAIZ:
            xd.append(os.path.join(raiz, c))
    ff_roam = os.path.join(roaming, "Mozilla", "Firefox", "Profiles")
    ff_local = os.path.join(local, "Mozilla", "Firefox", "Profiles")
    if os.path.isdir(ff_roam):
        if "Firefox" in nav:
            nav_log.append(f"Firefox: {len(_subpastas(ff_roam))} perfil(is)")
        else:
            xd.append(os.path.join(roaming, "Mozilla", "Firefox"))
    if os.path.isdir(ff_local):
        xd.append(ff_local)
    xd.append(base)  # nunca copiar o próprio backup
    return xd, list(EXCLUDE_FILES), nav_log


_SHELL_FOLDERS = {"Desktop": "Desktop", "Personal": "Documents", "My Pictures": "Pictures", "My Music": "Music",
                  "My Video": "Videos", "{374DE290-123F-4565-9164-39C4925E467B}": "Downloads"}


def _sid_do_perfil(usuario):
    if not IS_WIN:
        return None
    import winreg
    alvo = os.path.normcase(os.path.normpath(pasta_usuario(usuario)))
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList") as k:
            i = 0
            while True:
                try:
                    sid = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(k, sid) as sk:
                        caminho = winreg.QueryValueEx(sk, "ProfileImagePath")[0]
                    if os.path.normcase(os.path.normpath(os.path.expandvars(caminho))) == alvo:
                        return sid
                except OSError:
                    continue
    except OSError:
        pass
    return None


def pastas_conhecidas(usuario):
    """Onde o Windows guarda Desktop, Documentos, Downloads, Imagens, Músicas e Vídeos deste usuário.
    Lê o registro do usuário (carrega o NTUSER.DAT se ele não estiver logado). Pode apontar para
    OneDrive ou até outro disco."""
    if not IS_WIN:
        return []
    import winreg
    perfil = pasta_usuario(usuario)
    sub = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
    valores = {}

    def ler(raiz):
        with winreg.OpenKey(winreg.HKEY_USERS, raiz + "\\" + sub) as k:
            for nome in _SHELL_FOLDERS:
                try:
                    valores[nome] = winreg.QueryValueEx(k, nome)[0]
                except OSError:
                    pass

    lido = False
    sid = _sid_do_perfil(usuario)
    if sid:
        try:
            ler(sid)
            lido = True
        except OSError:
            lido = False
    if not lido:
        ntuser = os.path.join(perfil, "NTUSER.DAT")
        if os.path.isfile(ntuser):
            subprocess.run(["reg", "load", r"HKU\SolutikaTmp", ntuser], capture_output=True,
                           creationflags=CREATE_NO_WINDOW)
            try:
                ler("SolutikaTmp")
            except OSError:
                pass
            finally:
                import gc
                gc.collect()
                for _ in range(4):
                    r = subprocess.run(["reg", "unload", r"HKU\SolutikaTmp"], capture_output=True,
                                       creationflags=CREATE_NO_WINDOW)
                    if r.returncode == 0:
                        break
                    time.sleep(0.5)
    res = []
    for chave, padrao in _SHELL_FOLDERS.items():
        v = valores.get(chave)
        if not v:
            continue
        v = re.sub(r"%USERPROFILE%", lambda _m: perfil, v, flags=re.I)
        v = os.path.normpath(os.path.expandvars(v))
        res.append({"nome": padrao, "caminho": v, "existe": os.path.isdir(v),
                    "dentro": (_norm(v) + os.sep).startswith(_norm(perfil) + os.sep)})
    return res


def _tem_arquivo(path, xf=()):
    """True se existe ao menos um arquivo (que não seja de um tipo excluído) dentro da pasta."""
    pilha = [path]
    while pilha:
        d = pilha.pop()
        try:
            it = os.scandir(lp(d))
        except OSError:
            continue
        with it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        pilha.append(os.path.join(d, e.name))
                    elif not any(_name_match(e.name, x) for x in xf):
                        return True
                except OSError:
                    continue
    return False


PASTAS_IGNORADAS = {"appdata", "application data", "local settings", "cookies", "nethood", "printhood", "recent",
                    "sendto", "start menu", "templates", "my documents"}


def _eh_juncao(e):
    try:
        if e.is_symlink():
            return True
        if hasattr(e, "is_junction"):
            return e.is_junction()
        attrs = getattr(e.stat(follow_symlinks=False), "st_file_attributes", 0)
        return bool(attrs & 0x400) and not e.name.lower().startswith("onedrive")
    except OSError:
        return False


def pastas_do_perfil(usuario):
    """Pastas de primeiro nível do perfil que entram no backup (sem AppData e sem junções antigas)."""
    try:
        itens = list(os.scandir(pasta_usuario(usuario)))
    except OSError:
        return []
    nomes = []
    for e in itens:
        try:
            if not e.is_dir(follow_symlinks=False) or _eh_juncao(e):
                continue
        except OSError:
            continue
        if e.name.lower() not in PASTAS_IGNORADAS:
            nomes.append(e.name)
    return sorted(nomes, key=str.lower)


def onedrive_conteudo(usuario):
    """{pasta OneDrive: [subpastas]} para mostrar ao técnico o que está sincronizado lá dentro."""
    origem = pasta_usuario(usuario)
    return {n: sorted((x for x, _ in _subpastas(os.path.join(origem, n))), key=str.lower)
            for n in pastas_do_perfil(usuario) if n.lower().startswith("onedrive")}


def _resumo_pastas(ctx, usuario, origem, dest_usuario, base, excluidas):
    """Confere pasta por pasta o que entrou no backup. Devolve (salvas, ignoradas, faltando)."""
    salvas, ignoradas, faltando = [], [], []
    exc = {n.lower() for n in excluidas}
    ctx.log("Pastas do perfil:")
    for nome in pastas_do_perfil(usuario):
        full = os.path.join(origem, nome)
        if nome.lower() in exc:
            ignoradas.append(nome)
            ctx.log(f"   \u2013  {nome}: ignorada por escolha", "muted")
        elif _norm(full) == _norm(base):
            ignoradas.append(nome)
            ctx.log(f"   \u2013  {nome}: é a própria pasta de destino do backup", "muted")
        elif os.path.isdir(os.path.join(dest_usuario, nome)):
            if _tem_arquivo(full, EXCLUDE_FILES) and not _tem_arquivo(os.path.join(dest_usuario, nome)):
                faltando.append(nome)
                ctx.log(f"   \u2716  {nome}: tem arquivos na origem, mas está VAZIA no backup!", "error")
            else:
                salvas.append(nome)
                ctx.log(f"   \u2714  {nome}", "ok")
        else:
            try:
                vazia = not any(True for _ in os.scandir(full))
            except OSError:
                vazia = False
            if vazia:
                salvas.append(nome)
                ctx.log(f"   \u2714  {nome} (vazia)", "muted")
            else:
                faltando.append(nome)
                ctx.log(f"   \u2716  {nome}: NÃO foi copiada!", "error")
    return salvas, ignoradas, faltando


# ---------------------------------------------------------------------------
# Programas abertos, inventário, drivers
# ---------------------------------------------------------------------------
def _executando(nomes):
    try:
        r = subprocess.run([sys32("tasklist.exe"), "/FO", "CSV", "/NH"], capture_output=True,
                           timeout=30, creationflags=CREATE_NO_WINDOW)
        texto = r.stdout.decode(OEM, "replace").lower()
    except (OSError, subprocess.SubprocessError):
        return []
    achados = []
    for n in nomes:
        if f'"{n.lower()}"' in texto:
            achados.append(n)
    return achados


def fechar_programas(ctx, nomes, espera=8):
    abertos = _executando(nomes)
    if not abertos:
        return []
    ctx.log("Fechando programas abertos: " + ", ".join(abertos), "info")
    for n in abertos:
        subprocess.run([sys32("taskkill.exe"), "/IM", n], capture_output=True, creationflags=CREATE_NO_WINDOW)
    ctx.sleep(espera)
    for n in _executando(abertos):
        subprocess.run([sys32("taskkill.exe"), "/F", "/IM", n], capture_output=True, creationflags=CREATE_NO_WINDOW)
    return abertos


def _softwares_registro():
    itens = []
    if not IS_WIN:
        return itens
    import winreg
    caminho = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    for visao in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            chave = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, caminho, 0, winreg.KEY_READ | visao)
        except OSError:
            continue
        with chave:
            i = 0
            while True:
                try:
                    nome_sub = winreg.EnumKey(chave, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(chave, nome_sub) as sub:
                        def val(n):
                            try:
                                return str(winreg.QueryValueEx(sub, n)[0])
                            except OSError:
                                return ""
                        nome = val("DisplayName")
                        if nome:
                            itens.append((nome, val("DisplayVersion"), val("Publisher")))
                except OSError:
                    continue
    return sorted(set(itens), key=lambda t: t[0].lower())


def _impressoras():
    if not IS_WIN:
        return []
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
           "Get-Printer | Select-Object Name,DriverName,PortName | ConvertTo-Csv -NoTypeInformation"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=60, creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return []
    texto = r.stdout.decode("utf-8", "replace")
    linhas = list(csv.reader(texto.splitlines()))
    return linhas[1:] if len(linhas) > 1 else []


def gerar_inventario(meta):
    softs = _softwares_registro()
    with open(os.path.join(meta, "softwares.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["DisplayName", "DisplayVersion", "Publisher"])
        w.writerows(softs)
    imps = _impressoras()
    with open(os.path.join(meta, "impressoras.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Name", "DriverName", "PortName"])
        w.writerows(imps)
    return len(softs), len(imps)


def ler_inventario(pasta_backup):
    """Lê os CSVs do inventário: ([(nome, versao, editor)], [(nome, driver, porta)])."""
    meta = os.path.join(pasta_backup, "_meta")

    def ler(nome, n):
        try:
            with open(os.path.join(meta, nome), "r", encoding="utf-8-sig", newline="") as f:
                linhas = list(csv.reader(f))[1:]
        except OSError:
            return []
        return [tuple((l + [""] * n)[:n]) for l in linhas if l]

    return ler("softwares.csv", 3), ler("impressoras.csv", 3)


_RE_SISTEMA = re.compile(r"visual c\+\+|\.net|runtime|redistributable|webview2|windows (sdk|software development|"
                         r"driver package)|update for|hotfix|security update|\bkb\d{6,}|edge update|vcredist|directx",
                         re.I)
_RE_DRIVER = re.compile(r"driver|nvidia|realtek|intel\(r\)|intel®|\bamd\b|qualcomm|mediatek|chipset|bluetooth|"
                        r"graphics|wi-?fi|audio", re.I)


def classificar_software(nome):
    """Programas | Drivers e hardware | Componentes do sistema (para filtrar a lista do técnico)."""
    if _RE_SISTEMA.search(nome):
        return "Componentes do sistema"
    if _RE_DRIVER.search(nome):
        return "Drivers e hardware"
    return "Programas"


def _exportar_drivers(ctx, destino, estado):
    try:
        os.makedirs(destino, exist_ok=True)
        linhas = []
        rc = ctx.run_lines([sys32("dism.exe"), "/online", "/export-driver", f"/destination:{destino}"], linhas.append)
        estado["rc"] = rc
        estado["pacotes"] = len(_subpastas(destino))
        estado["linhas"] = [l for l in linhas if l.strip()][-4:]
    except Cancelado:
        estado["cancelado"] = True
    except Exception as e:  # noqa: BLE001
        estado["erro"] = str(e)
    finally:
        estado["done"] = True


# ---------------------------------------------------------------------------
# Compactação / extração do AppData
# ---------------------------------------------------------------------------
def _zip_thread(ctx, raiz, zip_path, filtro, stats):
    def ignorar(p):
        stats["ignorados"] += 1
        if len(stats["lista"]) < 50:
            stats["lista"].append(p)

    ultimo = time.monotonic()
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as zf:
            for full, st in andar(raiz, filtro, ignorar, ctx.check):
                rel = os.path.relpath(full, raiz).replace(os.sep, "/")
                try:
                    src = abrir_leitura(full)
                except OSError:
                    ignorar(full)
                    continue
                with src:
                    t = time.localtime(st.st_mtime)
                    data = (max(t[0], 1980),) + tuple(t[1:6])
                    zi = zipfile.ZipInfo(rel, date_time=data)
                    zi.compress_type = zipfile.ZIP_DEFLATED
                    zi.external_attr = 0o600 << 16
                    zi.file_size = st.st_size
                    try:
                        with zf.open(zi, "w", force_zip64=st.st_size > 0xFFFFFFFE) as dst:
                            shutil.copyfileobj(src, dst, 1024 * 1024)
                    except Cancelado:
                        raise
                    except Exception:  # noqa: BLE001
                        ignorar(full)
                        continue
                stats["arquivos"] += 1
                stats["bytes"] += st.st_size
                if time.monotonic() - ultimo > 0.6:
                    ultimo = time.monotonic()
                    ctx.status(f"Compactando o AppData... {fmt_int(stats['arquivos'])} arquivos "
                               f"({fmt_int(stats['bytes'] // (1024 * 1024))} MB lidos)")
        stats["ok"] = True
    except Cancelado:
        stats["cancelado"] = True
    except Exception as e:  # noqa: BLE001
        stats["erro"] = str(e)
    finally:
        stats["done"] = True


def extrair_appdata(ctx, zip_path, destino_raiz, stats):
    raiz = os.path.abspath(destino_raiz)
    raiz_n = _norm(raiz) + os.sep
    ultimo = time.monotonic()

    def ignorar(p):
        stats["ignorados"] += 1
        if len(stats["lista"]) < 50:
            stats["lista"].append(p)

    with zipfile.ZipFile(zip_path) as zf:
        infos = zf.infolist()
        stats["total"] = len(infos)
        for i, zi in enumerate(infos):
            ctx.check()
            alvo = os.path.abspath(os.path.join(raiz, zi.filename.replace("/", os.sep)))
            if not (_norm(alvo) + os.sep).startswith(raiz_n):
                ignorar(zi.filename)  # proteção contra caminhos maliciosos
                continue
            try:
                if zi.is_dir():
                    os.makedirs(lp(alvo), exist_ok=True)
                    continue
                os.makedirs(lp(os.path.dirname(alvo)), exist_ok=True)
                with zf.open(zi) as src, open(lp(alvo), "wb") as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                try:
                    ts = time.mktime(zi.date_time + (0, 0, -1))
                    os.utime(lp(alvo), (ts, ts))
                except (OSError, OverflowError, ValueError):
                    pass
                stats["arquivos"] += 1
            except OSError:
                ignorar(alvo)
            if time.monotonic() - ultimo > 0.6:
                ultimo = time.monotonic()
                ctx.status(f"Restaurando o AppData... {fmt_int(i + 1)} de {fmt_int(len(infos))} itens")


# ---------------------------------------------------------------------------
# Registro de eventos (alimenta a ficha do técnico)
# ---------------------------------------------------------------------------
def salvar_evento(meta, ev):
    caminho = os.path.join(meta, "eventos.json")
    lista = []
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            lista = json.load(f)
        if not isinstance(lista, list):
            lista = []
    except (OSError, ValueError):
        lista = []
    lista.append(ev)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)


def carregar_eventos(pasta_backup):
    caminho = os.path.join(pasta_backup, "_meta", "eventos.json")
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return [e for e in dados if isinstance(e, dict)] if isinstance(dados, list) else []
    except (OSError, ValueError):
        return []


# ---------------------------------------------------------------------------
# Estimativa de tamanho
# ---------------------------------------------------------------------------
def _robocopy():
    return shutil.which("robocopy") or sys32("robocopy.exe")


def run_estimate(ctx, p):
    usuario = p["usuario"]
    base = limpar_barra(os.path.normpath(p["destino"]))
    origem = pasta_usuario(usuario)
    xd, xf, _ = montar_exclusoes(origem, base, p)
    ctx.status("Estimando o tamanho do backup (pode levar alguns minutos)...")
    ctx.log(f"Estimando o tamanho de {origem} (já aplicando as exclusões)...")
    total = None
    if shutil.which("robocopy") or IS_WIN:
        nulo = os.path.join(tempfile.gettempdir(), "bk_nulo")
        linhas = []
        args = [_robocopy(), origem, nulo, "/L", "/E", "/XJ", "/R:0", "/W:0", "/BYTES", "/NJH", "/NFL", "/NDL",
                "/NP", "/XD"] + xd + ["/XF"] + xf
        ctx.run_lines(args, linhas.append)
        ctx.check()
        for l in linhas:
            if re.search(r"(Bytes|Files|Arquivos|Dirs|Pastas)", l):
                ctx.log(l.strip(), "muted")
        for l in linhas:
            m = re.search(r"Bytes\s*:\s*(\d+)", l)
            if m:
                total = int(m.group(1))
                break
    if total is None:
        ctx.log("Calculando o tamanho pelo método alternativo...", "muted")
        filtro = Filtro(xd, xf)
        total = 0
        for _, st in andar(origem, filtro, lambda _p: None, ctx.check):
            total += st.st_size
    livre = espaco_livre(base)
    ctx.log(f"Tamanho a copiar: {fmt_gb(total)}", "ok")
    if livre >= 0:
        ctx.log(f"Espaço livre no destino: {fmt_gb(livre)}", "ok")
        if total > livre * 0.9:
            ctx.log("ATENÇÃO: espaço insuficiente no destino. Escolha outro disco ou use mais exclusões.", "warn")
    else:
        ctx.log("Não foi possível checar o espaço livre do destino.", "warn")
    if p.get("compactar"):
        ctx.log("O AppData será compactado; o espaço real usado tende a ser menor que a estimativa.", "muted")
    return "ok", {"bytes": total, "livre": livre}


# ---------------------------------------------------------------------------
# BACKUP
# ---------------------------------------------------------------------------
def run_backup(ctx, p):
    inicio = datetime.now()
    t0 = time.monotonic()
    usuario = p["usuario"]
    base = limpar_barra(os.path.normpath(p["destino"]))
    origem = pasta_usuario(usuario)
    xd, xf, nav_log = montar_exclusoes(origem, base, p)
    xd_robo = list(xd) + ([os.path.join(origem, "AppData")] if p.get("compactar") else [])
    host = nome_computador()
    dest = os.path.join(base, f"{host}_{usuario}_{inicio:%Y%m%d_%H%M}")
    meta = os.path.join(dest, "_meta")
    avisos = []
    ev = {"tipo": "backup", "inicio": inicio.isoformat(timespec="seconds"), "maquina": host,
          "usuario": usuario, "origem": origem, "destino": dest, "opcoes": dict(p), "navegadores": nav_log}

    # 1) preparação
    ctx.phase("prep", "run")
    ctx.status("Preparando as pastas de destino...")
    if not os.path.isdir(origem):
        raise RuntimeError(f"Perfil de origem não encontrado: {origem}")
    os.makedirs(meta, exist_ok=True)
    ctx.arquivo_log(os.path.join(meta, "registro_backup.txt"))
    ctx.dest(dest)
    ctx.log(f"Destino: {dest}")
    if nav_log:
        ctx.log("Navegadores encontrados: " + " | ".join(nav_log))
    ctx.phase("prep", "ok")

    # 2) navegadores abertos travam histórico e logins
    nav_escolhidos = navegadores_escolhidos(p)
    modo_app = modo_appdata(p)
    ev["appdata_modo"] = modo_app
    ev["navegadores_escolhidos"] = nav_escolhidos
    if nav_escolhidos and p.get("fechar_nav"):
        ctx.phase("nav", "run")
        ctx.status("Fechando os navegadores abertos...")
        fechados = fechar_programas(ctx, BROWSER_EXES)
        ctx.log("Navegadores fechados: " + ", ".join(fechados) if fechados else "Nenhum navegador estava aberto.")
        ev["navegadores_fechados"] = fechados
        ctx.phase("nav", "ok")
    else:
        ctx.phase("nav", "skip")

    # 3) drivers em segundo plano (administrador)
    drv = None
    if p.get("drivers"):
        ctx.phase("drv", "run")
        ctx.log("Exportando drivers em segundo plano...")
        drv = {}
        threading.Thread(target=_exportar_drivers, args=(ctx, os.path.join(dest, "Drivers"), drv),
                         daemon=True).start()
    else:
        ctx.phase("drv", "skip")

    # 4) inventário
    ctx.phase("inv", "run")
    ctx.status("Gerando o inventário de softwares e impressoras...")
    try:
        n_soft, n_imp = gerar_inventario(meta)
        ev["softwares"], ev["impressoras"] = n_soft, n_imp
        ctx.log(f"Inventário salvo: {fmt_int(n_soft)} programas e {n_imp} impressora(s).", "ok")
        ctx.phase("inv", "ok")
    except Exception as e:  # noqa: BLE001
        avisos.append(f"o inventário falhou: {e}")
        ctx.log(f"AVISO: o inventário falhou: {e}", "warn")
        ctx.phase("inv", "err")

    # 5) AppData -> .zip em paralelo
    zip_path = os.path.join(dest, "AppData.zip")
    zstats = None
    appdata = os.path.join(origem, "AppData")
    if p.get("compactar") and os.path.isdir(appdata) and (modo_app != "nenhum" or nav_escolhidos):
        ctx.phase("zip", "run")
        ctx.log("Compactando o AppData em AppData.zip (em segundo plano)...")
        zstats = {"arquivos": 0, "bytes": 0, "ignorados": 0, "lista": [], "done": False}
        threading.Thread(target=_zip_thread, args=(ctx, appdata, zip_path, Filtro(xd, xf), zstats),
                         daemon=True).start()
    else:
        ctx.phase("zip", "skip")

    # 6) cópia do restante
    ctx.phase("cp", "run")
    ctx.status("Copiando os arquivos do usuário (a compactação roda em paralelo)...")
    mt = f"/MT:{int(p.get('threads', 32))}"
    ctx.log(f"Copiando os demais arquivos ({mt})...")
    t_cp = time.monotonic()
    args = [_robocopy(), origem, os.path.join(dest, "Usuario"), "/E", "/XJ", "/R:1", "/W:1", "/NP", "/NFL",
            "/NDL", "/NJH", mt, "/XD"] + xd_robo + ["/XF"] + xf

    def linha_robo(l):
        if l.strip():
            nivel = "error" if re.match(r"\s*(ERRO|ERROR)\b", l) else "muted"
            ctx.log(l.strip(), nivel)

    rc = ctx.run_lines(args, linha_robo)
    ctx.check()
    ev["robocopy_rc"] = rc
    if rc >= 8:
        ctx.log(f"ATENÇÃO: o robocopy retornou o código {rc} (houve falhas).", "warn")
        ctx.phase("cp", "err")
    else:
        ctx.log(f"Cópia concluída em {fmt_dur(time.monotonic() - t_cp)} (código {rc}).", "ok")
        ctx.phase("cp", "ok")
    # pastas do Windows (Documentos, Desktop...) redirecionadas para FORA do perfil, ex.: outro disco
    try:
        conhecidas = pastas_conhecidas(usuario)
    except Exception as e:  # noqa: BLE001
        conhecidas = []
        ctx.log(f"AVISO: não foi possível ler os locais das pastas do Windows: {e}", "warn")
    redir = []
    for k in conhecidas:
        ctx.log(f"Local de {k['nome']}: {k['caminho']}" + ("" if k["dentro"] else "  (FORA do perfil)"),
                "muted" if k["dentro"] else "accent")
        if k["existe"] and not k["dentro"] and _norm(k["caminho"]) != _norm(base) \
                and not (_norm(base) + os.sep).startswith(_norm(k["caminho"]) + os.sep):
            ctx.log(f"Copiando também {k['nome']} de {k['caminho']}...", "accent")
            alvo = os.path.join(dest, "Redirecionadas", k["nome"])
            rc2 = ctx.run_lines([_robocopy(), k["caminho"], alvo, "/E", "/XJ", "/R:1", "/W:1", "/NP", "/NFL", "/NDL",
                                 "/NJH", mt, "/XD", base, "/XF"] + xf, linha_robo)
            ctx.check()
            rc = max(rc, rc2)
            redir.append({"nome": k["nome"], "caminho": k["caminho"], "rc": rc2})
            if rc2 >= 8:
                ctx.log(f"ATENÇÃO: o robocopy retornou o código {rc2} em {k['nome']}.", "warn")
    ev["redirecionadas"] = redir
    ev["robocopy_rc"] = rc
    salvas, ignoradas, faltando = _resumo_pastas(ctx, usuario, origem, os.path.join(dest, "Usuario"), base,
                                                 p.get("excluir_pastas") or [])
    ev["pastas"] = {"salvas": salvas, "ignoradas": ignoradas, "faltando": faltando}
    if faltando:
        avisos.append("pastas do perfil que não entraram no backup: " + ", ".join(faltando))

    # 7) aguarda o zip e confere
    zip_ok = True
    if zstats is not None:
        while not zstats["done"]:
            ctx.sleep(0.5)
        ctx.check()
        if zstats.get("erro"):
            zip_ok = False
            ctx.log(f"ERRO ao compactar o AppData: {zstats['erro']}", "error")
        else:
            try:
                with zipfile.ZipFile(zip_path) as zf:
                    n = len(zf.infolist())
                if n != zstats["arquivos"]:
                    zip_ok = False
                    ctx.log(f"ERRO: o AppData.zip tem {n} itens, esperado {zstats['arquivos']}.", "error")
                else:
                    tam_zip = os.path.getsize(zip_path)
                    ctx.log(f"AppData.zip OK: {fmt_int(n)} arquivos, {fmt_gb(zstats['bytes'])} lidos, "
                            f"{fmt_gb(tam_zip)} no zip.", "ok")
                    ev["appdata_zip"] = {"arquivos": n, "bytes": zstats["bytes"], "zip_bytes": tam_zip}
            except (OSError, zipfile.BadZipFile) as e:
                zip_ok = False
                ctx.log(f"ERRO ao conferir o AppData.zip: {e}", "error")
        ctx.phase("zip", "ok" if zip_ok else "err")
        if zstats["ignorados"]:
            ev["appdata_ignorados"] = zstats["ignorados"]
            avisos.append(f"{zstats['ignorados']} arquivo(s) do AppData não puderam ser lidos (em uso ou sem permissão)")
            ctx.log(f"AVISO: {zstats['ignorados']} arquivo(s) do AppData não puderam ser lidos (em uso ou sem "
                    "permissão). Primeiros:", "warn")
            for item in zstats["lista"][:10]:
                ctx.log("   " + item, "muted")
            ctx.log("Dica: feche o Outlook e os navegadores e refaça o backup se precisar desses arquivos.", "warn")

    # 8) drivers
    if drv is not None:
        ctx.status("Aguardando a exportação dos drivers terminar...")
        while not drv.get("done"):
            ctx.sleep(0.5)
        ctx.check()
        if drv.get("erro") or drv.get("rc", 1) != 0:
            avisos.append("a exportação de drivers falhou")
            ctx.log("AVISO: a exportação de drivers falhou " + (drv.get("erro") or f"(código {drv.get('rc')})"), "warn")
            for l in drv.get("linhas", []):
                ctx.log("   " + l, "muted")
            ctx.phase("drv", "err")
        else:
            ev["drivers"] = drv.get("pacotes", 0)
            ctx.log(f"Drivers exportados: {drv.get('pacotes', 0)} pacote(s).", "ok")
            ctx.phase("drv", "ok")

    # 9) validação
    ctx.phase("val", "run")
    ctx.status("Validando origem x destino (conferindo se algo ficou para trás)...")
    ctx.log("Validando origem x destino...")
    pend = []
    args = [_robocopy(), origem, os.path.join(dest, "Usuario"), "/L", "/E", "/XJ", "/R:0", "/W:0", "/NJH", "/NJS",
            "/NDL", "/NP", "/NC", "/NS", "/XD"] + xd_robo + ["/XF"] + xf
    ctx.run_lines(args, lambda l: pend.append(l.strip()) if l.strip() else None)
    ctx.check()
    ev["pendentes"] = len(pend)
    if not pend:
        ctx.log("VALIDAÇÃO OK: nada pendente.", "ok")
        ctx.phase("val", "ok")
    else:
        ctx.log(f"VALIDAÇÃO: {len(pend)} item(ns) pendente(s). Primeiros:", "warn")
        for l in pend[:10]:
            ctx.log("   " + l, "muted")
        ctx.phase("val", "err")

    # 10) relatório
    ctx.phase("rel", "run")
    ctx.status("Gerando o relatório final...")
    ok = rc < 8 and not pend and zip_ok and not faltando
    fim = datetime.now()
    ev.update({"fim": fim.isoformat(timespec="seconds"), "duracao_s": int(time.monotonic() - t0),
               "resultado": "ok" if ok else "fail", "avisos": avisos, "zip_ok": zip_ok})
    ev["opcoes"] = {k: v for k, v in p.items()}
    zip_info = "AppData.zip: nao usado"
    if zstats is not None:
        zip_info = f"AppData.zip: {'ok' if zip_ok else 'FALHOU'}, ignorados: {zstats['ignorados']}"
    linhas = [f"Maquina: {host}", f"Usuario: {usuario}", f"Data: {fim:%d/%m/%Y %H:%M:%S}", f"Destino: {dest}",
              f"Codigo robocopy: {rc}", f"Pendentes: {len(pend)}", zip_info,
              f"Backup completo: {'SIM' if ok else 'NAO'}"]
    with open(os.path.join(meta, "relatorio.txt"), "w", encoding="utf-8-sig") as f:
        f.write("\r\n".join(linhas) + "\r\n")
    try:
        salvar_evento(meta, ev)
    except OSError as e:
        ctx.log(f"AVISO: não foi possível gravar o registro de eventos: {e}", "warn")
    ctx.phase("rel", "ok")

    if ok:
        ctx.log(">>> BACKUP COMPLETO <<<", "ok")
    else:
        ctx.log(">>> NÃO FORMATAR: revisar pendências <<<", "error")
    ctx.log(f"IMPORTANTE: o backup está nesta mesma máquina. Copie a pasta '{dest}' para o servidor "
            "(ou disco externo) ANTES de formatar.", "warn")
    if nav_log:
        ctx.log("NAVEGADORES: histórico, favoritos, preenchimento e dados de login foram copiados (sem caches).")
        ctx.log("ATENÇÃO SENHAS: Chrome/Edge protegem as senhas com a conta do Windows; após formatar elas podem NÃO "
                "abrir na máquina nova. Confirme que a sincronização está ativa ou exporte as senhas (CSV).", "warn")
        ctx.log("O backup contém dados sensíveis: restrinja o acesso à pasta.", "warn")
    return ("ok" if ok else "fail"), {"dest": dest, "evento": ev}


# ---------------------------------------------------------------------------
# RESTAURAÇÃO
# ---------------------------------------------------------------------------
def eh_backup(pasta):
    return bool(pasta) and any(os.path.exists(os.path.join(pasta, n)) for n in ("Usuario", "AppData.zip", "Drivers"))


def procurar_backups(raizes):
    """Procura pastas de backup dentro de uma lista de pastas-raiz (mais recentes primeiro)."""
    achados = []
    for raiz in raizes:
        try:
            for e in os.scandir(raiz):
                if e.is_dir() and eh_backup(e.path):
                    achados.append((e.stat().st_mtime, e.path))
        except OSError:
            continue
    achados.sort(reverse=True)
    return [p for _, p in achados]


def descrever_backup(pasta):
    """Resumo do conteúdo de um backup para mostrar na tela de restauração."""
    info = {"pasta": pasta, "nome": os.path.basename(pasta.rstrip("\\/")), "usuario": "", "maquina": "", "data": None,
            "tem_usuario": os.path.isdir(os.path.join(pasta, "Usuario")),
            "tem_zip": os.path.isfile(os.path.join(pasta, "AppData.zip")), "zip_bytes": 0,
            "tem_drivers": os.path.isdir(os.path.join(pasta, "Drivers")), "drivers": 0,
            "completo": None, "tem_softwares": os.path.isfile(os.path.join(pasta, "_meta", "softwares.csv"))}
    m = re.match(r"^([^_]+)_(.+)_(\d{8})_(\d{4})$", info["nome"])
    if m:
        info["maquina"], info["usuario"] = m.group(1), m.group(2)
        try:
            info["data"] = datetime.strptime(m.group(3) + m.group(4), "%Y%m%d%H%M")
        except ValueError:
            pass
    info["redirecionadas"] = (sorted(os.listdir(os.path.join(pasta, "Redirecionadas")))
                              if os.path.isdir(os.path.join(pasta, "Redirecionadas")) else [])
    try:
        info["pastas"] = sorted((n for n in os.listdir(os.path.join(pasta, "Usuario"))
                                 if os.path.isdir(os.path.join(pasta, "Usuario", n))), key=str.lower)
    except OSError:
        info["pastas"] = []
    if info["tem_zip"]:
        try:
            info["zip_bytes"] = os.path.getsize(os.path.join(pasta, "AppData.zip"))
        except OSError:
            pass
    if info["tem_drivers"]:
        n = 0
        for _r, _d, files in os.walk(os.path.join(pasta, "Drivers")):
            n += sum(1 for f in files if f.lower().endswith(".inf"))
        info["drivers"] = n
    rel = os.path.join(pasta, "_meta", "relatorio.txt")
    try:
        with open(rel, "r", encoding="utf-8-sig", errors="replace") as f:
            txt = f.read()
        mm = re.search(r"Backup completo:\s*(SIM|NAO)", txt)
        if mm:
            info["completo"] = mm.group(1) == "SIM"
    except OSError:
        pass
    return info


def perfil_carregado(usuario):
    """True se o usuário está com a sessão aberta neste computador."""
    if not IS_WIN:
        return False
    ps = ("(Get-CimInstance Win32_UserProfile | Where-Object { $_.LocalPath -ieq 'C:\\Users\\%s' }).Loaded"
          % usuario.replace("'", "''"))
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                           text=True, timeout=25, creationflags=CREATE_NO_WINDOW)
        return r.stdout.strip().lower() == "true"
    except (OSError, subprocess.SubprocessError):
        return False


def run_restore(ctx, p):
    inicio = datetime.now()
    t0 = time.monotonic()
    bk = p["backup"]
    usuario = p["usuario"]
    destino = pasta_usuario(usuario)
    host = nome_computador()
    avisos = []
    falhas = False
    reiniciar = False
    ev = {"tipo": "restauracao", "inicio": inicio.isoformat(timespec="seconds"), "maquina": host,
          "usuario": usuario, "backup": bk, "destino": destino, "opcoes": dict(p)}

    ctx.phase("prep", "run")
    ctx.status("Verificando o backup e o perfil de destino...")
    if not os.path.isdir(bk):
        raise RuntimeError(f"Pasta do backup não encontrada: {bk}")
    if not os.path.isdir(destino):
        raise RuntimeError(f"Perfil de destino não encontrado: {destino}")
    try:
        ctx.arquivo_log(os.path.join(bk, "_meta", f"registro_restauracao_{usuario}.txt"))
    except OSError:
        pass
    ctx.log(f"Backup:  {bk}")
    ctx.log(f"Destino: {destino}")
    ctx.phase("prep", "ok")

    if p.get("fechar"):
        ctx.phase("prog", "run")
        ctx.status("Fechando navegadores, Outlook e Teams...")
        fechados = fechar_programas(ctx, RESTORE_EXES, espera=6)
        ctx.log("Programas fechados: " + ", ".join(fechados) if fechados else "Nenhum desses programas estava aberto.")
        ev["programas_fechados"] = fechados
        ctx.phase("prog", "ok")
    else:
        ctx.phase("prog", "skip")

    # arquivos do usuário
    if p.get("arquivos"):
        ctx.phase("arq", "run")
        ctx.status("Copiando os arquivos do usuário para o perfil de destino (pode demorar)...")
        mt = f"/MT:{int(p.get('threads', 32))}"
        args = [_robocopy(), os.path.join(bk, "Usuario"), destino, "/E", "/XJ", "/R:1", "/W:1", "/NP", "/NFL",
                "/NDL", "/NJH", mt]
        if p.get("nao_sobrescrever_novos"):
            args.append("/XO")
        args += ["/XF", "NTUSER.DAT*", "UsrClass.dat*"]
        ctx.log(f"Copiando os arquivos do usuário ({mt})...")
        t_cp = time.monotonic()

        def linha_robo(l):
            if l.strip():
                ctx.log(l.strip(), "error" if re.match(r"\s*(ERRO|ERROR)\b", l) else "muted")

        rc = ctx.run_lines(args, linha_robo)
        ctx.check()
        redir_dir = os.path.join(bk, "Redirecionadas")
        if os.path.isdir(redir_dir):
            for nome in sorted(os.listdir(redir_dir)):
                ctx.log(f"Restaurando {nome} (estava fora do perfil) em {os.path.join(destino, nome)}...", "accent")
                a2 = [_robocopy(), os.path.join(redir_dir, nome), os.path.join(destino, nome), "/E", "/XJ", "/R:1",
                      "/W:1", "/NP", "/NFL", "/NDL", "/NJH", mt]
                if p.get("nao_sobrescrever_novos"):
                    a2.append("/XO")
                rc = max(rc, ctx.run_lines(a2, linha_robo))
                ctx.check()
        ev["robocopy_rc"] = rc
        if rc >= 8:
            falhas = True
            ctx.log(f"ATENÇÃO: o robocopy retornou o código {rc} (houve falhas).", "warn")
            ctx.phase("arq", "err")
        else:
            ctx.log(f"Arquivos copiados em {fmt_dur(time.monotonic() - t_cp)} (código {rc}).", "ok")
            ctx.phase("arq", "ok")
    else:
        ctx.phase("arq", "skip")

    # AppData
    if p.get("appdata"):
        ctx.phase("app", "run")
        ctx.status("Restaurando o AppData...")
        stats = {"arquivos": 0, "ignorados": 0, "lista": [], "total": 0}
        try:
            extrair_appdata(ctx, os.path.join(bk, "AppData.zip"), os.path.join(destino, "AppData"), stats)
            ev["appdata_arquivos"] = stats["arquivos"]
            ctx.log(f"AppData restaurado: {fmt_int(stats['arquivos'])} arquivos extraídos.", "ok")
            if stats["ignorados"]:
                ev["appdata_ignorados"] = stats["ignorados"]
                avisos.append(f"{stats['ignorados']} arquivo(s) do AppData não puderam ser substituídos")
                ctx.log(f"AVISO: {stats['ignorados']} arquivo(s) não puderam ser substituídos (em uso ou sem "
                        "permissão). Primeiros:", "warn")
                for item in stats["lista"][:10]:
                    ctx.log("   " + item, "muted")
                ctx.log("Dica: peça para o usuário sair da conta (logoff) e restaure só o AppData de novo.", "warn")
            ctx.phase("app", "ok")
        except Cancelado:
            raise
        except Exception as e:  # noqa: BLE001
            falhas = True
            ctx.log(f"ERRO ao restaurar o AppData: {e}", "error")
            ctx.phase("app", "err")
    else:
        ctx.phase("app", "skip")

    # drivers
    if p.get("drivers"):
        ctx.phase("drv", "run")
        ctx.status("Instalando os drivers do backup (pode levar vários minutos)...")
        ctx.log("Instalando drivers com o pnputil...")
        linhas = []
        rc = ctx.run_lines([sys32("pnputil.exe"), "/add-driver", os.path.join(bk, "Drivers", "*.inf"), "/subdirs",
                            "/install"], linhas.append)
        ctx.check()
        ev["drivers_rc"] = rc
        try:
            with open(os.path.join(tempfile.gettempdir(), "solutika_pnputil.log"), "w", encoding="utf-8") as f:
                f.write("\n".join(linhas))
        except OSError:
            pass
        for l in [x for x in linhas if x.strip()][-6:]:
            ctx.log("   " + l.strip(), "muted")
        if rc in (0, 259, 3010):
            ctx.log(f"Drivers instalados (código {rc}).", "ok")
            if rc == 3010:
                reiniciar = True
                ctx.log("Reinicie o computador para concluir a instalação dos drivers.", "warn")
            ctx.phase("drv", "ok")
        else:
            avisos.append(f"o pnputil retornou o código {rc}; alguns drivers podem não ter sido instalados")
            ctx.log(f"AVISO: o pnputil retornou o código {rc} (alguns drivers podem não ter sido instalados).", "warn")
            ctx.phase("drv", "err")
    else:
        ctx.phase("drv", "skip")

    # relatório
    ctx.phase("fim", "run")
    ctx.status("Gerando o relatório da restauração...")
    resultado = "fail" if falhas else ("warn" if avisos else "ok")
    ev.update({"fim": datetime.now().isoformat(timespec="seconds"), "duracao_s": int(time.monotonic() - t0),
               "resultado": resultado, "avisos": avisos, "reiniciar": reiniciar})
    try:
        salvar_evento(os.path.join(bk, "_meta"), ev)
        ctx.log("Registro da restauração salvo em _meta\\eventos.json.", "muted")
    except OSError:
        pass
    ctx.phase("fim", "ok")

    if p.get("appdata"):
        ctx.log("ATENÇÃO SENHAS: as senhas salvas do Chrome/Edge podem NÃO abrir se o Windows foi reinstalado. "
                "Use a sincronização da conta do navegador para recuperá-las.", "warn")
    if os.path.isfile(os.path.join(bk, "_meta", "softwares.csv")):
        ctx.log("IMPORTANTE: os programas instalados NÃO voltam sozinhos. Use a lista de softwares do backup para "
                "reinstalar o que o usuário precisa.", "warn")
    return resultado, {"evento": ev, "reiniciar": reiniciar}

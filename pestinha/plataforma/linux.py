"""
Linux (X11): xdotool e wmctrl para as janelas, xprintidle para o tempo ocioso, e pynput para o atalho.

As leituras rodam numa thread própria (o Coletor): cada comando é um subprocesso, e chamá-los
direto da thread do Qt travava a tela (~100 ms por segundo, com timeout de 1 s cada). As funções
públicas só leem o último valor coletado, então nunca bloqueiam o desenho.

A ordem de empilhamento e as janelas minimizadas vêm do próprio X11 (_NET_CLIENT_LIST_STACKING
e _NET_WM_STATE, pelo python-xlib): o `wmctrl -l` lista na ordem em que as janelas abriram, não
de cima para baixo. Janelas de outra área de trabalho ficam de fora.

Em Wayland a maior parte dessas leituras não existe: o pet continua andando, mas não enxerga as janelas
nem o tempo ocioso (fica como se você estivesse sempre ativo). Os comandos são opcionais; se faltarem,
a leitura correspondente vira o valor padrão. O atalho global só ouve teclas de janelas X11.
"""

import os
import shutil
import threading
import time

import psutil

from ..log import log
from ._comum import atalho_pynput, rodar

LARGURA_MINIMA, ALTURA_MINIMA = 120, 60
INTERVALO_OCIOSO = 0.1        # s entre leituras do xprintidle (o app lê a cada 100 ms)
INTERVALO_ATIVA = 0.5         # s entre leituras da janela ativa
INTERVALO_JANELAS = 0.25      # s entre leituras da lista de janelas
INTERVALO_TELA = 5.0          # s entre leituras do tamanho da tela

# no Wayland o pynput só ouve as teclas de programas X11 (XWayland)
LIMITACAO_ATALHO = ("no Wayland o atalho de pânico só funciona com janelas X11; use o menu da bandeja"
                    if os.environ.get("WAYLAND_DISPLAY") else None)


# ---------------- leitura das saídas (puras, testadas) ----------------

def parse_geometria(texto):
    """Retângulo (l, t, r, b) a partir de `xdotool getwindowgeometry --shell` (linhas CHAVE=valor)."""
    campos = {}
    for linha in (texto or "").splitlines():
        if "=" in linha:
            chave, valor = linha.split("=", 1)
            campos[chave.strip()] = valor.strip()
    try:
        x, y = int(campos["X"]), int(campos["Y"])
        return (x, y, x + int(campos["WIDTH"]), y + int(campos["HEIGHT"]))
    except (KeyError, ValueError):
        return None


def parse_wmctrl(texto, meu_pid, excluir, desktop_atual=None):
    """
    [(id, (l, t, r, b), False)] de `wmctrl -lGp`: id desktop pid x y largura altura host título.
    O título é descartado na hora (nunca sai daqui). Com `desktop_atual`, só fica a área de
    trabalho atual e as janelas fixas em todas (desktop -1).
    """
    achadas = []
    for linha in (texto or "").splitlines():
        partes = linha.split(None, 8)
        if len(partes) < 8:
            continue
        try:
            janela_id, desktop, pid = int(partes[0], 16), int(partes[1]), int(partes[2])
            x, y, largura, altura = (int(v) for v in partes[3:7])
        except ValueError:
            continue
        if pid == meu_pid or janela_id in excluir or largura < LARGURA_MINIMA or altura < ALTURA_MINIMA:
            continue
        if desktop_atual is not None and desktop not in (-1, desktop_atual):
            continue
        achadas.append((janela_id, (x, y, x + largura, y + altura), False))
    return achadas


def parse_desktop_atual(texto):
    """Índice da área de trabalho atual em `wmctrl -d` (a linha marcada com *), ou None."""
    for linha in (texto or "").splitlines():
        partes = linha.split()
        if len(partes) >= 2 and partes[1] == "*":
            try:
                return int(partes[0])
            except ValueError:
                return None
    return None


def ordenar_pelo_x11(achadas, empilhamento, escondidas):
    """
    Põe as janelas de cima para baixo e tira as minimizadas, segundo o X11.
    `empilhamento`: ids de baixo para cima (_NET_CLIENT_LIST_STACKING). Janelas que o X11 não
    conhece (por exemplo, ids de um compositor que lista também as janelas Wayland) mantêm a
    ordem do wmctrl, depois das conhecidas.
    """
    posicao = {janela: i for i, janela in enumerate(reversed(empilhamento))}      # 0 = topo
    visiveis = [a for a in achadas if a[0] not in escondidas]
    conhecidas = sorted((a for a in visiveis if a[0] in posicao), key=lambda a: posicao[a[0]])
    return conhecidas + [a for a in visiveis if a[0] not in posicao]


def cobre_algum_monitor(rect, monitores):
    """Diz se o retângulo cobre inteiro algum dos monitores (l, t, r, b)."""
    return any(rect[0] <= m[0] and rect[1] <= m[1] and rect[2] >= m[2] and rect[3] >= m[3]
               for m in monitores)


# ---------------- X11 direto (empilhamento e minimizadas) ----------------

class _X11:
    """Conexão ao X11 só para ler o empilhamento e o estado das janelas (python-xlib, opcional)."""

    def __init__(self):
        """Abre a conexão; sem python-xlib ou sem servidor X, fica desligado (devolve vazio)."""
        self.display = None
        try:
            from Xlib import X, display, error
        except ImportError:
            return
        self._X, self._erros = X, (error.XError, error.DisplayError, error.ConnectionClosedError, OSError)
        try:
            self.display = display.Display()
        except self._erros:
            self.display = None
            return
        atom = self.display.intern_atom
        self._empilhamento = atom("_NET_CLIENT_LIST_STACKING")
        self._estado = atom("_NET_WM_STATE")
        self._escondida = atom("_NET_WM_STATE_HIDDEN")

    def ler(self):
        """(ids de baixo para cima, ids minimizados). Vazio se não der para ler."""
        if self.display is None:
            return [], set()
        try:
            raiz = self.display.screen().root
            prop = raiz.get_full_property(self._empilhamento, self._X.AnyPropertyType)
            ids = [int(w) for w in prop.value] if prop else []
            escondidas = set()
            for janela in ids:
                estado = self.display.create_resource_object("window", janela).get_full_property(
                    self._estado, self._X.AnyPropertyType)
                if estado is not None and self._escondida in estado.value:
                    escondidas.add(janela)
        except self._erros:
            return [], set()
        return ids, escondidas


# ---------------- coletor em segundo plano ----------------

class Coletor:
    """Roda os comandos do sistema numa thread própria e guarda o último resultado de cada um."""

    def __init__(self):
        """Descobre quais comandos existem (uma vez só) e começa vazio."""
        self.tem = {cmd: shutil.which(cmd) is not None for cmd in ("xprintidle", "xdotool", "wmctrl")}
        self.ocioso = (0.0, time.monotonic())     # (segundos ociosos, quando foi lido)
        self.processo = "unknown"
        self.retangulo = None
        self.tela = None
        self.janelas = []                         # parse_wmctrl já ordenado, sem `excluir`
        self._proximo = {"ocioso": 0.0, "ativa": 0.0, "janelas": 0.0, "tela": 0.0}
        self._x11 = None
        self._thread = None

    def iniciar(self):
        """Faz uma leitura completa agora (o app começa com dados reais) e liga a thread."""
        self.passo(time.monotonic())
        self._thread = threading.Thread(target=self._laco, name="pestinha-sentidos", daemon=True)
        self._thread.start()

    def _laco(self):
        """Laço da thread: cada leitura no seu intervalo; um erro inesperado não mata os sentidos."""
        while True:
            try:
                self.passo(time.monotonic())
            except (OSError, ValueError, psutil.Error) as erro:
                log(f"[senses] leitura falhou: {erro}")
            time.sleep(0.05)

    def passo(self, agora):
        """Faz as leituras que já venceram."""
        if agora >= self._proximo["ocioso"]:
            self._proximo["ocioso"] = agora + INTERVALO_OCIOSO
            self._ler_ocioso(agora)
        if agora >= self._proximo["tela"]:
            self._proximo["tela"] = agora + INTERVALO_TELA
            self._ler_tela()
        if agora >= self._proximo["ativa"]:
            self._proximo["ativa"] = agora + INTERVALO_ATIVA
            self._ler_ativa()
        if agora >= self._proximo["janelas"]:
            self._proximo["janelas"] = agora + INTERVALO_JANELAS
            self._ler_janelas()

    def _ler_ocioso(self, agora):
        """Tempo ocioso pelo xprintidle (sem ele: 0, como se você estivesse sempre ativo)."""
        if not self.tem["xprintidle"]:
            return
        texto = (rodar(["xprintidle"]) or "").strip()
        if texto.isdigit():
            self.ocioso = (int(texto) / 1000.0, agora)

    def _ler_tela(self):
        """Tamanho da tela X inteira (usado só quando o Qt não informa os monitores)."""
        if not self.tem["xdotool"]:
            return
        partes = (rodar(["xdotool", "getdisplaygeometry"]) or "").split()
        if len(partes) == 2 and all(v.isdigit() for v in partes):
            self.tela = (0, 0, int(partes[0]), int(partes[1]))

    def _ler_ativa(self):
        """Programa e retângulo da janela ativa."""
        if not self.tem["xdotool"]:
            return
        janela = (rodar(["xdotool", "getactivewindow"]) or "").strip()
        if not janela:
            self.processo, self.retangulo = "unknown", None
            return
        pid = (rodar(["xdotool", "getwindowpid", janela]) or "").strip()
        try:
            self.processo = psutil.Process(int(pid)).name().lower()
        except (ValueError, psutil.Error):
            self.processo = "unknown"
        self.retangulo = parse_geometria(rodar(["xdotool", "getwindowgeometry", "--shell", janela]))

    def _ler_janelas(self):
        """Janelas visíveis da área de trabalho atual, de cima para baixo."""
        if not self.tem["wmctrl"]:
            self.janelas = []
            return
        desktop = parse_desktop_atual(rodar(["wmctrl", "-d"]))
        achadas = parse_wmctrl(rodar(["wmctrl", "-lGp"]), os.getpid(), set(), desktop)
        if self._x11 is None:
            self._x11 = _X11()
        empilhamento, escondidas = self._x11.ler()
        self.janelas = ordenar_pelo_x11(achadas, empilhamento, escondidas)


_coletor = None
_trava = threading.Lock()


def _dados():
    """O coletor, criado (e ligado) na primeira leitura."""
    global _coletor  # noqa: PLW0603 - um único por processo (singleton de módulo)
    with _trava:
        if _coletor is None:
            novo = Coletor()
            novo.iniciar()
            _coletor = novo
        return _coletor


def _monitores():
    """Retângulos físicos dos monitores pelo Qt no X11; fora dele (offscreen, Wayland), a tela X inteira."""
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.instance() is not None and QGuiApplication.platformName() == "xcb":
        monitores = []
        for tela in QGuiApplication.screens():
            g, dpr = tela.geometry(), tela.devicePixelRatio()
            monitores.append((g.x() * dpr, g.y() * dpr, (g.x() + g.width()) * dpr, (g.y() + g.height()) * dpr))
        if monitores:
            return monitores
    tela = _dados().tela
    return [tela] if tela else []


# ---------------- interface da plataforma ----------------

def ocioso_segundos():
    """Segundos sem teclado e mouse (último xprintidle + o tempo desde a leitura); 0 sem xprintidle."""
    dados = _dados()
    if not dados.tem["xprintidle"]:
        return 0.0
    valor, quando = dados.ocioso
    return valor + max(0.0, time.monotonic() - quando)


def processo_ativo():
    """Nome do programa da janela ativa (último lido pelo coletor)."""
    return _dados().processo


def retangulo_ativo(escala=1.0):
    """Retângulo da janela ativa (pixels físicos, já é a escala do X11), ou None."""
    del escala
    return _dados().retangulo


def tela_cheia():
    """Diz se a janela ativa cobre inteiro o monitor onde está (qualquer monitor, não a tela X toda)."""
    rect = _dados().retangulo
    return rect is not None and cobre_algum_monitor(rect, _monitores())


def janelas_visiveis(excluir, escala=1.0):
    """Janelas visíveis de outros programas, de cima para baixo (sem as do próprio pet)."""
    del escala
    return [j for j in _dados().janelas if j[0] not in excluir]


def sem_foco_nativo(janela_id):
    """O X11 não tem um jeito padrão de pedir isso: a janela do pet usa só as flags do Qt."""
    del janela_id


_display_ui = None          # conexão da thread do Qt (o Xlib não pode ser dividido entre threads)


def regiao_de_clique(janela_id, retangulos):
    """
    Só os `retangulos` (x, y, largura, altura) da janela recebem o mouse; no resto, o clique passa
    para a janela de baixo. É a forma de ENTRADA do XShape: o desenho não é cortado (os Zzz e a
    borda suave continuam aparecendo). Sem python-xlib ou sem X11, não faz nada.
    """
    global _display_ui  # noqa: PLW0603 - um único por processo (singleton de módulo)
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.platformName() != "xcb":
        return False            # offscreen/Wayland: o id não é uma janela X11 (poderia ser a de outro programa)
    try:
        from Xlib import X, display, error
        from Xlib.ext import shape
    except ImportError:
        return False
    erros = (error.XError, error.DisplayError, error.ConnectionClosedError, OSError)
    try:
        if _display_ui is None:
            _display_ui = display.Display()
        if not _display_ui.has_extension("SHAPE"):
            return False
        janela = _display_ui.create_resource_object("window", janela_id)
        janela.shape_rectangles(shape.SO.Set, shape.SK.Input, X.Unsorted, 0, 0,
                                [{"x": x, "y": y, "width": w, "height": h} for x, y, w, h in retangulos])
        _display_ui.flush()
    except erros:
        return False
    return True


def iniciar_atalho(callback):
    """Registra Ctrl+Alt+Shift+B pelo pynput; devolve True se conseguiu."""
    return atalho_pynput(callback)

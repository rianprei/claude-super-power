"""
Linux: o próprio X11 (python-xlib) para as janelas e o tempo ocioso, e pynput para o atalho.

Nada de comando externo: antes eram xdotool, wmctrl e xprintidle, que a maioria das distros não instala
(sem eles o pet não via nada), e o wmctrl somava a posição da janela duas vezes. As leituras rodam numa
thread própria (o Coletor), com uma conexão X só dela; as funções públicas só leem o último valor
coletado, então nunca bloqueiam o desenho.

A ordem de empilhamento, as minimizadas e a área de trabalho vêm das propriedades padrão (EWMH):
_NET_CLIENT_LIST_STACKING, _NET_WM_STATE, _NET_WM_DESKTOP e _NET_CURRENT_DESKTOP.

Numa sessão Wayland o pet roda pelo XWayland (preparar_qt): no Wayland nativo uma janela não pode se
posicionar nem ficar por cima, e ele não andaria. Pelo XWayland ele só enxerga as janelas X11. O tempo
ocioso vem do X (MIT-SCREEN-SAVER) ou, no GNOME Wayland, do Mutter (gdbus); no KDE Wayland não há como
ler e fica 0, como se você estivesse sempre ativo. O atalho global só ouve teclas de janelas X11.
"""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Any

import psutil

from ..log import log
from ._comum import atalho_pynput, rodar

LARGURA_MINIMA, ALTURA_MINIMA = 120, 60
INTERVALO_OCIOSO = 0.1        # s entre leituras do tempo ocioso pelo X (o app lê a cada 100 ms)
INTERVALO_OCIOSO_GNOME = 1.0  # s entre leituras pelo gdbus (um subprocesso por leitura)
INTERVALO_ATIVA = 0.5         # s entre leituras da janela ativa
INTERVALO_JANELAS = 0.25      # s entre leituras da lista de janelas
INTERVALO_TELA = 5.0          # s entre leituras do tamanho da tela
TODAS_AS_AREAS = 0xFFFFFFFF   # _NET_WM_DESKTOP de uma janela fixa em todas as áreas de trabalho
OCIOSO_GNOME = ["gdbus", "call", "--session", "--dest", "org.gnome.Mutter.IdleMonitor",
                "--object-path", "/org/gnome/Mutter/IdleMonitor/Core",
                "--method", "org.gnome.Mutter.IdleMonitor.GetIdletime"]

# no Wayland o pynput só ouve as teclas de programas X11 (XWayland)
LIMITACAO_ATALHO = ("no Wayland o atalho de pânico só funciona com janelas X11; use o menu da bandeja"
                    if os.environ.get("WAYLAND_DISPLAY") else None)


def preparar_qt():
    """Antes do QApplication: numa sessão Wayland com XWayland, o pet abre como janela X11.

    No Wayland nativo uma janela não escolhe a própria posição nem fica por cima das outras: o pet não
    andaria. Quem já escolheu a plataforma (QT_QPA_PLATFORM) é respeitado.
    """
    if os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY") and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "xcb"


# ---------------- leituras puras (testadas) ----------------

def parse_ocioso_gnome(texto):
    """Segundos ociosos a partir da resposta do Mutter, `(uint64 1234,)` em ms; None se não veio."""
    achado = re.search(r"\(uint64 (\d+),\)", texto or "")
    return int(achado.group(1)) / 1000.0 if achado else None


def filtrar_janelas(janelas, meu_pid, desktop_atual):
    """
    [(id, (l, t, r, b), False)] das janelas de outros programas, na ordem recebida (de cima para baixo).
    `janelas`: [(id, (l, t, r, b), pid, desktop, minimizada)]. Ficam de fora o próprio pet, as minimizadas,
    as pequenas (menus, balões) e as de outra área de trabalho (as fixas em todas ficam).
    """
    achadas = []
    for janela_id, rect, pid, desktop, minimizada in janelas:
        if pid == meu_pid or minimizada:
            continue
        if rect[2] - rect[0] < LARGURA_MINIMA or rect[3] - rect[1] < ALTURA_MINIMA:
            continue
        if desktop_atual is not None and desktop not in (None, desktop_atual, TODAS_AS_AREAS):
            continue
        achadas.append((janela_id, rect, False))
    return achadas


def cobre_algum_monitor(rect, monitores):
    """Diz se o retângulo cobre inteiro algum dos monitores (l, t, r, b)."""
    return any(rect[0] <= m[0] and rect[1] <= m[1] and rect[2] >= m[2] and rect[3] >= m[3]
               for m in monitores)


# ---------------- X11 direto ----------------

class _X11:
    """Conexão ao X11 (python-xlib) para as leituras; sem python-xlib ou sem servidor X, devolve vazio."""

    ATOMOS = ("_NET_CLIENT_LIST_STACKING", "_NET_WM_STATE", "_NET_WM_STATE_HIDDEN", "_NET_ACTIVE_WINDOW",
              "_NET_WM_PID", "_NET_WM_DESKTOP", "_NET_CURRENT_DESKTOP")

    def __init__(self, conectar=True):
        """Abre a conexão (`conectar=False`: desligado, para os testes não lerem o desktop de verdade)."""
        self.display: Any = None            # Xlib.display.Display (o python-xlib não tem tipos)
        self.tem_ocioso = False
        if not conectar:
            return
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
        self.raiz = self.display.screen().root
        self._atomo = {nome: self.display.intern_atom(nome) for nome in self.ATOMOS}
        self.tem_ocioso = self.display.has_extension("MIT-SCREEN-SAVER")     # o XWayland não tem

    def _prop(self, janela, nome):
        """Valores (lista de inteiros) da propriedade `nome` da janela; vazia se ela não tem."""
        valor = janela.get_full_property(self._atomo[nome], self._X.AnyPropertyType)
        return list(valor.value) if valor is not None else []

    def _janela(self, janela_id):
        return self.display.create_resource_object("window", janela_id)

    def _retangulo(self, janela):
        """(l, t, r, b) na tela: o canto vem de translate_coords (a geometria é relativa à moldura)."""
        tamanho = janela.get_geometry()
        canto = self.raiz.translate_coords(janela, 0, 0)
        return (canto.x, canto.y, canto.x + tamanho.width, canto.y + tamanho.height)

    def ocioso(self):
        """Segundos sem teclado e mouse (MIT-SCREEN-SAVER), ou None se o servidor não informa."""
        if self.display is None or not self.tem_ocioso:
            return None
        try:
            return self.raiz.screensaver_query_info().idle / 1000.0
        except self._erros:
            return None

    def ativa(self):
        """(pid ou None, retângulo ou None) da janela ativa."""
        if self.display is None:
            return None, None
        try:
            ids = self._prop(self.raiz, "_NET_ACTIVE_WINDOW")
            if not ids or not ids[0]:
                return None, None
            janela = self._janela(ids[0])
            pids = self._prop(janela, "_NET_WM_PID")
            return (pids[0] if pids else None), self._retangulo(janela)
        except self._erros:
            return None, None

    def janelas(self):
        """(área de trabalho atual, [(id, rect, pid, desktop, minimizada)] de cima para baixo)."""
        if self.display is None:
            return None, []
        try:
            atual = self._prop(self.raiz, "_NET_CURRENT_DESKTOP")
            empilhamento = self._prop(self.raiz, "_NET_CLIENT_LIST_STACKING")      # de baixo para cima
        except self._erros:
            return None, []
        lidas = []
        for janela_id in reversed(empilhamento):
            try:
                janela = self._janela(janela_id)
                pids, desktops = self._prop(janela, "_NET_WM_PID"), self._prop(janela, "_NET_WM_DESKTOP")
                minimizada = self._atomo["_NET_WM_STATE_HIDDEN"] in self._prop(janela, "_NET_WM_STATE")
                lidas.append((janela_id, self._retangulo(janela), pids[0] if pids else None,
                              desktops[0] if desktops else None, minimizada))
            except self._erros:
                continue            # a janela fechou no meio da leitura
        return (atual[0] if atual else None), lidas

    def tela(self):
        """(0, 0, largura, altura) da tela X inteira, ou None."""
        if self.display is None:
            return None
        try:
            g = self.raiz.get_geometry()
        except self._erros:
            return None
        return (0, 0, g.width, g.height)


# ---------------- coletor em segundo plano ----------------

class Coletor:
    """Faz as leituras numa thread própria e guarda o último resultado de cada uma."""

    def __init__(self, x11=None, gnome=None):
        """Começa vazio. `x11` e `gnome` (ler o ocioso pelo Mutter) servem aos testes."""
        self.ocioso = None                        # (segundos ociosos, quando foi lido); None: não há como ler
        self.processo = "unknown"
        self.retangulo = None
        self.tela = None
        self.janelas = []                         # filtrar_janelas, sem `excluir`
        self._proximo = {"ocioso": 0.0, "ativa": 0.0, "janelas": 0.0, "tela": 0.0}
        self._x11 = x11                           # aberto na thread do coletor (o Xlib não divide conexão)
        self._gnome = bool(os.environ.get("WAYLAND_DISPLAY")) if gnome is None else gnome
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
        if self._x11 is None:
            self._x11 = _X11()
        if agora >= self._proximo["ocioso"]:
            self._proximo["ocioso"] = agora + self._ler_ocioso(agora)
        if agora >= self._proximo["tela"]:
            self._proximo["tela"] = agora + INTERVALO_TELA
            self.tela = self._x11.tela()
        if agora >= self._proximo["ativa"]:
            self._proximo["ativa"] = agora + INTERVALO_ATIVA
            self._ler_ativa()
        if agora >= self._proximo["janelas"]:
            self._proximo["janelas"] = agora + INTERVALO_JANELAS
            atual, lidas = self._x11.janelas()
            self.janelas = filtrar_janelas(lidas, os.getpid(), atual)

    def _ler_ocioso(self, agora):
        """Tempo ocioso pelo X ou, no GNOME Wayland, pelo Mutter. Devolve quantos segundos esperar."""
        valor = self._x11.ocioso()
        if valor is not None:
            self.ocioso = (valor, agora)
            return INTERVALO_OCIOSO
        if self._gnome:
            valor = parse_ocioso_gnome(rodar(OCIOSO_GNOME))
            if valor is None:
                self._gnome = False                 # não é GNOME (ou não respondeu): não tenta de novo
            else:
                self.ocioso = (valor, agora)
        return INTERVALO_OCIOSO_GNOME

    def _ler_ativa(self):
        """Programa e retângulo da janela ativa."""
        pid, self.retangulo = self._x11.ativa()
        try:
            self.processo = psutil.Process(pid).name().lower() if pid else "unknown"
        except psutil.Error:
            self.processo = "unknown"


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
    """Segundos sem teclado e mouse (última leitura + o tempo desde ela); 0 se não há como ler."""
    dados = _dados()
    if dados.ocioso is None:
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

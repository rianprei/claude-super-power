"""
Android: o pet flutua sobre os outros apps, como no PC.

O Qt roda na activity do app, que sai da frente assim que o pet aparece. Cada janela de topo do Qt (pet,
bolinha, Ki, Kamehameha, menu, configurações...) é desenhada numa imagem e mandada à Ponte (Java,
android_java/org/claudesuperpower/Ponte.java), que a mostra numa janela flutuante do Android ("Exibir sobre
outros apps") na mesma posição. Só as áreas de toque recebem o dedo: a região de clique do corpo
(regiao_de_clique, a mesma do X11) ou a janela inteira; o resto da tela continua sendo dos outros apps. Os
toques voltam como eventos de mouse do Qt, então arrastar, cutucar, arremessar e o menu (toque longo)
funcionam como no PC. A notificação faz o papel do ícone da bandeja.

Sentidos: qualquer toque na tela (também em outros apps) conta como atividade para o tempo ocioso; o cursor
é o último toque no pet. O app em primeiro plano, as janelas e a tela cheia não são lidos (precisariam do
serviço de acessibilidade). Sem a permissão de sobreposição, o pet fica dentro do app, num palco preto.

Protocolo: ver Ponte.java. O socket é local (namespace abstrato) e a Ponte só aceita o próprio app (UID).
"""

from __future__ import annotations

import select
import socket
import struct
import time
import zlib
from typing import Any

COORDENADAS_LOGICAS = True          # não há janelas de outros programas para converter
LIMITACAO_ATALHO = "no Android não há atalho de teclado global; use a notificação ou o menu do pet (toque longo)"
NOME_PONTE = "\0claudesuperpower.ponte"
QUADRO_MS = 33                      # ~30 quadros por segundo nas janelas flutuantes
FLAG_POPUP = 1
TAMANHOS = {ord("M"): 1, ord("S"): 24, ord("T"): 16, ord("O"): 4}
ACOES_MOUSE = {0: "MouseButtonPress", 1: "MouseButtonRelease", 2: "MouseMove", 3: "MouseButtonRelease"}

_estado: dict[str, Any] = {"ponte": None}


def _ponte():
    return _estado["ponte"]


def ocioso_segundos():
    """Segundos desde o último toque na tela (em qualquer app, visto pela Ponte); sem ela, sempre ativo."""
    p = _ponte()
    return 0.0 if p is None else max(0.0, time.monotonic() - p.ultima_atividade)


def processo_ativo():
    """O app em primeiro plano não é lido (precisaria do serviço de acessibilidade)."""
    return "unknown"


def retangulo_ativo(escala=1.0):
    """Não há janelas de outros programas à vista do app."""
    del escala


def tela_cheia():
    """Não é lida: o pet fica por cima mesmo de vídeo em tela cheia (esconda pela notificação)."""
    return False


def janelas_visiveis(excluir, escala=1.0):
    """Não há barras de título para pousar."""
    del excluir, escala
    return []


def sem_foco_nativo(janela_id):
    """As janelas flutuantes nunca pegam o foco (FLAG_NOT_FOCUSABLE na Ponte)."""
    del janela_id


def iniciar_atalho(callback):
    """Sem atalho global no Android (a notificação e o menu do pet fazem o mesmo)."""
    del callback
    return False


def regiao_de_clique(janela_id, retangulos):
    """Guarda as áreas que recebem o toque (o corpo do pet): só elas viram áreas de toque na tela."""
    p = _ponte()
    if p is not None:
        p.regioes[janela_id] = list(retangulos)
    return True


def atravessar_clique(janela_id, sim):
    """Fora das áreas de toque o dedo já vai para o app de baixo."""
    del janela_id, sim


def cursor():
    """O "cursor" no celular: o último toque no pet (coordenadas lógicas), ou None antes do primeiro."""
    p = _ponte()
    return None if p is None else p.cursor


def area_util():
    """(l, t, r, b) lógicos da tela sem as barras do sistema, ou None antes de a Ponte informar."""
    p = _ponte()
    return None if p is None else p.area_util()


def estado_da_bandeja(pausado, escondido):
    """Atualiza a notificação (a bandeja do Android)."""
    p = _ponte()
    if p is not None:
        p.enviar(struct.pack(">B??", ord("N"), pausado, escondido))


def iniciar_sobreposicao(bandeja, palco=None):
    """Liga a Ponte: a partir daqui as janelas do Qt aparecem flutuando (se o Android permitir)."""
    _estado["ponte"] = Ponte(bandeja, palco)
    return _estado["ponte"]


def decodificar(buffer):
    """Separa as mensagens completas da Ponte em `buffer` (bytearray); devolve [(tipo, valores)] e consome."""
    msgs: list[tuple[str, Any]] = []
    while buffer:
        tipo = buffer[0]
        if tipo == ord("C"):
            if len(buffer) < 3:
                break
            n = struct.unpack_from(">H", buffer, 1)[0]
            if len(buffer) < 3 + n:
                break
            msgs.append(("C", bytes(buffer[3:3 + n]).decode("utf-8", "replace")))
            del buffer[:3 + n]
            continue
        tamanho = TAMANHOS.get(tipo)
        if tamanho is None:
            raise ValueError(f"mensagem desconhecida da Ponte: {tipo}")
        if len(buffer) < 1 + tamanho:
            break
        corpo = bytes(buffer[1:1 + tamanho])
        del buffer[:1 + tamanho]
        if tipo == ord("M"):
            msgs.append(("M", corpo[0] != 0))
        elif tipo == ord("S"):
            msgs.append(("S", struct.unpack(">6i", corpo)))
        elif tipo == ord("T"):
            msgs.append(("T", struct.unpack(">iiff", corpo)))
        else:
            msgs.append(("O", struct.unpack(">i", corpo)[0]))
    return msgs


def quadro(janela_id, x, y, w, h, popup, areas, pixels):
    """A mensagem 'F' de uma janela: posição e tamanho em pixels físicos, áreas de toque e a imagem (ou b"")."""
    cabecalho = struct.pack(">Biiiiiii", ord("F"), janela_id, x, y, w, h, FLAG_POPUP if popup else 0, len(areas))
    corpo = b"".join(struct.pack(">iiii", *a) for a in areas)
    return cabecalho + corpo + struct.pack(">i", len(pixels)) + pixels


class Ponte:
    """O lado Python da Ponte: espelha as janelas de topo do Qt e entrega os toques a elas."""

    def __init__(self, bandeja, palco=None, conectar=True):
        from PySide6.QtCore import QTimer

        self.bandeja = bandeja
        self.palco = palco
        self.sock = None
        self.buffer = bytearray()
        self.modo = False                   # a Ponte disse que a sobreposição está permitida
        self.tela = None                    # (w, h, topo, baixo, esq, dir) físicos
        self.regioes = {}                   # winId -> [(x, y, w, h)] lógicos
        self.enviadas = {}                  # id -> crc da última imagem
        self.janelas = {}                   # id -> widget (as que estão na tela)
        self.agarrado = None                # widget que recebeu o toque que desceu
        self.cursor = None
        self.ultima_atividade = time.monotonic()
        self.proxima_tentativa = 0.0
        self.timer = QTimer()
        self.timer.timeout.connect(self.passo)
        if conectar:
            self.timer.start(QUADRO_MS)

    # ---------------- conexão ----------------

    def conectar(self):
        """Tenta falar com a Ponte (ela sobe junto com a activity); tenta de novo a cada segundo."""
        agora = time.monotonic()
        if self.sock is not None or agora < self.proxima_tentativa:
            return
        self.proxima_tentativa = agora + 1.0
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.connect(NOME_PONTE)
        except OSError:
            s.close()
            return
        s.settimeout(2.0)
        self.sock = s

    def desconectar(self):
        if self.sock is not None:
            self.sock.close()
        self.sock = None
        self.modo = False
        self.enviadas.clear()
        self.janelas.clear()
        self._palco(True)

    def enviar(self, dados):
        if self.sock is None:
            return
        try:
            self.sock.sendall(dados)
        except OSError:
            self.desconectar()

    def ler(self):
        """Lê o que a Ponte mandou (sem esperar) e trata cada mensagem."""
        while self.sock is not None and select.select([self.sock], [], [], 0)[0]:
            try:
                parte = self.sock.recv(65536)
            except OSError:
                parte = b""
            if not parte:
                self.desconectar()
                return
            self.buffer += parte
        for tipo, valor in decodificar(self.buffer):
            self.tratar(tipo, valor)

    def tratar(self, tipo, valor):
        if tipo == "M":
            self.modo = valor
            self._palco(not valor)
            if not valor:
                self.enviadas.clear()
        elif tipo == "S":
            self.tela = valor
        elif tipo == "T":
            self.toque(*valor)
        elif tipo == "O":
            self.ultima_atividade = time.monotonic()
            self.fora(valor)
        elif tipo == "C":
            self.comando(valor)

    def _palco(self, visivel):
        if self.palco is not None:
            self.palco.setVisible(visivel)

    # ---------------- espelho das janelas ----------------

    def area_util(self):
        if self.tela is None:
            return None
        from PySide6.QtGui import QGuiApplication

        dpr = QGuiApplication.primaryScreen().devicePixelRatio()
        w, h, topo, baixo, esq, dir_ = self.tela
        return esq / dpr, topo / dpr, (w - dir_) / dpr, (h - baixo) / dpr

    def passo(self):
        """Um quadro: lê a Ponte e manda as janelas de topo visíveis (a imagem só quando mudou)."""
        self.conectar()
        if self.sock is None:
            return
        self.ler()
        if not self.modo or self.sock is None:
            return
        from PySide6.QtWidgets import QApplication

        vistas = {}
        for w in QApplication.topLevelWidgets():
            if w is self.palco or not w.isVisible() or w.width() <= 0 or w.height() <= 0:
                continue
            janela_id = int(w.winId()) & 0x7FFFFFFF
            vistas[janela_id] = w
            self.enviar(self.mensagem(janela_id, w))
        for janela_id in set(self.janelas) - set(vistas):
            self.enviar(struct.pack(">Bi", ord("H"), janela_id))
            self.enviadas.pop(janela_id, None)
        self.janelas = vistas

    def mensagem(self, janela_id, w):
        """A janela `w` em pixels físicos: posição, áreas de toque e a imagem (só se mudou desde a última)."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage
        from PySide6.QtWidgets import QMenu

        imagem = w.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888_Premultiplied)
        iw, ih = imagem.width(), imagem.height()
        pixels = bytes(imagem.constBits())[:iw * ih * 4]
        crc = zlib.crc32(pixels)
        if self.enviadas.get(janela_id) == crc:
            pixels = b""
        else:
            self.enviadas[janela_id] = crc
        fator = iw / max(1, w.width())                  # o grab já vem na escala da tela
        g = w.geometry()
        x, y = round(g.x() * fator), round(g.y() * fator)
        if w.windowFlags() & Qt.WindowType.WindowTransparentForInput:
            areas = []
        elif int(w.winId()) in self.regioes:
            areas = [(round(rx * fator), round(ry * fator), max(1, round(rw * fator)), max(1, round(rh * fator)))
                     for rx, ry, rw, rh in self.regioes[int(w.winId())]][:16]
        else:
            areas = [(0, 0, iw, ih)]
        popup = isinstance(w, QMenu) or w.windowType() == Qt.WindowType.Popup
        return quadro(janela_id, x, y, iw, ih, popup, areas, pixels)

    # ---------------- toques e comandos ----------------

    def toque(self, janela_id, acao, x, y):
        """Um toque numa área de toque vira mouse do Qt, no widget de baixo do dedo (o mesmo até soltar)."""
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtWidgets import QApplication

        janela = self.janelas.get(janela_id)
        if janela is None:
            return
        self.ultima_atividade = time.monotonic()
        fator = janela.devicePixelRatioF() or 1.0       # pixels físicos por unidade lógica
        global_ = QPointF(x / fator, y / fator)
        self.cursor = (global_.x(), global_.y())
        if acao == 0 or self.agarrado is None:
            local = janela.mapFromGlobal(global_.toPoint())
            self.agarrado = janela.childAt(local) or janela
        alvo = self.agarrado
        if acao in (1, 3):
            self.agarrado = None
        tipo = getattr(QEvent.Type, ACOES_MOUSE[acao])
        botao = Qt.MouseButton.NoButton if acao == 2 else Qt.MouseButton.LeftButton
        apertados = Qt.MouseButton.LeftButton if acao in (0, 2) else Qt.MouseButton.NoButton
        evento = QMouseEvent(tipo, QPointF(alvo.mapFromGlobal(global_.toPoint())), global_, botao, apertados,
                             Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(alvo, evento)

    def fora(self, janela_id):
        """Toque fora de um menu aberto (em outro app): fecha o menu, como clicar fora dele no PC."""
        from PySide6.QtWidgets import QApplication

        popup = QApplication.activePopupWidget()
        if popup is not None and int(popup.winId()) & 0x7FFFFFFF == janela_id:
            popup.close()

    def comando(self, texto):
        """Os botões da notificação são os itens do menu da bandeja do PC."""
        sinal = {"hide": "toggle_hidden", "pause": "toggle_pause", "settings": "open_settings",
                 "quit": "quit"}.get(texto)
        if sinal is not None and self.bandeja is not None:
            getattr(self.bandeja, sinal).emit()

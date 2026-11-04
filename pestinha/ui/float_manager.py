"""
FLOATS - os painéis flutuantes (monitor neural e painel de protesto).

Só aparecem quando você abre pelo menu do pet ou pela bandeja; nada abre sozinho (nem no modo
teste, que só encurta os tempos). Ficam até você fechar: o × no canto, o mesmo item do menu ou
"Fechar painéis" na bandeja. Somem junto com o pet (escondido, desligado, tela cheia).
A posição fica salva (paths.panels).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QPushButton

from ..body.desenho_rosto import APAGADO, FUNDO, LARANJA
from .monitor import NeuralMonitor
from .panel import StrikePanel

KEYS = ("neural", "greve")


class FloatManager:
    """Guarda os painéis abertos (monitor neural, painel de protesto) e decide quando eles podem aparecer."""
    def __init__(self, app):
        """Começa sem painéis abertos."""
        self.app = app
        self.windows = {}
        self.opened = set()             # painéis que você abriu (menu ou bandeja)

    def window(self, key):
        """Devolve o painel `key`, criando-o na primeira vez (com a posição salva ou a padrão)."""
        if key not in self.windows:
            screen = QGuiApplication.primaryScreen().availableGeometry()
            if key == "neural":
                self.windows[key] = NeuralMonitor(self.app, (screen.x() + 20, screen.y() + 20))
            else:
                self.windows[key] = StrikePanel(self.app, (screen.right() - 600, screen.y() + 40))
            _botao_fechar(self.windows[key], lambda: self.close(key))
        return self.windows[key]

    def sync(self, base):
        """Mostra os painéis abertos se `base` (pet ativo, não escondido, sem tela cheia atrapalhando); senão esconde."""
        for key in KEYS:
            if base and key in self.opened:
                self.window(key).show()
            elif key in self.windows:
                self.windows[key].hide()

    def open(self, key):
        """Abre um painel, se o pet estiver ativo, visível e a tela não estiver cheia."""
        if not self.app.floats_base():          # desligado, escondido ou tela cheia: não abre
            return
        self.opened.add(key)
        w = self.window(key)
        w.show()
        w.raise_()

    def close(self, key):
        """Fecha um painel e o esquece da lista de abertos."""
        self.opened.discard(key)
        if key in self.windows:
            self.windows[key].hide()

    def toggle(self, key):
        """Abre o painel se estiver fechado; fecha se estiver aberto."""
        if key in self.opened:
            self.close(key)
        else:
            self.open(key)

    def close_all(self):
        """Fecha todos os painéis de uma vez ("Fechar painéis" na bandeja)."""
        for key in KEYS:
            self.close(key)

    def visible_handles(self):
        """Identificadores das janelas dos painéis visíveis (o pet não deve contá-los como janelas de outros programas)."""
        return {int(w.winId()) for w in self.windows.values() if w.isVisible()}


def _botao_fechar(janela, fechar):
    """× no canto de cima à direita: os painéis não têm a moldura do sistema (e o tamanho é fixo)."""
    botao = QPushButton("×", janela)
    botao.setFixedSize(24, 24)
    botao.move(janela.width() - 30, 6)
    botao.setCursor(Qt.CursorShape.PointingHandCursor)
    botao.setToolTip("Fechar o painel")
    botao.setStyleSheet(f"QPushButton {{ background: transparent; color: {APAGADO}; border: none; border-radius: 5px;"
                        f" font-size: 18px; font-weight: bold; }}"
                        f" QPushButton:hover {{ background: {LARANJA}; color: {FUNDO}; }}")
    botao.clicked.connect(fechar)
    return botao

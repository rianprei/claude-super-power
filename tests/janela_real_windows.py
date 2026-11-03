"""
Prova, num Windows de verdade (Qt nativo, não offscreen), que o clique atravessa a aura semitransparente.

Roda num processo à parte, chamado por tests/test_windows.py: abre uma janela igual à do pet (sem moldura, por cima, fundo transparente),
pintada inteira com alfa baixo como a aura, e pergunta ao Windows quem recebe o clique no meio dela.
Sai com 0 se o clique atravessa com atravessar_clique(True) e volta para a janela com False.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import win32con
import win32gui
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from pestinha import plataforma
from pestinha.body.pet import overlay_flags

GA_ROOT = 2


class Aura(QWidget):
    """Janela do tamanho da do Super Saiyajin, toda com a cor da aura em alfa baixo."""

    def __init__(self):
        super().__init__(None, overlay_flags())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(272, 300)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(255, 200, 40, 40))
        p.end()


def esperar(segundos):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        QApplication.processEvents()
        time.sleep(0.02)


def quem_recebe(ponto):
    hwnd = win32gui.WindowFromPoint(ponto)
    return win32gui.GetAncestor(hwnd, GA_ROOT) if hwnd else 0


def main():
    app = QApplication(sys.argv)
    janela = Aura()
    janela.move(200, 200)
    janela.show()
    esperar(1.0)
    hwnd = int(janela.winId())
    esq, topo, dir_, base = win32gui.GetWindowRect(hwnd)
    meio = ((esq + dir_) // 2, (topo + base) // 2)
    estilo = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    print(f"hwnd={hwnd} rect={(esq, topo, dir_, base)} layered={bool(estilo & win32con.WS_EX_LAYERED)} "
          f"dpr={janela.devicePixelRatio()}")

    antes = quem_recebe(meio)
    print(f"sem atravessar: {'a janela' if antes == hwnd else antes}")
    plataforma.atravessar_clique(hwnd, True)
    esperar(0.2)
    atravessando = quem_recebe(meio)
    print(f"atravessando: {'a janela' if atravessando == hwnd else atravessando}")
    plataforma.atravessar_clique(hwnd, False)
    esperar(0.2)
    depois = quem_recebe(meio)
    print(f"de volta: {'a janela' if depois == hwnd else depois}")
    janela.close()
    del app
    ok = antes == hwnd and atravessando != hwnd and depois == hwnd
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

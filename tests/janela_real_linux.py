"""
Prova, num X de verdade (com gerenciador de janelas), que o leitor do X11 enxerga as janelas: abre uma
janela comum e confere se ela vem na lista com a posição e o tamanho que o Qt diz, e se o próprio pet
fica de fora do que ele vê.

Roda num processo à parte, chamado por tests/test_plataforma.py. Sai com 0 se tudo confere; com 2 se não há
X com gerenciador de janelas (não dá para testar).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import qt_legado

qt_legado.ativar()     # antes do PySide6 (conjunto legado)

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QWidget

from pestinha.plataforma import linux


def esperar(segundos):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        QApplication.processEvents()
        time.sleep(0.02)


def main():
    app = QApplication(sys.argv)
    x11 = linux._X11()
    if app.platformName() != "xcb" or x11.display is None:
        print(f"sem X11 (plataforma {app.platformName()})")
        return 2
    gerenciador = x11.raiz.get_full_property(x11.display.intern_atom("_NET_SUPPORTING_WM_CHECK"),
                                             x11._X.AnyPropertyType)
    if gerenciador is None:
        print("X sem gerenciador de janelas (sem EWMH)")
        return 2
    janela = QWidget()
    janela.setWindowTitle("sonda do leitor X11")
    janela.resize(400, 300)
    janela.show()
    esperar(1.5)
    canto = janela.mapToGlobal(QPoint(0, 0))
    escala = janela.devicePixelRatioF()           # o X11 fala em pixels físicos; o Qt 5 escala pelo DPI da tela
    esperado = tuple(round(v * escala) for v in
                     (canto.x(), canto.y(), canto.x() + janela.width(), canto.y() + janela.height()))
    atual, lidas = x11.janelas()
    minhas = [j for j in lidas if j[2] == os.getpid()]
    print(f"área {atual} · {len(lidas)} janela(s) · minhas: {minhas} · esperado {esperado}")
    vistas_por_outro = linux.filtrar_janelas(lidas, -1, atual)
    vistas_pelo_pet = linux.filtrar_janelas(lidas, os.getpid(), atual)
    ok = (len(minhas) == 1 and all(abs(a - b) <= 1 for a, b in zip(minhas[0][1], esperado))
          and any(j[0] == minhas[0][0] for j in vistas_por_outro)
          and not any(j[0] == minhas[0][0] for j in vistas_pelo_pet))
    print(f"tela {x11.tela()} · ociosidade {x11.ocioso()} · ativa {x11.ativa()}")
    janela.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

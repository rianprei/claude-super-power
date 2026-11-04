"""
Prova, num macOS de verdade (Qt Cocoa, não offscreen), que as janelas do pet ficam visíveis com outro app ativo,
não têm sombra e deixam o clique atravessar a aura.

Roda num processo à parte, chamado por tests/test_macos.py: abre uma janela igual à do pet e lê o NSWindow dela.
Sai com 0 se tudo confere.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import qt_legado

qt_legado.ativar()     # antes do PySide6 (conjunto legado)

import objc
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from pestinha import plataforma
from pestinha.body.pet import overlay_flags


def janela_do_pet(sempre_visivel):
    """Janela com as mesmas marcas da do pet; `sempre_visivel` liga WA_MacAlwaysShowToolWindow."""
    janela = QWidget(None, overlay_flags())
    janela.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    janela.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    janela.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, sempre_visivel)
    janela.setFixedSize(272, 300)
    janela.show()
    return janela


def esperar(segundos):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        QApplication.processEvents()
        time.sleep(0.02)


def ns(janela):
    return objc.objc_object(c_void_p=int(janela.winId())).window()


def main():
    app = QApplication(sys.argv)
    print(f"plataforma Qt: {app.platformName()}")
    pet, comum = janela_do_pet(True), janela_do_pet(False)
    esperar(1.0)
    print(f"sem o atributo, some com outro app ativo: {bool(ns(comum).hidesOnDeactivate())}")
    visivel = not ns(pet).hidesOnDeactivate()
    sem_sombra = not ns(pet).hasShadow()
    plataforma.atravessar_clique(int(pet.winId()), True)
    atravessa = bool(ns(pet).ignoresMouseEvents())
    plataforma.atravessar_clique(int(pet.winId()), False)
    volta = not ns(pet).ignoresMouseEvents()
    print(f"fica visível: {visivel} · sem sombra: {sem_sombra} · clique atravessa: {atravessa} · volta: {volta}")
    pet.close()
    comum.close()
    del app
    return 0 if visivel and sem_sombra and atravessa and volta else 1


if __name__ == "__main__":
    sys.exit(main())

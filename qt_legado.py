"""
Conjunto legado (Windows 7, 8 e 8.1, Windows de 32 bits, macOS 10.13, Linux com glibc 2.17): sem o PySide6
instalado, o pacote qt5compat (o PySide2, Qt 5.15, com a cara do PySide6) responde pelo nome PySide6.
Chame ativar() antes de qualquer `from PySide6...`. Com o PySide6 de verdade, não faz nada.
"""

from __future__ import annotations

import importlib.util
import sys

MODULOS = ("QtCore", "QtGui", "QtWidgets")


def ativar() -> bool:
    """Registra o qt5compat como PySide6 em sys.modules se o PySide6 não está instalado; True se registrou."""
    if "PySide6" in sys.modules or importlib.util.find_spec("PySide6") is not None:
        return False
    import qt5compat
    import qt5compat.QtCore
    import qt5compat.QtGui
    import qt5compat.QtWidgets

    sys.modules["PySide6"] = qt5compat
    for nome in MODULOS:
        sys.modules[f"PySide6.{nome}"] = getattr(qt5compat, nome)
    return True

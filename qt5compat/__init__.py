"""
PySide6 por cima do PySide2 (Qt 5.15), para os sistemas em que o Qt 6 não roda: Windows 7, 8 e 8.1 (e os de
32 bits), macOS 10.13 e Linux com glibc 2.17 a 2.27. Só entra quando o PySide6 de verdade não está instalado
(qt_legado.ativar() registra este pacote como PySide6 em sys.modules: com outro nome, o PyInstaller não o
confunde com o PySide6 de verdade).

O código do app usa a API do Qt 6; o PySide2 5.15 já aceita os enums nesse estilo (Qt.WindowType.Tool...).
Aqui ficam só as diferenças que o app usa: exec() sem sublinhado, position()/globalPosition() nos eventos
de mouse, QAction no QtGui, e a escala de tela automática que o Qt 6 liga sozinho.
"""

from PySide2 import __version__ as versao_qt5

__version__ = f"qt5-{versao_qt5}"

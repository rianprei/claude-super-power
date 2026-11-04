"""QtWidgets do Qt 5 com os nomes do PySide6. Liga a escala de tela automática, que no Qt 6 já vem ligada."""

from PySide2.QtCore import QCoreApplication, Qt
from PySide2.QtGui import QGuiApplication
from PySide2.QtWidgets import *
from PySide2.QtWidgets import QApplication, QDialog, QMenu, QMessageBox

# antes de criar o app (o Qt 5 só lê isso aí): DPI por monitor e fator de escala sem arredondar
QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

for _classe in (QApplication, QDialog, QMenu, QMessageBox):
    _classe.exec = _classe.exec_

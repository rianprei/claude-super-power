"""QtGui do Qt 5 com os nomes do PySide6 (no Qt 6 a QAction mudou do QtWidgets para cá)."""

from PySide2.QtGui import *
from PySide2.QtGui import QGuiApplication, QMouseEvent
from PySide2.QtWidgets import QAction, QActionGroup, QShortcut  # noqa: F401

QGuiApplication.exec = QGuiApplication.exec_
QMouseEvent.globalPosition = QMouseEvent.screenPos      # QPointF global, como no Qt 6
QMouseEvent.position = QMouseEvent.localPos

"""QtCore do Qt 5 com os nomes do PySide6."""

from PySide2.QtCore import *
from PySide2.QtCore import Property, QCoreApplication, Signal, Slot  # noqa: F401

QCoreApplication.exec = QCoreApplication.exec_

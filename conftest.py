"""
Configuração comum dos testes (pasta tests/).

- Qt sem janela: os testes rodam em qualquer máquina, sem abrir nada na tela.
- Isolamento: apps e janelas criados num teste não continuam rodando nos seguintes, e nenhum teste
  lê o desktop real (janela ativa, tela cheia, lista de janelas).
"""
import gc
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True)
def _sem_desktop_real(monkeypatch):
    """Os sentidos do Linux não leem o desktop de quem roda os testes (janela ativa, tela cheia, wmctrl)."""
    from pestinha.plataforma import linux
    coletor = linux.Coletor()
    coletor.tem = dict.fromkeys(coletor.tem, False)       # sem comandos: sem subprocesso e sem thread
    monkeypatch.setattr(linux, "_coletor", coletor)


@pytest.fixture(autouse=True)
def _encerrar_apps_e_janelas():
    from PySide6.QtWidgets import QApplication
    qt = QApplication.instance()
    antes = set(qt.topLevelWidgets()) if qt else set()
    yield
    from PySide6.QtCore import QTimer

    from pestinha.app import PestinhaApp
    for obj in gc.get_objects():
        if isinstance(obj, PestinhaApp):
            for timer in obj.findChildren(QTimer):
                timer.stop()
    qt = QApplication.instance()
    if qt:
        for widget in set(qt.topLevelWidgets()) - antes:
            for timer in widget.findChildren(QTimer):
                timer.stop()
            widget.close()

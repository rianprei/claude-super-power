"""
Configuração comum dos testes (pasta tests/).

- Qt sem janela: os testes rodam em qualquer máquina, sem abrir nada na tela.
- Isolamento: apps e janelas criados num teste não continuam rodando nos seguintes, e nenhum teste
  lê o desktop real (janela ativa, tela cheia, lista de janelas).
"""

from __future__ import annotations

import gc
import os

import qt_legado

qt_legado.ativar()     # antes do PySide6: no conjunto legado, o Qt 5 com a cara dele

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True)
def _sem_desktop_real(monkeypatch):
    """Os sentidos não leem o desktop de quem roda os testes (janela ativa, tela cheia, lista de janelas).

    No Linux, o coletor fica sem conexão com o X; no Windows e no macOS, as leituras viram um desktop vazio
    (no Windows 11 ARM do CI a janela da frente cobre a tela e o app achava que era tela cheia).
    """
    from pestinha import plataforma
    from pestinha.plataforma import linux
    # sem X e sem gdbus: nem conexão, nem subprocesso, nem thread
    monkeypatch.setattr(linux, "_coletor", linux.Coletor(x11=linux._X11(conectar=False), gnome=False))
    if plataforma._backend is not linux:
        monkeypatch.setattr(plataforma, "tela_cheia", lambda: False)
        monkeypatch.setattr(plataforma, "retangulo_ativo", lambda *_a, **_k: None)
        monkeypatch.setattr(plataforma, "janelas_visiveis", lambda *_a, **_k: [])
        monkeypatch.setattr(plataforma, "processo_ativo", lambda: "unknown")
        monkeypatch.setattr(plataforma, "ocioso_segundos", lambda: 0.0)


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

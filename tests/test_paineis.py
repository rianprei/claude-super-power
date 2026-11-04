"""Painéis do menu (monitor neural e painel de protesto): só abrem quando você pede e fecham fácil."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from PySide6.QtWidgets import QApplication

from pestinha import config
from pestinha.app import PestinhaApp
from pestinha.paths import Paths
from pestinha.settings_store import SettingsStore


@pytest.fixture
def pet_app(tmp_path):
    app_qt = QApplication.instance() or QApplication([])
    app_qt.setQuitOnLastWindowClosed(False)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS))           # modo teste desligado (padrão)
    app = PestinhaApp(store, paths)
    yield app
    app.floats.close_all()
    for w in list(app.floats.windows.values()):
        w.close()


def test_painel_aberto_no_menu_fica_na_tela_fora_do_modo_teste(pet_app):
    pet_app.floats.open("neural")
    pet_app.floats.sync(pet_app.floats_base())
    assert pet_app.floats.window("neural").isVisible()


def test_clicar_de_novo_fecha_o_painel(pet_app):
    pet_app.floats.toggle("greve")
    pet_app.floats.toggle("greve")
    pet_app.floats.sync(pet_app.floats_base())
    assert not pet_app.floats.window("greve").isVisible()


def test_esconder_o_bryan_esconde_o_painel(pet_app):
    pet_app.floats.open("greve")
    pet_app.floats.sync(False)
    assert not pet_app.floats.window("greve").isVisible()


def test_x_no_canto_fecha_o_painel(pet_app):
    from PySide6.QtWidgets import QPushButton
    pet_app.floats.open("neural")
    janela = pet_app.floats.window("neural")
    botao = next(b for b in janela.findChildren(QPushButton) if b.text() == "×")
    assert botao.geometry().right() < janela.width() and botao.y() < 40        # dentro, no canto de cima
    botao.click()
    assert not janela.isVisible() and "neural" not in pet_app.floats.opened
    pet_app.floats.sync(pet_app.floats_base())
    assert not janela.isVisible()                                               # e não volta sozinho


def test_fechar_paineis_na_bandeja_fecha_todos(pet_app):
    pet_app.floats.open("neural")
    pet_app.floats.open("greve")
    pet_app.tray.fechar_paineis.emit()
    assert not pet_app.floats.opened
    assert not any(w.isVisible() for w in pet_app.floats.windows.values())


def test_modo_teste_nao_abre_painel_sozinho_e_o_menu_fecha_o_que_abriu(pet_app):
    pet_app.apply_perms(dict(pet_app.perms, modo_teste=True, mostrar_emocao=True))
    assert not any(w.isVisible() for w in pet_app.floats.windows.values())
    pet_app.floats.toggle("greve")                                              # abre pelo menu
    assert pet_app.floats.window("greve").isVisible()
    pet_app.floats.toggle("greve")                                              # o mesmo item fecha
    assert not pet_app.floats.window("greve").isVisible()

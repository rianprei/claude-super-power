"""Android: a Ponte espelha as janelas do Qt em janelas flutuantes e devolve os toques como mouse (lado Python).

O lado Java (android_java/.../Ponte.java) é simulado por um servidor no socket local, o mesmo protocolo.
"""
from __future__ import annotations

import os
import socket
import struct
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from pestinha.plataforma import android


@pytest.fixture(autouse=True)
def _qt():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def java(monkeypatch):
    """Um 'Java' falso: servidor no socket local que a Ponte procura."""
    nome = f"\0teste-ponte-{os.getpid()}-{time.monotonic_ns()}"
    monkeypatch.setattr(android, "NOME_PONTE", nome)
    servidor = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    servidor.bind(nome)
    servidor.listen(1)
    servidor.settimeout(2.0)
    yield servidor
    servidor.close()


def _ler_quadros(conexao, tempo=0.3):
    """Lê o que a Ponte mandou e separa as mensagens 'F' e 'H'."""
    conexao.settimeout(tempo)
    dados = b""
    try:
        while True:
            parte = conexao.recv(1 << 20)
            if not parte:
                break
            dados += parte
    except TimeoutError:
        pass
    msgs, i = [], 0
    while i < len(dados):
        tipo = dados[i]
        if tipo == ord("F"):
            jid, x, y, w, h, flags, n = struct.unpack_from(">iiiiiii", dados, i + 1)
            i += 29
            areas = [struct.unpack_from(">iiii", dados, i + 16 * k) for k in range(n)]
            i += 16 * n
            tamanho = struct.unpack_from(">i", dados, i)[0]
            i += 4 + tamanho
            msgs.append(("F", jid, x, y, w, h, flags, areas, tamanho))
        elif tipo == ord("H"):
            msgs.append(("H", struct.unpack_from(">i", dados, i + 1)[0]))
            i += 5
        elif tipo == ord("N"):
            msgs.append(("N", dados[i + 1], dados[i + 2]))
            i += 3
        else:
            raise AssertionError(f"mensagem inesperada {tipo}")
    return msgs


def _janela(x=100, y=200, w=80, h=60, transparente=False):
    flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
    if transparente:
        flags |= Qt.WindowType.WindowTransparentForInput
    janela = QWidget(None, flags)
    janela.setGeometry(x, y, w, h)
    janela.show()
    return janela


def test_decodifica_mensagens_inteiras_e_espera_as_pela_metade():
    buffer = bytearray(b"M\x01" + b"S" + struct.pack(">6i", 720, 1640, 40, 30, 0, 0)
                       + b"T" + struct.pack(">iiff", 7, 0, 10.5, 20.0) + b"O" + struct.pack(">i", 7)
                       + b"C" + struct.pack(">H", 4) + b"hide" + b"T" + struct.pack(">i", 7))
    msgs = android.decodificar(buffer)
    assert msgs == [("M", True), ("S", (720, 1640, 40, 30, 0, 0)), ("T", (7, 0, 10.5, 20.0)), ("O", 7),
                    ("C", "hide")]
    assert bytes(buffer) == b"T" + struct.pack(">i", 7)          # a metade fica para o próximo pedaço
    with pytest.raises(ValueError):
        android.decodificar(bytearray(b"Z"))


def test_espelha_as_janelas_visiveis_com_area_de_toque_e_so_reenvia_a_imagem_quando_muda(java):
    pet, efeito = _janela(), _janela(300, 50, 40, 40, transparente=True)
    ponte = android.Ponte(bandeja=None, conectar=False)
    ponte.conectar()
    conexao, _ = java.accept()
    conexao.sendall(b"M\x01")
    ponte.regioes[int(pet.winId())] = [(10, 5, 50, 40)]
    ponte.passo()
    msgs = [m for m in _ler_quadros(conexao) if m[0] == "F"]
    por_id = {m[1]: m for m in msgs}
    _, _, x, y, w, h, _flags, areas, tamanho = por_id[int(pet.winId()) & 0x7FFFFFFF]
    fator = w / 80
    assert (x, y) == (round(100 * fator), round(200 * fator)) and tamanho == w * h * 4
    assert areas == [(round(10 * fator), round(5 * fator), round(50 * fator), round(40 * fator))]
    assert por_id[int(efeito.winId()) & 0x7FFFFFFF][7] == []          # efeito: o toque atravessa
    pet.move(120, 200)
    ponte.passo()
    msgs = [m for m in _ler_quadros(conexao) if m[0] == "F" and m[1] == int(pet.winId()) & 0x7FFFFFFF]
    assert msgs[0][2] == round(120 * fator) and msgs[0][8] == 0      # só andou: sem reenviar a imagem
    efeito.hide()
    ponte.passo()
    assert ("H", int(efeito.winId()) & 0x7FFFFFFF) in _ler_quadros(conexao)
    for j in (pet, efeito):
        j.close()
    ponte.desconectar()
    conexao.close()


def test_toque_vira_mouse_no_widget_e_o_toque_longe_conta_como_atividade():
    recebidos = []

    class Alvo(QWidget):
        def mousePressEvent(self, e):
            recebidos.append(("press", e.globalPosition().x(), e.position().x()))

        def mouseMoveEvent(self, e):
            recebidos.append(("move", e.globalPosition().x(), bool(e.buttons() & Qt.MouseButton.LeftButton)))

        def mouseReleaseEvent(self, e):
            recebidos.append(("release", e.globalPosition().x(), e.position().x()))

    alvo = Alvo(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
    alvo.setGeometry(100, 100, 80, 80)
    alvo.show()
    ponte = android.Ponte(bandeja=None, conectar=False)
    jid = int(alvo.winId()) & 0x7FFFFFFF
    ponte.janelas[jid] = alvo
    f = alvo.devicePixelRatioF()
    ponte.ultima_atividade = 0.0
    ponte.tratar("T", (jid, 0, 120 * f, 130 * f))
    ponte.tratar("T", (jid, 2, 300 * f, 130 * f))                      # arrastou para fora: o mesmo widget
    ponte.tratar("T", (jid, 1, 310 * f, 130 * f))
    assert [r[0] for r in recebidos] == ["press", "move", "release"]
    assert recebidos[0][1:] == (pytest.approx(120), pytest.approx(20))
    assert recebidos[1][2] is True and recebidos[2][1] == pytest.approx(310)
    assert ponte.cursor == (pytest.approx(310), pytest.approx(130))  # o "cursor" é o último toque
    assert time.monotonic() - ponte.ultima_atividade < 1.0
    ponte.ultima_atividade = 0.0
    ponte.tratar("O", 12345)                                          # tocou em outro app
    assert time.monotonic() - ponte.ultima_atividade < 1.0
    alvo.close()


def test_toque_fora_do_menu_fecha_o_menu(monkeypatch):
    menu = QMenu()
    menu.addAction("x")
    ponte = android.Ponte(bandeja=None, conectar=False)
    monkeypatch.setattr(QApplication, "activePopupWidget", staticmethod(lambda: menu))
    fechou = Mock()
    monkeypatch.setattr(menu, "close", fechou)
    ponte.fora(1)                                                     # fora de outra janela: nada
    fechou.assert_not_called()
    ponte.fora(int(menu.winId()) & 0x7FFFFFFF)
    fechou.assert_called_once()


def test_botoes_da_notificacao_sao_os_da_bandeja_e_a_area_util_tira_as_barras():
    bandeja = SimpleNamespace(**{n: Mock() for n in ("toggle_hidden", "toggle_pause", "open_settings", "quit")})
    ponte = android.Ponte(bandeja=bandeja, conectar=False)
    for texto, sinal in (("hide", "toggle_hidden"), ("pause", "toggle_pause"), ("settings", "open_settings"),
                         ("quit", "quit")):
        ponte.tratar("C", texto)
        getattr(bandeja, sinal).emit.assert_called_once()
    ponte.tratar("C", "desconhecido")                                 # ignora
    assert ponte.area_util() is None
    ponte.tratar("S", (720, 1640, 40, 30, 0, 0))
    dpr = QApplication.primaryScreen().devicePixelRatio()
    assert ponte.area_util() == (0.0, 40 / dpr, 720 / dpr, 1610 / dpr)


def test_sem_permissao_o_palco_aparece_e_com_permissao_some():
    palco = Mock()
    ponte = android.Ponte(bandeja=None, palco=palco, conectar=False)
    ponte.tratar("M", False)
    palco.setVisible.assert_called_with(True)
    ponte.tratar("M", True)
    palco.setVisible.assert_called_with(False)

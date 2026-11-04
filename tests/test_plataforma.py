"""
Plataforma: cada sistema expõe as mesmas funções, e as leituras de texto (wmctrl, xdotool, ioreg,
janelas do Quartz) são testadas com saídas de exemplo, em qualquer sistema.

Não há Mac nem Linux nos testes automatizados: o caminho real desses sistemas ainda precisa ser
testado numa máquina de verdade (ver README).
"""

from __future__ import annotations

import os
import subprocess  # nosec B404 - roda o próprio Python com um script fixo dos testes
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pestinha import plataforma
from pestinha.plataforma import android, linux
from pestinha.sense.senses import detect_activity

# Backends nativos só podem ser importados no seu próprio sistema.
# Isso evita carregar pywin32 no macOS e QuickMacHotKey no Windows/Linux.
macos = None
windows = None
if sys.platform == "darwin":
    from pestinha.plataforma import macos
elif sys.platform == "win32":
    from pestinha.plataforma import windows

FUNCOES = ["ocioso_segundos", "processo_ativo", "retangulo_ativo", "tela_cheia",
           "janelas_visiveis", "sem_foco_nativo", "iniciar_atalho"]


def test_cada_sistema_expoe_as_mesmas_funcoes():
    modulos = [linux, android]
    if macos is not None:
        modulos.append(macos)
    if windows is not None:
        modulos.append(windows)

    for modulo in modulos:
        for nome in FUNCOES:
            assert callable(getattr(modulo, nome)), (modulo.__name__, nome)


def test_a_plataforma_escolhida_e_a_do_sistema_atual():
    esperado = {"win32": windows, "darwin": macos}.get(sys.platform, linux)
    assert plataforma._backend is esperado


def test_janelas_do_x11_pulam_o_proprio_pet_pequenas_e_minimizadas():
    lidas = [
        (0xA, (10, 20, 1290, 740), 2222, 0, False),
        (0xB, (0, 0, 1920, 1080), 4444, 0, False),       # o próprio pet
        (0xC, (0, 0, 80, 40), 3333, 0, False),           # janelinha pequena
        (0xD, (30, 40, 530, 340), 5555, 0, True),        # minimizada
        (0xE, (30, 40, 530, 340), None, None, False),    # sem pid nem área: fica
    ]
    assert linux.filtrar_janelas(lidas, meu_pid=4444, desktop_atual=0) == [
        (0xA, (10, 20, 1290, 740), False), (0xE, (30, 40, 530, 340), False)]


def test_janelas_de_outra_area_de_trabalho_ficam_de_fora():
    lidas = [(1, (0, 0, 500, 400), 10, 0, False), (2, (0, 0, 500, 400), 11, 1, False),
             (3, (0, 0, 500, 400), 12, linux.TODAS_AS_AREAS, False)]
    assert [j[0] for j in linux.filtrar_janelas(lidas, 1, desktop_atual=0)] == [1, 3]
    assert [j[0] for j in linux.filtrar_janelas(lidas, 1, desktop_atual=None)] == [1, 2, 3]


def test_ocioso_do_gnome_vem_em_milissegundos():
    assert linux.parse_ocioso_gnome("(uint64 2500,)\n") == 2.5
    assert linux.parse_ocioso_gnome("Error: GDBus.Error:org.freedesktop.DBus.Error.ServiceUnknown") is None
    assert linux.parse_ocioso_gnome(None) is None


def test_no_wayland_o_pet_abre_pelo_xwayland(monkeypatch):
    for nome in ("WAYLAND_DISPLAY", "DISPLAY", "QT_QPA_PLATFORM"):
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    linux.preparar_qt()
    assert "QT_QPA_PLATFORM" not in os.environ          # sem XWayland: fica no Wayland
    monkeypatch.setenv("DISPLAY", ":1")
    linux.preparar_qt()
    assert os.environ["QT_QPA_PLATFORM"] == "xcb"
    monkeypatch.setenv("QT_QPA_PLATFORM", "wayland")     # quem escolheu é respeitado
    linux.preparar_qt()
    assert os.environ["QT_QPA_PLATFORM"] == "wayland"


@pytest.mark.skipif(sys.platform != "darwin", reason="Requer backend macOS")
def test_ioreg_converte_nanossegundos():
    texto = '  | |   "HIDIdleTime" = 2500000000\n  | |   "outra" = 5'
    assert macos is not None
    assert macos.ocioso_do_ioreg(texto) == 2.5
    assert macos.ocioso_do_ioreg("sem a chave") == 0.0


def _janela(pid, x, y, w, h, camada=0, janela_id=1):
    return {"kCGWindowOwnerPID": pid, "kCGWindowLayer": camada, "kCGWindowNumber": janela_id,
            "kCGWindowBounds": {"X": x, "Y": y, "Width": w, "Height": h}}


@pytest.mark.skipif(sys.platform != "darwin", reason="Requer backend macOS")
def test_quartz_janela_da_frente_e_do_programa_ativo():
    janelas = [
        _janela(10, 0, 0, 30, 20, janela_id=1),          # menu, pequeno: ignorado
        _janela(20, 100, 100, 800, 600, janela_id=2),    # programa ativo, a de cima
        _janela(20, 50, 50, 900, 700, janela_id=3),
    ]
    assert macos is not None
    assert macos.janela_da_frente(janelas, pid=20) == (100, 100, 900, 700)
    assert macos.janela_da_frente(janelas, pid=99) is None


@pytest.mark.skipif(sys.platform != "darwin", reason="Requer backend macOS")
def test_quartz_ignora_camadas_e_o_proprio_pet():
    janelas = [
        _janela(7, 0, 0, 1440, 900, janela_id=1),                 # o próprio pet
        _janela(8, 0, 0, 1440, 40, janela_id=2),                  # barra de menu (camada alta)
        _janela(9, 200, 150, 600, 400, janela_id=3),
    ]
    janelas[1]["kCGWindowLayer"] = 25
    assert macos is not None
    achadas = macos.janelas_de(janelas, meu_pid=7, excluir={99}, escala=2.0)
    assert achadas == [(3, (400.0, 300.0, 1600.0, 1100.0), False)]


@pytest.mark.skipif(sys.platform != "darwin", reason="Requer backend macOS")
def test_tela_cheia_no_mac_compara_com_a_tela():
    assert macos is not None
    assert macos._cobre((0, 0, 1440, 900), (0, 0, 1440, 900)) is True
    assert macos._cobre((100, 0, 1440, 900), (0, 0, 1440, 900)) is False


@pytest.mark.skipif(sys.platform != "darwin", reason="Requer backend macOS")
def test_atalho_do_mac_usa_control_option_shift(monkeypatch):
    """O atalho registrado deve ser o mesmo Ctrl+Alt/Option+Shift+B mostrado na interface."""
    assert macos is not None
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    assert app is not None
    capturado = {}

    class Atalho:
        def unregister(self):
            pass

    def quick_hot_key(**kwargs):
        capturado.update(kwargs)
        return lambda _callback: Atalho()

    if macos.mask is None:
        pytest.skip("sem QuickMacHotKey (conjunto legado): o atalho vai pelo pynput")
    monkeypatch.setattr(macos, "_hotkey", None)
    monkeypatch.setattr(macos, "quickHotKey", quick_hot_key)
    assert macos.iniciar_atalho(lambda: None) is True
    assert capturado == {
        "virtualKey": macos.kVK_ANSI_B,
        "modifierMask": macos.mask(macos.controlKey, macos.optionKey, macos.shiftKey),
    }


def test_atividade_reconhece_nomes_de_todos_os_sistemas():
    assert detect_activity("code.exe", 0.0, 300.0) == "PROGRAMMING"        # Windows
    assert detect_activity("code", 0.0, 300.0) == "PROGRAMMING"            # Linux
    assert detect_activity("Visual Studio Code", 0.0, 300.0) == "PROGRAMMING"   # macOS
    assert detect_activity("Google Chrome", 0.0, 300.0) == "BROWSING"
    assert detect_activity("Discord.exe", 0.0, 300.0) == "SOCIAL"
    assert detect_activity("Spotify", 0.0, 300.0) == "MUSIC"
    assert detect_activity("programa-desconhecido", 0.0, 300.0) == "IDLE"
    assert detect_activity("code", 400.0, 300.0) == "AWAY"


@pytest.mark.skipif(not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"),
                    reason="precisa de um X de verdade (DISPLAY)")
def test_no_x11_de_verdade_o_leitor_enxerga_as_janelas():
    env = dict(os.environ, QT_QPA_PLATFORM="xcb")
    script = Path(__file__).with_name("janela_real_linux.py")
    r = subprocess.run([sys.executable, str(script)], env=env, capture_output=True,  # noqa: S603  # nosec B603
                       text=True, timeout=60, check=False)
    if r.returncode == 2:
        pytest.skip(r.stdout.strip())
    assert r.returncode == 0, r.stdout + r.stderr


def test_android_devolve_tudo_neutro_e_o_menu_vem_pelo_toque():
    assert android.ocioso_segundos() == 0.0
    assert android.processo_ativo() == "unknown"
    assert android.retangulo_ativo() is None
    assert android.tela_cheia() is False
    assert android.janelas_visiveis({1}) == []
    assert android.iniciar_atalho(lambda: None) is False
    assert "toque longo" in android.LIMITACAO_ATALHO


@pytest.mark.skipif(sys.platform != "darwin", reason="Requer backend macOS")
def test_sem_quickmachotkey_o_mac_usa_o_pynput(monkeypatch):
    assert macos is not None
    chamadas = []
    monkeypatch.setattr(macos, "_hotkey", None)
    monkeypatch.setattr(macos, "quickHotKey", None)
    monkeypatch.setattr(macos, "atalho_pynput", lambda cb: chamadas.append(cb) or True)
    assert macos.iniciar_atalho(print) is True and chamadas == [print]

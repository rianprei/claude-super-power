"""
PLATAFORMA - a única parte do código que conhece o sistema operacional.

Cada sistema tem um módulo com as mesmas funções (windows.py, macos.py, linux.py, android.py). Este arquivo
escolhe o certo na importação. Os retângulos são em pixels físicos (o app converte para coordenadas
lógicas pela escala de cada tela) ou, se COORDENADAS_LOGICAS, já nas coordenadas do Qt (macOS, em pontos).

    ocioso_segundos()            segundos desde o último teclado ou mouse
    processo_ativo()             nome (minúsculo) do programa em primeiro plano
    retangulo_ativo(escala)      retângulo da janela em primeiro plano, ou None
    tela_cheia()                 a janela em primeiro plano cobre o monitor inteiro
    janelas_visiveis(excluir, escala)   [(id, (l, t, r, b), maximizada)] de cima para baixo
    sem_foco_nativo(janela_id)   a janela do pet não rouba o foco (quando o sistema permite)
    iniciar_atalho(callback)     Ctrl+Alt+Shift+B; devolve True se registrou
    LIMITACAO_ATALHO             texto se o atalho registrado só funciona em parte (ou None)
    regiao_de_clique(id, rets)   só esses retângulos da janela recebem o mouse (X11; nos outros, nada)
    atravessar_clique(id, sim)   o clique atravessa a janela inteira (Windows e macOS; no X11, nada)
    pasta_de_dados()             pasta do app nos dados do usuário (quando a do programa não serve)
    preparar_qt()                antes do QApplication (Linux: Wayland abre pelo XWayland)
"""

import os
import sys
from pathlib import Path

# o Python do Android diz "android" a partir do 3.13; antes (python-for-android) diz "linux", mas tem isto
ANDROID = sys.platform == "android" or hasattr(sys, "getandroidapilevel")

if sys.platform == "win32":
    from . import windows as _backend
elif sys.platform == "darwin":
    from . import macos as _backend
elif ANDROID:
    from . import android as _backend
else:
    from . import linux as _backend  # type: ignore[no-redef]  # ANDROID não é teste de plataforma para o mypy

NOME_DO_SISTEMA = "Android" if ANDROID else {"win32": "Windows", "darwin": "macOS"}.get(sys.platform, "Linux")

ocioso_segundos = _backend.ocioso_segundos
processo_ativo = _backend.processo_ativo
retangulo_ativo = _backend.retangulo_ativo
tela_cheia = _backend.tela_cheia
janelas_visiveis = _backend.janelas_visiveis
sem_foco_nativo = _backend.sem_foco_nativo
iniciar_atalho = _backend.iniciar_atalho
LIMITACAO_ATALHO = getattr(_backend, "LIMITACAO_ATALHO", None)
COORDENADAS_LOGICAS = getattr(_backend, "COORDENADAS_LOGICAS", False)
preparar_qt = getattr(_backend, "preparar_qt", lambda: None)


def _sem_regiao(janela_id, retangulos):
    """Windows e macOS já deixam o clique passar nos pixels transparentes: nada a fazer."""
    del janela_id, retangulos
    return False


def _sem_atravessar(janela_id, sim):
    """X11 recorta a região de entrada (regiao_de_clique): nada a fazer."""
    del janela_id, sim


regiao_de_clique = getattr(_backend, "regiao_de_clique", _sem_regiao)
atravessar_clique = getattr(_backend, "atravessar_clique", _sem_atravessar)


def pasta_de_dados():
    """Pasta do app nos dados do usuário: %LOCALAPPDATA% no Windows, ~/Library/Application Support no macOS,
    a pasta privada do app no Android, $XDG_DATA_HOME (ou ~/.local/share) no Linux."""
    casa = Path.home()
    if ANDROID:
        base = Path(os.environ.get("ANDROID_PRIVATE") or casa)
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or casa / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = casa / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or casa / ".local" / "share")
    return base / "Claude Super Power"

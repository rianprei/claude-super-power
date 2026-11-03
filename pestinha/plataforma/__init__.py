"""
PLATAFORMA - a única parte do código que conhece o sistema operacional.

Cada sistema tem um módulo com as mesmas funções (windows.py, macos.py, linux.py). Este arquivo
escolhe o certo na importação. Os retângulos são em pixels físicos (o app divide pelo dpr).

    ocioso_segundos()            segundos desde o último teclado ou mouse
    processo_ativo()             nome (minúsculo) do programa em primeiro plano
    retangulo_ativo(escala)      retângulo da janela em primeiro plano, ou None
    tela_cheia()                 a janela em primeiro plano cobre o monitor inteiro
    janelas_visiveis(excluir, escala)   [(id, (l, t, r, b), maximizada)] de cima para baixo
    sem_foco_nativo(janela_id)   a janela do pet não rouba o foco (quando o sistema permite)
    iniciar_atalho(callback)     Ctrl+Alt+Shift+B; devolve True se registrou
    LIMITACAO_ATALHO             texto se o atalho registrado só funciona em parte (ou None)
    regiao_de_clique(id, rets)   só esses retângulos da janela recebem o mouse (X11; nos outros, nada)
"""

import sys

if sys.platform == "win32":
    from . import windows as _backend
elif sys.platform == "darwin":
    from . import macos as _backend
else:
    from . import linux as _backend

NOME_DO_SISTEMA = {"win32": "Windows", "darwin": "macOS"}.get(sys.platform, "Linux")

ocioso_segundos = _backend.ocioso_segundos
processo_ativo = _backend.processo_ativo
retangulo_ativo = _backend.retangulo_ativo
tela_cheia = _backend.tela_cheia
janelas_visiveis = _backend.janelas_visiveis
sem_foco_nativo = _backend.sem_foco_nativo
iniciar_atalho = _backend.iniciar_atalho
LIMITACAO_ATALHO = getattr(_backend, "LIMITACAO_ATALHO", None)


def _sem_regiao(janela_id, retangulos):
    """Windows e macOS já deixam o clique passar nos pixels transparentes: nada a fazer."""
    del janela_id, retangulos
    return False


regiao_de_clique = getattr(_backend, "regiao_de_clique", _sem_regiao)

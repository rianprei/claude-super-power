"""
Android: o pet mora dentro do próprio app. O Android não deixa um app Qt flutuar sobre os outros nem ler
as janelas, o programa em primeiro plano ou o tempo ocioso deles, e não há atalho de teclado global. Tudo
isso devolve o valor neutro: o pet anda, brinca, sente e aprende na tela do app, e o menu abre com um toque
longo nele (pet.py).
"""

COORDENADAS_LOGICAS = True          # não há janelas de outros programas para converter
LIMITACAO_ATALHO = "no Android não há atalho de teclado global; use o menu do pet (toque longo)"


def ocioso_segundos():
    """O Android não informa o tempo sem toque a outros apps: fica como se você estivesse sempre ativo."""
    return 0.0


def processo_ativo():
    """O app em primeiro plano é sempre o próprio pet."""
    return "unknown"


def retangulo_ativo(escala=1.0):
    """Não há janelas de outros programas."""
    del escala


def tela_cheia():
    """O pet já ocupa a tela do app."""
    return False


def janelas_visiveis(excluir, escala=1.0):
    """Não há barras de título para pousar."""
    del excluir, escala
    return []


def sem_foco_nativo(janela_id):
    """Dentro do app o foco não atrapalha ninguém."""
    del janela_id


def iniciar_atalho(callback):
    """Sem atalho global no Android (o menu do pet faz o mesmo)."""
    del callback
    return False

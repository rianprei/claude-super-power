"""
Confere a glibc mínima de cada binário de um app empacotado (a pasta do PyInstaller, no Linux).

A glibc é a única biblioteca que o executável usa do sistema e não leva junto: se um binário pede uma
versão mais nova que a da distro, o app não abre ("version GLIBC_2.38 not found"). Isto lê, em cada ELF, as
versões GLIBC_x.y que ele pede (a tabela de versões fica em texto, terminada em zero) e falha se alguma
passar do limite.

    python ferramentas/minimo_glibc.py dist/Pestinha 2.28
"""

import re
import sys
from pathlib import Path

ELF = b"\x7fELF"
VERSAO = re.compile(rb"GLIBC_(\d+)\.(\d+)(?:\.\d+)?\x00")


def minimo(caminho: Path) -> tuple[int, int] | None:
    """Maior GLIBC_x.y pedida pelo arquivo, ou None se não é ELF ou não pede nenhuma."""
    with open(caminho, "rb") as f:
        if f.read(4) != ELF:
            return None
        dados = f.read()
    versoes = [(int(a), int(b)) for a, b in VERSAO.findall(dados)]
    return max(versoes) if versoes else None


def acima_do_limite(pasta: Path, limite: tuple[int, int]) -> list[tuple[str, tuple[int, int]]]:
    """[(arquivo, glibc)] dos binários que pedem uma glibc mais nova que `limite`."""
    achados = []
    for arquivo in sorted(pasta.rglob("*")):
        if arquivo.is_file() and not arquivo.is_symlink():
            versao = minimo(arquivo)
            if versao is not None and versao > limite:
                achados.append((str(arquivo.relative_to(pasta)), versao))
    return achados


def main(argv: list[str]) -> int:
    pasta, limite_texto = Path(argv[1]), argv[2]
    maior, menor = (int(x) for x in limite_texto.split("."))
    achados = acima_do_limite(pasta, (maior, menor))
    for nome, (a, b) in achados:
        print(f"{nome}: glibc {a}.{b}")
    print(f"{len(achados)} binário(s) acima da glibc {limite_texto}")
    return 1 if achados else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

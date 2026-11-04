"""
Confere o macOS mínimo de cada binário de um app empacotado (Pestinha.app ou a pasta do PyInstaller).

O GitHub não tem máquinas com macOS antigo: isto lê, em cada arquivo Mach-O, a versão mínima gravada pelo
compilador (LC_BUILD_VERSION ou LC_VERSION_MIN_MACOSX) da arquitetura pedida e falha se alguma passar do
limite. Um binário com mínimo 15.0 pode usar o que não existe no macOS 14: um só basta para o app inteiro não abrir.
A etiqueta da roda não serve: a do PySide6 6.11.3 diz macOS 13, mas os módulos dele pedem o 15.

    python ferramentas/minimo_macos.py dist/Pestinha.app 10.14 x86_64
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

CPU = {"x86_64": 0x01000007, "arm64": 0x0100000C}
FAT, FAT_64 = 0xCAFEBABE, 0xCAFEBABF
FINO = {b"\xce\xfa\xed\xfe": 28, b"\xcf\xfa\xed\xfe": 32}      # Mach-O de 32 e 64 bits (little-endian): tamanho do cabeçalho
LC_VERSION_MIN_MACOSX, LC_BUILD_VERSION, PLATAFORMA_MACOS = 0x24, 0x32, 1
MAX_ARQUITETURAS = 20       # um .class do Java também começa com CAFEBABE, mas com um "número" bem maior


def _versao(codificada: int) -> tuple[int, int]:
    """xxxx.yy.zz codificado em 32 bits -> (maior, menor)."""
    return codificada >> 16, (codificada >> 8) & 0xFF


def _minimo_fino(f, inicio: int) -> tuple[int, int] | None:
    """Mínimo de macOS de um Mach-O que começa em `inicio`, ou None se não tiver o comando."""
    f.seek(inicio)
    cabecalho = f.read(32)
    tamanho = FINO.get(cabecalho[:4])
    if tamanho is None:
        return None
    ncmds, sizeofcmds = struct.unpack_from("<II", cabecalho, 16)
    f.seek(inicio + tamanho)
    comandos = f.read(sizeofcmds)
    pos = 0
    for _ in range(ncmds):
        if pos + 8 > len(comandos):
            break
        cmd, cmdsize = struct.unpack_from("<II", comandos, pos)
        if cmd == LC_BUILD_VERSION and struct.unpack_from("<I", comandos, pos + 8)[0] == PLATAFORMA_MACOS:
            return _versao(struct.unpack_from("<I", comandos, pos + 12)[0])
        if cmd == LC_VERSION_MIN_MACOSX:
            return _versao(struct.unpack_from("<I", comandos, pos + 8)[0])
        pos += max(cmdsize, 8)
    return None


def minimo(caminho: Path, arquitetura: str) -> tuple[int, int] | None:
    """Mínimo de macOS da fatia `arquitetura` do arquivo (fino ou universal), ou None se não for Mach-O dela."""
    cpu = CPU[arquitetura]
    with open(caminho, "rb") as f:
        inicio = f.read(8)
        if len(inicio) < 8:
            return None
        if inicio[:4] in FINO:
            return _minimo_fino(f, 0) if struct.unpack_from("<I", inicio, 4)[0] == cpu else None
        magica, n = struct.unpack(">II", inicio)
        if magica not in (FAT, FAT_64) or n > MAX_ARQUITETURAS:
            return None
        formato, passo = (">IIQQII", 32) if magica == FAT_64 else (">IIIII", 20)
        tabela = f.read(n * passo)
        for i in range(n):
            tipo, _sub, deslocamento, *_ = struct.unpack_from(formato, tabela, i * passo)
            if tipo == cpu:
                return _minimo_fino(f, deslocamento)
    return None


def acima_do_limite(pasta: Path, limite: tuple[int, int], arquitetura: str) -> list[tuple[str, tuple[int, int]]]:
    """[(arquivo, mínimo)] dos binários que pedem um macOS mais novo que `limite`."""
    achados = []
    for arquivo in sorted(pasta.rglob("*")):
        if arquivo.is_file() and not arquivo.is_symlink():
            versao = minimo(arquivo, arquitetura)
            if versao is not None and versao > limite:
                achados.append((str(arquivo.relative_to(pasta)), versao))
    return achados


def main(argv: list[str]) -> int:
    pasta, limite_texto, arquitetura = Path(argv[1]), argv[2], argv[3]
    maior, menor = (int(x) for x in limite_texto.split("."))
    achados = acima_do_limite(pasta, (maior, menor), arquitetura)
    for nome, (a, b) in achados:
        print(f"{nome}: macOS {a}.{b}")
    print(f"{len(achados)} binário(s) de {arquitetura} acima do macOS {limite_texto}")
    return 1 if achados else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

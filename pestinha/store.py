"""
STORE - a única forma de gravar e ler arquivos de estado.

Escrita atômica (arquivo temporário + fsync + troca), leitura tolerante (arquivo
ausente ou corrompido vira o valor padrão, sem derrubar o app) e uma linha
por registro para os históricos. Todos os módulos usam isto.
"""

import contextlib
import json
import os
import shutil
import tempfile
from pathlib import Path


def _gravar_atomico(path, texto):
    """Grava `texto` num temporário único da mesma pasta, força para o disco e troca pelo definitivo."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(texto)
            f.flush()
            os.fsync(f.fileno())
        Path(tmp).replace(path)
    except BaseException:
        with contextlib.suppress(OSError):
            Path(tmp).unlink()
        raise


def write_json(path, data, indent=None):
    """Grava um JSON de forma atômica, recusando NaN e infinito (ValueError antes de tocar no arquivo)."""
    _gravar_atomico(path, json.dumps(data, ensure_ascii=False, indent=indent, allow_nan=False))


def _sem_nan(valor):
    """Recusa NaN e infinito ao gravar ou ler JSON."""
    raise ValueError(f"constante não permitida no JSON: {valor}")


def preservar(path, sufixo, copiar=False):
    """
    Guarda `path` como `path.sufixo` sem sobrescrever cópias anteriores (.sufixo, .sufixo.2, ...).
    copiar=False move (arquivo ilegível sai do caminho); copiar=True deixa o original onde está.
    """
    path = Path(path)
    alvo = path.with_name(f"{path.name}.{sufixo}")
    n = 2
    try:
        original = path.read_bytes() if copiar else None
        while alvo.exists():
            if original is not None and alvo.read_bytes() == original:
                return alvo                     # a mesma cópia já está guardada: não acumula
            alvo = path.with_name(f"{path.name}.{sufixo}.{n}")
            n += 1
        if copiar:
            shutil.copy2(path, alvo)
        else:
            path.replace(alvo)
    except OSError:
        return None
    return alvo


def read_json(path, default=None, guardar_corrompido=True):
    """
    Lê um JSON; arquivo ausente ou corrompido devolve `default`.

    Arquivo de estado corrompido é guardado como .corrompido (para não ser sobrescrito).
    Conteúdo que você edita (pets/*.json) usa guardar_corrompido=False: fica onde está.
    """
    path = Path(path)
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.loads(f.read(), parse_constant=_sem_nan)
    except OSError:
        return default
    except ValueError:
        if guardar_corrompido:
            preservar(path, "corrompido")
        return default


def append_line(path, line):
    """Acrescenta uma linha no fim de um arquivo de texto (cria a pasta se preciso)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write(line.rstrip("\n") + "\n")


def decodificar(dados):
    """Texto de um arquivo editado à mão: UTF-8 (com ou sem BOM) ou, se não for, Windows-1252."""
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dados.decode("cp1252", errors="replace")


def read_lines(path):
    """Lê as linhas de um arquivo de texto (UTF-8, UTF-8 com BOM ou ANSI); vazio se não existir."""
    try:
        return decodificar(Path(path).read_bytes()).splitlines()
    except OSError:
        return []


def write_lines(path, lines):
    """Grava uma lista de linhas em um arquivo de texto (atômico)."""
    _gravar_atomico(path, "".join(line.rstrip("\n") + "\n" for line in lines))

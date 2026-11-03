"""
LOG - um lugar só para mensagens do app: terminal e arquivo em memory/logs/.

O arquivo é aparado quando passa de 1 MB (fica com a metade mais recente).
Se o arquivo não puder ser escrito, a mensagem vai só para o terminal.
"""

import contextlib
import datetime
from pathlib import Path

MAX_BYTES = 1_000_000
_estado: dict[str, Path | None] = {"arquivo": None}     # um dict, não `global`: setup e desligar só trocam a chave


def setup(path):
    """Escolhe o arquivo do log (criado sob demanda)."""
    _estado["arquivo"] = Path(path)


def desligar_arquivo():
    """Para de gravar em arquivo (usado ao apagar os dados: nada pode recriar a pasta)."""
    _estado["arquivo"] = None


def _trim(arquivo):
    """Corta o início do log quando ele passa do limite, para não crescer sem fim."""
    try:
        if arquivo.exists() and arquivo.stat().st_size > MAX_BYTES:
            lines = arquivo.read_text(encoding="utf-8", errors="replace").splitlines()
            arquivo.write_text("\n".join(lines[len(lines) // 2:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def log(*parts):
    """Escreve uma mensagem no terminal e no arquivo do log (uma linha por chamada)."""
    text = " ".join(str(p) for p in parts)
    try:
        print(text)
    except UnicodeEncodeError:
        with contextlib.suppress(OSError, ValueError):
            print(text.encode("ascii", "replace").decode("ascii"))
    except (OSError, ValueError):
        pass        # terminal fechado (EIO, pipe quebrado) ou stdout já fechado: o arquivo ainda recebe
    arquivo = _estado["arquivo"]
    if arquivo is None:
        return
    try:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        with open(arquivo, "a", encoding="utf-8") as f:     # modo texto: "\n" já vira o fim de linha do sistema
            f.write(f"{stamp} {text}\n")
        _trim(arquivo)
    except OSError:
        pass

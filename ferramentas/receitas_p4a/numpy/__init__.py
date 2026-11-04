"""
Receita local do numpy para o python-for-android fixado no commit f8e5c05 (variante compatível: Android 9,
Python 3.11): a mesma receita dele, compilando sem ambiente isolado.

Motivo (visto no CI): o `python -m build` de hoje (1.6) cria o ambiente isolado com o venv do Python do
próprio build (hostpython, que roda da pasta de compilação), e dentro desse venv os módulos nativos dele não
são achados: o meson-python morre em `import subprocess` ("No module named '_posixsubprocess'"). O Python de
fora acha (o PYTHONPATH da receita aponta para eles), então as dependências de build vão direto para o
site-packages do hostpython, nas versões que o numpy 1.26 pede, e o build roda com --no-isolation.

Usada só quando PESTINHA_P4A_RECEITAS aponta para esta pasta (ferramentas/gerar_android.py).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import ClassVar

import pythonforandroid.recipes as receitas

# este módulo é carregado com o mesmo nome do original (pythonforandroid.recipes.numpy): o original vem pelo arquivo
_arquivo = Path(receitas.__file__).parent / "numpy" / "__init__.py"
_spec = importlib.util.spec_from_file_location("p4a_numpy_original", _arquivo)
if _spec is None or _spec.loader is None:
    raise ImportError(f"receita original do numpy não encontrada: {_arquivo}")
_original = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_original)


class NumpySemIsolamento(_original.NumpyRecipe):
    """O numpy da receita original, sem o ambiente isolado do `python -m build`."""

    # listas: o python-for-android acrescenta itens nelas (meson, ninja, o arquivo de compilação cruzada)
    hostpython_prerequisites: ClassVar[list[str]] = ["Cython>=3.0.6,<3.1", "meson-python>=0.15.0,<0.16.0", "pyproject-metadata>=0.7.1",
                                "packaging"]
    extra_build_args: ClassVar[list[str]] = [*_original.NumpyRecipe.extra_build_args, "--no-isolation", "--skip-dependency-check"]


recipe = NumpySemIsolamento()

"""
Gera o APK do Android com o pyside6-android-deploy (PySide6 6.12, Python 3.14 no aparelho, Android 10 ou mais
novo, arm64-v8a ou x86_64). Na raiz do projeto, com o PySide6 de desktop da mesma versão instalado:

    python ferramentas/gerar_android.py --name ClaudeSuperPower --wheel-pyside pyside6-...android_aarch64.whl \
        --wheel-shiboken shiboken6-...android_aarch64.whl --ndk-path $NDK --sdk-path $SDK -f

Os argumentos são os do pyside6-android-deploy. Duas variáveis de ambiente escolhem a variante:
- PESTINHA_API_MINIMA: a API mínima do Android (29 com o PySide6 6.12; 28 com o 6.8.3, o último cujas
  bibliotecas não usam TLS nativo do ELF e por isso abrem no Android 9);
- PESTINHA_P4A e PESTINHA_P4A_COMMIT: o branch e o commit do python-for-android. A ferramenta do 6.8.3 clona o
  develop, que hoje traz o Python 3.14 (as rodas dela são cp311); a v2024.01.21 tem o Python 3.11, mas o
  bootstrap Qt dela ainda chama QtNative.setEnvironmentVariable, que o Qt 6.8 tirou. O commit f8e5c05 (agosto de
  2024) tem o bootstrap já adaptado, o Python 3.11.5 e o numpy 1.26.5. Vazias: as da ferramenta.
- PESTINHA_P4A_RECEITAS: pasta de receitas locais do python-for-android (ferramentas/receitas_p4a com o commit
  f8e5c05: o numpy dele não compila com o `build` de hoje). Vazia: só as receitas dele. A ferramenta escreve um buildozer.spec só com
python3, shiboken6 e PySide6; aqui ele ganha o resto, antes do build:
- Android 10 (API 29) como mínimo (a ferramenta diz 28, mas as rodas não abrem no 9);
- numpy (a rede neural do pet);
- os arquivos de conteúdo dos pets (json, txt e imagens), que não são .py;
- fora do pacote: testes, ferramentas, documentação, executáveis de desktop e a memória local.
"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

import PySide6

REQUISITOS = "python3,shiboken6,PySide6,numpy"
EXTENSOES = "py,png,jpg,jpeg,gif,webp,json,txt"
FORA = "tests,ferramentas,docs,executáveis,build,dist,memory,bin,.github,.buildozer"
# Android 10 com o PySide6 6.12: a libshiboken6 dele usa TLS nativo do ELF, que o Android 9 não carrega
# ("dlopen failed: unknown reloc type 16", visto no emulador com API 28)
API_MINIMA = os.environ.get("PESTINHA_API_MINIMA", "29")
P4A = os.environ.get("PESTINHA_P4A", "")
P4A_COMMIT = os.environ.get("PESTINHA_P4A_COMMIT", "")
P4A_RECEITAS = os.environ.get("PESTINHA_P4A_RECEITAS", "")


def main() -> None:
    scripts = Path(PySide6.__file__).parent / "scripts"
    sys.path.insert(0, str(scripts))
    from deploy_lib.android import (
        buildozer,  # mesmo módulo que o android_deploy.py importa
    )

    original = buildozer.BuildozerConfig.__init__

    def completar(self, spec, config):
        original(self, spec, config)
        self.set_value("app", "requirements", REQUISITOS)
        self.set_value("app", "source.include_exts", EXTENSOES, raise_warning=False)
        self.set_value("app", "source.exclude_dirs", FORA, raise_warning=False)
        self.set_value("app", "android.minapi", API_MINIMA, raise_warning=False)
        self.set_value("app", "android.ndk_api", API_MINIMA, raise_warning=False)
        if P4A:
            self.set_value("app", "p4a.branch", P4A, raise_warning=False)
        if P4A_COMMIT:
            self.set_value("app", "p4a.commit", P4A_COMMIT, raise_warning=False)
        if P4A_RECEITAS:
            pasta = Path(P4A_RECEITAS).resolve()
            if not (pasta / "numpy" / "__init__.py").is_file():
                raise SystemExit(f"PESTINHA_P4A_RECEITAS sem receitas: {pasta}")
            self.set_value("app", "p4a.local_recipes", str(pasta), raise_warning=False)
        self.update_config()

    buildozer.BuildozerConfig.__init__ = completar
    sys.argv = [str(scripts / "android_deploy.py"), *sys.argv[1:]]
    runpy.run_path(str(scripts / "android_deploy.py"), run_name="__main__")


if __name__ == "__main__":
    main()

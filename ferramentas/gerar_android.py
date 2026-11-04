"""
Gera o APK do Android com o pyside6-android-deploy (PySide6 6.12, Python 3.14 no aparelho, Android 9 ou mais
novo, arm64-v8a ou x86_64). Na raiz do projeto, com o PySide6 de desktop da mesma versão instalado:

    python ferramentas/gerar_android.py --name ClaudeSuperPower --wheel-pyside pyside6-...android_aarch64.whl \
        --wheel-shiboken shiboken6-...android_aarch64.whl --ndk-path $NDK --sdk-path $SDK -f

Os argumentos são os do pyside6-android-deploy. A ferramenta escreve um buildozer.spec só com
python3, shiboken6 e PySide6; aqui ele ganha o resto, antes do build:
- numpy (a rede neural do pet);
- os arquivos de conteúdo dos pets (json, txt e imagens), que não são .py;
- fora do pacote: testes, ferramentas, documentação, executáveis de desktop e a memória local.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import PySide6

REQUISITOS = "python3,shiboken6,PySide6,numpy"
EXTENSOES = "py,png,jpg,jpeg,gif,webp,json,txt"
FORA = "tests,ferramentas,docs,executáveis,build,dist,memory,bin,.github,.buildozer"


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
        self.update_config()

    buildozer.BuildozerConfig.__init__ = completar
    sys.argv = [str(scripts / "android_deploy.py"), *sys.argv[1:]]
    runpy.run_path(str(scripts / "android_deploy.py"), run_name="__main__")


if __name__ == "__main__":
    main()

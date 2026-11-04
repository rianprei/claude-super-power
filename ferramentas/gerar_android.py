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
- PESTINHA_P4A_RECEITAS: pasta com receitas a mais para o python-for-android (ferramentas/receitas_p4a com o
  commit f8e5c05: o numpy dele não compila com o `build` de hoje). Elas são copiadas para a pasta de receitas da
  ferramenta, ao lado das do PySide6 e do shiboken6 (que copiam as bibliotecas do Qt para o APK: apontar o
  p4a.local_recipes para outra pasta as esconderia, e o APK sairia sem o Qt). Vazia: só as da ferramenta. A ferramenta escreve um buildozer.spec só com
python3, shiboken6 e PySide6; aqui ele ganha o resto, antes do build:
- Android 10 (API 29) como mínimo (a ferramenta diz 28, mas as rodas não abrem no 9);
- numpy (a rede neural do pet);
- os arquivos de conteúdo dos pets (json, txt e imagens), que não são .py;
- fora do pacote: testes, ferramentas, documentação, executáveis de desktop e a memória local;
- o pet flutuando sobre os outros apps, como no PC: a activity de entrada e a Ponte (android_java/, ver
  pestinha/plataforma/android.py), a permissão SYSTEM_ALERT_WINDOW ("Exibir sobre outros apps") e o Qt
  continuando a rodar com a activity em segundo plano (android.app.background_running).
"""

from __future__ import annotations

import os
import runpy
import shutil
import sys
from pathlib import Path

import PySide6

REQUISITOS = "python3,shiboken6,PySide6,numpy"
EXTENSOES = "py,png,jpg,jpeg,gif,webp,json,txt"
FORA = "tests,ferramentas,docs,executáveis,build,dist,memory,bin,.github,.buildozer,android_java"
JAVA = Path(__file__).resolve().parent.parent / "android_java"
ENTRADA = "org.claudesuperpower.Entrada"
PERMISSOES = ("SYSTEM_ALERT_WINDOW", "PACKAGE_USAGE_STATS")     # flutuar; ver o app em uso (como no PC)
META_DADOS = "android.app.background_running=true"
# Android 10 com o PySide6 6.12: a libshiboken6 dele usa TLS nativo do ELF, que o Android 9 não carrega
# ("dlopen failed: unknown reloc type 16", visto no emulador com API 28)
API_MINIMA = os.environ.get("PESTINHA_API_MINIMA", "29")
P4A = os.environ.get("PESTINHA_P4A", "")
P4A_COMMIT = os.environ.get("PESTINHA_P4A_COMMIT", "")
P4A_RECEITAS = os.environ.get("PESTINHA_P4A_RECEITAS", "")


def copiar_receitas(origem: Path, destino: Path) -> None:
    """Copia cada receita (uma pasta com __init__.py) de `origem` para a pasta de receitas da ferramenta."""
    receitas = [r for r in sorted(origem.iterdir()) if (r / "__init__.py").is_file()] if origem.is_dir() else []
    if not receitas or not (destino / "PySide6").is_dir():
        raise SystemExit(f"receitas: nada para copiar de {origem} ou {destino} sem a receita do PySide6")
    for receita in receitas:
        shutil.copytree(receita, destino / receita.name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
        print(f"receita {receita.name} -> {destino / receita.name}")


def somar_permissoes(atuais: str, novas: tuple[str, ...]) -> str:
    """As permissões que a ferramenta achou (texto "A, B") mais as nossas, sem repetir."""
    lista = [p.strip() for p in atuais.split(",") if p.strip()]
    return ", ".join(dict.fromkeys([*lista, *novas]))


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
            copiar_receitas(Path(P4A_RECEITAS).resolve(), Path(config.recipe_dir))
        self.set_value("app", "android.add_src", str(JAVA), raise_warning=False)
        self.set_value("app", "android.entrypoint", ENTRADA, raise_warning=False)
        self.set_value("app", "android.meta_data", META_DADOS, raise_warning=False)
        atuais = self.get_value("app", "android.permissions", ignore_fail=True) or ""
        self.set_value("app", "android.permissions", somar_permissoes(atuais, PERMISSOES), raise_warning=False)
        self.update_config()

    buildozer.BuildozerConfig.__init__ = completar
    sys.argv = [str(scripts / "android_deploy.py"), *sys.argv[1:]]
    runpy.run_path(str(scripts / "android_deploy.py"), run_name="__main__")


if __name__ == "__main__":
    main()

"""
PESTINHA - ponto de entrada.

Rodar:
    python main.py              passo a passo (primeira vez) e tela de permissões
    python main.py --direto     usa as permissões salvas
    python main.py --sair-em N  fecha sozinho depois de N segundos (para testes)

Dependências em requirements.txt. Pânico: Ctrl + Alt + Shift + B (desliga tudo e continua desligado).
"""

from __future__ import annotations

import argparse
import shutil
import sys

import qt_legado

qt_legado.ativar()     # antes do PySide6: no conjunto legado, o Qt 5 com a cara dele

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QWidget

from pestinha import config, plataforma
from pestinha.app import PestinhaApp
from pestinha.paths import Paths, memoria_gravavel
from pestinha.settings_store import SettingsStore
from pestinha.ui.onboarding import Onboarding
from pestinha.ui.ui import SettingsDialog, face_icon


def apagar_memoria(paths):
    """Apaga memory/ e confirma o resultado; devolve (sucesso, caminhos que falharam)."""
    falhas = []
    if paths.memory.exists():
        shutil.rmtree(paths.memory, onerror=lambda _f, caminho, _e: falhas.append(str(caminho)))
    return not falhas and not paths.memory.exists(), falhas


def palco_android():
    """Tela cheia preta atrás de tudo. No Android as janelas do Qt não ficam transparentes (o fundo delas sai
    preto) e o fundo da tela é claro: no palco preto o pet, a bolinha e o notebook aparecem sem a caixa."""
    palco = QWidget()
    palco.setStyleSheet("background: black;")
    palco.showFullScreen()
    return palco


def main():
    parser = argparse.ArgumentParser(description=config.APP_NOME)
    parser.add_argument("--direto", action="store_true", help="pula a tela inicial")
    parser.add_argument("--sair-em", type=float, default=0.0, help="fecha sozinho após N segundos (teste)")
    args = parser.parse_args()

    plataforma.preparar_qt()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    paths = Paths(memoria=memoria_gravavel())
    store = SettingsStore(paths)
    perms = store.perms
    pet = config.load_pet(paths, config.escolher_pet(paths, perms["pet"]))
    app.setWindowIcon(face_icon(corpo=pet["corpo"]))       # o passo a passo usa este ícone
    if not args.direto and not plataforma.ANDROID:    # no Android as permissões de desktop não se aplicam
        first_time = not paths.permissions.exists()
        if first_time and Onboarding(pet["nome"], pet["corpo"]).exec() != QDialog.DialogCode.Accepted:
            pass                                    # "Pular" também segue para as permissões
        dialog = SettingsDialog(perms, paths, first_run=True)
        # o diálogo trabalha numa cópia: cada escolha vem por aqui, mas só é gravada ao clicar em Começar
        # (quem clica em Sair não deixa permissões salvas, e o passo a passo volta na próxima vez)
        dialog.changed.connect(lambda novo: perms.update(config.permissoes_validas(novo)))
        apagado = []

        def apagar_tudo():
            sucesso, falhas = apagar_memoria(paths)
            if not sucesso:
                detalhe = f"\n\nArquivos que falharam: {', '.join(falhas)}" if falhas else ""
                QMessageBox.warning(
                    dialog, "Não foi possível apagar tudo",
                    "Alguns dados continuam na pasta memory/. Feche programas que possam estar "
                    f"usando esses arquivos e tente novamente.{detalhe}",
                )
                return
            apagado.append(True)
            dialog.reject()

        dialog.wipe_all.connect(apagar_tudo)
        if dialog.exec() != QDialog.DialogCode.Accepted or apagado:
            return 0
        store.save()                                # grava já: a próxima vez não mostra o passo a passo

    palco = palco_android() if plataforma.ANDROID else None     # antes do pet: fica atrás dele
    pet_app = PestinhaApp(store, paths)
    if args.sair_em > 0:
        QTimer.singleShot(int(args.sair_em * 1000), pet_app.quit)
    codigo = app.exec()
    del palco                       # o palco viveu até aqui, atrás do pet
    return codigo


if __name__ == "__main__":
    sys.exit(main())

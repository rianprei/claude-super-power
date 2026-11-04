#!/bin/sh
# Gera as rodas do PySide6 6.8.3 para Android de 32 bits (o Qt não publica rodas de 32 bits):
#
#   sh ferramentas/gerar_rodas_android_32bits.sh armv7a "$ANDROID_HOME" "$ANDROID_HOME/ndk/26.1.10909125"
#
# armv7a: os celulares de 32 bits; i686: o x86 de 32 bits (emulador). Usa o Qt 6.8.3 para Android do instalador
# oficial (aqtinstall), o pyside-setup v6.8.3 e a ferramenta de compilação cruzada dele, só com QtCore, QtGui e
# QtWidgets (o que o app usa), na API 28 (Android 9: o NDK usa TLS emulado abaixo da API 29).
# Resultado: pyside-setup/dist/*.whl (PySide6 e shiboken6).
set -eu
ARCH="$1"
SDK="$2"
NDK="$3"
QT=6.8.3
case "$ARCH" in
    armv7a) QT_ARCH=android_armv7 ;;
    i686) QT_ARCH=android_x86 ;;
    *) echo "arquitetura desconhecida: $ARCH" >&2; exit 2 ;;
esac
python -m pip install -q aqtinstall gitpython "markupsafe==2.0.1" jinja2 tqdm
python -m aqt install-qt linux desktop "$QT" linux_gcc_64 -O "$HOME/Qt"
python -m aqt install-qt linux android "$QT" "$QT_ARCH" -O "$HOME/Qt"
git clone -q --depth 1 -b "v$QT" https://github.com/qtproject/pyside-pyside-setup.git pyside-setup
cd pyside-setup
python -m pip install -q -r requirements.txt
# só os módulos que o app usa: o build inteiro leva horas
sed -i 's/"--no-qt-tools"\]/"--no-qt-tools", "--module-subset=Core,Gui,Widgets"]/' tools/cross_compile_android/main.py
grep -q -- '--module-subset=Core,Gui,Widgets' tools/cross_compile_android/main.py
python tools/cross_compile_android/main.py --plat-name "$ARCH" --qt-install-path "$HOME/Qt/$QT" \
    --ndk-path "$NDK" --sdk-path "$SDK" --api-level 28 --auto-accept-license --skip-update
ls dist/

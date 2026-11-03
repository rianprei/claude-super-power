#!/bin/sh
# Gera o app de Linux compatível (glibc 2.28: Debian 10+, Ubuntu 20.04+, RHEL/Alma/Rocky 8+, openSUSE Leap 15...)
# dentro de um AlmaLinux 8, com o conjunto de requirements-compativel.txt. Na raiz do projeto:
#
#   docker run --rm -v "$PWD:/src" -w /src almalinux:8 sh ferramentas/gerar_linux_compativel.sh
#
# Resultado: dist/Pestinha/ (executável + assets/ + pets/), já podado e com a glibc conferida.
set -eu
dnf install -y -q epel-release >/dev/null
# gcc e kernel-headers: o evdev (dependência do pynput) só vem como código-fonte
# xcb-util-*: entram no app (muitas distros não instalam), o PyInstaller copia as daqui
dnf install -y -q python3.11 python3.11-devel gcc kernel-headers binutils findutils \
    xcb-util-cursor xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil libxkbcommon-x11 \
    mesa-libEGL mesa-libGL fontconfig >/dev/null
python3.11 -m venv /tmp/venv
/tmp/venv/bin/pip install -q -r requirements-compativel.txt pyinstaller==6.22.3
/tmp/venv/bin/python -m PyInstaller --noconfirm --log-level WARN --onedir --name Pestinha \
    --add-data "../assets:assets" --add-data "../pets:pets" \
    --distpath dist --workpath build/work --specpath build main.py
cp -R assets pets dist/Pestinha/
/tmp/venv/bin/python ferramentas/podar_linux.py dist/Pestinha
/tmp/venv/bin/python ferramentas/minimo_glibc.py dist/Pestinha 2.28

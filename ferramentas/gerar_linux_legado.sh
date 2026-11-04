#!/bin/sh
# Gera o app de Linux legado (glibc 2.17: CentOS/RHEL 7, Ubuntu 16.04 e 18.04, Debian 9...) num CentOS 7
# (manylinux2014), com Python 3.8 (o do uv, que tem a libpython compartilhada que o PyInstaller pede) e o
# conjunto de requirements-legado.txt (Qt 5.15). Na raiz do projeto:
#
#   docker run --rm -v "$PWD:/src" -w /src quay.io/pypa/manylinux2014_x86_64 sh ferramentas/gerar_linux_legado.sh
#
# Resultado: dist/Pestinha/ (executável + assets/ + pets/), já podado e com a glibc conferida.
set -eu
# xcb-util-*: entram no app (muitas distros não instalam); gcc e kernel-headers: o evdev (pynput) é compilado
yum install -y -q xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil libxkbcommon-x11 \
    mesa-libGL mesa-libEGL fontconfig gcc kernel-headers >/dev/null
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/tmp/uv sh >/dev/null
/tmp/uv/uv venv -q -p 3.8 /tmp/venv
VIRTUAL_ENV=/tmp/venv /tmp/uv/uv pip install -q -r requirements-legado.txt pyinstaller==6.22.3
/tmp/venv/bin/python -m PyInstaller --noconfirm --log-level WARN --onedir --name Pestinha \
    --add-data "../assets:assets" --add-data "../pets:pets" \
    --distpath dist --workpath build/work --specpath build main.py
cp -R assets pets dist/Pestinha/
/tmp/venv/bin/python ferramentas/podar_linux.py dist/Pestinha
/tmp/venv/bin/python ferramentas/minimo_glibc.py dist/Pestinha 2.17

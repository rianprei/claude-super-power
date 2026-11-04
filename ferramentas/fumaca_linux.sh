#!/bin/sh
# Teste de fumaça do executável de Linux dentro de um container de qualquer distro.
#
#   docker run --rm -v "$PWD/pestinha:/app:ro" -v "$PWD/ferramentas:/f:ro" debian:12 sh /f/fumaca_linux.sh
#
# Instala só o que todo desktop Linux já tem (servidor X, Mesa, fontconfig, uma fonte, glib e D-Bus), abre o pet num
# X virtual por 8 s e confere: saiu sem erro, gravou a memory/ e o Qt carregou a plataforma X11 (xcb).
# O que faltar além disso (como a libxcb-cursor0, que muitas distros não instalam) precisa vir dentro do app.
set -eu

instalar() {
    if command -v apt-get >/dev/null; then
        export DEBIAN_FRONTEND=noninteractive
        pacotes="xvfb libegl1 libgl1 fontconfig fonts-dejavu-core libglib2.0-0 libdbus-1-3"
        # shellcheck disable=SC2086
        apt-get update -qq || true
        # Ubuntu 16.04: a EGL e a GL ainda se chamavam libegl1-mesa e libgl1-mesa-glx
        apt-cache policy libegl1 2>/dev/null | grep -q 'Candidate: [0-9]' || pacotes="$(echo "$pacotes" | sed 's/libegl1 libgl1/libegl1-mesa libgl1-mesa-glx/')"
        if ! apt-get install -y -qq --no-install-recommends $pacotes >/dev/null; then
            # Debian antigo: os pacotes saíram do espelho principal e foram para o archive.debian.org
            sed -i -e 's|http://deb.debian.org|http://archive.debian.org|g' \
                -e 's|http://security.debian.org|http://archive.debian.org|g' /etc/apt/sources.list
            apt-get -o Acquire::Check-Valid-Until=false update -qq
            apt-get install -y -qq --no-install-recommends $pacotes >/dev/null
        fi
    elif command -v dnf >/dev/null; then
        dnf install -y -q xorg-x11-server-Xvfb mesa-libEGL mesa-libGL fontconfig dejavu-sans-fonts glib2 dbus-libs >/dev/null
    elif command -v yum >/dev/null; then
        pacotes="xorg-x11-server-Xvfb mesa-libEGL mesa-libGL fontconfig dejavu-sans-fonts glib2 dbus-libs"
        # shellcheck disable=SC2086
        if ! yum install -y -q $pacotes >/dev/null 2>&1; then
            # CentOS 7: os espelhos saíram do ar, os pacotes ficaram no vault.centos.org
            sed -i -e 's|^mirrorlist=|#mirrorlist=|' -e 's|^#\{0,1\}baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|' \
                /etc/yum.repos.d/CentOS-*.repo
            yum install -y -q $pacotes >/dev/null
        fi
    elif command -v pacman >/dev/null; then
        pacman -Sy --noconfirm --needed xorg-server-xvfb mesa fontconfig ttf-dejavu glib2 dbus >/dev/null
    elif command -v zypper >/dev/null; then
        zypper -q -n install xorg-x11-server-Xvfb Mesa-libEGL1 Mesa-libGL1 fontconfig dejavu-fonts libglib-2_0-0 libdbus-1-3 >/dev/null
    else
        echo "gerenciador de pacotes desconhecido" >&2
        exit 2
    fi
}

. /etc/os-release
echo "== $PRETTY_NAME · $(ldd --version 2>&1 | head -n 1)"
instalar
# todo sistema instalado tem um machine-id; o de um container pode vir vazio, e a libdbus aborta sem ele
[ -s /etc/machine-id ] || tr -d '-' </proc/sys/kernel/random/uuid >/etc/machine-id

Xvfb :99 -screen 0 1280x800x24 -nolisten tcp >/dev/null 2>&1 &
sleep 2
export DISPLAY=:99 QT_QPA_PLATFORM=xcb

# numa pasta gravável, como quem baixou e descompactou: a memory/ nasce ao lado do executável
cp -R /app /tmp/pestinha
cd /tmp/pestinha
set +e
./Pestinha --direto --sair-em 8 >saida.txt 2>&1
codigo=$?
set -e
cat saida.txt
if [ "$codigo" -ne 0 ]; then
    echo "FALHOU: saiu com $codigo"
    exit 1
fi
if grep -q -e "Traceback" -e "Could not load the Qt platform plugin" -e "could not connect to display" \
        -e "Fontconfig error" -e "symbol lookup error" -e "version .* not found" saida.txt; then
    echo "FALHOU: erro na saída"
    exit 1
fi
test -d memory/pets || { echo "FALHOU: não gravou a memory/"; exit 1; }
echo "OK: abriu, rodou 8 s, gravou a memória e fechou"

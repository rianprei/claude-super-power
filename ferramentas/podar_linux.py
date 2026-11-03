"""
Tira do app de Linux (pasta do PyInstaller) as bibliotecas que todo desktop já tem e que precisam ser as do
próprio sistema.

O PyInstaller leva as da máquina que gerou o app. Numa distro mais nova, as velhas atrapalham:
- a fontconfig antiga não entende a configuração de fontes da distro (erros de "Fontconfig");
- a libstdc++ antiga, carregada primeiro, impede o driver de vídeo da distro de abrir;
- a glib antiga quebra o tema do GTK.
As versões do sistema são compatíveis com as antigas, então usar as dele é sempre seguro. A lista é a
mesma ideia da "excludelist" do AppImage. As do xcb que muitas distros não instalam (como a
libxcb-cursor) continuam dentro do app.

    python ferramentas/podar_linux.py dist/Pestinha
"""

import sys
from pathlib import Path

DO_SISTEMA = (
    "libstdc++.so.6", "libgcc_s.so.1",                                          # compilador
    "libfontconfig.so.1", "libfreetype.so.6", "libexpat.so.1", "libpng16.so.16", "libz.so.1",   # fontes
    "libX11.so.6", "libX11-xcb.so.1", "libXau.so.6", "libXext.so.6", "libxcb.so.1",         # X11
    "libGL.so.1", "libEGL.so.1", "libGLX.so.0", "libGLdispatch.so.0", "libOpenGL.so.0", "libdrm.so.2",
    "libglib-2.0.so.0", "libgobject-2.0.so.0", "libgthread-2.0.so.0", "libdbus-1.so.3", "libuuid.so.1",
)


def podar(pasta: Path) -> list[str]:
    """Apaga da pasta do app (inclusive de _internal/) as bibliotecas da lista; devolve as que apagou."""
    apagadas = []
    for arquivo in sorted(pasta.rglob("*")):
        if arquivo.name in DO_SISTEMA and (arquivo.is_file() or arquivo.is_symlink()):
            arquivo.unlink()
            apagadas.append(str(arquivo.relative_to(pasta)))
    return apagadas


def main(argv: list[str]) -> int:
    apagadas = podar(Path(argv[1]))
    for nome in apagadas:
        print(f"usa a do sistema: {nome}")
    print(f"{len(apagadas)} biblioteca(s) tirada(s) do app")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

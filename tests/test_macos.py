"""
macOS: janelas do pet visíveis com outro app ativo, sem sombra, clique na aura e o macOS mínimo dos binários.
A lógica roda em qualquer sistema; o último teste abre janelas de verdade e só roda no macOS.
"""

from __future__ import annotations

import os
import struct
import subprocess  # nosec B404 - roda o próprio Python com um script fixo dos testes
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pestinha import config
from pestinha.app import PestinhaApp
from pestinha.body.pet import overlay_flags
from pestinha.paths import Paths
from pestinha.settings_store import SettingsStore
from pestinha.world.objetos import Thing

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import minimo_macos

X86, ARM = minimo_macos.CPU["x86_64"], minimo_macos.CPU["arm64"]


def _build_version(maior, menor):
    return struct.pack("<IIIIII", 0x32, 24, 1, (maior << 16) | (menor << 8), 0, 0)


def _version_min(maior, menor):
    return struct.pack("<IIII", 0x24, 16, (maior << 16) | (menor << 8), 0)


def _fino(cpu, comando):
    """Mach-O de 64 bits com um comando de carga só (o resto não importa para a leitura)."""
    return struct.pack("<IIIIIIII", 0xFEEDFACF, cpu, 0, 6, 1, len(comando), 0, 0) + comando


def _universal(*fatias):
    cabecalho = struct.pack(">II", 0xCAFEBABE, len(fatias))
    corpo, tabela = b"", b""
    for i, (cpu, dados) in enumerate(fatias):
        deslocamento = 4096 * (i + 1)
        tabela += struct.pack(">IIIII", cpu, 0, deslocamento, len(dados), 12)
        corpo = corpo.ljust(deslocamento - 4096, b"\0") + dados
    return (cabecalho + tabela).ljust(4096, b"\0") + corpo


def test_minimo_le_a_fatia_da_arquitetura_pedida(tmp_path):
    universal = tmp_path / "QtCore"
    universal.write_bytes(_universal((X86, _fino(X86, _version_min(10, 14))), (ARM, _fino(ARM, _build_version(11, 0)))))
    assert minimo_macos.minimo(universal, "x86_64") == (10, 14)
    assert minimo_macos.minimo(universal, "arm64") == (11, 0)
    novo = tmp_path / "numpy.so"
    novo.write_bytes(_fino(ARM, _build_version(14, 0)))
    assert minimo_macos.minimo(novo, "arm64") == (14, 0)
    assert minimo_macos.minimo(novo, "x86_64") is None              # fatia de outra arquitetura
    (tmp_path / "texto.txt").write_text("CAFEBABE não é Mach-O", encoding="utf-8")
    (tmp_path / "Classe.class").write_bytes(struct.pack(">II", 0xCAFEBABE, 52))     # Java, não universal
    assert minimo_macos.acima_do_limite(tmp_path, (13, 0), "arm64") == [("numpy.so", (14, 0))]
    assert minimo_macos.main(["", str(tmp_path), "13.0", "arm64"]) == 1
    assert minimo_macos.main(["", str(tmp_path), "14.0", "arm64"]) == 0


def test_janelas_por_cima_nao_somem_no_mac_e_nao_tem_sombra(tmp_path):
    qt = QApplication.instance() or QApplication([])
    qt.setQuitOnLastWindowClosed(False)
    paths = Paths(root=tmp_path)
    s = SettingsStore(paths)
    s.update(dict(config.DEFAULT_PERMISSIONS))
    app = PestinhaApp(s, paths)
    app.floats.open("neural")
    janelas = [app.pet, app.ball, Thing(40, 40), app.floats.windows["neural"]]
    assert all(j.testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow) for j in janelas)
    assert overlay_flags() & Qt.WindowType.NoDropShadowWindowHint


@pytest.mark.skipif(sys.platform != "darwin", reason="precisa do macOS de verdade (NSWindow)")
def test_no_mac_as_janelas_do_pet_funcionam_de_verdade():
    env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}      # Qt Cocoa, não offscreen
    script = Path(__file__).with_name("janela_real_macos.py")
    r = subprocess.run([sys.executable, str(script)], env=env, capture_output=True,  # noqa: S603  # nosec B603
                       text=True, timeout=60, check=False)
    assert r.returncode == 0, r.stdout + r.stderr

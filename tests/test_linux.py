"""
Linux: o app empacotado roda em qualquer distro com a glibc mínima dele. Testa as ferramentas do build:
a glibc que cada binário pede e a poda das bibliotecas que têm de ser as do sistema.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import minimo_glibc
import podar_linux


def _elf(*versoes):
    """Um ELF de mentira com as versões de glibc pedidas na tabela de texto (como no .dynstr)."""
    return b"\x7fELF" + b"\x00" * 60 + b"".join(v.encode() + b"\x00" for v in versoes)


def test_glibc_minima_e_a_maior_pedida_por_cada_binario(tmp_path):
    (tmp_path / "_internal").mkdir()
    (tmp_path / "Pestinha").write_bytes(_elf("GLIBC_2.2.5", "GLIBC_2.17", "GLIBC_PRIVATE"))
    (tmp_path / "_internal" / "libQt6Core.so.6").write_bytes(_elf("GLIBC_2.28", "GLIBCXX_3.4.29"))
    (tmp_path / "_internal" / "libnova.so").write_bytes(_elf("GLIBC_2.38"))
    (tmp_path / "_internal" / "texto.txt").write_bytes(b"GLIBC_2.99\x00 num texto qualquer")
    assert minimo_glibc.minimo(tmp_path / "Pestinha") == (2, 17)
    assert minimo_glibc.minimo(tmp_path / "_internal" / "texto.txt") is None          # não é ELF
    assert minimo_glibc.acima_do_limite(tmp_path, (2, 28)) == [(str(Path("_internal/libnova.so")), (2, 38))]
    assert minimo_glibc.main(["", str(tmp_path), "2.28"]) == 1
    assert minimo_glibc.main(["", str(tmp_path), "2.38"]) == 0


def test_poda_tira_so_as_bibliotecas_do_sistema(tmp_path):
    interno = tmp_path / "_internal"
    interno.mkdir()
    for nome in ("libfontconfig.so.1", "libstdc++.so.6", "libglib-2.0.so.0", "libxcb-cursor.so.0",
                 "libQt6Core.so.6", "libxkbcommon.so.0", "libgthread-2.0.so.0"):
        (interno / nome).write_bytes(b"x")
    apagadas = podar_linux.podar(tmp_path)
    assert sorted(Path(a).name for a in apagadas) == ["libfontconfig.so.1", "libglib-2.0.so.0", "libstdc++.so.6"]
    assert sorted(f.name for f in interno.iterdir()) == ["libQt6Core.so.6", "libgthread-2.0.so.0", "libxcb-cursor.so.0", "libxkbcommon.so.0"]

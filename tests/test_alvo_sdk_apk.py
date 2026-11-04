"""ferramentas/alvo_sdk_apk.py: troca o targetSdkVersion no manifesto binário do Android sem mexer no resto."""
from __future__ import annotations

import struct
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import alvo_sdk_apk


def _manifesto(alvo=35, minimo=29):
    """XML binário mínimo: cabeçalho, mapa de recursos (minSdk, targetSdk) e um elemento com os dois."""
    mapa = struct.pack("<HHI", 0x0180, 8, 16) + struct.pack("<II", 0x0101020C, 0x01010270)
    attrs = b"".join(struct.pack("<IIIHBBI", 0xFFFFFFFF, nome, 0xFFFFFFFF, 8, 0, 0x10, valor)
                     for nome, valor in ((0, minimo), (1, alvo)))
    ext = struct.pack("<IIHHHHHH", 0xFFFFFFFF, 2, 20, 20, 2, 0, 0, 0)
    elemento = struct.pack("<HHIII", 0x0102, 16, 16 + len(ext) + len(attrs), 1, 0xFFFFFFFF) + ext + attrs
    corpo = mapa + elemento
    return struct.pack("<HHI", 0x0003, 8, 8 + len(corpo)) + corpo


def _valores(axml):
    return [struct.unpack_from("<I", axml, len(axml) - 40 + 16 + 20 * k)[0] for k in range(2)]


def test_troca_so_o_alvo():
    novo = alvo_sdk_apk.trocar_alvo(_manifesto(alvo=35), 29)
    assert _valores(novo) == [29, 29] and len(novo) == len(_manifesto())
    assert _valores(alvo_sdk_apk.trocar_alvo(_manifesto(alvo=35, minimo=24), 29)) == [24, 29]   # o mínimo fica


def test_recusa_o_que_nao_e_manifesto_binario():
    with pytest.raises(ValueError):
        alvo_sdk_apk.trocar_alvo(b"<manifest/>", 29)


def test_apk_inteiro_mantem_os_outros_arquivos_e_tira_a_assinatura_v1(tmp_path):
    origem, destino = tmp_path / "a.apk", tmp_path / "b.apk"
    with zipfile.ZipFile(origem, "w") as z:
        z.writestr("AndroidManifest.xml", _manifesto())
        z.writestr(zipfile.ZipInfo("resources.arsc"), b"tabela")          # guardado sem compressão
        z.writestr("META-INF/CERT.RSA", b"assinatura")
        z.writestr("lib/arm64-v8a/libmain.so", b"\x7fELF")
    alvo_sdk_apk.main(str(origem), str(destino), 29)
    with zipfile.ZipFile(destino) as z:
        assert sorted(z.namelist()) == ["AndroidManifest.xml", "lib/arm64-v8a/libmain.so", "resources.arsc"]
        assert _valores(z.read("AndroidManifest.xml")) == [29, 29]
        assert z.getinfo("resources.arsc").compress_type == zipfile.ZIP_STORED

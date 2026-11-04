"""
Troca o targetSdkVersion no AndroidManifest.xml binário de um APK, sem recompilar (depois: zipalign e assinar):

    python ferramentas/alvo_sdk_apk.py ClaudeSuperPower.apk sem_assinatura.apk 29

Por quê 29: no celular de teste (HyperOS 3, Android 16, com root) o Android recusa qualquer APK com alvo na API
30 ou mais ("requires the resources.arsc ... aligned on a 4-byte boundary"), até um de referência feito só com
o aapt2 do Google; com alvo 29 instala e roda. O Qt continua compilado contra a API 35 e o mínimo não muda.
"""
from __future__ import annotations

import struct
import sys
import zipfile

ALVO_SDK = 0x01010270          # android:targetSdkVersion
TIPO_INT = 0x10                # Res_value TYPE_INT_DEC


def trocar_alvo(axml: bytes, novo: int) -> bytes:
    dados = bytearray(axml)
    if struct.unpack_from("<H", dados, 0)[0] != 0x0003:
        raise ValueError("não é XML binário do Android")
    pos, resmap, trocas = struct.unpack_from("<H", dados, 2)[0], [], 0
    while pos < len(dados):
        tipo, cab, tam = struct.unpack_from("<HHI", dados, pos)
        if tipo == 0x0180:                                   # mapa string -> id de recurso
            resmap = list(struct.unpack_from(f"<{(tam - cab) // 4}I", dados, pos + cab))
        elif tipo == 0x0102:                                 # início de elemento
            ext = pos + cab
            inicio, passo, quantos = struct.unpack_from("<HHH", dados, ext + 8)
            for k in range(quantos):
                a = ext + inicio + k * passo
                nome = struct.unpack_from("<I", dados, a + 4)[0]
                dtipo = dados[a + 15]
                if nome < len(resmap) and resmap[nome] == ALVO_SDK and dtipo == TIPO_INT:
                    struct.pack_into("<I", dados, a + 16, novo)
                    trocas += 1
        pos += tam
    if trocas != 1:
        raise ValueError(f"esperava 1 targetSdkVersion, achei {trocas}")
    return bytes(dados)


def main(origem: str, destino: str, novo: int) -> None:
    with zipfile.ZipFile(origem) as zi, zipfile.ZipFile(destino, "w") as zo:
        for i in zi.infolist():
            if i.filename.startswith("META-INF/") and i.filename.rsplit(".", 1)[-1] in ("SF", "RSA", "MF", "EC"):
                continue                                     # assinatura v1 antiga: vai ser refeita
            conteudo = zi.read(i.filename)
            if i.filename == "AndroidManifest.xml":
                conteudo = trocar_alvo(conteudo, novo)
            novo_item = zipfile.ZipInfo(i.filename, date_time=i.date_time)
            novo_item.compress_type, novo_item.external_attr = i.compress_type, i.external_attr
            zo.writestr(novo_item, conteudo)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))

"""Regressões da auditoria de 2026-11: cada teste prende uma correção (o código antigo falhava nele)."""
import json
import math
import sys
import threading
import time
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from pestinha import config, log as log_module, migracao, store
from pestinha.app import PestinhaApp
from pestinha.core.homeostasis import Drives
from pestinha.core.nervous_system import LIFBrain
from pestinha.core.protesto import load_signs
from pestinha.mathutil import clamp, valor_real
from pestinha.paths import Paths
from pestinha.plataforma import _comum, linux
from pestinha.settings_store import SettingsStore
from pestinha.world.mischief import MischiefEngine

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def pet_app(tmp_path):
    app_qt = QApplication.instance() or QApplication([])
    app_qt.setQuitOnLastWindowClosed(False)
    paths = Paths(root=tmp_path)
    s = SettingsStore(paths)
    s.update(dict(config.DEFAULT_PERMISSIONS))
    return PestinhaApp(s, paths)


# ---------------- conteúdo que você edita ----------------

def test_cartazes_em_ansi_nao_derrubam_e_saem_certos(tmp_path):
    arquivo = tmp_path / "cartazes.txt"
    arquivo.write_bytes("[greve]\nNÃO VOU TRABALHAR\n".encode("cp1252"))
    assert load_signs(arquivo)["greve"] == ["NÃO VOU TRABALHAR"]


def test_cartazes_com_bom_nao_perdem_a_primeira_secao(tmp_path):
    arquivo = tmp_path / "cartazes.txt"
    arquivo.write_bytes(b"\xef\xbb\xbf[greve]\nFRASE MINHA\n")
    assert load_signs(arquivo)["greve"] == ["FRASE MINHA"]


def test_recadinhos_em_ansi_saem_legiveis(tmp_path):
    arquivo = tmp_path / "recadinhos.txt"
    arquivo.write_bytes("olá você".encode("cp1252"))
    assert store.read_lines(arquivo) == ["olá você"]


def test_pet_json_com_erro_fica_no_lugar_e_continua_na_lista(tmp_path):
    paths = Paths(root=tmp_path)
    paths.pets.mkdir()
    (paths.pets / "meupet.json").write_text('{"nome": "Meu Pet",}', encoding="utf-8")
    pet = config.load_pet(paths, "meupet")
    assert pet["nome"] == "Meupet"                                   # padrão
    assert (paths.pets / "meupet.json").exists()
    assert not list(paths.pets.glob("*.corrompido"))
    assert config.list_pets(paths) == ["meupet"]


def test_load_pet_nao_compartilha_dicts_do_padrao(tmp_path):
    pet = config.load_pet(Paths(root=tmp_path), "bryan")
    pet["brincadeira"]["bola"] = 99.0
    assert config.DEFAULT_PET["brincadeira"]["bola"] == 1.0


def test_recadinho_que_some_e_volta_com_o_mesmo_mtime_e_relido(tmp_path):
    arquivo = tmp_path / "recadinhos.txt"
    arquivo.write_text("um\n", encoding="utf-8")
    notas = config.Notes(arquivo)
    assert notas.has_lines()
    mtime = arquivo.stat().st_mtime
    arquivo.unlink()
    assert not notas.has_lines()
    arquivo.write_text("dois\n", encoding="utf-8")
    import os
    os.utime(arquivo, (mtime, mtime))
    assert notas.pick() == "dois"


# ---------------- estado do pet ----------------

def test_rede_de_outra_semente_e_guardada_antes_de_ser_sobrescrita(tmp_path):
    arquivo = tmp_path / "nervous.json"
    LIFBrain(seed=7).save(str(arquivo))
    original = arquivo.read_bytes()
    assert LIFBrain(seed=8).load(str(arquivo)) is False
    copia = tmp_path / "nervous.json.descartado"
    assert copia.read_bytes() == original and arquivo.read_bytes() == original
    LIFBrain(seed=8).load(str(arquivo))                               # de novo: não acumula cópias
    assert sorted(p.name for p in tmp_path.iterdir()) == ["nervous.json", "nervous.json.descartado"]


def test_homeostase_com_tipos_errados_e_guardada(tmp_path):
    arquivo = tmp_path / "drives.json"
    arquivo.write_text('{"energy": "cheia"}', encoding="utf-8")
    assert Drives().load(arquivo, config.PROFILES["normal"]) is False
    assert (tmp_path / "drives.json.descartado").exists()


def test_gravacao_recusada_nao_estraga_o_arquivo_nem_deixa_temporario(tmp_path):
    arquivo = tmp_path / "x.json"
    store.write_json(arquivo, {"a": 1})
    with pytest.raises(ValueError):
        store.write_json(arquivo, {"a": float("nan")})
    assert json.loads(arquivo.read_text(encoding="utf-8")) == {"a": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["x.json"]


def test_corrompido_nao_sobrescreve_o_corrompido_anterior(tmp_path):
    arquivo = tmp_path / "x.json"
    for texto in ("{ruim 1", "{ruim 2"):
        arquivo.write_text(texto, encoding="utf-8")
        assert store.read_json(arquivo, default="padrão") == "padrão"
    assert (tmp_path / "x.json.corrompido").read_text(encoding="utf-8") == "{ruim 1"
    assert (tmp_path / "x.json.corrompido.2").read_text(encoding="utf-8") == "{ruim 2"


def test_save_do_app_aguenta_valor_recusado_pelo_store(pet_app, monkeypatch):
    monkeypatch.setattr(pet_app.drives, "save", Mock(side_effect=ValueError("NaN")))
    pet_app.castigo.salvar = Mock()
    pet_app.save()                                       # não levanta
    pet_app.castigo.salvar.assert_called_once()          # e as partes seguintes ainda gravam


def test_quit_fecha_mesmo_se_algo_falhar(pet_app, monkeypatch):
    sair = Mock()
    monkeypatch.setattr("pestinha.controle.sessao.QApplication.quit", sair)
    monkeypatch.setattr(pet_app, "save", Mock(side_effect=RuntimeError("falha inesperada")))
    with pytest.raises(RuntimeError):
        pet_app.quit()
    sair.assert_called_once()


def test_clamp_e_valor_real_nao_deixam_passar_nan_nem_infinito():
    assert clamp(float("nan")) == 0.0 and clamp(2.0) == 1.0 and clamp(-1.0) == 0.0 and clamp(0.5) == 0.5
    for ruim in (float("inf"), float("-inf"), float("nan")):
        with pytest.raises(ValueError):
            valor_real(ruim)


def test_rede_esparsa_da_o_mesmo_drive_da_densa():
    cerebro = LIFBrain()
    cerebro.stimulate({"WORK": 1.0, "TYPING": 0.8, "POKE": 1.0})
    for _ in range(500):
        denso = (cerebro.spikes * cerebro.pre_gain) @ cerebro.W_lif
        ativos = np.flatnonzero(cerebro.spikes)
        esparso = cerebro.pre_gain[ativos] @ cerebro.W_lif[ativos] if ativos.size else np.zeros_like(denso)
        assert np.allclose(denso, esparso, atol=1e-12)
        assert np.array_equal(ativos, cerebro._ativos)
        cerebro._substep()


def test_restaurar_e_migrar_de_novo_nao_vira_conflito(tmp_path):
    paths = Paths(root=tmp_path)
    paths.memory.mkdir()
    (paths.memory / "drives.json").write_text('{"energy": 0.5}', encoding="utf-8")
    assert migracao.migrar(paths, "bryan").pet_ok("bryan")
    (paths.pet("bryan").drives).write_text('{"energy": 0.9}', encoding="utf-8")   # o pet viveu depois
    migracao.restaurar(paths, "bryan")
    de_novo = migracao.migrar(paths, "bryan")
    assert de_novo.pet_ok("bryan") and not de_novo.conflitos
    guardadas = list((paths.legado / "bryan").glob("pasta-nova-*/drives.json"))
    assert [p.read_text(encoding="utf-8") for p in guardadas] == ['{"energy": 0.9}']   # nada se perdeu


# ---------------- app ----------------

def test_esconder_o_notebook_fica_salvo(pet_app, tmp_path):
    pet_app.menu_alternar_notebook()
    assert pet_app.mesa.escondido and pet_app.store.perms["notebook"] is False
    salvo = json.loads((tmp_path / "memory" / "permissions.json").read_text(encoding="utf-8"))
    assert salvo["notebook"] is False
    outro = PestinhaApp(SettingsStore(Paths(root=tmp_path)), Paths(root=tmp_path))
    assert outro.mesa.escondido and not outro.mesa.caderno.isVisible()


def test_travessura_consultada_nao_gasta_o_sorteio_do_recadinho(tmp_path):
    pasta = tmp_path / "pets" / "bryan"
    pasta.mkdir(parents=True)
    (pasta / "recadinhos.txt").write_text("um\ndois\n", encoding="utf-8")
    motor = MischiefEngine(Paths(root=tmp_path).conteudo("bryan"))
    perms = dict(config.DEFAULT_PERMISSIONS, travessuras=True, memes=False, fotos=False)
    assert "bilhete" in motor.available("feliz", perms)
    assert motor.notes.last is None


def test_log_aguenta_terminal_fechado(tmp_path, monkeypatch):
    arquivo = tmp_path / "log.txt"
    log_module.setup(arquivo)
    monkeypatch.setattr("builtins.print", Mock(side_effect=OSError(5, "EIO")))
    log_module.log("ainda grava")
    log_module.desligar_arquivo()
    assert arquivo.read_text(encoding="utf-8").endswith("ainda grava\n")     # modo texto: \r\n no Windows


# ---------------- Linux ----------------

def test_rodar_aguenta_bytes_invalidos_na_saida():
    saida = _comum.rodar([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'\\xff ok')"], tempo=10)
    assert saida == "� ok"


def test_wmctrl_filtra_outra_area_de_trabalho():
    saida = "0x0a 0 10 0 0 500 400 host a\n0x0b 1 11 0 0 500 400 host b\n0x0c -1 12 0 0 500 400 host fixa"
    assert [j[0] for j in linux.parse_wmctrl(saida, 1, set(), desktop_atual=0)] == [0x0a, 0x0c]
    assert linux.parse_desktop_atual("0  - DG: x\n1  * DG: x\n") == 1
    assert linux.parse_desktop_atual("") is None


def test_janelas_ficam_de_cima_para_baixo_e_sem_minimizadas():
    achadas = [(1, (0, 0, 9, 9), False), (2, (0, 0, 9, 9), False), (3, (0, 0, 9, 9), False),
               (99, (0, 0, 9, 9), False)]
    ordem = linux.ordenar_pelo_x11(achadas, empilhamento=[1, 3, 2], escondidas={3})
    assert [j[0] for j in ordem] == [2, 1, 99]           # 2 no topo; 3 minimizada; 99 desconhecida no fim


def test_tela_cheia_vale_para_qualquer_monitor():
    monitores = [(0, 0, 1920, 1080), (1920, 0, 3840, 1080)]
    assert linux.cobre_algum_monitor((1920, 0, 3840, 1080), monitores)
    assert not linux.cobre_algum_monitor((1920, 0, 3000, 1080), monitores)


def test_sentidos_do_linux_nao_rodam_comandos_na_thread_do_qt(monkeypatch):
    chamadas = []

    def rodar_falso(comando, tempo=1.0):
        chamadas.append((threading.current_thread().name, comando[0]))
        return {"xprintidle": "2500", "xdotool": "", "wmctrl": ""}.get(comando[0], "")

    monkeypatch.setattr(linux, "rodar", rodar_falso)
    monkeypatch.setattr(linux, "_X11", lambda: Mock(ler=Mock(return_value=([], set()))))   # sem servidor X real
    coletor = linux.Coletor()
    coletor.tem = dict.fromkeys(coletor.tem, True)
    coletor.passo(time.monotonic())                      # o que a thread de sentidos faz
    monkeypatch.setattr(linux, "_coletor", coletor)
    feitas = len(chamadas)
    assert math.isclose(linux.ocioso_segundos(), 2.5, abs_tol=0.5)
    assert linux.processo_ativo() == "unknown"
    assert linux.janelas_visiveis(set()) == []
    assert not linux.tela_cheia()
    assert len(chamadas) == feitas                        # ler não roda comando nenhum


def test_regiao_de_clique_nao_mexe_em_janela_fora_do_x11():
    QApplication.instance() or QApplication([])
    assert linux.regiao_de_clique(1, [(0, 0, 10, 10)]) is False     # offscreen: id não é janela X11

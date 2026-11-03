"""
Windows: o que só quebra lá (DPI misto, clique na aura, arquivo preso por antivírus, pasta sem permissão).
A lógica roda em qualquer sistema; o último teste abre uma janela de verdade e só roda no Windows.
"""
import os
import subprocess  # nosec B404 - roda o próprio Python com um script fixo dos testes
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from pestinha import config, paths as paths_mod, store
from pestinha.app import PestinhaApp, retangulo_logico
from pestinha.body import pet as pet_mod
from pestinha.paths import Paths
from pestinha.settings_store import SettingsStore

# notebook a 150% (1920x1080 físicos = 1280x720 lógicos) e, à direita, um monitor a 100%:
# o Qt mantém o canto de cada tela, então o segundo começa em x = 1920 também no lógico
TELAS = [(0, 0, 1280, 720, 1.5), (1920, 0, 1920, 1080, 1.0)]


def test_dpi_misto_converte_pela_escala_de_cada_tela():
    assert retangulo_logico((300, 150, 900, 750), TELAS) == (200, 100, 600, 500)
    assert retangulo_logico((2000, 100, 2800, 700), TELAS) == (2000, 100, 2800, 700)   # antes: /1.5
    assert retangulo_logico((-600, 30, -300, 330), TELAS) == (-400, 20, -200, 220)     # fora: a principal


def test_troca_espera_o_antivirus_soltar_o_arquivo(tmp_path, monkeypatch):
    alvo = tmp_path / "estado.json"
    original = Path.replace
    falhas = {"n": 2}

    def replace(self, destino):
        if falhas["n"]:
            falhas["n"] -= 1
            raise PermissionError(13, "arquivo em uso por outro processo")
        return original(self, destino)

    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr(store.time, "sleep", lambda _s: None)
    store.write_json(alvo, {"ok": 1})
    assert store.read_json(alvo) == {"ok": 1}

    falhas["n"] = store.TENTATIVAS_TROCA          # preso o tempo todo: desiste e não deixa temporário
    with pytest.raises(PermissionError):
        store.write_json(alvo, {"ok": 2})
    assert store.read_json(alvo) == {"ok": 1}
    assert [f.name for f in tmp_path.iterdir()] == ["estado.json"]


def test_memoria_vai_para_a_pasta_do_usuario_se_o_programa_nao_pode_gravar(tmp_path, monkeypatch):
    assert paths_mod.memoria_gravavel(tmp_path) == tmp_path / "memory"

    def negado(**_kw):
        raise PermissionError(13, "Acesso negado")      # Arquivos de Programas: os.access diria que pode

    monkeypatch.setattr(paths_mod.tempfile, "TemporaryFile", negado)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    esperado = tmp_path / "AppData" / "Local" / "Claude Super Power" / "memory"
    assert paths_mod.memoria_gravavel(tmp_path / "Arquivos de Programas") == esperado
    assert Paths(root=tmp_path, memoria=esperado).permissions == esperado / "permissions.json"


def test_clique_atravessa_a_janela_so_fora_do_corpo(tmp_path, monkeypatch):
    qt = QApplication.instance() or QApplication([])
    qt.setQuitOnLastWindowClosed(False)
    paths = Paths(root=tmp_path)
    s = SettingsStore(paths)
    s.update(dict(config.DEFAULT_PERMISSIONS))
    janela = PestinhaApp(s, paths).pet
    janela.show()
    chamadas = []
    monkeypatch.setattr(pet_mod.plataforma, "atravessar_clique", lambda _id, sim: chamadas.append(sim))
    _w, _h, cx, cy = janela.geometria
    cursor = {"local": QPoint(int(cx), int(cy))}
    monkeypatch.setattr(pet_mod, "QCursor", SimpleNamespace(pos=lambda: janela.mapToGlobal(cursor["local"])))

    janela._atualizar_regiao_de_clique()
    cursor["local"] = QPoint(1, 1)                  # canto da janela: transparente (ou aura)
    janela._atualizar_regiao_de_clique()
    janela._atualizar_regiao_de_clique()            # sem mudança: não chama de novo
    janela.body.held = True                         # arrastando para fora do corpo: não solta o mouse
    cursor["local"] = QPoint(int(cx), int(cy))
    janela._atualizar_regiao_de_clique()
    assert chamadas == [False, True]


@pytest.mark.skipif(sys.platform != "win32", reason="precisa do Windows de verdade (janela em camadas)")
def test_no_windows_o_clique_atravessa_a_aura_de_verdade():
    env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}      # Qt de verdade, não offscreen
    script = Path(__file__).with_name("janela_real_windows.py")
    r = subprocess.run([sys.executable, str(script)], env=env, capture_output=True,  # noqa: S603  # nosec B603
                       text=True, timeout=60, check=False)
    assert r.returncode == 0, r.stdout + r.stderr

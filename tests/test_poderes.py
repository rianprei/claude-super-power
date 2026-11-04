"""Voo, teletransporte e Kamehameha do Clawd SSJ2: a rede decide, o controlador executa com física por tempo."""
from __future__ import annotations

import math
import random

import pytest
from PySide6.QtWidgets import QApplication

from pestinha.body.pet_state import PetState
from pestinha.core.physics import Body
from pestinha.mind import poderes as pod
from pestinha.mind.poderes import PoderesController
from pestinha.world import kamehameha as kam
from pestinha.world.kamehameha import Kamehameha, comprimento_na_tela
from pestinha.world.teleporte import Teleporte

TELA = (0, 0, 1600, 900)
DT = 1 / 60
QUER = 1e6          # taxa absurda: a chance passa de 1, o poder sai no primeiro quadro


@pytest.fixture(autouse=True)
def _qt():
    random.seed(11)
    return QApplication.instance() or QApplication([])


def _no_chao(x=500.0):
    corpo = Body(x, TELA[3] - 45.0 - 1.0, 60.0, 45.0)
    for _ in range(10):
        corpo.step(DT, TELA, [])
    assert corpo.grounded
    return corpo


def _patas(corpo):
    return lambda: [(corpo.x - 50.0, corpo.y - 5.0), (corpo.x + 50.0, corpo.y - 5.0)]


def _simular(ctl, corpo, estado, segundos, motor=None, cursor=(1200.0, 300.0), livre=True, t0=0.0, depois=None):
    """Física e controlador juntos; o motor pedido só dispara no primeiro quadro. Devolve [(t, corpo...)]."""
    t, linha = t0, []
    while t < t0 + segundos:
        corpo.step(DT, TELA, [])
        motores = {motor: QUER} if motor and t == t0 else {}
        alvo = cursor(t) if callable(cursor) else cursor
        ctl.tick(t, DT, corpo, estado, TELA, alvo, motores, _patas(corpo), livre, False)
        linha.append((t, corpo.x, corpo.y, corpo.vx, corpo.vy, corpo.angle, corpo.flutuando, corpo.grounded,
                      ctl.atual, estado.escala))
        if depois:
            depois(t)
        t += DT
    return linha


def test_a_rede_quer_os_poderes_so_transformada_e_cada_emocao_puxa_um():
    from pestinha.core.nervous_system import LIFBrain

    def medias(extra):
        cerebro = LIFBrain(seed=7)
        soma = dict.fromkeys(("VOO", "TELEPORTE", "KAMEHAMEHA"), 0.0)
        for _ in range(300):                                   # 30 s
            cerebro.stimulate({"WORK": 0.5, **extra})
            cerebro.step(100)
            for nome in soma:
                soma[nome] += cerebro.motor_activity()[nome] / 300
        return soma

    sem, com = medias({}), medias({"PODER": 1.0})
    assert all(sem[n] < 0.5 < com[n] for n in sem)                         # sem Super Saiyajin, nada
    assert medias({"PODER": 1.0, "DISMISS": 1.0})["KAMEHAMEHA"] > com["KAMEHAMEHA"]   # bravo: Kamehameha
    assert medias({"PODER": 1.0, "PLAY": 1.0})["VOO"] > com["VOO"]                    # brincando: voa
    assert medias({"PODER": 1.0, "FATIGUE": 1.0})["VOO"] < com["VOO"]                 # cansado: menos


def test_voo_decola_acelera_e_freia_suave_inclina_para_onde_vai_e_pousa_macio(monkeypatch):
    monkeypatch.setattr(pod, "DURACAO_VOO", (5.0, 5.0))
    corpo, estado, ctl = _no_chao(), PetState(), PoderesController()
    linha = _simular(ctl, corpo, estado, 12.0, motor="VOO")
    voando = [r for r in linha if r[8] == "VOO"]
    assert voando and min(r[2] for r in voando) < linha[0][2] - 150          # subiu de verdade
    vel = [math.hypot(r[3], r[4]) for r in voando]
    assert max(vel) <= pod.VELOCIDADE_VOO + pod.BALANCO[0] + 1.0             # sem disparar
    acel = [math.hypot(b[3] - a[3], b[4] - a[4]) / DT for a, b in zip(voando, voando[1:])]
    assert max(acel) <= pod.ACEL_VOO + 1.0                                   # sem trancos
    rapidos = [r for r in voando if abs(r[3]) > 150]
    assert rapidos and all(abs(r[5]) <= pod.INCLINA_MAX + 0.01 for r in voando)
    assert all(r[5] * r[3] > 0 for r in rapidos if abs(r[5]) > 2.0)         # inclina para onde vai
    assert ctl.atual is None and corpo.grounded and not corpo.flutuando       # pousou
    assert max(corpo.pop_impacts(), default=0.0) < 260                        # macio: sem quicar
    assert estado.poder < 0.05                                                # a aura voltou ao normal


def test_voo_pousa_na_hora_se_deixar_de_estar_livre():
    corpo, estado, ctl = _no_chao(), PetState(), PoderesController()
    _simular(ctl, corpo, estado, 1.5, motor="VOO")
    assert ctl.atual == "VOO" and estado.poder > 0.5                         # aura mais forte no ar
    _simular(ctl, corpo, estado, 6.0, livre=False, t0=1.5)                   # dormiu, por exemplo
    assert ctl.atual is None and corpo.grounded


def test_teleporte_some_num_risco_e_reaparece_longe_com_efeito_nas_duas_pontas():
    corpo, estado, ctl = _no_chao(400.0), PetState(), PoderesController()
    linha = _simular(ctl, corpo, estado, 1.2, motor="TELEPORTE")
    escalas = [r[9] for r in linha]
    assert any(sx == 0.0 for sx, _sy in escalas)                              # sumiu
    assert any(0.0 < sx < 1.0 and sy > 1.0 for sx, sy in escalas[:8])         # fechou esticando
    assert escalas[-1] == (1.0, 1.0) and ctl.atual is None                    # voltou inteiro
    assert abs(corpo.x - 400.0) >= pod.TELE_LONGE and corpo.grounded         # longe, e no chão
    assert ctl.efeitos == [] and len({id(e) for e in _efeitos_criados(400.0)}) == 2


def _efeitos_criados(x):
    """Os dois efeitos de um teletransporte saindo de x (saída e chegada)."""
    corpo, estado, ctl = _no_chao(x), PetState(), PoderesController()
    vistos = []
    _simular(ctl, corpo, estado, 0.4, motor="TELEPORTE", depois=lambda _t: vistos.extend(ctl.efeitos))
    assert [e.chegada for e in dict.fromkeys(vistos)] == [False, True]
    return list(dict.fromkeys(vistos))


def test_teleporte_no_ar_continua_voando():
    corpo, estado, ctl = _no_chao(), PetState(), PoderesController()
    _simular(ctl, corpo, estado, 1.5, motor="VOO")
    ctl.pronto_em["TELEPORTE"] = 0.0
    ctl.atual, ctl.voo = None, None                                           # entre um ponto e outro
    corpo.vx = corpo.vy = 0.0
    linha = _simular(ctl, corpo, estado, 0.7, motor="TELEPORTE", t0=1.5)
    assert linha[0][8] == "TELEPORTE" and linha[-1][8] == "VOO" and corpo.flutuando


def test_kamehameha_firme_carrega_entre_as_patas_mira_o_cursor_do_disparo_e_escorrega_para_tras():
    corpo, estado, ctl = _no_chao(400.0), PetState(), PoderesController()
    cursor = {"p": (1300.0, 860.0)}
    vistos = []

    def ver(_t):
        if ctl.kame is not None:
            vistos.append((ctl.kame.fase, ctl.kame.ex, ctl.kame.ey, estado.concentrado, ctl.kame.width()))

    linha = _simular(ctl, corpo, estado, kam.CARGA / 2, motor="KAMEHAMEHA", cursor=lambda _t: cursor["p"], depois=ver)
    assert vistos[0][0] == "carga" and vistos[0][1:3] == (pytest.approx(corpo.x), pytest.approx(corpo.y - 5.0))
    cursor["p"] = (1300.0, 500.0)                                             # mexeu durante a carga
    x_antes = corpo.x
    linha += _simular(ctl, corpo, estado, 6.0, cursor=lambda _t: cursor["p"], t0=kam.CARGA / 2, depois=ver)
    fases = [v[0] for v in vistos]
    assert fases.index("feixe") > 0 and "fim" in fases and ctl.kame is None and ctl.atual is None
    assert all(v[3] for v in vistos) and not estado.concentrado               # firme o golpe todo, e solto depois
    largura_feixe = max(v[4] for v in vistos if v[0] == "feixe")
    assert largura_feixe > kam.LADO_CARGA                                     # a janela cresceu para o feixe
    assert corpo.x < x_antes - 10                                             # o feixe empurrou para trás
    assert estado.gaze[0] > 0.9                                               # encarando o alvo


def test_feixe_trava_a_mira_no_disparo_e_para_na_borda_da_tela():
    cursor = {"p": (900.0, 300.0)}
    k = Kamehameha(lambda: [(190.0, 300.0), (210.0, 300.0)], lambda: cursor["p"], 0.0, TELA, semente=1)
    t = 0.0
    while k.fase == "carga":
        t += DT
        k.passo(t, DT)
    assert (k.dx, k.dy) == (pytest.approx(1.0), pytest.approx(0.0)) and k.comprimento == pytest.approx(700.0)
    cursor["p"] = (200.0, 900.0)                                               # depois do disparo não muda
    for _ in range(30):
        t += DT
        k.passo(t, DT)
    assert (k.dx, k.dy) == (pytest.approx(1.0), pytest.approx(0.0)) and k.ponta == pytest.approx(700.0)
    k.close()
    assert comprimento_na_tela(1500.0, 450.0, 1.0, 0.0, TELA, 900.0) == pytest.approx(100.0)   # borda
    assert comprimento_na_tela(800.0, 450.0, 1.0, 0.0, TELA, 10.0) == kam.MINIMO               # mínimo
    assert comprimento_na_tela(0.0, 450.0, 1.0, 0.0, (0, 0, 9000, 900), 8000.0) == kam.ALCANCE


def test_pegar_ele_ou_destransformar_acaba_o_poder_na_hora():
    corpo, estado, ctl = _no_chao(), PetState(), PoderesController()
    _simular(ctl, corpo, estado, 1.0, motor="VOO")
    corpo.held = True
    _simular(ctl, corpo, estado, DT, t0=1.0)
    assert ctl.atual is None and not corpo.flutuando
    corpo.held = False
    for _ in range(200):
        corpo.step(DT, TELA, [])
    ctl.pronto_em["KAMEHAMEHA"] = 0.0
    _simular(ctl, corpo, estado, 0.5, motor="KAMEHAMEHA", t0=5.0)
    assert ctl.atual == "KAMEHAMEHA" and estado.concentrado
    ctl.tick(5.6, DT, corpo, estado, TELA, (0, 0), {}, lambda: None, True, False)    # destransformou
    assert ctl.atual is None and ctl.kame is None and not estado.concentrado


def test_so_decide_livre_transformado_e_com_recarga():
    corpo, estado, ctl = _no_chao(), PetState(), PoderesController()
    ctl.tick(0.0, DT, corpo, estado, TELA, (0, 0), {"VOO": QUER}, lambda: None, True, False)
    assert ctl.atual is None                                                  # fora do Super Saiyajin
    ctl.tick(0.0, DT, corpo, estado, TELA, (0, 0), {"VOO": QUER}, _patas(corpo), False, False)
    assert ctl.atual is None                                                  # dormindo, preso, sentado...
    ctl.pronto_em["VOO"] = 10.0
    ctl.tick(0.0, DT, corpo, estado, TELA, (0, 0), {"VOO": QUER}, _patas(corpo), True, False)
    assert ctl.atual is None                                                  # ainda recarregando


def test_efeitos_desenham_sem_erro_em_todas_as_fases():
    for chegada in (False, True):
        e = Teleporte(300.0, 300.0, 0.0, chegada=chegada, semente=2)
        t = 0.0
        while e.passo(t, DT):
            if round(t / DT) % 6 == 0:
                e.grab()
            t += DT
        e.close()
    k = Kamehameha(lambda: [(190.0, 300.0), (210.0, 300.0)], lambda: (900.0, 300.0), 0.0, TELA, semente=3)
    t = 0.0
    while k.passo(t, DT):
        if round(t / DT) % 10 == 0:
            assert not k.grab().toImage().isNull()
        t += DT
    k.close()

"""Rajadas de Ki do Clawd em Super Saiyajin: fases, física por tempo, desenho e a troca do papel pelo Ki."""
from __future__ import annotations

import math
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from pestinha.body import pet as pet_mod
from pestinha.mind.revolucao import RevolucaoController
from pestinha.world import ki as ki_mod
from pestinha.world.ki import ACELERACAO, CARGA, CLARAO, LADO, VELOCIDADE, KiBlast

TELA = (0, 0, 3000, 2000)
DT = 1 / 120


@pytest.fixture(autouse=True)
def _qt():
    return QApplication.instance() or QApplication([])


def _rodar(ki, ate, obstaculos=(), limites=TELA):
    """Anda o Ki até `ate` segundos (ou até acabar); devolve [(t, fase, x, y)]."""
    t, linha = 0.0, []
    while t < ate:
        t += DT
        vivo = ki.passo(t, DT, limites, obstaculos)
        linha.append((t, ki.fase, ki.ex, ki.ey))
        if not vivo:
            break
    return linha


def test_carrega_na_pata_voa_rapido_e_explode_no_alvo():
    pata = {"p": (100.0, 500.0)}
    ki = KiBlast(lambda: pata["p"], (700.0, 500.0), 0.0, semente=1)
    linha = _rodar(ki, CARGA / 2)
    pata["p"] = (110.0, 490.0)                      # o pet se mexeu: a carga vai junto
    linha += _rodar(ki, CARGA * 0.4)
    assert all(f == "carga" for _t, f, _x, _y in linha)
    assert (ki.ex, ki.ey) == (110.0, 490.0)
    ki = KiBlast(lambda: (100.0, 500.0), (700.0, 500.0), 0.0, semente=1)
    linha = _rodar(ki, 3.0)
    inicio_voo = next(t for t, f, _x, _y in linha if f == "voo")
    explodiu = next(t for t, f, _x, _y in linha if f == "clarao")
    assert inicio_voo == pytest.approx(CARGA, abs=2 * DT)
    voo = explodiu - inicio_voo
    assert voo == pytest.approx(600 / VELOCIDADE + ACELERACAO / 2, abs=3 * DT)      # ~0,38 s para 600 px
    assert linha[-1][0] - explodiu == pytest.approx(CLARAO, abs=2 * DT)              # some depois do flash
    x_explosao = next(x for _t, f, x, _y in linha if f == "clarao")
    assert x_explosao == pytest.approx(700.0, abs=1.0)


def test_explode_no_obstaculo_e_na_borda_da_tela():
    ki = KiBlast(lambda: (100.0, 500.0), (900.0, 500.0), 0.0, semente=2)
    linha = _rodar(ki, 2.0, obstaculos=[(400, 450, 80, 100)])
    x_explosao = next(x for _t, f, x, _y in linha if f == "clarao")
    assert 400 <= x_explosao <= 400 + VELOCIDADE * DT + 1
    ki = KiBlast(lambda: (100.0, 500.0), (5000.0, 500.0), 0.0, semente=3)
    linha = _rodar(ki, 3.0, limites=(0, 0, 1920, 1080))
    assert next(x for _t, f, x, _y in linha if f == "clarao") <= 1920 + VELOCIDADE * DT


def test_desenho_esfera_de_nucleo_branco_borda_dourada_e_fundo_transparente():
    ki = KiBlast(lambda: (300.0, 300.0), (1300.0, 300.0), 0.0, semente=4)
    _rodar(ki, CARGA + 0.1)
    assert ki.fase == "voo"
    img = ki.grab().toImage()
    escala = img.devicePixelRatio()                  # o Qt 5 escala pelo DPI da tela (offscreen: ~1,04)

    def cor(dx):
        return img.pixelColor(round((LADO / 2 + dx) * escala), round(LADO / 2 * escala))

    nucleo = cor(0)
    assert nucleo.red() > 240 and nucleo.green() > 235 and nucleo.blue() > 200          # núcleo branco
    borda = cor(int(ki.raio()) - 1)
    assert borda.red() > 230 and borda.green() > 170 and borda.blue() < 160              # amarelo-dourado
    atras = cor(-60)                                                                     # rastro dourado
    assert atras.alpha() > 0 and atras.red() > atras.blue()
    assert img.pixelColor(2, 2).alpha() == 0                                           # resto transparente


def _revolucao():
    play = Mock()
    return RevolucaoController(play, Mock()), play


def test_em_super_saiyajin_atira_ki_da_pata_do_lado_do_cursor_e_com_coice(monkeypatch):
    monkeypatch.setattr("pestinha.mind.revolucao.CHANCE_FORTE_MAX", 0.0)      # só o Ki normal aqui
    monkeypatch.setattr("pestinha.mind.revolucao.random.random", lambda: 0.0)        # dispara e sempre em dupla
    monkeypatch.setattr("pestinha.mind.revolucao.random.uniform", lambda a, b: a)
    rev, play = _revolucao()
    corpo = SimpleNamespace(x=500.0, y=400.0, vx=0.0)
    patas = [(450.0, 380.0), (550.0, 380.0)]
    rev.tick(0.0, DT, TELA, (100.0, 300.0), (0, 0), corpo, True, True, [], 50.0, patas=lambda: patas)
    assert len(rev.kis) == 1 and not rev.papeis and play.throw_at.call_count == 0
    assert (rev.kis[0].ex, rev.kis[0].ey) == patas[0]                # cursor à esquerda: pata esquerda
    assert corpo.vx > 0                                              # coice para o outro lado
    monkeypatch.setattr("pestinha.mind.revolucao.random.random", lambda: 0.99)
    rev.tick(0.2, DT, TELA, (100.0, 300.0), (0, 0), corpo, True, True, [], 50.0, patas=lambda: patas)
    assert len(rev.kis) == 2 and (rev.kis[1].ex, rev.kis[1].ey) == patas[1]     # a dupla vem da outra pata
    assert len(rev.janelas()) == 2
    rev.fechar()
    assert rev.kis == []


def test_fora_do_super_saiyajin_continua_atirando_papel(monkeypatch):
    monkeypatch.setattr("pestinha.mind.revolucao.random.random", lambda: 0.0)
    rev, play = _revolucao()
    corpo = SimpleNamespace(x=500.0, y=400.0, vx=0.0)
    rev.tick(0.0, DT, TELA, (100.0, 300.0), (0, 0), corpo, True, True, [], 50.0, patas=lambda: None)
    assert len(rev.papeis) == 1 and rev.kis == [] and play.throw_at.call_count == 1
    rev.fechar()


def test_patas_na_tela_giram_com_o_corpo():
    estado = SimpleNamespace(super_saiyajin_desde=None, gaze=(0.0, 0.0))
    pet = SimpleNamespace(corpo="clawd3d", state=estado, body=SimpleNamespace(x=1000.0, y=600.0, angle=0.0))
    assert pet_mod.PetWindow.patas_na_tela(pet, 0.0) is None                     # sem Super Saiyajin: papel
    estado.super_saiyajin_desde = 0.0
    esquerda, direita = pet_mod.PetWindow.patas_na_tela(pet, 0.0)
    assert esquerda[0] < 1000.0 < direita[0] and esquerda[1] < 600.0
    pet.body.angle = 90.0
    girada = pet_mod.PetWindow.patas_na_tela(pet, 0.0)[0]
    assert math.hypot(girada[0] - 1000.0, girada[1] - 600.0) == pytest.approx(
        math.hypot(esquerda[0] - 1000.0, esquerda[1] - 600.0))
    assert girada[1] < 600.0 - 40                                                 # a pata esquerda foi para cima
    pet.corpo = "tela"
    assert pet_mod.PetWindow.patas_na_tela(pet, 0.0) is None


def test_faiscas_freiam_por_tempo_e_nao_por_quadro():
    a = KiBlast(lambda: (0.0, 0.0), (500.0, 0.0), 0.0, semente=5)
    a.faiscas = [[0.0, 0.0, 100.0, 0.0, 0.0, 1.0, ki_mod.AMARELO]]
    a.agora = 0.1
    for _ in range(12):
        a._mover_faiscas(0.1 / 12)
    b = KiBlast(lambda: (0.0, 0.0), (500.0, 0.0), 0.0, semente=5)
    b.faiscas = [[0.0, 0.0, 100.0, 0.0, 0.0, 1.0, ki_mod.AMARELO]]
    b.agora = 0.1
    b._mover_faiscas(0.1)
    assert a.faiscas[0][2] == pytest.approx(b.faiscas[0][2])


def test_a_rede_quer_atirar_ki_so_quando_sente_o_poder():
    from pestinha.core.nervous_system import LIFBrain

    def media_ki(poder, extra=None):
        cerebro = LIFBrain(seed=7)
        taxas = []
        for _ in range(300):                                   # 30 s
            cerebro.stimulate({"WORK": 0.5, "PODER": poder, **(extra or {})})
            cerebro.step(100)
            taxas.append(cerebro.motor_activity()["KI"])
        return sum(taxas) / len(taxas)

    transformado = media_ki(1.0)
    assert media_ki(0.0) < 0.5 < transformado                 # sem Super Saiyajin, a vontade quase não existe
    assert media_ki(1.0, {"FATIGUE": 1.0}) < transformado      # cansado atira menos


def test_fora_da_revolucao_o_motor_ki_decide_e_mira_no_cursor(monkeypatch):
    monkeypatch.setattr("pestinha.mind.revolucao.CHANCE_FORTE_MAX", 0.0)      # só o Ki normal aqui
    monkeypatch.setattr("pestinha.mind.revolucao.random.uniform", lambda a, b: (a + b) / 2)
    corpo = SimpleNamespace(x=500.0, y=600.0, vx=0.0)
    patas = [(450.0, 580.0), (550.0, 580.0)]
    cursor = (900.0, 650.0)

    def atirar(ki_hz, livre=True, sorte=0.5, com_patas=True):
        monkeypatch.setattr("pestinha.mind.revolucao.random.random", lambda: sorte)
        rev, _play = _revolucao()
        rev.tick(0.0, 1.0, TELA, cursor, (0, 0), corpo, True, False, [], 0.0,
                 patas=(lambda: patas) if com_patas else (lambda: None), ki_hz=ki_hz, livre=livre)
        kis = list(rev.kis)
        rev.fechar()
        return kis, rev

    assert atirar(ki_hz=0.0)[0] == []                          # a rede não quer: não atira
    assert atirar(ki_hz=60.0, livre=False)[0] == []           # dormindo, preso ou escondido: não atira
    assert atirar(ki_hz=60.0, com_patas=False)[0] == []       # fora do Super Saiyajin: não atira
    kis, _ = atirar(ki_hz=60.0)
    assert len(kis) == 1 and kis[0].alvo() == cursor              # sempre no cursor
    assert (kis[0].ex, kis[0].ey) == patas[1]                       # da pata do lado dele


def test_a_mira_e_o_cursor_na_hora_do_disparo_e_nao_no_comeco_da_carga():
    alvo = {"p": (900.0, 500.0)}
    ki = KiBlast(lambda: (100.0, 500.0), lambda: alvo["p"], 0.0, semente=6)
    _rodar(ki, CARGA / 2)
    alvo["p"] = (100.0, 100.0)                       # o mouse foi para cima durante a carga
    linha = _rodar(ki, 3.0)
    x, y = next((x, y) for _t, f, x, y in linha if f == "clarao")
    assert (x, y) == (pytest.approx(100.0, abs=1.0), pytest.approx(100.0, abs=1.0))


def test_as_vezes_sai_o_forte_teleguiado_um_por_vez_e_com_coice_maior(monkeypatch):
    monkeypatch.setattr("pestinha.mind.revolucao.random.random", lambda: 0.0)
    rev, _play = _revolucao()
    corpo = SimpleNamespace(x=500.0, y=400.0, vx=0.0)
    patas = [(450.0, 380.0), (550.0, 380.0)]
    rev.tick(0.0, DT, TELA, (100.0, 300.0), (0, 0), corpo, True, False, [], 0.0,
             patas=lambda: patas, ki_hz=60.0, livre=True)
    assert len(rev.kis) == 1 and rev.kis[0].forte and rev._segundo is None      # forte: sem dupla
    assert corpo.vx == pytest.approx(175.0)
    rev.tick(0.01, DT, TELA, (100.0, 300.0), (0, 0), corpo, True, False, [], 0.0,
             patas=lambda: patas, ki_hz=60.0, livre=True)
    assert [ki.forte for ki in rev.kis] == [True, False]                         # só uma teleguiada por vez
    rev.fechar()
    from pestinha.mind import revolucao
    assert min(revolucao.CHANCE_FORTE_MAX, revolucao.CHANCE_FORTE_BASE
                                              + revolucao.CHANCE_FORTE_POR_HZ * 10.0) > revolucao.CHANCE_FORTE_BASE   # mais vontade, mais forte


def test_o_forte_persegue_o_cursor_que_foge_e_explode_nele():
    estado = {"t": 0.0}

    def cursor():                                    # o mouse foge em curva
        t = estado["t"]
        return (900.0 + 300.0 * math.sin(t * 1.3), 260.0 + 220.0 * math.sin(t * 2.1))

    ki = KiBlast(lambda: (160.0, 640.0), cursor, 0.0, semente=3, forte=True)
    t, explodiu = 0.0, None
    while t < 6.0:
        t += DT
        estado["t"] = t
        if not ki.passo(t, DT, (0, 0, 1400, 800)):
            break
        if ki.fase == "clarao" and explodiu is None:
            explodiu = (ki.ex, ki.ey, cursor())
    assert explodiu is not None
    x, y, (cx, cy) = explodiu
    assert math.hypot(x - cx, y - cy) <= ki_mod.ACERTO + ki_mod.VELOCIDADE_FORTE * DT      # alcançou o cursor
    assert ki.perfil.raio > ki_mod.RAIO and ki.perfil.lado > LADO                          # e é maior

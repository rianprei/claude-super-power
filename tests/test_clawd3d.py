"""
Clawd: o mascote do Claude Code em blocos 3D (corpo "clawd3d") e o modo Super Saiyajin 1 do menu.

O corpo vem do pets/<pet>.json ("tela" é o padrão; valor desconhecido fica com o padrão). O desenho
apoia os pés onde a física apoia o corpo em qualquer giro, e o cabelo dourado só aparece transformado.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from pestinha import config
from pestinha.body.clawd3d import draw_clawd
from pestinha.body.desenho_rosto import BODY_H
from pestinha.body.pet import CX, CY, JANELA_SSJ, WIN
from pestinha.core.emotion import EYE_SHAPES
from pestinha.paths import Paths
from pestinha.settings_store import SettingsStore

PATHS = Paths(root=ROOT)


def pintar(emocao="observando", gaze=(0.0, 0.0), carinho=False, ssj=None, blink=1.0):
    """O Clawd como a janela do pet pinta: 200x200, centro em (CX, CY), fundo transparente."""
    QApplication.instance() or QApplication([])
    img = QImage(WIN, WIN, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate(CX, CY)
    draw_clawd(p, dict(EYE_SHAPES[emocao]), gaze, blink, emocao, carinho=carinho, ssj=ssj, now=2.0)
    p.end()
    return img


def opacos(img, filtro=lambda c: True):
    """(x, y) dos pixels opacos que passam no filtro de cor."""
    return [(x, y) for y in range(img.height()) for x in range(img.width())
            if QColor.fromRgba(img.pixel(x, y)).alpha() > 200 and filtro(QColor.fromRgba(img.pixel(x, y)))]


def dourado(c):
    return c.red() > 200 and c.green() > 150 and c.blue() < 120 and c.green() > c.red() * 0.7


def test_corpo_vem_do_json_e_valor_desconhecido_fica_com_o_padrao(tmp_path):
    assert config.load_pet(PATHS, "clawd")["corpo"] == "clawd3d"
    assert config.load_pet(PATHS, "bryan")["corpo"] == "tela"
    (tmp_path / "pets").mkdir()
    (tmp_path / "pets" / "x.json").write_text(json.dumps({"corpo": "dragao"}), encoding="utf-8")
    assert config.load_pet(Paths(root=tmp_path), "x")["corpo"] == "tela"


def test_pes_no_chao_em_qualquer_giro_e_toda_expressao():
    base = CY + BODY_H / 2
    for emocao in EYE_SHAPES:
        for gaze in ((0.0, 0.0), (1.0, 0.0), (-1.0, 0.3), (0.0, 0.9)):
            pontos = opacos(pintar(emocao, gaze))
            assert pontos, (emocao, gaze)
            assert abs(max(y for _x, y in pontos) - base) <= 2, (emocao, gaze)     # nem afunda nem flutua
    assert opacos(pintar("feliz", carinho=True))                                     # > <


def visiveis_em_volta(ssj, gaze, now, folga=150):
    """Pixels visíveis (qualquer alfa) desenhados numa tela com folga, em coordenadas da janela do Super Saiyajin."""
    QApplication.instance() or QApplication([])
    largura, altura, cx, cy = JANELA_SSJ
    img = QImage(largura + 2 * folga, altura + 2 * folga, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate(cx + folga, cy + folga)
    draw_clawd(p, dict(EYE_SHAPES["bravo"]), gaze, 1.0, "bravo", ssj=ssj, now=now)
    p.end()
    return [(x - folga, y - folga) for y in range(0, img.height(), 2) for x in range(0, img.width(), 2)
            if QColor.fromRgba(img.pixel(x, y)).alpha() > 0]


def test_cabelo_dourado_so_no_super_saiyajin():
    topo_do_corpo = CY - BODY_H / 2
    assert not opacos(pintar(), dourado)
    for ssj in (0.0, 0.2):                            # clarão e cabelo crescendo: só não pode quebrar
        assert opacos(pintar(ssj=ssj))
    transformado = opacos(pintar(ssj=3.0), dourado)
    assert len([y for _x, y in transformado if y < topo_do_corpo]) > 500           # juba volumosa em cima


def test_juba_e_aura_cabem_inteiras_na_janela_do_super_saiyajin():
    largura, altura, _cx, _cy = JANELA_SSJ
    for ssj, gaze, now in ((3.0, (0.0, 0.0), 0.3), (3.0, (1.0, -1.0), 1.1), (3.0, (-1.0, 1.0), 1.7),
                           (0.2, (0.0, 0.0), 0.5), (0.9, (0.6, 0.0), 0.9)):     # pronto e transformando
        pontos = visiveis_em_volta(ssj, gaze, now)
        assert min(x for x, _y in pontos) >= 0 and max(x for x, _y in pontos) < largura, (ssj, gaze)
        assert min(y for _x, y in pontos) >= 0 and max(y for _x, y in pontos) < altura, (ssj, gaze)


def test_cache_da_juba_tem_limite_e_desenha_igual_ao_vivo():
    import pestinha.body.clawd3d as c
    for i in range(c.CACHE_CABELO + 15):              # mais ângulos do que cabem no cache
        pintar(ssj=3.0, gaze=(-1.0 + 2.0 * i / (c.CACHE_CABELO + 15), 0.0))
    assert len(c._cache_cabelo) <= c.CACHE_CABELO
    assert len(c._cache_aura) <= c.QUADROS_AURA
    # o guardado e o ao vivo (mesmo ângulo inteiro, mesmo quadro da aura) quase não diferem
    cam = c._Camera(10, 16)
    pes = max(cam.girar(v)[1] for v in c.SOLAS)
    cam.dy = BODY_H / 2 - pes * c.U

    def tela(desenhar):
        img = QImage(300, 300, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(150, 200)
        desenhar(p)
        p.end()
        return img
    vivo = tela(lambda p: (c._cupula(p, cam), c._cabelo(p, cam, 1.0, c.CAMADAS_FRENTE)))
    guardado = tela(lambda p: c._juba(p, "frente", 10, 16, cam.dy, 1.0))
    total = diferenca = 0
    for y in range(300):
        for x in range(300):
            a, b = QColor.fromRgba(vivo.pixel(x, y)).alpha(), QColor.fromRgba(guardado.pixel(x, y)).alpha()
            total += a
            diferenca += abs(a - b)
    assert total > 0 and diferenca / total < 0.03, diferenca / total   # só as bordas (colado em y fracionário)


def test_menu_liga_e_desliga_o_super_saiyajin(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    import shutil

    import pestinha.app as app_mod
    shutil.copytree(PATHS.pets, tmp_path / "pets")
    paths = Paths(root=tmp_path)
    monkeypatch.setattr(app_mod, "PanicHotkey", lambda: SimpleNamespace(ok=True, pressed=Mock()))
    SettingsStore(paths).update(dict(config.DEFAULT_PERMISSIONS, pet="clawd"))
    app = app_mod.PestinhaApp(SettingsStore(paths), paths)
    for timer in app.findChildren(app_mod.QTimer):
        timer.stop()
    assert app.pet.corpo == "clawd3d"
    assert app.pet_state.super_saiyajin_desde is None
    app.menu_super_saiyajin()
    assert app.pet_state.super_saiyajin_desde is not None
    assert SettingsStore(paths).perms["super_saiyajin"] is True                      # fica salvo
    app.pet.grab()                                                                   # pinta de verdade, sem erro
    app.menu_super_saiyajin()
    assert app.pet_state.super_saiyajin_desde is None
    assert SettingsStore(paths).perms["super_saiyajin"] is False
    app.pet.grab()
    app.apply_perms(dict(app.perms, super_saiyajin=True))                            # pela tela de Configurações
    assert app.pet_state.super_saiyajin_desde is not None
    app.apply_perms(dict(app.perms, super_saiyajin=False))
    assert app.pet_state.super_saiyajin_desde is None


def test_super_saiyajin_salvo_volta_ao_abrir_e_nao_vale_para_a_telinha(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    import shutil

    import pestinha.app as app_mod
    shutil.copytree(PATHS.pets, tmp_path / "pets")
    paths = Paths(root=tmp_path)
    monkeypatch.setattr(app_mod, "PanicHotkey", lambda: SimpleNamespace(ok=True, pressed=Mock()))
    for pet, transformado in (("clawd", True), ("bryan", False)):
        SettingsStore(paths).update(dict(config.DEFAULT_PERMISSIONS, pet=pet, super_saiyajin=True))
        app = app_mod.PestinhaApp(SettingsStore(paths), paths)
        for timer in app.findChildren(app_mod.QTimer):
            timer.stop()
        assert (app.pet_state.super_saiyajin_desde is not None) is transformado, pet


def test_icone_das_janelas_e_da_bandeja_e_o_do_pet():
    QApplication.instance() or QApplication([])
    from pestinha.body.clawd3d import CORPO
    from pestinha.ui.ui import face_icon

    def laranjas(icone):
        img = icone.pixmap(128, 128).toImage()
        return opacos(img, lambda c: abs(c.red() - CORPO.red()) + abs(c.green() - CORPO.green())
                      + abs(c.blue() - CORPO.blue()) < 60)
    assert len(laranjas(face_icon(corpo="clawd3d"))) > 500                        # o Clawd, não a telinha
    assert not laranjas(face_icon())


def test_tema_do_claude_code_nas_janelas_e_no_passo_a_passo(tmp_path):
    QApplication.instance() or QApplication([])
    import shutil

    from pestinha.body.desenho_rosto import FUNDO, LARANJA
    from pestinha.ui.onboarding import Onboarding
    from pestinha.ui.ui import MENU_STYLE, STYLE, SettingsDialog
    assert "$" not in STYLE + MENU_STYLE                                            # todo marcador foi trocado
    assert FUNDO in STYLE and LARANJA in STYLE and LARANJA in MENU_STYLE
    assert "#63e56f" not in STYLE                                                   # nada do verde antigo
    shutil.copytree(PATHS.pets, tmp_path / "pets")
    paths = Paths(root=tmp_path)
    d = SettingsDialog(dict(config.DEFAULT_PERMISSIONS, pet="clawd"), paths, first_run=True)
    assert d.windowTitle() == config.APP_NOME == "Claude Super Power"
    assert "personagem: Claude" in d.banner_sub.text()
    d.pet_combo.setCurrentIndex(d.pet_combo.findData("bryan"))                      # trocar o pet atualiza a caixa
    assert "personagem: Bryan" in d.banner_sub.text()
    o = Onboarding("Claude", "clawd3d")
    textos = [o.stack.widget(i).text() for i in range(o.stack.count())]
    assert any("mascote do Claude Code" in t for t in textos)
    assert not any("telinha" in t for t in textos)


def test_janela_cresce_no_super_saiyajin_e_volta_ao_tamanho_normal(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    import shutil

    import pestinha.app as app_mod
    shutil.copytree(PATHS.pets, tmp_path / "pets")
    paths = Paths(root=tmp_path)
    monkeypatch.setattr(app_mod, "PanicHotkey", lambda: SimpleNamespace(ok=True, pressed=Mock()))
    SettingsStore(paths).update(dict(config.DEFAULT_PERMISSIONS, pet="clawd", modo_teste=True, mostrar_emocao=True))
    app = app_mod.PestinhaApp(SettingsStore(paths), paths)
    for timer in app.findChildren(app_mod.QTimer):
        timer.stop()
    pet = app.pet
    pet.animate(0.0)
    assert (pet.width(), pet.height()) == (WIN, WIN)
    app.menu_super_saiyajin()
    pet.animate(0.0)
    largura, altura, cx, cy = JANELA_SSJ
    assert (pet.width(), pet.height()) == (largura, altura)
    assert (pet.x() + cx, pet.y() + cy) == (int(pet.body.x - cx) + cx, int(pet.body.y - cy) + cy)   # corpo no mesmo lugar
    pet.grab()                                                                       # pinta com o rótulo, sem erro
    app.menu_super_saiyajin()
    pet.animate(0.0)
    assert (pet.width(), pet.height()) == (WIN, WIN)


def test_micro_raios_piscam_a_cada_meio_segundo_e_somem():
    import pestinha.body.clawd3d as c

    largura, altura, cx, cy = JANELA_SSJ

    def ciano(now, ssj=3.0):
        img = QImage(largura, altura, QImage.Format.Format_ARGB32)
        img.fill(0)
        p = QPainter(img)
        p.translate(cx, cy)
        if ssj:
            c._raios(p, now)
        else:
            draw_clawd(p, dict(EYE_SHAPES["bravo"]), (0.0, 0.0), 1.0, "bravo", now=now)
        p.end()
        return len(opacos(img, lambda cor: cor.blue() > 200 and cor.red() < 150 and cor.green() > 150))
    assert c.RAIOS == 6 and c.PERIODO_RAIO == 0.5
    vezes = {k: set() for k in range(c.RAIOS)}
    acesos = {}
    passo = 0.002
    for i in range(3000):                                # 6 s: cada raio acende uma vez a cada 0,5 s, no seu relógio
        vivos = c._raios_vivos(i * passo)
        assert len(vivos) <= c.RAIOS
        for k, n, u, forca in vivos:
            assert 0.0 <= u < 1.0 and 0.7 <= forca <= 1.0
            vezes[k].add(n)
            acesos.setdefault(n, []).append(i)
    assert all(11 <= len(v) <= 13 for v in vezes.values()), {k: len(v) for k, v in vezes.items()}
    inteiros = [len(q) * passo for q in acesos.values() if q[0] > 0 and q[-1] < 2999]       # sem os cortados nas pontas
    assert inteiros and all(c.VIDA_RAIO[0] - 2 * passo <= v <= c.VIDA_RAIO[1] + passo for v in inteiros)
    agora = next(i * 0.01 for i in range(1000) if any(u < 0.1 for _k, _n, u, _f in c._raios_vivos(i * 0.01)))   # no clarão
    assert ciano(agora) > 0 and ciano(agora) == ciano(agora)             # pinta, e o mesmo em todo quadro
    assert not any(ciano(k * 0.05, ssj=None) for k in range(20))         # sem transformação, sem raio


def test_micro_raio_em_zigue_zague_com_dobras_afiadas_e_tamanho_pela_altura():
    import itertools
    import math

    from PySide6.QtCore import QPointF

    import pestinha.body.clawd3d as c
    for n in range(300):
        pts = c._zigue(n, QPointF(0.0, 0.0), 0.3 * n)
        assert 3 <= len(pts) - 2 <= 5, n                                             # 3 a 5 dobras
        trechos = [(b.x() - a.x(), b.y() - a.y()) for a, b in itertools.pairwise(pts)]
        total = sum(math.hypot(*t) for t in trechos)
        assert 0.08 * c.ALTURA_CLAWD - 1e-6 <= total <= 0.15 * c.ALTURA_CLAWD + 1e-6, n
        for (ax, ay), (bx, by) in itertools.pairwise(trechos):                     # ângulo na ponta de cada dobra
            cos = -(ax * bx + ay * by) / (math.hypot(ax, ay) * math.hypot(bx, by))
            assert 45.0 - 1e-6 <= math.degrees(math.acos(max(-1.0, min(1.0, cos)))) <= 70.0 + 1e-6, n

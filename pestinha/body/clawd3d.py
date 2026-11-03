"""
CLAWD 3D - o mascote do Claude Code em blocos 3D, desenhado só com o QPainter (sem OpenGL).

O modelo são caixas (corpo, braços e quatro pernas). Ele gira para o lado do olhar e é visto um pouco
de cima. Cada face recebe sombra de uma luz fixa e as faces são pintadas de trás para frente (algoritmo
do pintor), em camadas: pernas e depois corpo. Os olhos são desenhados no plano da face da frente com a
mesma forma de olho (EYE_SHAPES) do rosto original, então as emoções continuam valendo.

Super Saiyajin, no estilo dos animes de luta: uma massa alta de mechas grossas que sobem como labaredas,
em três camadas (trás, meio, frente), e uma franja caindo na testa. A raiz e a ponta de cada mecha são
pontos 3D na cabeça, então a juba gira junto. Cada mecha abre no meio e a ponta vira de volta para
dentro (a juba fica volumosa e fecha em cima); corpo cheio até o meio e ponta fina; degradê dourado,
sombreamento de anime (a metade longe da luz mais escura, com corte na espinha) e um reflexo fino. Os olhos
mantêm a forma de cada emoção e só ganham a cor turquesa, contorno e um reflexo. A aura
(SSJ2) são três camadas de labaredas douradas, altas, pontudas e irregulares, cada vez mais brancas para
dentro, com borda luminosa, brilho amarelo-branco no centro e pulso rápido; na borda de fora dela, seis
micro-raios em zigue-zague de quinas vivas e pontas afiadas (núcleo branco, contorno azul-ciano, brilho e
faíscas), cada um com o seu relógio.

Coordenadas do modelo em blocos: x para a direita, y para baixo, z para quem olha. O modo Super
Saiyajin chega como "há quanto tempo ele transformou" (None = desligado). O único estado é cache de
desenho: a juba pronta por ângulo de visão (arredondado a 1°) e a aura como um ciclo de quadros a 12 por
segundo (como animação de anime); juntos custam ~1/5 de desenhar tudo a cada quadro.
"""

import itertools
import math
from collections import OrderedDict

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)

from .desenho_rosto import BODY_H, LARANJA

U = 6.8                 # px por bloco
INCLINACAO = 16.0       # graus: visto um pouco de cima (a face de cima aparece)
GIRO_OLHAR = 28.0       # graus de giro para o lado do olhar
CORPO = QColor(LARANJA)
OLHO = QColor("#1b1411")
OLHO_SSJ = QColor("#36dccb")            # turquesa do Super Saiyajin (mesmo formato de olho, só a cor muda)
CONTORNO_OLHO_SSJ = QColor("#0b6d64")
BRILHO_OLHO_SSJ = QColor("#e6fffb")
CABELO = QColor("#ffd23f")              # cor de referência do cabelo (os tons saem de TONS_CABELO)
CRESCER_CABELO = 0.35   # s para o cabelo crescer na transformação
EXPLOSAO = 1.2          # s do clarão da transformação


def _unit(v):
    """Vetor de tamanho 1."""
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


LUZ = _unit((-0.35, -0.7, 0.62))        # de cima, da esquerda e da frente

FRENTE = 3.0                            # z da face da frente do corpo
TOPO = -6.5                             # y da face de cima do corpo
# caixas (x0, x1, y0, y1, z0, z1), nas proporções do adesivo: corpo 12x9, braços na altura dos olhos
PERNAS = tuple((x, x + 1.0, 2.5, 5.5, 0.6, 2.2) for x in (-4.5, -2.5, 1.5, 3.5))   # mais para a frente: aparecem
TRONCO = ((-6.0, 6.0, TOPO, 2.5, -FRENTE, FRENTE),
          (-7.5, -6.0, -4.5, -1.5, -1.5, 1.5),
          (6.0, 7.5, -4.5, -1.5, -1.5, 1.5))
# Juba: (z da raiz, comprimento no centro, largura da raiz, brilho, inclinação em z, posições de -1 a 1
# na largura da cabeça). Todas sobem: a mecha abre no meio e a ponta volta só um pouco para dentro, então
# a juba fica volumosa dos lados e fecha em cima sem virar uma chama fechada. As de trás são as mais altas.
CAMADAS_CABELO = (
    (-1.8, 15.5, 6.8, 0.88, -0.25, (-1.0, -0.67, -0.34, 0.0, 0.34, 0.67, 1.0)),     # trás: as mais altas
    (0.2, 13.0, 6.4, 0.97, -0.10, (-0.86, -0.5, -0.17, 0.17, 0.5, 0.86)),           # meio
    (2.2, 10.0, 5.8, 1.05, 0.05, (-0.62, -0.21, 0.21, 0.62)),                       # frente: curtas e cheias
)
BOJO, DENTRO = 0.38, -0.1              # quanto a mecha abre no meio e quanto a ponta volta para o centro
FRANJA = ((-1.0, 172.0, 4.0, 2.8, -0.28), (1.3, -170.0, 3.4, 2.4, 0.3))   # (x, ângulo, comprimento, largura, curva)
PERFIL_MECHA = ((0.0, 1.0), (0.3, 0.8), (0.62, 0.42), (0.88, 0.1), (1.0, 0.0))   # grossa na raiz, ponta afiada
CAMADAS_FRENTE = (1, 2, 3)              # na frente do corpo (a 0 fica atrás; a 3 é a franja)
# raiz (0) → ponta (1): dourado intenso, amarelo luminoso, amarelo quase branco
TONS_CABELO = ((0.0, (255, 190, 22)), (0.45, (255, 228, 92)), (0.8, (255, 238, 140)), (1.0, (255, 242, 166)))
SOMBRA_CABELO = QColor(201, 120, 8, 150)                # dourado-alaranjado: a metade longe da luz
CONTORNO_CABELO = (104, 54, 0)                          # contorno marcado de cada mecha
# Super Saiyajin: janela maior, com espaço em cima e dos lados para a juba e a aura (largura, altura,
# centro x, centro y do corpo dentro dela).
JANELA_SSJ = (272, 300, 136.0, 226.0)
REGIAO_AURA = QRectF(-JANELA_SSJ[2], -JANELA_SSJ[3], JANELA_SSJ[0], JANELA_SSJ[1])   # a janela, com o pet na origem
MARGEM_AURA = 8.0                       # px livres entre a aura e a borda da janela
# Aura SSJ2 em px, com o centro do pet na origem: um oval que envolve corpo e juba (mais estreito nos pés,
# em +BODY_H/2) e, por cima e pelos lados, labaredas altas, pontudas e irregulares subindo.
AURA_CY, AURA_RX, AURA_RY = -60.0, 100.0, 110.0
LABAREDAS, LABAREDA = 15, 56.0          # labaredas por camada e o comprimento da maior (px)
CAMADAS_AURA = (                        # (tamanho, cor da borda, cor do meio, alfa da borda, alfa do meio)
    (1.0, (255, 176, 20), (255, 226, 110), 215, 150),             # de fora: ouro
    (0.84, (255, 214, 60), (255, 242, 170), 185, 120),            # meio: amarelo
    (0.66, (255, 246, 170), (255, 255, 236), 160, 130),           # de dentro: branco-amarelado
)
CICLO_AURA, QUADROS_AURA = 2.0, 24      # s do ciclo e quadros guardados (12 por segundo, como animação de anime)
PULSOS = 6                              # pulsos da aura por ciclo: 3 por segundo
CACHE_CABELO = 40                       # ângulos de visão guardados da juba (os mais recentes)
REGIAO_CABELO = QRectF(-125.0, -170.0, 250.0, 185.0)   # onde a juba cabe com a câmera sem deslocamento
# Micro-raios elétricos SSJ2: RAIOS raios em volta da aura, cada um com o seu relógio: uma vez a cada
# PERIODO_RAIO s ele nasce num ponto sorteado, dá um clarão, oscila e some (VIDA_RAIO s). Ficam nos dois
# lados, em cima, no meio e embaixo, na borda da aura (longe do Clawd). Medidas em fração da altura dele
# transformado (dos pés à ponta da juba).
PERIODO_RAIO, VIDA_RAIO, RAIOS = 0.5, (0.16, 0.28), 6
ALTURA_CLAWD = 203.0                    # px, dos pés à ponta da juba (medido no desenho)
RAIO_COMPRIMENTO, RAIO_ESPESSURA = (0.08, 0.15), (0.006, 0.012)
FAIXAS_RAIO = (0.3, 0.5, 0.7)           # alturas na aura (fração de π a partir do topo): em cima, meio, embaixo
RAIO_DOBRAS, RAIO_ANGULO = (3, 5), (45.0, 70.0)        # dobras e o ângulo de cada uma (graus, na ponta da dobra)
OLHO_X, OLHO_Y = 4.1, -3.0              # centro dos olhos na face da frente (o y sobe com o dy da forma)


def _caixa(x0, x1, y0, y1, z0, z1):
    """As seis faces de uma caixa e o centro dela."""
    v = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    faces = [(v[0], v[1], v[3], v[2]), (v[4], v[6], v[7], v[5]),      # x0, x1
             (v[0], v[4], v[5], v[1]), (v[2], v[3], v[7], v[6]),      # y0 (cima), y1 (baixo)
             (v[0], v[2], v[6], v[4]), (v[1], v[5], v[7], v[3])]      # z0, z1
    return faces, ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)


def _mechas():
    """As mechas da juba no modelo: (camada, raiz, meio da curva, ponta, largura da raiz, brilho). Calculado uma vez."""
    mechas = []
    for camada, (z, comprimento, largura, brilho, iz, posicoes) in enumerate(CAMADAS_CABELO):
        for i, s in enumerate(posicoes):
            tam = comprimento * (0.62 + 0.38 * (1.0 - s * s)) * (1.0 + 0.08 * math.sin(i * 2.7 + camada))
            raiz = (5.5 * s, TOPO + 1.1 * s * s, z)             # as dos lados nascem mais baixo
            espelho = 1.0 if s >= 0 else -1.0
            bojo = tam * (BOJO * s + espelho * (0.05 if i % 2 else -0.03))    # abre no meio, alternando
            meio = (raiz[0] + bojo, raiz[1] - tam * 0.62, z + iz * tam * 0.62)
            ponta = (raiz[0] * (1.0 - DENTRO), raiz[1] - tam, z + iz * tam)  # a ponta volta para dentro
            mechas.append((camada, raiz, meio, ponta, largura, brilho))
    for x, angulo, tam, largura, curva in FRANJA:         # caem na testa, entre os olhos
        a = math.radians(angulo)
        raiz = (x, TOPO + 0.4, FRENTE + 0.12)
        d = _unit((math.sin(a), -math.cos(a), 0.15))
        mechas.append((3, *_espinha(raiz, d, tam, curva * tam), largura, 1.02))
    return mechas


def _espinha(raiz, d, tam, curva):
    """Raiz, ponto de controle e ponta da espinha: sobe na direção d e a ponta desvia `curva` para o lado."""
    meio = tuple(raiz[k] + d[k] * tam * 0.75 for k in range(3))     # reta até perto da ponta: o gancho fica no fim
    ponta = (raiz[0] + d[0] * tam + curva, raiz[1] + d[1] * tam, raiz[2] + d[2] * tam)
    return raiz, meio, ponta


class _Camera:
    """Gira o modelo (para o lado e para baixo) e projeta na tela, em px."""

    def __init__(self, giro, inclinacao):
        """Guarda senos e cossenos dos dois ângulos (graus)."""
        a, b = math.radians(giro), math.radians(inclinacao)
        self.ca, self.sa, self.cb, self.sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
        self.dy = 0.0

    def girar(self, v):
        """Ponto do modelo nas coordenadas de quem olha (z maior = mais perto)."""
        x, y, z = v
        x1, z1 = x * self.ca + z * self.sa, -x * self.sa + z * self.ca
        return x1, y * self.cb + z1 * self.sb, -y * self.sb + z1 * self.cb

    def tela(self, v):
        """Ponto do modelo em px na tela (centro do pet na origem)."""
        x, y, _z = self.girar(v)
        return QPointF(x * U, y * U + self.dy)


def _sombra(cor, k):
    """A cor escurecida (k < 1) ou clareada (k > 1)."""
    return QColor(min(255, int(cor.red() * k)), min(255, int(cor.green() * k)), min(255, int(cor.blue() * k)))


def _malha(solidos):
    """Faces prontas para girar: (vértices, normal unitária para fora, centro da face). Calculado uma vez."""
    malha = []
    for faces, centro in solidos:
        for face in faces:
            a = [face[1][i] - face[0][i] for i in range(3)]
            b = [face[2][i] - face[0][i] for i in range(3)]
            n = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
            meio = tuple(sum(v[i] for v in face) / len(face) for i in range(3))
            if sum(n[i] * (meio[i] - centro[i]) for i in range(3)) < 0:      # normal para fora do sólido
                n = (-n[0], -n[1], -n[2])
            malha.append((face, _unit(n), meio))
    return malha


MALHA_PERNAS = _malha([_caixa(*c) for c in PERNAS])
MALHA_TRONCO = _malha([_caixa(*c) for c in TRONCO])
MECHAS = _mechas()
# a base da juba cobre a face de cima: os cantos dela e uma cúpula baixa
CUPULA = [(x, TOPO - 0.3, z) for x in (-6.3, 6.3) for z in (-3.3, 3.3)] + \
         [(x, TOPO - 2.4, z) for x in (-4.6, 4.6) for z in (-2.3, 2.3)]
SOLAS = [(x, y1, z) for x0, x1, _y0, y1, z0, z1 in PERNAS for x in (x0, x1) for z in (z0, z1)]


def _pintar(p, cam, malha, cor):
    """Pinta as faces viradas para quem olha, de trás para frente, com sombra pela luz."""
    visiveis = []
    for face, normal, meio in malha:
        nx, ny, nz = cam.girar(normal)                  # o giro é rígido: a normal gira junto
        if nz <= 1e-9:                                  # de costas para quem olha
            continue
        luz = 0.62 + 0.55 * max(0.0, nx * LUZ[0] + ny * LUZ[1] + nz * LUZ[2])
        visiveis.append((cam.girar(meio)[2], face, luz))
    visiveis.sort(key=lambda f: f[0])
    for _z, face, luz in visiveis:
        tom = _sombra(cor, luz)
        p.setPen(QPen(tom.darker(118), 0.8))
        p.setBrush(tom)
        p.drawPolygon(QPolygonF([cam.tela(v) for v in face]))


def _olhos(p, cam, shape, gaze, blink, emotion, carinho, ssj):
    """Olhos na face da frente: a forma vem de EYE_SHAPES; no carinho, os > < do adesivo."""
    z = FRENTE + 0.02
    gx, gy = gaze
    cy = OLHO_Y + shape["dy"] / 25.0 + gy * 0.3
    if carinho:
        p.setPen(QPen(OLHO, U * 0.42, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for lado in (-1, 1):
            cx = lado * OLHO_X
            ponta = cx - lado * 0.45                     # > na esquerda, < na direita
            p.drawPolyline(QPolygonF([cam.tela((ponta + lado * 0.9, cy - 0.75, z)), cam.tela((ponta, cy, z)),
                                      cam.tela((ponta + lado * 0.9, cy + 0.75, z))]))
        return
    w = shape["w"] / 30.0 * 1.15
    h = max(shape["h"] * blink, 3.0) / 40.0 * 2.4
    if emotion == "curioso":
        h *= 1.08
    interno = max(shape["inner"], 0.3) if ssj else shape["inner"]        # transformado: olhar decidido
    for lado in (-1, 1):
        cx = lado * OLHO_X + gx * 0.35
        fora, dentro = cx + lado * w / 2, cx - lado * w / 2
        topo, base = cy - h / 2, cy + h / 2
        pts = [(fora, topo + shape["outer"] * h), (dentro, topo + interno * h), (dentro, base)]
        if shape["smile"] > 0.02:
            pts.append((cx, base - shape["smile"] * h * 0.9))           # sorriso: base em ^
        pts.append((fora, base))
        p.setPen(QPen(CONTORNO_OLHO_SSJ, 1.0) if ssj else Qt.PenStyle.NoPen)
        p.setBrush(OLHO_SSJ if ssj else OLHO)
        p.drawPolygon(QPolygonF([cam.tela((x, y, z)) for x, y in pts]))
        bx = cx + lado * w * 0.15                        # reflexo: um quadradinho claro logo abaixo da pálpebra
        by = topo + h * (0.35 * interno + 0.65 * shape["outer"]) + 0.2
        if ssj and base - by > 0.9:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(BRILHO_OLHO_SSJ)
            p.drawPolygon(QPolygonF([cam.tela((x, y, z)) for x, y in
                                     ((bx - 0.2, by), (bx + 0.2, by), (bx + 0.2, by + 0.4), (bx - 0.2, by + 0.4))]))


def _envoltoria(pts):
    """Contorno convexo de pontos na tela (QPointF), em ordem."""
    pts = sorted(pts, key=lambda q: (q.x(), q.y()))

    def cruz(o, a, b):
        return (a.x() - o.x()) * (b.y() - o.y()) - (a.y() - o.y()) * (b.x() - o.x())

    baixo: list[QPointF] = []
    cima: list[QPointF] = []
    for q in pts:
        while len(baixo) >= 2 and cruz(baixo[-2], baixo[-1], q) <= 0:
            baixo.pop()
        baixo.append(q)
    for q in reversed(pts):
        while len(cima) >= 2 and cruz(cima[-2], cima[-1], q) <= 0:
            cima.pop()
        cima.append(q)
    return baixo[:-1] + cima[:-1]


def _tom(rgb, k, alfa=255):
    """Cor de TONS_CABELO com o brilho da camada."""
    return QColor(min(255, int(rgb[0] * k)), min(255, int(rgb[1] * k)), min(255, int(rgb[2] * k)), alfa)


def _na_curva(b, c, t, u):
    """Ponto e normal unitária (para a esquerda da direção) da curva quadrática b→c→t em u."""
    m = 1.0 - u
    x = m * m * b.x() + 2 * m * u * c.x() + u * u * t.x()
    y = m * m * b.y() + 2 * m * u * c.y() + u * u * t.y()
    dx = 2 * m * (c.x() - b.x()) + 2 * u * (t.x() - c.x())
    dy = 2 * m * (c.y() - b.y()) + 2 * u * (t.y() - c.y())
    n = math.hypot(dx, dy) or 1.0
    return QPointF(x, y), (dy / n, -dx / n)


def _suave(caminho, pontos):
    """Liga os pontos com uma curva suave que passa por todos (Catmull-Rom em cúbicas)."""
    for i in range(len(pontos) - 1):
        p0, p1, p2 = pontos[max(0, i - 1)], pontos[i], pontos[i + 1]
        p3 = pontos[min(len(pontos) - 1, i + 2)]
        caminho.cubicTo(p1 + (p2 - p0) / 6.0, p2 - (p3 - p1) / 6.0, p2)


def _mecha(p, cam, raiz, meio, ponta, largura, brilho, escala):
    """Uma mecha: sobe como labareda (cheia até o meio, ponta fina e curva), com degradê, sombra de anime e reflexo."""
    def esc(v):
        return tuple(raiz[k] + (v[k] - raiz[k]) * escala for k in range(3))

    b, c, t = cam.tela(raiz), cam.tela(esc(meio)), cam.tela(esc(ponta))
    hw = largura * U * 0.5 * max(0.4, escala)
    amostras = [(u, k, *_na_curva(b, c, t, u)) for u, k in PERFIL_MECHA]
    sinal = -1.0 if amostras[0][3][0] > 0 else 1.0      # o lado "esquerdo" da mecha é o da luz (esquerda da tela)

    def borda(lado, fator=1.0):
        return [QPointF(q.x() + sinal * n[0] * hw * k * lado * fator, q.y() + sinal * n[1] * hw * k * lado * fator)
                for _u, k, q, n in amostras]

    luz, escuro = borda(1.0), borda(-1.0)
    espinha = [q for _u, _k, q, _n in amostras]
    subida = espinha[1] - espinha[0]
    fundo = espinha[0] - subida * (hw * 0.35 / max(1.0, math.hypot(subida.x(), subida.y())))
    caminho = QPainterPath(luz[0])
    _suave(caminho, luz)
    _suave(caminho, escuro[::-1])
    caminho.lineTo(fundo)                             # a raiz entra na juba
    caminho.closeSubpath()
    degrade = QLinearGradient(b, t)
    for pos, rgb in TONS_CABELO:
        degrade.setColorAt(pos, _tom(rgb, brilho))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(degrade))
    p.drawPath(caminho)
    sombra = QPainterPath(fundo)                      # metade longe da luz, com corte na espinha (anime)
    _suave(sombra, [fundo, *espinha[1:]])
    _suave(sombra, escuro[::-1])
    sombra.closeSubpath()
    p.setBrush(SOMBRA_CABELO)
    p.drawPath(sombra)
    reflexo = QPainterPath(borda(1.0, 0.55)[0])       # brilho fino do lado da luz, até perto da ponta
    _suave(reflexo, borda(1.0, 0.55)[:4])
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(255, 252, 215, int(175 * min(1.0, brilho))), max(1.0, hw * 0.12),
                  Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawPath(reflexo)
    p.setPen(QPen(_tom(CONTORNO_CABELO, brilho, 235), 1.2))
    p.drawPath(caminho)


def _cabelo(p, cam, escala, camadas):
    """Pinta as mechas das camadas pedidas, de trás para frente."""
    for camada in camadas:
        mechas = [m for m in MECHAS if m[0] == camada]
        mechas.sort(key=lambda m: cam.girar(m[1])[2])
        for _camada, raiz, meio, ponta, largura, brilho in mechas:
            _mecha(p, cam, raiz, meio, ponta, largura, brilho, escala)


def _cupula(p, cam):
    """Base da juba por cima da cabeça (esconde a face de cima, de onde as mechas nascem)."""
    contorno = _envoltoria([cam.tela(v) for v in CUPULA])
    alto = min(q.y() for q in contorno)
    baixo = max(q.y() for q in contorno)
    degrade = QLinearGradient(QPointF(0, alto), QPointF(0, baixo))
    degrade.setColorAt(0.0, _tom(TONS_CABELO[2][1], 1.0))
    degrade.setColorAt(1.0, _tom(TONS_CABELO[0][1], 1.0))
    p.setPen(QPen(_tom((140, 70, 0), 1.0, 230), 1.3))
    p.setBrush(QBrush(degrade))
    p.drawPolygon(QPolygonF(contorno))


def _acaso(n, j):
    """Número de 0 a 1 que só depende de (n, j): o mesmo desenho em todo quadro que o pede."""
    h = (n * 2654435761 + j * 2246822519 + 374761393) & 0xFFFFFFFF
    h = ((h ^ (h >> 15)) * 2246822519) & 0xFFFFFFFF
    return ((h ^ (h >> 13)) & 0xFFFFFF) / float(0x1000000)


def _dentro(q):
    """O ponto puxado para dentro da janela do Super Saiyajin (com margem)."""
    r = REGIAO_AURA.adjusted(MARGEM_AURA, MARGEM_AURA, -MARGEM_AURA, -MARGEM_AURA)
    return QPointF(min(r.right(), max(r.left(), q.x())), min(r.bottom(), max(r.top(), q.y())))


def _contorno_aura(semente, k, pulso, escala):
    """
    Contorno de uma camada da aura (k = tamanho; 1 = a de fora): oval com labaredas altas, pontudas e
    irregulares saindo por cima e pelos lados, todas subindo; o fundo, nos pés, fica liso.
    """
    rx, ry = AURA_RX * k * escala, AURA_RY * k * escala
    cy = AURA_CY + AURA_RY - ry                          # encolhe para os pés: a base fica no lugar

    def oval(th, f=1.0):
        return QPointF(rx * f * math.sin(th), cy - ry * f * math.cos(th))

    inicio, fim = -0.8 * math.pi, 0.8 * math.pi
    passo = (fim - inicio) / LABAREDAS
    vales = [oval(inicio + i * passo, 0.9 + 0.08 * _acaso(semente, 3 * i)) for i in range(LABAREDAS + 1)]
    pts = [oval(-math.pi + (inicio + math.pi) * j / 4) for j in range(4)]         # fundo e começo do lado esquerdo
    for i in range(LABAREDAS):
        meio = inicio + passo * (i + 0.5 + 0.35 * (_acaso(semente, 3 * i + 1) - 0.5))
        b = oval(meio)
        s = math.sin(meio)
        dx, dy = 0.5 * s, -1.0                           # sobe e abre um pouco para o seu lado
        n = math.hypot(dx, dy)
        dx, dy = dx / n, dy / n
        baixa = max(0.0, (abs(meio) - 0.5 * math.pi) / (0.3 * math.pi))           # as de baixo são curtas
        tam = LABAREDA * k * escala * (0.45 + 0.55 * _acaso(semente, 3 * i + 2)) * (0.82 + 0.3 * pulso) * (1.0 - 0.5 * baixa)
        ponta = QPointF(b.x() + dx * tam, b.y() + dy * tam)
        for a, z in ((vales[i], ponta), (ponta, vales[i + 1])):               # flancos tortos: uma quina no meio
            if a is not ponta:
                pts.append(a)
            torto = 7.0 * (_acaso(semente * 7 + i, len(pts)) - 0.5)
            pts.append(QPointF((a.x() + z.x()) / 2 - dy * torto, (a.y() + z.y()) / 2 + dx * torto))
            if a is not ponta:
                pts.append(ponta)
    pts.append(vales[-1])
    pts += [oval(fim + (math.pi - fim) * j / 4) for j in range(1, 4)]          # fim do lado direito e fundo
    return [_dentro(q) for q in pts]


def _aura(p, quadro, forca, escala=1.0):
    """
    Aura SSJ2: camadas de labaredas douradas (de fora para dentro, cada vez mais brancas), borda luminosa,
    brilho amarelo-branco no centro e um pulso rápido (PULSOS por ciclo). `quadro` sorteia as labaredas.
    """
    pulso = 0.5 + 0.5 * math.sin(math.tau * PULSOS * quadro / QUADROS_AURA)
    vivo = forca * (0.85 + 0.15 * pulso)
    centro = QPointF(0.0, AURA_CY + AURA_RY * (1.0 - escala) + 12.0)
    topo, base = AURA_CY - AURA_RY - LABAREDA, AURA_CY + AURA_RY

    def cor(rgb, alfa):
        r, g, b = rgb
        return QColor(r, g, b, max(0, min(255, int(alfa * vivo))))

    p.save()
    for camada, (k, borda, meio, alfa_borda, alfa_meio) in enumerate(CAMADAS_AURA):
        contorno = QPolygonF(_contorno_aura(quadro * 13 + camada * 5 + 1, k, pulso, escala))
        enchimento = QRadialGradient(centro, AURA_RY * k * escala * 1.25)    # meio mais claro, borda mais forte
        enchimento.setColorAt(0.0, cor(meio, alfa_meio))
        enchimento.setColorAt(0.6, cor(meio, alfa_meio * 1.2))
        enchimento.setColorAt(1.0, cor(borda, alfa_borda))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(enchimento))
        p.drawPolygon(contorno)
        p.setBrush(Qt.BrushStyle.NoBrush)
        # borda luminosa: brilho largo de quina redonda (a quina em bico esticaria para fora da janela) e
        # um fio claro de quina viva por cima
        for largura, rgb, alfa, quina in ((6.0, borda, 90, Qt.PenJoinStyle.RoundJoin),
                                          (2.0, (255, 250, 200), 235, Qt.PenJoinStyle.MiterJoin)):
            linha = QLinearGradient(QPointF(0.0, topo), QPointF(0.0, base))        # some nos pés
            linha.setColorAt(0.0, cor(rgb, alfa))
            linha.setColorAt(0.72, cor(rgb, alfa * 0.8))
            linha.setColorAt(1.0, cor(rgb, 0))
            p.setPen(QPen(QBrush(linha), largura * k, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, quina))
            p.drawPolygon(contorno)
    brilho = QRadialGradient(centro, 80.0 * escala)     # brilho amarelo-branco no centro
    for pos, alfa in ((0.0, 190), (0.5, 80), (1.0, 0)):
        brilho.setColorAt(pos, cor((255, 254, 232), alfa))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(brilho))
    p.drawEllipse(centro, 80.0 * escala, 80.0 * escala)
    p.restore()


def _zigue(n, origem, rumo, altura=ALTURA_CLAWD):
    """
    Pontos de um micro-raio: zigue-zague de RAIO_DOBRAS dobras afiadas (ângulo na ponta de cada uma dentro de
    RAIO_ANGULO), comprimento total em RAIO_COMPRIMENTO da altura, seguindo `rumo` (radianos) a partir da origem.
    """
    dobras = RAIO_DOBRAS[0] + min(RAIO_DOBRAS[1] - RAIO_DOBRAS[0], int(_acaso(n, 2) * (RAIO_DOBRAS[1] - RAIO_DOBRAS[0] + 1)))
    comprimento = altura * (RAIO_COMPRIMENTO[0] + (RAIO_COMPRIMENTO[1] - RAIO_COMPRIMENTO[0]) * _acaso(n, 3))
    # trechos longos para a frente e curtos voltando (o raio avança, como um ⚡), cada um com seu tamanho
    pesos = [(1.0 if i % 2 == 0 else 0.42) * (0.75 + 0.5 * _acaso(n, 10 + i)) for i in range(dobras + 1)]
    sinal = 1.0 if _acaso(n, 4) < 0.5 else -1.0
    direcoes = [0.0]
    for i in range(dobras):                              # a cada dobra vira 180° menos o ângulo da ponta
        ponta = math.radians(RAIO_ANGULO[0] + (RAIO_ANGULO[1] - RAIO_ANGULO[0]) * _acaso(n, 20 + i))
        direcoes.append(direcoes[-1] + sinal * (math.pi - ponta))
        sinal = -sinal
    desvio = rumo - sum(w * d for w, d in zip(pesos, direcoes, strict=True)) / sum(pesos)   # em média, segue o rumo
    pts = [origem]
    for peso, d in zip(pesos, direcoes, strict=True):
        passo = comprimento * peso / sum(pesos)
        pts.append(QPointF(pts[-1].x() + passo * math.cos(d + desvio), pts[-1].y() + passo * math.sin(d + desvio)))
    return pts


def _raios_vivos(now):
    """
    Os raios acesos agora: (k, n, u, força), com k o raio (0 a RAIOS-1), n a vez dele (sorteia forma e lugar),
    u de 0 (nasce) a 1 (some) e força de 0 a 1. Cada raio tem o seu relógio: se sobrepõem e se alternam.
    """
    vivos = []
    for k in range(RAIOS):
        atraso = _acaso(k, 99) * PERIODO_RAIO
        vez = math.floor((now + atraso) / PERIODO_RAIO)
        n = vez * RAIOS + k
        vida = VIDA_RAIO[0] + (VIDA_RAIO[1] - VIDA_RAIO[0]) * _acaso(n, 9)
        idade = now + atraso - (vez * PERIODO_RAIO + _acaso(n, 0) * (PERIODO_RAIO - vida))
        if 0.0 <= idade < vida:
            vivos.append((k, n, idade / vida, 0.7 + 0.3 * _acaso(n, 8)))
    return vivos


def _fita(pts, largura):
    """Polígono do raio com a largura `largura` no meio e ponta afiada nas duas pontas (sem curva: quinas vivas)."""
    trechos = [math.hypot(b.x() - a.x(), b.y() - a.y()) or 1e-6 for a, b in itertools.pairwise(pts)]
    total, andado = sum(trechos), 0.0
    esquerda, direita = [], []
    for i, q in enumerate(pts):
        vizinhos = ([(pts[i - 1], q, trechos[i - 1])] if i > 0 else []) + \
                   ([(q, pts[i + 1], trechos[i])] if i < len(pts) - 1 else [])
        normais = [((a.y() - b.y()) / d, (b.x() - a.x()) / d) for a, b, d in vizinhos]
        nx, ny = sum(n[0] for n in normais), sum(n[1] for n in normais)
        tam = math.hypot(nx, ny) or 1.0
        nx, ny = nx / tam, ny / tam
        miter = 1.0 / max(0.35, abs(nx * normais[0][0] + ny * normais[0][1]))      # quina não afina
        if i > 0:
            andado += trechos[i - 1]
        meia = 0.5 * largura * max(0.0, math.sin(math.pi * min(1.0, andado / total))) ** 0.6 * miter      # 0 nas pontas: afiado
        esquerda.append(QPointF(q.x() + nx * meia, q.y() + ny * meia))
        direita.append(QPointF(q.x() - nx * meia, q.y() - ny * meia))
    return QPolygonF(esquerda + direita[::-1])


def _raios(p, now):
    """Micro-raios SSJ2: núcleo branco, contorno azul-ciano, brilho em volta e faíscas de vez em quando."""
    p.save()
    for k, n, u, forca in _raios_vivos(now):
        fase = int(u * 4)                                # oscila: muda um pouco 4 vezes na vida
        if u < 0.15:
            alfa = 1.0                                   # clarão: brilho total
        else:                                            # depois oscila e some, cada raio com a sua força
            alfa = forca * ((1.0 - u) / 0.85) ** 1.3 * (0.7 + 0.3 * _acaso(n, 40 + fase))
        lado = -1.0 if k % 2 == 0 else 1.0               # metade de cada lado, em cima, no meio e embaixo
        th = lado * math.pi * (FAIXAS_RAIO[k // 2 % len(FAIXAS_RAIO)] + 0.1 * (_acaso(n, 1) - 0.5))
        f = 1.0 + 0.1 * _acaso(n, 5)                     # na borda de fora da aura: longe da silhueta, no escuro
        origem = QPointF(AURA_RX * f * math.sin(th), AURA_CY - AURA_RY * f * math.cos(th))
        rumo = math.atan2(math.sin(th) * AURA_RY, math.cos(th) * AURA_RX)          # ao longo da borda
        rumo += (math.pi if _acaso(n, 6) < 0.5 else 0.0) + 0.9 * (_acaso(n, 7) - 0.5)
        base = _zigue(n, origem, rumo)
        tremor = 0.7 * U * 0.15                          # a oscilação mexe as quinas de leve
        pts = [_dentro(QPointF(q.x() + tremor * (2 * _acaso(n * 5 + fase, 60 + i) - 1),
                               q.y() + tremor * (2 * _acaso(n * 5 + fase, 70 + i) - 1))) for i, q in enumerate(base)]
        espessura = ALTURA_CLAWD * (RAIO_ESPESSURA[0] + (RAIO_ESPESSURA[1] - RAIO_ESPESSURA[0]) * _acaso(n, 3 + fase))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(20, 140, 255, int(85 * alfa)), espessura * 3.2, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))           # brilho suave em volta
        p.drawPolyline(QPolygonF(pts))
        p.setPen(Qt.PenStyle.NoPen)
        clarao = 1.35 if u < 0.15 else 1.0               # no clarão o núcleo engrossa
        for largura, cor, a in ((1.8, (40, 210, 255), 250), (0.8 * clarao, (250, 255, 255), 255)):
            p.setBrush(QColor(*cor, int(a * alfa)))
            p.drawPolygon(_fita(pts, espessura * largura))
        if _acaso(n, 50) < 0.6:                          # faíscas: de vez em quando, 1 a 3 pontinhos se soltando
            for j in range(1 + int(_acaso(n, 51) * 3)):
                q = pts[1 + int(_acaso(n, 52 + j) * (len(pts) - 2))]
                ang = math.tau * _acaso(n, 56 + j)
                d = 2.0 + 7.0 * u
                p.setBrush(QColor(210, 248, 255, int(230 * alfa * (1.0 - u))))
                p.drawEllipse(QPointF(q.x() + d * math.cos(ang), q.y() + d * math.sin(ang)), 0.9, 0.9)
    p.restore()


_cache_cabelo: OrderedDict[tuple[str, int, int, float], QPixmap] = OrderedDict()   # (parte, giro, inclinação, dpr)
_cache_aura: dict[int, QPixmap] = {}                                                # quadro da aura


def _pre_desenho(regiao, dpr, desenhar):
    """Desenha numa imagem transparente do tamanho da região (para guardar e só colar depois)."""
    imagem = QPixmap(max(1, round(regiao.width() * dpr)), max(1, round(regiao.height() * dpr)))
    imagem.setDevicePixelRatio(dpr)
    imagem.fill(Qt.GlobalColor.transparent)
    q = QPainter(imagem)
    q.setRenderHint(QPainter.RenderHint.Antialiasing)
    q.translate(-regiao.left(), -regiao.top())
    desenhar(q)
    q.end()
    return imagem


def _juba(p, parte, giro, inclinacao, dy, dpr):
    """Cola a parte da juba ("tras" ou "frente") já pronta para este ângulo, desenhando se ainda não tiver."""
    chave = (parte, round(giro), round(inclinacao), dpr)
    imagem = _cache_cabelo.get(chave)
    if imagem is None:
        cam = _Camera(chave[1], chave[2])
        if parte == "tras":
            imagem = _pre_desenho(REGIAO_CABELO, dpr, lambda q: _cabelo(q, cam, 1.0, (0,)))
        else:
            imagem = _pre_desenho(REGIAO_CABELO, dpr, lambda q: (_cupula(q, cam), _cabelo(q, cam, 1.0, CAMADAS_FRENTE)))
        _cache_cabelo[chave] = imagem
        if len(_cache_cabelo) > CACHE_CABELO:
            _cache_cabelo.popitem(last=False)          # esquece o ângulo mais antigo
    else:
        _cache_cabelo.move_to_end(chave)
    p.drawPixmap(QPointF(REGIAO_CABELO.left(), REGIAO_CABELO.top() + dy), imagem)


def _aura_pronta(p, now):
    """Cola o quadro da aura deste instante (12 por segundo, em ciclo), desenhando se ainda não tiver."""
    quadro = int(now * QUADROS_AURA / CICLO_AURA) % QUADROS_AURA
    imagem = _cache_aura.get(quadro)
    if imagem is None:     # shortcut: aura guardada em 1x (fica um pouco macia em tela 2x), guardar no dpr se incomodar
        imagem = _pre_desenho(REGIAO_AURA, 1.0, lambda q: _aura(q, quadro, 1.0))
        _cache_aura[quadro] = imagem
    p.drawPixmap(QRectF(REGIAO_AURA), imagem, QRectF(imagem.rect()))


def draw_clawd(p, shape, gaze=(0.0, 0.0), blink=1.0, emotion="observando", carinho=False, ssj=None, now=0.0):
    """
    Desenha o Clawd com o centro do pet na origem do painter e os pés em +BODY_H/2 (onde a física
    apoia o corpo). `ssj` = segundos desde a transformação em Super Saiyajin, ou None (desligado).
    """
    gx, gy = gaze
    giro, inclinacao = GIRO_OLHAR * gx + 5.0 * math.sin(now * 0.7), INCLINACAO + 6.0 * gy
    cam = _Camera(giro, inclinacao)
    pes = max(cam.girar(v)[1] for v in SOLAS)
    cam.dy = BODY_H / 2 - pes * U                        # os pés tocam o chão em qualquer giro

    escala = 0.0 if ssj is None else min(1.0, max(0.05, ssj / CRESCER_CABELO))
    pronto = ssj is not None and ssj >= EXPLOSAO        # transformação acabou: usa o que está guardado
    dpr = p.device().devicePixelRatioF() if p.device() is not None else 1.0
    if pronto:
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)   # o corpo pode estar girado
        _aura_pronta(p, now)
        _juba(p, "tras", giro, inclinacao, cam.dy, dpr)  # a camada de trás fica atrás do corpo
    elif ssj is not None:                                # transformando: desenha ao vivo (dura 1,2 s)
        forca = 1.0 + 1.2 * (1.0 - ssj / EXPLOSAO)
        _aura(p, int(now * QUADROS_AURA / CICLO_AURA), forca, 0.55 + 0.45 * escala)
        _cabelo(p, cam, escala, (0,))
    _pintar(p, cam, MALHA_PERNAS, CORPO)
    _pintar(p, cam, MALHA_TRONCO, CORPO)
    if pronto:
        _juba(p, "frente", giro, inclinacao, cam.dy, dpr)
    elif ssj is not None:
        _cupula(p, cam)
        _cabelo(p, cam, escala, CAMADAS_FRENTE)
    _olhos(p, cam, shape, gaze, blink, emotion, carinho, ssj is not None)
    if ssj is not None:
        _raios(p, now)
    if ssj is not None and ssj < EXPLOSAO:                                   # clarão da transformação
        k = ssj / EXPLOSAO
        p.setPen(QPen(QColor(255, 250, 220, int(220 * (1 - k))), 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(0, -50.0), 30 + 76 * k, 30 + 90 * k)

"""
KI - as rajadas de Ki do Clawd em Super Saiyajin (no lugar das bolinhas de papel da revolução).

Cada rajada é uma esfera pequena e redonda de energia dourada: núcleo branco, borda amarelo-dourada, brilho em
volta e faíscas elétricas azul-ciano (as mesmas da aura). Ela vive em três fases:

    carga    nasce na pata e cresce em CARGA segundos, com faíscas entrando nela; segue a pata se ele se mexe
    voo      sai em alta velocidade (acelera em ACELERACAO s até VELOCIDADE) rumo ao alvo, com rastro de energia
    clarão   ao chegar no alvo, bater num objeto ou na borda da tela, some num flash curto com estilhaços

A janela é pequena (LADO px), acompanha a esfera e deixa o clique passar. A física é por tempo (`passo`), sem
depender da taxa de quadros; o desenho só lê o estado.
"""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from ..body.pet import overlay_flags

CARGA = 0.18            # s carregando na pata
ACELERACAO = 0.05       # s até a velocidade de cruzeiro
VELOCIDADE = 1700.0     # px/s
RAIO = 9.0              # px da esfera pronta
RASTRO = 0.065          # s de posições no rastro (~110 px em cruzeiro)
CLARAO = 0.26           # s do flash final
ALCANCE = 2400.0        # px: some mesmo sem acertar nada
LADO = 280              # px da janela: cabe o rastro, o brilho e os estilhaços
FAISCA_VIDA = (0.12, 0.3)       # s de vida de cada partícula
ATRITO = 7.0                    # 1/s: as faíscas freiam no ar (por tempo, não por quadro)

DOURADO = (255, 196, 40)
AMARELO = (255, 232, 110)
BRANCO_QUENTE = (255, 250, 225)
CIANO = (150, 232, 255)


def _cor(rgb, alfa):
    """QColor de uma tupla (r, g, b) com alfa."""
    return QColor(rgb[0], rgb[1], rgb[2], max(0, min(255, alfa)))


def _suave(u):
    """0 -> 1 com saída macia e um leve passo além (a esfera "estoura" para o tamanho)."""
    u = max(0.0, min(1.0, u))
    return 1.0 + 2.2 * (u - 1.0) ** 3 + 1.2 * (u - 1.0) ** 2


class KiBlast(QWidget):
    """Uma rajada de Ki. `pata()` diz onde a pata está agora (a carga a acompanha); `alvo` é para onde ela vai:
    um ponto ou uma função lida no instante do disparo (o cursor de agora, não o de quando a carga começou)."""

    def __init__(self, pata, alvo, now, semente=None):
        """Nasce carregando na pata, já visível."""
        super().__init__(None, overlay_flags() | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)    # macOS: não some com outro app ativo
        self.setFixedSize(LADO, LADO)
        self.pata = pata
        self.alvo = alvo
        self.nascimento = now
        self.fase = "carga"
        self.ex, self.ey = pata()
        self.dx = self.dy = 0.0             # direção do voo (unitária)
        self.velocidade = 0.0
        self.andado = 0.0
        self.distancia = 0.0                # até o alvo, medida no disparo
        self.inicio_fase = now
        self.rastro = []                    # [(t, x, y)] dos últimos RASTRO s
        self.faiscas = []                   # [[x, y, vx, vy, nascimento, vida, cor]]
        self.agora = now
        self.acaso = random.Random(semente)
        self._posicionar()

    # ---------------- física ----------------

    def passo(self, now, dt, limites, obstaculos=()):
        """Avança `dt` segundos. `limites` = (l, t, r, b) da tela; `obstaculos` = [(x, y, w, h)]. False: acabou."""
        self.agora = now
        if self.fase == "carga":
            self.ex, self.ey = self.pata()
            self._faiscas_entrando(dt)
            if now - self.inicio_fase >= CARGA:
                self._disparar(now)
        elif self.fase == "voo":
            self.velocidade = VELOCIDADE * min(1.0, (now - self.inicio_fase) / ACELERACAO)
            passo = min(self.velocidade * dt, self.distancia - self.andado)
            self.ex += self.dx * passo
            self.ey += self.dy * passo
            self.andado += passo
            self.rastro.append((now, self.ex, self.ey))
            self.rastro = [r for r in self.rastro if now - r[0] <= RASTRO]
            self._faiscas_soltas(dt)
            if (self.andado >= self.distancia - 0.5 or self.andado >= ALCANCE or self._fora(limites)
                    or self._bateu(obstaculos)):
                self._explodir(now)
        elif now - self.inicio_fase >= CLARAO:
            return False
        self._mover_faiscas(dt)
        self._posicionar()
        self.update()
        return True

    def _disparar(self, now):
        """Fim da carga: mira no alvo a partir da pata e sai."""
        ax, ay = self.alvo() if callable(self.alvo) else self.alvo
        vx, vy = ax - self.ex, ay - self.ey
        self.distancia = math.hypot(vx, vy) or 1.0
        self.dx, self.dy = vx / self.distancia, vy / self.distancia
        self.distancia = min(self.distancia, ALCANCE)
        self.fase, self.inicio_fase = "voo", now
        self.rastro = [(now, self.ex, self.ey)]

    def _explodir(self, now):
        """Some num flash: estilhaços dourados e brancos para todos os lados."""
        self.fase, self.inicio_fase = "clarao", now
        for _ in range(14):
            a = self.acaso.uniform(0, math.tau)
            v = self.acaso.uniform(220.0, 520.0)
            self._faisca(self.ex, self.ey, math.cos(a) * v, math.sin(a) * v, BRANCO_QUENTE if self.acaso.random() < 0.4 else AMARELO)

    def _fora(self, limites):
        esq, topo, dir_, base = limites
        return not (esq <= self.ex <= dir_ and topo <= self.ey <= base)

    def _bateu(self, obstaculos):
        return any(x <= self.ex <= x + w and y <= self.ey <= y + h for x, y, w, h in obstaculos)

    # ---------------- partículas ----------------

    def _faisca(self, x, y, vx, vy, cor):
        self.faiscas.append([x, y, vx, vy, self.agora, self.acaso.uniform(*FAISCA_VIDA), cor])

    def _faiscas_entrando(self, dt):
        """Na carga, faíscas vêm de fora e entram na esfera."""
        if self.acaso.random() < 60.0 * dt:
            a = self.acaso.uniform(0, math.tau)
            d = self.acaso.uniform(22.0, 34.0)
            self._faisca(self.ex + math.cos(a) * d, self.ey + math.sin(a) * d,
                         -math.cos(a) * d / 0.14, -math.sin(a) * d / 0.14, CIANO if self.acaso.random() < 0.5 else AMARELO)

    def _faiscas_soltas(self, dt):
        """No voo, o rastro solta faíscas que ficam para trás e se espalham um pouco."""
        if self.acaso.random() < 90.0 * dt:
            lado = self.acaso.uniform(-1.0, 1.0)
            self._faisca(self.ex - self.dx * RAIO, self.ey - self.dy * RAIO,
                         -self.dx * 120.0 - self.dy * lado * 90.0, -self.dy * 120.0 + self.dx * lado * 90.0,
                         CIANO if self.acaso.random() < 0.35 else AMARELO)

    def _mover_faiscas(self, dt):
        vivas = []
        for f in self.faiscas:
            if self.agora - f[4] < f[5]:
                f[0] += f[2] * dt
                f[1] += f[3] * dt
                freio = math.exp(-ATRITO * dt)
                f[2] *= freio
                f[3] *= freio
                vivas.append(f)
        self.faiscas = vivas

    # ---------------- janela e desenho ----------------

    def _posicionar(self):
        self.move(int(self.ex - LADO / 2), int(self.ey - LADO / 2))

    def raio(self):
        """Raio da esfera agora: cresce na carga, pulsa no voo."""
        if self.fase == "carga":
            return RAIO * _suave((self.agora - self.inicio_fase) / CARGA)
        if self.fase == "voo":
            return RAIO * (1.0 + 0.06 * math.sin(self.agora * 55.0))
        return 0.0

    def paintEvent(self, _event):
        """Rastro, brilho, esfera, arcos elétricos, faíscas e o clarão final."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ox, oy = self.ex - LADO / 2, self.ey - LADO / 2         # tela -> janela
        centro = QPointF(self.ex - ox, self.ey - oy)
        if self.fase == "voo":
            self._desenhar_rastro(p, ox, oy)
        if self.fase in ("carga", "voo"):
            r = self.raio()
            if r > 0.5:
                self._desenhar_esfera(p, centro, r)
                self._desenhar_arcos(p, centro, r)
        else:
            self._desenhar_clarao(p, centro)
        self._desenhar_faiscas(p, ox, oy)
        p.end()

    def _desenhar_rastro(self, p, ox, oy):
        """Rastro de energia: uma fita contínua que afina e apaga para trás, com o miolo mais claro."""
        pontos = [(x - ox, y - oy) for _t, x, y in self.rastro]
        if len(pontos) < 2:
            return
        cauda, cabeca = QPointF(*pontos[0]), QPointF(*pontos[-1])
        nx, ny = -self.dy, self.dx                          # o voo é reto: a normal é a mesma em toda a fita
        p.setPen(Qt.PenStyle.NoPen)
        for largura, cor, alfa in ((0.95, DOURADO, 170), (0.38, BRANCO_QUENTE, 230)):
            n = len(pontos) - 1
            lado = [(x + nx * RAIO * largura * (i / n) ** 0.7, y + ny * RAIO * largura * (i / n) ** 0.7)
                    for i, (x, y) in enumerate(pontos)]
            outro = [(x - nx * RAIO * largura * (i / n) ** 0.7, y - ny * RAIO * largura * (i / n) ** 0.7)
                     for i, (x, y) in enumerate(pontos)]
            degrade = QLinearGradient(cauda, cabeca)
            degrade.setColorAt(0.0, _cor(cor, 0))
            degrade.setColorAt(0.6, _cor(cor, int(alfa * 0.45)))
            degrade.setColorAt(1.0, _cor(cor, alfa))
            p.setBrush(degrade)
            p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in lado + outro[::-1]]))

    def _desenhar_esfera(self, p, c, r):
        """Brilho em volta e a esfera: núcleo branco, meio amarelo, borda dourada."""
        cintila = 0.85 + 0.15 * math.sin(self.agora * 37.0)
        brilho = QRadialGradient(c, r * 3.2)
        brilho.setColorAt(0.0, _cor(AMARELO, int(150 * cintila)))
        brilho.setColorAt(0.35, _cor(DOURADO, int(90 * cintila)))
        brilho.setColorAt(1.0, _cor(DOURADO, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brilho)
        p.drawEllipse(c, r * 3.2, r * 3.2)
        esfera = QRadialGradient(c, r)
        esfera.setColorAt(0.0, QColor(255, 255, 255))
        esfera.setColorAt(0.38, _cor(BRANCO_QUENTE, 255))
        esfera.setColorAt(0.72, _cor(AMARELO, 255))
        esfera.setColorAt(1.0, _cor(DOURADO, 255))
        p.setBrush(esfera)
        p.setPen(QPen(QColor(255, 236, 140, 230), 1.4))
        p.drawEllipse(c, r, r)

    def _desenhar_arcos(self, p, c, r):
        """Dois arcos elétricos em zigue-zague em volta da esfera, novos a cada quadro (piscam)."""
        for _ in range(2):
            a = self.acaso.uniform(0, math.tau)
            pts = []
            for j in range(5):
                ang = a + j * 0.32
                d = r * self.acaso.uniform(1.25, 1.95)
                pts.append(QPointF(c.x() + math.cos(ang) * d, c.y() + math.sin(ang) * d))
            p.setPen(QPen(QColor(90, 200, 255, 110), 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                          Qt.PenJoinStyle.MiterJoin))
            p.drawPolyline(pts)
            p.setPen(QPen(_cor(CIANO, 235), 1.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                          Qt.PenJoinStyle.MiterJoin))
            p.drawPolyline(pts)

    def _desenhar_clarao(self, p, c):
        """Flash: núcleo branco que encolhe, anel dourado que abre e brilho que apaga."""
        k = min(1.0, (self.agora - self.inicio_fase) / CLARAO)
        brilho = QRadialGradient(c, RAIO * (2.5 + 3.5 * k))
        brilho.setColorAt(0.0, _cor(BRANCO_QUENTE, int(200 * (1 - k))))
        brilho.setColorAt(0.4, _cor(DOURADO, int(120 * (1 - k))))
        brilho.setColorAt(1.0, _cor(DOURADO, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brilho)
        p.drawEllipse(c, RAIO * (2.5 + 3.5 * k), RAIO * (2.5 + 3.5 * k))
        p.setBrush(QColor(255, 255, 255, int(255 * (1 - k) ** 2)))
        p.drawEllipse(c, RAIO * 1.3 * (1 - k), RAIO * 1.3 * (1 - k))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(_cor(AMARELO, int(230 * (1 - k))), 0.6 + 3.0 * (1 - k)))
        p.drawEllipse(c, RAIO * (1.0 + 2.6 * k), RAIO * (1.0 + 2.6 * k))

    def _desenhar_faiscas(self, p, ox, oy):
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, _vx, _vy, nasc, vida, cor in self.faiscas:
            k = 1.0 - (self.agora - nasc) / vida
            p.setBrush(_cor(cor, int(240 * k)))
            p.drawEllipse(QPointF(x - ox, y - oy), 0.8 + 1.4 * k, 0.8 + 1.4 * k)

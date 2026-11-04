"""
KI - as rajadas de Ki do Clawd em Super Saiyajin (no lugar das bolinhas de papel da revolução).

Cada rajada é uma esfera pequena e redonda de energia dourada: núcleo branco, borda amarelo-dourada, brilho em
volta e faíscas elétricas azul-ciano (as mesmas da aura). Ela vive em três fases:

    carga    nasce na pata e cresce em CARGA segundos, com faíscas entrando nela; segue a pata se ele se mexe
    voo      sai em alta velocidade (acelera em ACELERACAO s até VELOCIDADE) rumo ao alvo, com rastro de energia
    clarão   ao chegar no alvo, bater num objeto ou na borda da tela, some num flash curto com estilhaços

A rajada forte (`forte=True`) é maior e mais brutal: carrega mais (CARGA_FORTE), com mais raios e uma coroa
de labaredas, e é teleguiada: no voo vira para o cursor (no máximo GIRO rad/s, então faz curva), atravessa os
post-its e só explode ao alcançar o cursor, na borda da tela ou depois de VIDA_TELEGUIADO; o clarão é bem maior,
com duas ondas de choque.

A janela é pequena (LADO px, ou LADO_FORTE), acompanha a esfera e deixa o clique passar. A física é por tempo
(`passo`), sem depender da taxa de quadros; o desenho só lê o estado.
"""

from __future__ import annotations

import math
import random
from typing import NamedTuple

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

# rajada forte (teleguiada)
CARGA_FORTE = 0.55
VELOCIDADE_FORTE = 1050.0
RAIO_FORTE = 17.0
RASTRO_FORTE = 0.16
CLARAO_FORTE = 0.55
LADO_FORTE = 520
GIRO = 5.5              # rad/s: o quanto ela consegue virar para o cursor (faz curva, não teleporta)
VIDA_TELEGUIADO = 4.0   # s de voo no máximo
ACERTO = 22.0           # px do cursor: acertou


class Perfil(NamedTuple):
    """Tamanho, tempos e força de uma rajada."""
    carga: float
    velocidade: float
    raio: float
    rastro: float
    clarao: float
    lado: int
    estilhacos: int
    arcos: int


NORMAL = Perfil(CARGA, VELOCIDADE, RAIO, RASTRO, CLARAO, LADO, 14, 2)
FORTE = Perfil(CARGA_FORTE, VELOCIDADE_FORTE, RAIO_FORTE, RASTRO_FORTE, CLARAO_FORTE, LADO_FORTE, 32, 4)

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

    def __init__(self, pata, alvo, now, semente=None, forte=False):
        """Nasce carregando na pata, já visível. `forte`: a rajada grande e teleguiada."""
        super().__init__(None, overlay_flags() | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)    # macOS: não some com outro app ativo
        self.forte = forte
        self.perfil = FORTE if forte else NORMAL
        self.setFixedSize(self.perfil.lado, self.perfil.lado)
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
            if now - self.inicio_fase >= self.perfil.carga:
                self._disparar(now)
        elif self.fase == "voo":
            self.velocidade = self.perfil.velocidade * min(1.0, (now - self.inicio_fase) / ACELERACAO)
            if self.forte:
                acertou = self._perseguir(dt)
            else:
                passo = min(self.velocidade * dt, self.distancia - self.andado)
                self.ex += self.dx * passo
                self.ey += self.dy * passo
                self.andado += passo
                acertou = self.andado >= self.distancia - 0.5 or self.andado >= ALCANCE or self._bateu(obstaculos)
            self.rastro.append((now, self.ex, self.ey))
            self.rastro = [r for r in self.rastro if now - r[0] <= self.perfil.rastro]
            self._faiscas_soltas(dt)
            if acertou or self._fora(limites):
                self._explodir(now)
        elif now - self.inicio_fase >= self.perfil.clarao:
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

    def _perseguir(self, dt):
        """Teleguiada: vira para o cursor de agora (até GIRO rad/s) e anda. True quando acertou ou cansou."""
        ax, ay = self.alvo() if callable(self.alvo) else self.alvo
        desejado = math.atan2(ay - self.ey, ax - self.ex)
        atual = math.atan2(self.dy, self.dx)
        virada = (desejado - atual + math.pi) % math.tau - math.pi
        atual += max(-GIRO * dt, min(GIRO * dt, virada))
        self.dx, self.dy = math.cos(atual), math.sin(atual)
        self.ex += self.dx * self.velocidade * dt
        self.ey += self.dy * self.velocidade * dt
        self.andado += self.velocidade * dt
        perto = math.hypot(ax - self.ex, ay - self.ey) <= ACERTO
        return perto or self.agora - self.inicio_fase >= VIDA_TELEGUIADO

    def _explodir(self, now):
        """Some num flash: estilhaços dourados e brancos para todos os lados (bem mais na forte)."""
        self.fase, self.inicio_fase = "clarao", now
        forca = 1.8 if self.forte else 1.0
        for _ in range(self.perfil.estilhacos):
            a = self.acaso.uniform(0, math.tau)
            v = self.acaso.uniform(220.0, 520.0) * forca
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
        if self.acaso.random() < (160.0 if self.forte else 60.0) * dt:
            a = self.acaso.uniform(0, math.tau)
            d = self.acaso.uniform(22.0, 34.0) * (2.0 if self.forte else 1.0)
            self._faisca(self.ex + math.cos(a) * d, self.ey + math.sin(a) * d,
                         -math.cos(a) * d / 0.14, -math.sin(a) * d / 0.14, CIANO if self.acaso.random() < 0.5 else AMARELO)

    def _faiscas_soltas(self, dt):
        """No voo, o rastro solta faíscas que ficam para trás e se espalham um pouco."""
        if self.acaso.random() < (180.0 if self.forte else 90.0) * dt:
            lado = self.acaso.uniform(-1.0, 1.0)
            r = self.perfil.raio
            self._faisca(self.ex - self.dx * r, self.ey - self.dy * r,
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
        self.move(int(self.ex - self.perfil.lado / 2), int(self.ey - self.perfil.lado / 2))

    def raio(self):
        """Raio da esfera agora: cresce na carga, pulsa no voo."""
        r = self.perfil.raio
        if self.fase == "carga":
            return r * _suave((self.agora - self.inicio_fase) / self.perfil.carga)
        if self.fase == "voo":
            return r * (1.0 + (0.1 if self.forte else 0.06) * math.sin(self.agora * 55.0))
        return 0.0

    def paintEvent(self, _event):
        """Rastro, brilho, esfera, arcos elétricos, faíscas e o clarão final."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ox, oy = self.ex - self.perfil.lado / 2, self.ey - self.perfil.lado / 2      # tela -> janela
        centro = QPointF(self.ex - ox, self.ey - oy)
        if self.fase == "voo":
            self._desenhar_rastro(p, ox, oy)
        if self.fase in ("carga", "voo"):
            r = self.raio()
            if r > 0.5:
                if self.forte:
                    self._desenhar_coroa(p, centro, r)
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
        normais = []                                        # uma por ponto: a fita acompanha a curva da teleguiada
        for i in range(len(pontos)):
            (ax, ay), (bx, by) = pontos[max(0, i - 1)], pontos[min(len(pontos) - 1, i + 1)]
            d = math.hypot(bx - ax, by - ay) or 1.0
            normais.append((-(by - ay) / d, (bx - ax) / d))
        raio = self.perfil.raio * (1.35 if self.forte else 1.0)
        n = len(pontos) - 1
        p.setPen(Qt.PenStyle.NoPen)
        for largura, cor, alfa in ((0.95, DOURADO, 170), (0.38, BRANCO_QUENTE, 230)):
            meia = [raio * largura * (i / n) ** 0.7 for i in range(n + 1)]
            lado = [(x + nx * m, y + ny * m) for (x, y), (nx, ny), m in zip(pontos, normais, meia)]
            outro = [(x - nx * m, y - ny * m) for (x, y), (nx, ny), m in zip(pontos, normais, meia)]
            degrade = QLinearGradient(cauda, cabeca)
            degrade.setColorAt(0.0, _cor(cor, 0))
            degrade.setColorAt(0.6, _cor(cor, int(alfa * 0.45)))
            degrade.setColorAt(1.0, _cor(cor, alfa))
            p.setBrush(degrade)
            p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in lado + outro[::-1]]))

    def _desenhar_esfera(self, p, c, r):
        """Brilho em volta e a esfera: núcleo branco, meio amarelo, borda dourada."""
        cintila = 0.85 + 0.15 * math.sin(self.agora * 37.0)
        alcance = r * (4.6 if self.forte else 3.2)
        brilho = QRadialGradient(c, alcance)
        brilho.setColorAt(0.0, _cor(AMARELO, int((210 if self.forte else 150) * cintila)))
        brilho.setColorAt(0.35, _cor(DOURADO, int((140 if self.forte else 90) * cintila)))
        brilho.setColorAt(1.0, _cor(DOURADO, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brilho)
        p.drawEllipse(c, alcance, alcance)
        esfera = QRadialGradient(c, r)
        esfera.setColorAt(0.0, QColor(255, 255, 255))
        esfera.setColorAt(0.38, _cor(BRANCO_QUENTE, 255))
        esfera.setColorAt(0.72, _cor(AMARELO, 255))
        esfera.setColorAt(1.0, _cor(DOURADO, 255))
        p.setBrush(esfera)
        p.setPen(QPen(QColor(255, 236, 140, 230), 1.4))
        p.drawEllipse(c, r, r)

    def _desenhar_arcos(self, p, c, r):
        """Arcos elétricos em zigue-zague em volta da esfera, novos a cada quadro (piscam); 4 na forte."""
        for _ in range(self.perfil.arcos):
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
        k = min(1.0, (self.agora - self.inicio_fase) / self.perfil.clarao)
        r = self.perfil.raio
        alcance = r * ((4.0 + 10.0 * k) if self.forte else (2.5 + 3.5 * k))
        brilho = QRadialGradient(c, alcance)
        brilho.setColorAt(0.0, _cor(BRANCO_QUENTE, int((255 if self.forte else 220) * (1 - k))))
        brilho.setColorAt(0.4, _cor(DOURADO, int((190 if self.forte else 130) * (1 - k))))
        brilho.setColorAt(1.0, _cor(DOURADO, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brilho)
        p.drawEllipse(c, alcance, alcance)
        p.setBrush(QColor(255, 255, 255, int(255 * (1 - k) ** 2)))
        nucleo = r * (2.4 if self.forte else 1.3) * (1 - k)          # a forte estoura numa bola branca maior
        p.drawEllipse(c, nucleo, nucleo)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(_cor(AMARELO, int(230 * (1 - k))), 0.6 + 3.0 * (1 - k)))
        p.drawEllipse(c, r * (1.0 + 2.6 * k), r * (1.0 + 2.6 * k))
        if self.forte:                                      # segunda onda de choque, branca, mais rápida
            k2 = min(1.0, k * 1.6)
            p.setPen(QPen(QColor(255, 255, 255, int(220 * (1 - k2))), 1.0 + 5.0 * (1 - k2)))
            p.drawEllipse(c, r * (1.2 + 6.0 * k2), r * (1.2 + 6.0 * k2))

    def _desenhar_coroa(self, p, c, r):
        """Só na forte: labaredas de energia girando em volta da esfera e um halo que pulsa."""
        giro = self.agora * 7.0
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(8):
            a = giro + i * math.tau / 8
            comprimento = r * (2.1 + 0.7 * math.sin(self.agora * 23.0 + i * 1.7))
            for largura, alcance, cor, alfa in ((0.42, 1.0, AMARELO, 205), (0.2, 0.8, BRANCO_QUENTE, 230)):
                pontas = [QPointF(c.x() + math.cos(a + d) * r * 0.85, c.y() + math.sin(a + d) * r * 0.85)
                          for d in (-largura, largura)]
                pico = QPointF(c.x() + math.cos(a) * comprimento * alcance, c.y() + math.sin(a) * comprimento * alcance)
                p.setBrush(_cor(cor, alfa))
                p.drawPolygon(QPolygonF([pontas[0], pico, pontas[1]]))
        pulso = 1.0 + 0.25 * math.sin(self.agora * 18.0)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(_cor(BRANCO_QUENTE, 140), 1.6))
        p.drawEllipse(c, r * 1.45 * pulso, r * 1.45 * pulso)

    def _desenhar_faiscas(self, p, ox, oy):
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, _vx, _vy, nasc, vida, cor in self.faiscas:
            k = 1.0 - (self.agora - nasc) / vida
            p.setBrush(_cor(cor, int(240 * k)))
            tamanho = (0.8 + 1.4 * k) * (1.7 if self.forte else 1.0)
            p.drawEllipse(QPointF(x - ox, y - oy), tamanho, tamanho)

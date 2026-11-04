"""
TELEPORTE - o efeito do teletransporte do Clawd SSJ2 (quem decide e move o corpo é mind/poderes.py).

Dois efeitos, um em cada ponta, nas mesmas cores da aura (ouro, amarelo-branco) e dos micro-raios (ciano):

    saída     clarão branco, uma fenda de luz vertical que fecha (o corpo "some num risco"), anéis de distorção
              que abrem ondulando (o espaço "dobra") com uma faixa escura logo atrás de cada um (como lente),
              riscos de luz puxados para o centro e partículas de energia jogadas para fora
    chegada   o contrário: partículas e riscos vêm de fora em espiral para o ponto, os anéis fecham, e no
              fim um clarão com onda de choque e a fenda que abre (o corpo "sai do risco")

Distorção simulada (sem capturar a tela): capturar exigiria permissão de gravação de tela no macOS e não
funciona no Wayland. A física é por tempo (`passo`), o desenho só lê o estado.
"""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF, QRadialGradient
from PySide6.QtWidgets import QWidget

from ..body.pet import overlay_flags

LADO = 340              # px da janela
DURACAO = 0.5           # s de cada efeito
FECHAR = 0.12           # s: a fenda da saída fecha (o corpo some)
ABRIR = 0.18            # s: na chegada, o clarão vem neste instante (o corpo aparece)
ANEIS = 3
PARTICULAS = 34
RISCOS = 14
ATRITO = 5.0            # 1/s: as partículas freiam no ar
OURO = (255, 196, 40)
AMARELO = (255, 238, 140)
BRANCO = (255, 252, 236)
CIANO = (150, 232, 255)


def _cor(rgb, alfa):
    return QColor(rgb[0], rgb[1], rgb[2], max(0, min(255, int(alfa))))


class Teleporte(QWidget):
    """Um efeito de teletransporte em (x, y): `chegada=False` na saída, True no ponto onde ele reaparece."""

    def __init__(self, x, y, now, chegada=False, semente=None):
        """Nasce já visível e deixa o clique passar."""
        super().__init__(None, overlay_flags() | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)    # macOS: não some com outro app ativo
        self.setFixedSize(LADO, LADO)
        self.cx, self.cy = x, y
        self.chegada = chegada
        self.inicio = self.agora = now
        self.acaso = random.Random(semente)
        self.riscos = [(self.acaso.uniform(0, math.tau), self.acaso.uniform(0.6, 1.0)) for _ in range(RISCOS)]
        self.estourou = not chegada         # na chegada, as partículas só estouram para fora no clarão
        self.particulas = []                # [x, y, vx, vy, vida, cor, ângulo, distância] relativos ao centro
        for _ in range(PARTICULAS):
            a = self.acaso.uniform(0, math.tau)
            cor = CIANO if self.acaso.random() < 0.4 else (AMARELO if self.acaso.random() < 0.6 else BRANCO)
            d = self.acaso.uniform(90.0, 150.0)             # chegada: começa fora e vem em espiral
            x, y = (math.cos(a) * d, math.sin(a) * d) if chegada else (0.0, 0.0)
            self.particulas.append([x, y, 0.0, 0.0, self.acaso.uniform(0.3, DURACAO), cor, a, d])
        if not chegada:
            self._estourar(260.0, 620.0)
        self.move(int(x - LADO / 2), int(y - LADO / 2))

    def passo(self, now, dt):
        """Avança `dt` segundos. False: acabou."""
        self.agora = now
        t = now - self.inicio
        if t >= DURACAO:
            return False
        if not self.estourou and t >= ABRIR:
            self._estourar(200.0, 480.0)                    # o clarão da chegada joga tudo para fora
        freio = math.exp(-ATRITO * dt)
        for q in self.particulas:
            if not self.estourou:                           # chegando em espiral até o centro
                u = t / ABRIR
                d, ang = q[7] * (1.0 - u) ** 2, q[6] + 2.4 * u
                q[0], q[1] = math.cos(ang) * d, math.sin(ang) * d
                continue
            q[0] += q[2] * dt
            q[1] += q[3] * dt
            q[2] *= freio
            q[3] *= freio
        self.update()
        return True

    def _estourar(self, vmin, vmax):
        """Todas as partículas saem do lugar onde estão para fora, um pouco para cima (a energia sobe)."""
        self.estourou = True
        for q in self.particulas:
            a, v = self.acaso.uniform(0, math.tau), self.acaso.uniform(vmin, vmax)
            q[2], q[3] = math.cos(a) * v, math.sin(a) * v - 100.0

    # ---------------- desenho ----------------

    def paintEvent(self, _event):
        """Clarão, fenda, anéis de distorção, riscos e partículas."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(LADO / 2, LADO / 2)
        t = self.agora - self.inicio
        k = min(1.0, t / DURACAO)
        flash = (1.0 - min(1.0, t / FECHAR)) if not self.chegada else max(0.0, 1.0 - abs(t - ABRIR) / 0.12)
        self._clarao(p, flash)
        self._fenda(p, t)
        self._aneis(p, t, k)
        self._riscos(p, t)
        self._particulas(p, t)
        p.end()

    def _clarao(self, p, forca):
        if forca <= 0.0:
            return
        r = 70.0 + 50.0 * forca
        g = QRadialGradient(QPointF(0, 0), r)
        g.setColorAt(0.0, _cor(BRANCO, 250 * forca))
        g.setColorAt(0.35, _cor(AMARELO, 170 * forca))
        g.setColorAt(1.0, _cor(OURO, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(0, 0), r, r)

    def _fenda(self, p, t):
        """Risco de luz vertical: fecha na saída (o corpo some nele), abre na chegada (ele sai dele)."""
        if self.chegada:
            u = (t - ABRIR) / 0.16
            if not 0.0 <= u <= 1.0:
                return
            largura, alfa = 2.0 + 26.0 * u, 255 * (1.0 - u)
        else:
            u = t / (FECHAR * 1.6)
            if u > 1.0:
                return
            largura, alfa = 30.0 * (1.0 - u) + 1.5, 255 * (1.0 - u * 0.6)
        altura = 120.0 + 60.0 * (1.0 - abs(u - 0.5) * 2)
        g = QRadialGradient(QPointF(0, -20), altura)
        g.setColorAt(0.0, _cor(BRANCO, alfa))
        g.setColorAt(0.6, _cor(CIANO, alfa * 0.6))
        g.setColorAt(1.0, _cor(CIANO, 0))
        p.setBrush(g)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(0, -20), largura, altura)

    def _aneis(self, p, t, k):
        """Anéis de distorção ondulando: abrem na saída, fecham na chegada; uma faixa escura atrás (lente)."""
        for i in range(ANEIS):
            u = k * 1.25 - i * 0.14
            if not 0.0 < u < 1.0:
                continue
            raio = (12.0 + 128.0 * u) if not self.chegada else (132.0 * (1.0 - u) + 8.0)   # x1,11 cabe em LADO/2
            alfa = 200 * math.sin(math.pi * u)
            pts, sombra = [], []
            for j in range(49):
                th = math.tau * j / 48
                onda = 1.0 + 0.07 * math.sin(6 * th + t * 26.0 + i * 1.7) + 0.04 * math.sin(11 * th - t * 31.0)
                pts.append(QPointF(math.cos(th) * raio * onda, math.sin(th) * raio * onda * 0.92))
                sombra.append(QPointF(math.cos(th) * (raio * onda - 7), math.sin(th) * (raio * onda - 7) * 0.92))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(10, 20, 40, int(alfa * 0.22)), 7.0))
            p.drawPolyline(QPolygonF(sombra))
            p.setPen(QPen(_cor(CIANO, alfa * 0.7), 4.0))
            p.drawPolyline(QPolygonF(pts))
            p.setPen(QPen(_cor(BRANCO, alfa), 1.4))
            p.drawPolyline(QPolygonF(pts))

    def _riscos(self, p, t):
        """Riscos de luz: puxados para o centro (saída) ou chegando de fora (chegada)."""
        if self.chegada:
            u = t / ABRIR
            if u > 1.0:
                return
        else:
            u = t / (DURACAO * 0.6)
            if u > 1.0:
                return
        for a, forca in self.riscos:
            fora = 150.0 * forca * (1.0 - u)
            dentro = max(0.0, fora - 55.0 * forca)
            alfa = 230 * (1.0 - u) * forca
            ini = QPointF(math.cos(a) * fora, math.sin(a) * fora)
            fim = QPointF(math.cos(a) * dentro, math.sin(a) * dentro)
            p.setPen(QPen(_cor(AMARELO, alfa), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(ini, fim)

    def _particulas(self, p, t):
        p.setPen(Qt.PenStyle.NoPen)
        for q in self.particulas:
            x, y, vida, cor = q[0], q[1], q[4], q[5]
            if t > vida:
                continue
            k = 1.0 - t / vida
            p.setBrush(_cor(cor, 245 * k))
            r = 1.0 + 2.2 * k
            p.drawEllipse(QPointF(x, y), r, r)

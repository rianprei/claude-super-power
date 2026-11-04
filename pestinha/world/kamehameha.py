"""
KAMEHAMEHA - o feixe de energia do Clawd SSJ2 (quem decide, segura o corpo e mira é mind/poderes.py).

Três fases, por tempo (`passo`), sem depender da taxa de quadros:

    carga     CARGA s: uma esfera azul-branca cresce entre as patas, com fios de energia ligando cada pata a
              ela, partículas entrando em espiral, arcos elétricos ciano e um brilho que pulsa cada vez mais rápido
    feixe     FEIXE s: a mira é travada no cursor (no disparo) e a ponta do feixe corre a VELOCIDADE px/s até
              lá (pelo menos MINIMO px, no máximo ALCANCE, sempre dentro da tela); o feixe é contínuo, com borda
              ondulando, miolo branco, faixas em espiral girando e a esfera na raiz; na ponta, uma explosão que
              fica ardendo, joga estilhaços e solta uma onda de choque a cada CHOQUE s
    fim       DISSIPA s: o feixe afina da raiz para a ponta e a explosão final abre e apaga

Na carga, a janela é pequena e segue as patas; no disparo ela cresce uma vez só para cobrir o feixe
inteiro e a explosão (não muda de tamanho a cada quadro). Deixa o clique passar.
"""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
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

CARGA = 1.6             # s carregando
FEIXE = 1.5             # s de feixe
DISSIPA = 0.45          # s apagando
VELOCIDADE = 4200.0     # px/s da ponta do feixe
MINIMO, ALCANCE = 320.0, 1900.0     # px do comprimento do feixe
RAIO_ESFERA = 21.0      # px da esfera pronta
LARGURA = 27.0          # px: meia largura do feixe
ABRE = 0.08             # s: o feixe abre até a largura cheia
FOGO = 74.0             # px: raio da explosão na ponta
CHOQUE = 0.25           # s entre as ondas de choque
LADO_CARGA = 300        # px da janela na carga
MARGEM = 210            # px em volta do feixe na janela do disparo (a explosão e o recuo cabem)
ATRITO = 4.0            # 1/s das partículas
AZUL = (60, 140, 255)
CIANO = (130, 220, 255)
GELO = (215, 245, 255)
BRANCO = (255, 255, 255)


def _cor(rgb, alfa):
    return QColor(rgb[0], rgb[1], rgb[2], max(0, min(255, int(alfa))))


def _suave(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3.0 - 2.0 * u)


def comprimento_na_tela(x, y, dx, dy, limites, desejado):
    """Comprimento do feixe saindo de (x, y) na direção unitária (dx, dy): o desejado, preso entre MINIMO e
    ALCANCE, e cortado na borda da tela `limites` = (l, t, r, b)."""
    esq, topo, dir_, base = limites
    teto = ALCANCE
    for d, lo, hi, o in ((dx, esq, dir_, x), (dy, topo, base, y)):
        if d > 1e-9:
            teto = min(teto, (hi - o) / d)
        elif d < -1e-9:
            teto = min(teto, (lo - o) / d)
    return max(0.0, min(max(desejado, MINIMO), teto))


class Kamehameha(QWidget):
    """O golpe: `maos()` = ((x, y) esquerda, (x, y) direita) das patas agora; `alvo()` = o cursor agora."""

    def __init__(self, maos, alvo, now, limites, semente=None):
        """Nasce carregando entre as patas, já visível."""
        super().__init__(None, overlay_flags() | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)    # macOS: não some com outro app ativo
        self.maos, self.alvo, self.limites = maos, alvo, limites
        self.fase, self.inicio_fase, self.agora = "carga", now, now
        self.ox = self.oy = 0.0             # canto da janela na tela
        self.patas = maos()
        self.ex, self.ey = self._centro()   # a esfera (raiz do feixe)
        self.dx, self.dy = 1.0, 0.0         # direção do feixe (travada no disparo)
        self.comprimento = 0.0              # até onde o feixe vai
        self.ponta = 0.0                    # até onde ele já chegou
        self.ultimo_choque = -1.0
        self.choques = []                   # instantes das ondas de choque
        self.particulas = []                # [x, y, vx, vy, nascimento, vida, cor] na tela
        self.acaso = random.Random(semente)
        self.setFixedSize(LADO_CARGA, LADO_CARGA)
        self._seguir()

    # ---------------- física ----------------

    def _centro(self):
        (lx, ly), (rx, ry) = self.patas
        return (lx + rx) / 2, (ly + ry) / 2

    def passo(self, now, dt):
        """Avança `dt` segundos. False: acabou."""
        self.agora = now
        t = now - self.inicio_fase
        self.patas = self.maos()
        self.ex, self.ey = self._centro()
        if self.fase == "carga":
            self._entrando(dt, t)
            self._seguir()
            if t >= CARGA:
                self._disparar(now)
        elif self.fase == "feixe":
            self.ponta = min(self.comprimento, self.ponta + VELOCIDADE * dt)
            if self.ponta >= self.comprimento:
                self._ardendo(now, dt)
            if t >= FEIXE:
                self.fase, self.inicio_fase = "fim", now
                self._estilhacos(48, 260.0, 760.0)
                self.choques.append(now)
        elif t >= DISSIPA:
            return False
        self._mover(dt)
        self.update()
        return True

    def _disparar(self, now):
        """Fim da carga: trava a mira no cursor de agora e abre a janela do tamanho do feixe."""
        ax, ay = self.alvo()
        vx, vy = ax - self.ex, ay - self.ey
        d = math.hypot(vx, vy)
        if d < 1.0:
            vx, vy, d = 1.0, 0.0, 1.0
        self.dx, self.dy = vx / d, vy / d
        self.comprimento = comprimento_na_tela(self.ex, self.ey, self.dx, self.dy, self.limites, d)
        self.fase, self.inicio_fase = "feixe", now
        fx, fy = self.fim()
        x0, y0 = min(self.ex, fx) - MARGEM, min(self.ey, fy) - MARGEM
        x1, y1 = max(self.ex, fx) + MARGEM, max(self.ey, fy) + MARGEM
        self.ox, self.oy = x0, y0
        self.setFixedSize(int(x1 - x0), int(y1 - y0))
        self.move(int(x0), int(y0))

    def fim(self):
        """Onde o feixe termina (a explosão)."""
        return self.ex + self.dx * self.comprimento, self.ey + self.dy * self.comprimento

    def _seguir(self):
        """Na carga, a janela pequena segue a esfera."""
        self.ox, self.oy = self.ex - LADO_CARGA / 2, self.ey - LADO_CARGA / 2
        self.move(int(self.ox), int(self.oy))

    def _entrando(self, dt, t):
        """Partículas que entram em espiral na esfera; cada vez mais, até o disparo."""
        if self.acaso.random() < (40.0 + 160.0 * t / CARGA) * dt:
            a = self.acaso.uniform(0, math.tau)
            d = self.acaso.uniform(60.0, 110.0)
            vel = d / 0.28
            giro = a + 1.1                          # entra torto: espiral
            self._particula(self.ex + math.cos(a) * d, self.ey + math.sin(a) * d,
                            -math.cos(giro) * vel, -math.sin(giro) * vel, 0.28,
                            BRANCO if self.acaso.random() < 0.4 else CIANO)

    def _ardendo(self, now, dt):
        """A explosão na ponta: estilhaços o tempo todo e uma onda de choque a cada CHOQUE s."""
        if now - self.ultimo_choque >= CHOQUE:
            self.ultimo_choque = now
            self.choques.append(now)
        if self.acaso.random() < 140.0 * dt:
            self._estilhacos(2, 180.0, 520.0)

    def _estilhacos(self, n, vmin, vmax):
        fx, fy = self.fim()
        for _ in range(n):
            a = self.acaso.uniform(0, math.tau)
            v = self.acaso.uniform(vmin, vmax)
            self._particula(fx, fy, math.cos(a) * v, math.sin(a) * v, self.acaso.uniform(0.25, 0.6),
                            BRANCO if self.acaso.random() < 0.35 else (CIANO if self.acaso.random() < 0.6 else GELO))

    def _particula(self, x, y, vx, vy, vida, cor):
        self.particulas.append([x, y, vx, vy, self.agora, vida, cor])

    def _mover(self, dt):
        freio = math.exp(-ATRITO * dt)
        vivas = []
        for q in self.particulas:
            if self.agora - q[4] < q[5]:
                q[0] += q[2] * dt
                q[1] += q[3] * dt
                q[2] *= freio
                q[3] *= freio
                vivas.append(q)
        self.particulas = vivas
        self.choques = [c for c in self.choques if self.agora - c < 0.6]

    def raio_esfera(self):
        """A esfera: cresce na carga; no feixe fica cheia; no fim some."""
        t = self.agora - self.inicio_fase
        if self.fase == "carga":
            return RAIO_ESFERA * (0.2 + 0.8 * _suave(t / CARGA)) * (1.0 + 0.08 * math.sin(t * (14.0 + 30.0 * t)))
        if self.fase == "feixe":
            return RAIO_ESFERA * 1.15 * (1.0 + 0.05 * math.sin(self.agora * 47.0))
        return RAIO_ESFERA * (1.0 - _suave(t / DISSIPA))

    def largura(self):
        """Meia largura do feixe agora."""
        t = self.agora - self.inicio_fase
        if self.fase == "feixe":
            return LARGURA * _suave(t / ABRE) * (1.0 + 0.04 * math.sin(self.agora * 61.0))
        if self.fase == "fim":
            return LARGURA * (1.0 - _suave(t / DISSIPA)) ** 1.5
        return 0.0

    # ---------------- desenho ----------------

    def paintEvent(self, _event):
        """Esfera, fios das patas, feixe, explosão, ondas de choque e partículas."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(-self.ox, -self.oy)                 # desenha em coordenadas da tela
        if self.fase in ("feixe", "fim"):
            self._desenhar_feixe(p)
            self._desenhar_explosao(p)
        if self.fase == "carga":
            self._desenhar_fios(p)
        self._desenhar_esfera(p)
        self._desenhar_particulas(p)
        p.end()

    def _desenhar_esfera(self, p):
        r = self.raio_esfera()
        if r <= 0.5:
            return
        c = QPointF(self.ex, self.ey)
        t = self.agora - self.inicio_fase
        pulso = 0.8 + 0.2 * math.sin(self.agora * (20.0 + (25.0 * t / CARGA if self.fase == "carga" else 25.0)))
        brilho = QRadialGradient(c, r * 4.2)
        brilho.setColorAt(0.0, _cor(GELO, 200 * pulso))
        brilho.setColorAt(0.3, _cor(CIANO, 120 * pulso))
        brilho.setColorAt(1.0, _cor(AZUL, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brilho)
        p.drawEllipse(c, r * 4.2, r * 4.2)
        esfera = QRadialGradient(c, r)
        esfera.setColorAt(0.0, _cor(BRANCO, 255))
        esfera.setColorAt(0.5, _cor(GELO, 255))
        esfera.setColorAt(0.85, _cor(CIANO, 245))
        esfera.setColorAt(1.0, _cor(AZUL, 230))
        p.setBrush(esfera)
        p.setPen(QPen(_cor(BRANCO, 200), 1.2))
        p.drawEllipse(c, r, r)
        for _ in range(3 if self.fase == "carga" else 2):          # arcos elétricos piscando
            a = self.acaso.uniform(0, math.tau)
            pts = [QPointF(c.x() + math.cos(a + j * 0.3) * r * self.acaso.uniform(1.2, 2.0),
                           c.y() + math.sin(a + j * 0.3) * r * self.acaso.uniform(1.2, 2.0)) for j in range(5)]
            p.setPen(QPen(_cor(CIANO, 120), 3.0))
            p.drawPolyline(QPolygonF(pts))
            p.setPen(QPen(_cor(BRANCO, 235), 1.0))
            p.drawPolyline(QPolygonF(pts))

    def _desenhar_fios(self, p):
        """Na carga: um fio de energia ondulando de cada pata até a esfera."""
        t = self.agora - self.inicio_fase
        alfa = 90 + 140 * _suave(t / CARGA)
        for i, (px, py) in enumerate(self.patas):
            pts = []
            for j in range(9):
                u = j / 8
                x, y = px + (self.ex - px) * u, py + (self.ey - py) * u
                onda = 4.0 * math.sin(u * math.pi) * math.sin(self.agora * 40.0 + j * 1.3 + i * 2.0)
                pts.append(QPointF(x, y + onda))
            p.setPen(QPen(_cor(CIANO, alfa * 0.5), 5.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawPolyline(QPolygonF(pts))
            p.setPen(QPen(_cor(BRANCO, alfa), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawPolyline(QPolygonF(pts))

    def _desenhar_feixe(self, p):
        """O feixe no sistema dele (x ao longo do feixe): brilho, corpo de borda ondulada, miolo e espirais."""
        w = self.largura()
        if w <= 0.3 or self.ponta <= 1.0:
            return
        L = self.ponta
        p.save()
        p.translate(self.ex, self.ey)
        p.rotate(math.degrees(math.atan2(self.dy, self.dx)))
        tt = self.agora
        # brilho de fora
        brilho = QLinearGradient(QPointF(0, -w * 2.2), QPointF(0, w * 2.2))
        brilho.setColorAt(0.0, _cor(AZUL, 0))
        brilho.setColorAt(0.5, _cor(CIANO, 110))
        brilho.setColorAt(1.0, _cor(AZUL, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brilho)
        p.drawRoundedRect(QRectF(-w, -w * 2.2, L + w, w * 4.4), w * 2.0, w * 2.0)
        # corpo: borda ondulando, correndo para a ponta
        passos = max(8, int(L / 14))
        cima, baixo = [], []
        for j in range(passos + 1):
            x = L * j / passos
            ab = min(1.0, x / (w * 1.5) + 0.55)                       # alarga saindo da esfera
            onda = 1.0 + 0.09 * math.sin(x * 0.045 - tt * 38.0) + 0.05 * math.sin(x * 0.12 + tt * 23.0)
            cima.append(QPointF(x, -w * ab * onda))
            baixo.append(QPointF(x, w * ab * (2.0 - onda)))
        corpo = QLinearGradient(QPointF(0, -w), QPointF(0, w))
        corpo.setColorAt(0.0, _cor(AZUL, 230))
        corpo.setColorAt(0.28, _cor(CIANO, 245))
        corpo.setColorAt(0.5, _cor(BRANCO, 255))
        corpo.setColorAt(0.72, _cor(CIANO, 245))
        corpo.setColorAt(1.0, _cor(AZUL, 230))
        p.setBrush(corpo)
        p.drawPolygon(QPolygonF(cima + baixo[::-1]))
        # miolo branco
        p.setBrush(_cor(BRANCO, 240))
        p.drawRoundedRect(QRectF(0, -w * 0.3, L, w * 0.6), w * 0.3, w * 0.3)
        # faixas de energia em espiral, girando
        for fase in (0.0, math.pi):
            pts = [QPointF(L * j / passos, w * 0.78 * math.sin(L * j / passos * 0.035 - tt * 30.0 + fase))
                   for j in range(passos + 1)]
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(_cor(GELO, 170), 1.8))
            p.drawPolyline(QPolygonF(pts))
        # ponta: a frente do feixe enquanto corre
        if self.ponta < self.comprimento:
            g = QRadialGradient(QPointF(L, 0), w * 1.6)
            g.setColorAt(0.0, _cor(BRANCO, 255))
            g.setColorAt(0.5, _cor(CIANO, 200))
            g.setColorAt(1.0, _cor(AZUL, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawEllipse(QPointF(L, 0), w * 1.6, w * 1.6)
        p.restore()

    def _desenhar_explosao(self, p):
        """Na ponta: a bola de fogo que arde (feixe) e estoura (fim), e as ondas de choque."""
        if self.ponta < self.comprimento:
            return
        fx, fy = self.fim()
        c = QPointF(fx, fy)
        t = self.agora - self.inicio_fase
        if self.fase == "feixe":
            r, forca = FOGO * (0.85 + 0.15 * math.sin(self.agora * 33.0)), 1.0
        else:
            u = _suave(t / DISSIPA)
            r, forca = FOGO * (1.0 + 1.1 * u), 1.0 - u
        pontas = []                                     # labaredas pontudas e irregulares, novas a cada quadro
        giro = self.acaso.uniform(0, math.tau)
        for j in range(32):
            a = giro + math.tau * j / 32
            d = r * (1.0 if j % 2 else self.acaso.uniform(1.3, 1.9))
            pontas.append(QPointF(fx + math.cos(a) * d, fy + math.sin(a) * d))
        chama = QRadialGradient(c, r * 1.9)
        chama.setColorAt(0.0, _cor(BRANCO, 240 * forca))
        chama.setColorAt(0.55, _cor(CIANO, 200 * forca))
        chama.setColorAt(1.0, _cor(AZUL, 60 * forca))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(chama)
        p.drawPolygon(QPolygonF(pontas))
        g = QRadialGradient(c, r * 1.6)
        g.setColorAt(0.0, _cor(BRANCO, 255 * forca))
        g.setColorAt(0.3, _cor(GELO, 235 * forca))
        g.setColorAt(0.6, _cor(CIANO, 160 * forca))
        g.setColorAt(1.0, _cor(AZUL, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(c, r * 1.6, r * 1.6)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for c0 in self.choques:
            u = (self.agora - c0) / 0.6
            raio = r * (0.6 + 2.0 * u)
            p.setPen(QPen(_cor(BRANCO, 220 * (1.0 - u)), 1.0 + 6.0 * (1.0 - u)))
            p.drawEllipse(c, raio, raio * 0.9)

    def _desenhar_particulas(self, p):
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, _vx, _vy, nasc, vida, cor in self.particulas:
            k = 1.0 - (self.agora - nasc) / vida
            p.setBrush(_cor(cor, 245 * k))
            r = 1.0 + 2.4 * k
            p.drawEllipse(QPointF(x, y), r, r)

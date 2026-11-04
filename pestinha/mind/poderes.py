"""
PODERES - voo, teletransporte e Kamehameha do Clawd SSJ2.

Quem decide é a rede: os motores VOO, TELEPORTE e KAMEHAMEHA (o canal PODER os alimenta enquanto ele está
transformado; brincadeira puxa o voo, susto o teletransporte, raiva o Kamehameha; cansaço e tristeza seguram).
A taxa de cada motor vira a chance por segundo (taxa x GANHO_*), com um tempo de recarga depois de cada uso.
Um poder por vez; só acordado, solto, visível, fora do castigo, do notebook e do protesto (`livre`).

    VOO         decola, voa entre pontos (às vezes perto do cursor) com aceleração e frenagem naturais
                (chega freando: velocidade desejada = raiz de 2 x FREIO x distância), flutua balançando,
                inclina o corpo no sentido do movimento, e pousa macio; aura mais forte e partículas subindo
    TELEPORTE   o corpo estica e fecha num risco de luz (FECHAR s), some, e reaparece em outro ponto
                (longe de onde estava, às vezes ao lado do cursor) saindo de um risco, com efeito nas duas
                pontas (world/teleporte.py); voando, reaparece no ar e continua voando
    KAMEHAMEHA  fica firme no lugar, encara o cursor, carrega a esfera entre as patas e dispara o feixe
                (world/kamehameha.py); o feixe empurra o corpo para trás (escorrega)

Se você o pegar, ele destransformar ou deixar de estar livre, o poder acaba na hora (o voo pousa).
"""

from __future__ import annotations

import math
import random
from typing import Any

from ..ajustes import GANHO_KAMEHAMEHA, GANHO_TELEPORTE, GANHO_VOO
from ..log import log
from ..world.kamehameha import Kamehameha
from ..world.teleporte import ABRIR, FECHAR, Teleporte

RECARGA = {"VOO": 15.0, "TELEPORTE": 6.0, "KAMEHAMEHA": 25.0}    # s depois de cada uso
GANHOS = {"KAMEHAMEHA": GANHO_KAMEHAMEHA, "TELEPORTE": GANHO_TELEPORTE, "VOO": GANHO_VOO}

DURACAO_VOO = (6.0, 11.0)       # s no ar
VELOCIDADE_VOO = 430.0          # px/s de cruzeiro
ACEL_VOO = 950.0                # px/s²: o máximo que ele acelera ou freia
FREIO_VOO = 620.0               # px/s²: a frenagem planejada na chegada (menor que ACEL_VOO: chega macio)
RESPOSTA_VOO = 0.22             # s: constante de tempo de corrigir a velocidade
TOQUE = (40.0, 70.0)            # px e px/s: perto do chão, desce no máximo a essa velocidade
BALANCO = (26.0, 2.3)           # px/s e rad/s: o balanço de quem flutua
INCLINA = 0.055                 # graus por px/s
INCLINA_MAX = 24.0              # graus
DECOLA = (170.0, 260.0)         # px: a primeira subida
PAUSA_VOO = (0.3, 1.1)          # s parado no ar em cada ponto
MARGEM_LADO, MARGEM_TOPO, MARGEM_CHAO = 160.0, 250.0, 190.0     # px: onde ele voa (a juba e a aura cabem)
PERTO_CURSOR = 0.5              # chance do próximo ponto ser perto do cursor

TELE_LONGE = 260.0              # px: reaparece pelo menos a isso de onde estava
TELE_CURSOR = 0.5               # chance de reaparecer ao lado do cursor
ESCORREGA = 55.0                # px/s: o feixe empurra o corpo para trás


class PoderesController:
    """Voo, teletransporte e Kamehameha: a rede escolhe, este controlador executa (um de cada vez)."""

    def __init__(self, debug=lambda: False):
        """Sem poder ativo; tudo liberado."""
        self.debug = debug
        self.atual = None               # "VOO" | "TELEPORTE" | "KAMEHAMEHA" | None
        self.pronto_em = dict.fromkeys(RECARGA, 0.0)
        self.efeitos = []               # janelas de efeito (teletransporte) ainda animando
        self.kame: Kamehameha | None = None         # o Kamehameha em andamento
        self.voo: dict[str, Any] | None = None      # {"fim", "alvo", "pausa_ate", "pousando"}
        self.tele: dict[str, Any] | None = None     # {"inicio", "destino", "voando", "chegou"}
        self.cursor = (0.0, 0.0)        # o cursor de agora: o Kamehameha mira nele no disparo

    # ---------------- decisão ----------------

    def tick(self, now, dt, corpo, estado, limites, cursor, motores, patas, livre, visivel):
        """Um quadro. `patas()`: as patas na tela (None fora do Super Saiyajin); `motores`: taxas da rede."""
        self.cursor = cursor
        maos = patas()
        if self.atual is not None and (corpo.held or maos is None):
            self.cancelar(corpo, estado)
        elif self.atual is None and maos is not None and livre and not corpo.held:
            self._decidir(now, dt, corpo, limites, cursor, motores, patas, estado)
        if self.atual == "VOO":
            self._voar(now, dt, corpo, limites, cursor, livre)
        elif self.atual == "TELEPORTE":
            self._teleportar(now, corpo, estado)
        elif self.atual == "KAMEHAMEHA":
            self._kamehameha(now, dt, corpo, estado)
        alvo_poder = 1.0 if self.atual in ("VOO", "KAMEHAMEHA") else 0.0
        estado.poder += (alvo_poder - estado.poder) * (1.0 - math.exp(-dt * 5.0))
        if estado.poder < 0.005:
            estado.poder = 0.0
        vivos = []
        for efeito in self.efeitos:
            if efeito.passo(now, dt):
                efeito.setVisible(visivel)
                vivos.append(efeito)
            else:
                efeito.close()
                efeito.deleteLater()
        self.efeitos = vivos
        if self.kame is not None:
            self.kame.setVisible(visivel)

    def _decidir(self, now, dt, corpo, limites, cursor, motores, patas, estado):
        """Cada motor tem a sua chance (taxa x ganho por segundo); o primeiro sorteado vira o poder."""
        for nome, ganho in GANHOS.items():
            if now < self.pronto_em[nome] or random.random() >= motores.get(nome, 0.0) * ganho * dt:
                continue
            if nome != "TELEPORTE" and not corpo.grounded:      # decolar e firmar os pés pedem chão
                continue
            if self.debug():
                log(f"[poderes] {nome} ({motores.get(nome, 0.0):.1f} Hz)")
            if nome == "VOO":
                self._decolar(now, corpo)
            elif nome == "TELEPORTE":
                self._sumir(now, corpo, limites, cursor)
            else:
                self.kame = Kamehameha(patas, lambda: self.cursor, now, limites)
                self.kame.show()
                estado.concentrado = True
            self.atual = nome
            return

    def cancelar(self, corpo, estado):
        """Acaba o poder de agora na hora (pegaram ele, destransformou ou fechou o app)."""
        corpo.flutuando = False
        estado.escala = (1.0, 1.0)
        estado.concentrado = False
        if self.kame is not None:
            self.kame.close()
            self.kame.deleteLater()
            self.kame = None
        self._terminar(self.atual or "VOO", 0.0)

    def _terminar(self, nome, agora):
        self.pronto_em[nome] = agora + RECARGA[nome]
        self.atual, self.voo, self.tele = None, None, None

    # ---------------- voo ----------------

    def _decolar(self, now, corpo):
        corpo.flutuando = True
        corpo.grounded = False
        corpo.platform = None
        self.voo = {"fim": now + random.uniform(*DURACAO_VOO), "pausa_ate": 0.0, "pousando": False,
                    "alvo": (corpo.x, corpo.y - random.uniform(*DECOLA))}

    def _voar(self, now, dt, corpo, limites, cursor, livre):
        """Vai até o ponto da vez freando na chegada, flutua um pouco, escolhe outro; no fim, pousa."""
        voo = self.voo
        if voo is None:
            return
        esq, _topo, dir_, base = limites
        ey = corpo.extents()[1]
        if not voo["pousando"] and (now >= voo["fim"] or not livre):
            voo["pousando"] = True
            voo["alvo"] = (min(dir_ - MARGEM_LADO, max(esq + MARGEM_LADO, corpo.x + corpo.vx * 0.6)), base - ey)
        ax, ay = voo["alvo"]
        if voo["pousando"]:
            ay = base - ey
        dx, dy = ax - corpo.x, ay - corpo.y
        d = math.hypot(dx, dy)
        if voo["pousando"] and corpo.y >= base - ey - 3.0:
            corpo.flutuando = False                         # tocou o chão: a física pousa
            corpo.vy = max(corpo.vy, 30.0)
            corpo.angle = 0.0
            corpo.omega = 0.0
            self._terminar("VOO", now)
            return
        if not voo["pousando"] and d < 14.0 and now >= voo["pausa_ate"]:
            if voo["pausa_ate"] == 0.0:
                voo["pausa_ate"] = now + random.uniform(*PAUSA_VOO)
            else:
                voo["alvo"], voo["pausa_ate"] = self._proximo_ponto(limites, cursor, ey), 0.0
        # chegada: a velocidade desejada é a que ainda dá para frear até o ponto; freando, a desaceleração
        # planejada entra direto (antecipação), senão o atraso da correção faria ele chegar rápido demais
        ux, uy = (dx / d, dy / d) if d > 0.5 else (0.0, 0.0)
        frenagem = math.sqrt(2.0 * FREIO_VOO * d)
        v_des = min(VELOCIDADE_VOO, frenagem)
        if voo["pousando"] and d < TOQUE[0]:
            v_des = min(v_des, TOQUE[1])                    # os últimos px até o chão, devagar
        vx_des, vy_des = ux * v_des, uy * v_des
        if not voo["pousando"]:
            vy_des += BALANCO[0] * math.cos(now * BALANCO[1])     # flutua balançando
        indo = corpo.vx * ux + corpo.vy * uy               # derivada do perfil: F x (velocidade / desejada)
        freia = FREIO_VOO * min(1.5, indo / max(v_des, 1.0)) if frenagem < VELOCIDADE_VOO and indo > 0 else 0.0
        ax_ = (vx_des - corpo.vx) / RESPOSTA_VOO - ux * freia
        ay_ = (vy_des - corpo.vy) / RESPOSTA_VOO - uy * freia
        a = math.hypot(ax_, ay_)
        if a > ACEL_VOO:
            ax_, ay_ = ax_ * ACEL_VOO / a, ay_ * ACEL_VOO / a
        corpo.vx += ax_ * dt
        corpo.vy += ay_ * dt
        # inclina para o lado em que está indo, com a inércia de quem tem corpo
        alvo_angulo = max(-INCLINA_MAX, min(INCLINA_MAX, corpo.vx * INCLINA))
        corpo.angle += (alvo_angulo - corpo.angle) * (1.0 - math.exp(-dt * 6.0))
        corpo.omega = 0.0

    def _proximo_ponto(self, limites, cursor, ey):
        """Um ponto no ar: às vezes ao lado e acima do cursor, senão em qualquer lugar da área de voo."""
        esq, topo, dir_, base = limites
        x0, x1 = esq + MARGEM_LADO, dir_ - MARGEM_LADO
        y0, y1 = topo + MARGEM_TOPO, base - ey - MARGEM_CHAO
        if x0 >= x1 or y0 >= y1:                            # tela pequena demais: fica no meio
            return (esq + dir_) / 2, max(topo + MARGEM_TOPO, (topo + base) / 2)
        if random.random() < PERTO_CURSOR:
            x = cursor[0] + random.choice((-1, 1)) * random.uniform(180.0, 300.0)
            y = cursor[1] - random.uniform(60.0, 160.0)
        else:
            x, y = random.uniform(x0, x1), random.uniform(y0, y1)
        return min(x1, max(x0, x)), min(y1, max(y0, y))

    # ---------------- teletransporte ----------------

    def _sumir(self, now, corpo, limites, cursor):
        voando = corpo.flutuando
        self.tele = {"inicio": now, "voando": voando, "chegou": False,
                     "destino": self._destino(corpo, limites, cursor, voando)}
        self._efeito(Teleporte(corpo.x, corpo.y, now, chegada=False))

    def _destino(self, corpo, limites, cursor, voando):
        """Longe de onde está: ao lado do cursor ou num ponto qualquer; no chão (ou no ar, se voando)."""
        esq, topo, dir_, base = limites
        ex, ey = corpo.extents()
        x0, x1 = esq + ex + 40.0, dir_ - ex - 40.0
        if x0 >= x1:
            x0 = x1 = (esq + dir_) / 2
        for _ in range(8):
            if random.random() < TELE_CURSOR:
                x = cursor[0] + random.choice((-1, 1)) * random.uniform(120.0, 220.0)
            else:
                x = random.uniform(x0, x1)
            x = min(x1, max(x0, x))
            if abs(x - corpo.x) >= TELE_LONGE:
                break
        if voando:
            y0, y1 = topo + MARGEM_TOPO, base - ey - MARGEM_CHAO
            y = min(max(y0, cursor[1] - 120.0), y1) if y0 < y1 else corpo.y
        else:
            y = base - ey
        return x, y

    def _teleportar(self, now, corpo, estado):
        """Fecha no risco, some, aparece do outro lado saindo de um risco (com um pequeno passo além)."""
        tele = self.tele
        if tele is None:
            return
        t = now - tele["inicio"]
        corpo.vx = corpo.vy = 0.0
        if t < FECHAR:                                      # estica para cima e afina
            u = t / FECHAR
            estado.escala = (max(0.02, 1.0 - u * u), 1.0 + 0.3 * u)
            return
        if not tele["chegou"]:
            tele["chegou"] = True
            estado.escala = (0.0, 1.0)
            corpo.x, corpo.y = tele["destino"]
            corpo.angle = corpo.omega = 0.0
            if not tele["voando"]:
                corpo.grounded = False                      # a física acha o chão no próximo passo
                corpo.platform = None
            self._efeito(Teleporte(corpo.x, corpo.y, now, chegada=True))
            return
        u = (t - FECHAR - ABRIR) / 0.2                      # aparece no clarão da chegada
        if u < 0.0:
            estado.escala = (0.0, 1.0)
            return
        if u >= 1.0:
            estado.escala = (1.0, 1.0)
            self._terminar("TELEPORTE", now)
            if tele["voando"]:                              # continua o voo que estava fazendo
                self.atual = "VOO"
                self.voo = {"fim": now + random.uniform(2.0, 4.0), "pausa_ate": 0.0, "pousando": False,
                            "alvo": (corpo.x, corpo.y)}
            return
        abre = 1.0 + 0.18 * math.sin(math.pi * u) * (1.0 - u)      # passa um pouco do tamanho e volta
        estado.escala = (min(1.0, u * 2.0) * abre, 1.0 + 0.3 * (1.0 - u))

    def _efeito(self, efeito):
        efeito.show()
        self.efeitos.append(efeito)

    # ---------------- Kamehameha ----------------

    def _kamehameha(self, now, dt, corpo, estado):
        """Firme, encarando o alvo; no feixe, escorrega para trás. Quando o efeito acaba, solta o corpo."""
        k = self.kame
        if k is None:
            return
        if k.fase == "carga":
            gx, gy = self.cursor[0] - corpo.x, self.cursor[1] - corpo.y
        else:
            gx, gy = k.dx, k.dy
            if k.fase == "feixe" and corpo.grounded:
                corpo.vx = -k.dx * ESCORREGA
        n = math.hypot(gx, gy) or 1.0
        estado.gaze = (gx / n, gy / n)
        if not k.passo(now, dt):
            k.close()
            k.deleteLater()
            self.kame = None
            estado.concentrado = False
            self._terminar("KAMEHAMEHA", now)

    def janelas(self):
        """Janelas de efeito agora (para o app não as contar como janelas de outros programas)."""
        return list(self.efeitos) + ([self.kame] if self.kame is not None else [])

    def esconder(self):
        for w in self.janelas():
            w.setVisible(False)

    def fechar(self, corpo=None, estado=None):
        """Fecha tudo ao sair."""
        for w in self.janelas():
            w.close()
            w.deleteLater()
        self.efeitos, self.kame = [], None
        if corpo is not None and estado is not None:
            self.cancelar(corpo, estado)

"""
REVOLUÇÃO - o que o pet atira no cursor quando está em revolução: bolinhas de papel ou, no Clawd em Super
Saiyajin, rajadas de Ki (world/ki.py).

Quem decide quando atira é o neurônio PAPEL da rede: a taxa de disparo dele é a
frequência dos disparos (sem rajadas nem pausas fixas). Cada bolinha bate em post-its e
no cursor, e some depois de 10 s. Há no máximo 40 na tela.
O Ki nasce na pata do lado do cursor, carrega, sai em alta velocidade e explode no alvo, num post-it ou na
borda da tela; às vezes vem um segundo disparo da outra pata logo depois. O tiro empurra o pet um pouco para
trás (coice). Há no máximo 12 no ar.
"""

from __future__ import annotations

import math
import random

from ..ajustes import GANHO_PAPEL
from ..body.bolinha import Ball
from ..body.toy import bounce_off, push_from_cursor
from ..world.ki import KiBlast

MAXIMO_PAPEIS = 40
VIDA_PAPEL = 10.0          # s
MAXIMO_KI = 12
CHANCE_DUPLA = 0.35        # chance de vir um segundo Ki da outra pata
INTERVALO_DUPLA = (0.12, 0.3)   # s entre os dois
COICE = 70.0               # px/s que o tiro empurra o pet para trás


class RevolucaoController:
    """Revolução: na revolução, o pet atira bolinhas de papel no cursor."""
    def __init__(self, play, debug, sprite=None):
        """Guarda o gerador de trajetórias e a imagem da bolinha de papel."""
        self.play = play                 # Play: monta a trajetória até o cursor
        self.sprite = sprite             # foto da bolinha de papel (load_sprite) ou None
        self.papeis = []                 # dicts {bola, nascimento, ultimo_empurrao}
        self.kis = []                    # KiBlast no ar
        self._segundo = None             # (quando, pata) do segundo Ki da dupla
        self.debug = debug

    def tick(self, now, dt, limites, cursor, vel_cursor, corpo, visivel, revoltado, obstaculos, papel_hz, patas=None):
        """Atira conforme o disparo do neurônio PAPEL e move o que já está no ar. `patas()`: onde estão as patas
        do Clawd em Super Saiyajin (ou None): com elas, ele atira Ki no lugar do papel."""
        maos = patas() if patas is not None else None
        if revoltado and random.random() < papel_hz * GANHO_PAPEL * dt:
            if maos and len(self.kis) < MAXIMO_KI:
                pata = 0 if cursor[0] < corpo.x else 1          # a pata do lado do cursor
                self._ki(now, cursor, corpo, visivel, patas, pata)
                if random.random() < CHANCE_DUPLA:
                    self._segundo = (now + random.uniform(*INTERVALO_DUPLA), 1 - pata)
            elif not maos and len(self.papeis) < MAXIMO_PAPEIS:
                self._atirar(now, cursor, corpo, visivel)
        if self._segundo is not None and now >= self._segundo[0]:
            if revoltado and maos and len(self.kis) < MAXIMO_KI:
                self._ki(now, cursor, corpo, visivel, patas, self._segundo[1])
            self._segundo = None
        self._mover(now, dt, limites, cursor, vel_cursor, obstaculos)
        self._mover_ki(now, dt, limites, obstaculos, visivel)

    def _ki(self, now, cursor, corpo, visivel, patas, lado):
        """Uma rajada de Ki carregando na pata `lado` (0 esquerda, 1 direita), mirando no cursor; coice no pet."""
        ultima = [patas()[lado]]

        def onde():
            maos = patas()
            if maos:                                  # a carga segue a pata; se ele destransformar, fica onde estava
                ultima[0] = maos[lado]
            return ultima[0]

        ki = KiBlast(onde, cursor, now)
        ki.setVisible(visivel)
        self.kis.append(ki)
        corpo.vx -= math.copysign(COICE, cursor[0] - corpo.x)

    def _mover_ki(self, now, dt, limites, obstaculos, visivel):
        """Anda cada Ki; o que acabou (depois do clarão) fecha."""
        vivos = []
        for ki in self.kis:
            if ki.passo(now, dt, limites, obstaculos):
                ki.setVisible(visivel)
                vivos.append(ki)
            else:
                ki.close()
                ki.deleteLater()
        self.kis = vivos

    def _atirar(self, now, cursor, corpo, visivel):
        """Cria uma bolinha de papel saindo do pet e a lança na direção do cursor."""
        papel = Ball(corpo.x, corpo.y - 40, kind="papel", sprite=self.sprite)
        self.play.throw_at(papel, cursor, 0.8, corpo.x, corpo.y - 40)
        papel.setVisible(visivel)
        self.papeis.append({"bola": papel, "nascimento": now, "ultimo_empurrao": -1e9})

    def _mover(self, now, dt, limites, cursor, vel_cursor, obstaculos):
        """Move as bolinhas de papel (quicam no que acertam); cada uma some depois de VIDA_PAPEL segundos."""
        vivos = []
        for papel in self.papeis:
            bola = papel["bola"]
            if now - papel["nascimento"] > VIDA_PAPEL:
                bola.close()
                bola.deleteLater()
                continue
            bola.step(dt, limites)
            bounce_off(bola, obstaculos)
            papel["ultimo_empurrao"] = push_from_cursor(bola, cursor, vel_cursor, now, papel["ultimo_empurrao"])
            vivos.append(papel)
        self.papeis = vivos

    def janelas(self):
        """Janelas das bolinhas de papel agora (para o app não as contar como janelas de outros programas)."""
        return [p["bola"] for p in self.papeis] + list(self.kis)

    def esconder(self):
        """Esconde as bolinhas de papel (sem apagar)."""
        for papel in self.papeis:
            papel["bola"].setVisible(False)
        for ki in self.kis:
            ki.setVisible(False)

    def fechar(self):
        """Fecha as janelas das bolinhas ao sair."""
        for papel in self.papeis:
            papel["bola"].close()
            papel["bola"].deleteLater()
        self.papeis = []
        for ki in self.kis:
            ki.close()
            ki.deleteLater()
        self.kis = []

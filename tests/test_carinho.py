"""Carinho: olhinhos fechados de felicidade enquanto ele recebe carinho, e voltam ao normal depois."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pestinha.body.pet_state import PetState


def test_feliz_fechado_aparece_depois_do_carinho_e_some():
    st = PetState()
    st.mark_caress(now=100.0)
    assert st.feliz_fechado(now=100.5) is True
    assert st.feliz_fechado(now=200.0) is False


def test_feliz_dura_mais_que_o_carinho():
    st = PetState()
    st.mark_caress(now=100.0)
    assert st.caressing(now=101.0) is False
    assert st.feliz_fechado(now=101.0) is True

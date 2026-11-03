"""Funções matemáticas pequenas, sem dependências. Usadas por módulos puros e de sensores."""

import math


def valor_real(valor, minimo=float("-inf"), maximo=float("inf")):
    """Converte para float e rejeita NaN, infinito ou fora do intervalo (levanta ValueError)."""
    x = float(valor)
    if not math.isfinite(x) or not minimo <= x <= maximo:
        raise ValueError(f"valor fora do domínio: {valor!r}")
    return x


def clamp(x, lo=0.0, hi=1.0):
    """Limita `x` ao intervalo [lo, hi]. NaN vira `lo` (um NaN nunca entra no estado do pet)."""
    if math.isnan(x):
        return lo
    return max(lo, min(x, hi))

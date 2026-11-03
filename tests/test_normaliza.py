from datetime import date
from decimal import Decimal

import pytest

from cub_sp.normaliza import chave, mes_referencia, numero_br


@pytest.mark.parametrize("texto, esperado", [
    ("Custo unitário básico no Estado de São Paulo*, outubro de 2026 em R$/m²", date(2026, 10, 1)),
    ("boletim-economico-marco-2026-sem-desoneracao.pdf", date(2026, 3, 1)),
    ("Boletim Econômico Março/2026", date(2026, 3, 1)),
    ("CUB out/26", date(2026, 10, 1)),
    ("uploads/2026/02/boletim_fevereiro_2026.pdf", date(2026, 2, 1)),
    ("boletim 2026-05 sem desoneração", date(2026, 5, 1)),
    ("cartilha do cub", None),
])
def test_mes_referencia(texto, esperado):
    assert mes_referencia(texto) == esperado


def test_numero_br():
    assert numero_br("2.199,84") == Decimal("2199.84")
    assert numero_br("-0,49") == Decimal("-0.49")
    assert numero_br("0,33%") == Decimal("0.33")
    with pytest.raises(ValueError):
        numero_br("abc")


def test_chave():
    assert chave("  Padrão   NORMAL ") == "padrao normal"

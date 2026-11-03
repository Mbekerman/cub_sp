from datetime import date
from decimal import Decimal

import pytest

from cub_sp.quadro import COMBINACOES, QuadroNaoEncontrado, extrair_quadro
from tests.conftest import OUTUBRO_2026, pdf_boletim


def test_le_os_onze_valores_de_outubro(pdf_outubro):
    quadro = extrair_quadro(pdf_outubro)
    assert quadro.referencia == date(2026, 10, 1)
    assert quadro.pagina == 2
    assert {(v.padrao, v.tipo) for v in quadro.valores} == set(COMBINACOES)
    por_chave = {(v.padrao, v.tipo): v for v in quadro.valores}
    assert por_chave[("baixo", "R-1")].custo_m2 == Decimal("2199.84")
    assert por_chave[("baixo", "R-1")].variacao_mes == Decimal("0.29")
    assert por_chave[("baixo", "PIS")].custo_m2 == Decimal("1528.83")
    assert por_chave[("normal", "R-16")].custo_m2 == Decimal("2183.36")
    assert por_chave[("normal", "R-16")].variacao_mes == Decimal("0.35")
    assert por_chave[("alto", "R-16")].custo_m2 == Decimal("2854.95")
    assert por_chave[("alto", "R-8")].variacao_mes == Decimal("0.30")


def test_ordem_dos_valores_e_estavel(pdf_outubro):
    quadro = extrair_quadro(pdf_outubro)
    assert [(v.padrao, v.tipo) for v in quadro.valores] == [
        ("baixo", "R-1"), ("baixo", "PP-4"), ("baixo", "R-8"), ("baixo", "PIS"),
        ("normal", "R-1"), ("normal", "PP-4"), ("normal", "R-8"), ("normal", "R-16"),
        ("alto", "R-1"), ("alto", "R-8"), ("alto", "R-16"),
    ]


def test_variacao_negativa_e_titulo_sem_asterisco():
    dados = {k: list(v) for k, v in OUTUBRO_2026.items()}
    dados["alto"][0] = ("R-1", "3.250,10", "-0,49")
    quadro = extrair_quadro(pdf_boletim("Custo unitário básico no Estado de São Paulo, novembro de 2026 em R$/m²", dados))
    assert quadro.referencia == date(2026, 11, 1)
    alto_r1 = next(v for v in quadro.valores if (v.padrao, v.tipo) == ("alto", "R-1"))
    assert alto_r1.variacao_mes == Decimal("-0.49")


def test_quadro_incompleto_e_erro():
    dados = {k: list(v) for k, v in OUTUBRO_2026.items()}
    dados["normal"] = dados["normal"][:3]
    with pytest.raises(QuadroNaoEncontrado, match="faltam.*normal.*R-16"):
        extrair_quadro(pdf_boletim(dados=dados))


def test_pdf_sem_quadro_e_erro():
    from reportlab.pdfgen import canvas
    import io

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(40, 700, "Boletim sem o quadro do CUB")
    c.save()
    with pytest.raises(QuadroNaoEncontrado, match="nenhuma página"):
        extrair_quadro(buffer.getvalue())

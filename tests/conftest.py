"""Gera um PDF parecido com o quadro do boletim do Sinduscon-SP, para testar a leitura sem rede."""

from __future__ import annotations

import io

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# Valores do boletim de outubro de 2026 (quadro "Custo unitário básico no Estado de São Paulo").
OUTUBRO_2026 = {
    "baixo": [("R-1", "2.199,84", "0,29"), ("PP-4", "2.056,26", "0,36"), ("R-8", "1.957,98", "0,36"), ("PIS", "1.528,83", "0,33")],
    "normal": [("R-1", "2.697,79", "0,28"), ("PP-4", "2.562,21", "0,33"), ("R-8", "2.245,68", "0,32"), ("R-16", "2.183,36", "0,35")],
    "alto": [("R-1", "3.265,97", "0,31"), ("R-8", "2.635,67", "0,30"), ("R-16", "2.854,95", "0,34")],
}


def desenhar_quadro(c: canvas.Canvas, y_topo: float, titulo: str, dados=OUTUBRO_2026) -> None:
    largura, _ = A4
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y_topo, titulo)
    colunas = {"baixo": 40, "normal": 230, "alto": 420}
    rotulos = {"baixo": "Padrão Baixo", "normal": "Padrão Normal", "alto": "Padrão Alto"}
    y = y_topo - 22
    for padrao, x in colunas.items():
        c.drawString(x + 40, y, rotulos[padrao])
    y -= 14
    c.setFont("Helvetica", 9)
    for padrao, x in colunas.items():
        c.drawString(x + 50, y, "Custo m²")
        c.drawString(x + 110, y, "% mês")
    for i in range(4):
        y -= 14
        for padrao, x in colunas.items():
            if i >= len(dados[padrao]):
                continue
            tipo, custo, pct = dados[padrao][i]
            c.drawString(x, y, tipo)
            c.drawRightString(x + 95, y, custo)
            c.drawRightString(x + 140, y, pct)
    y -= 18
    c.setFont("Helvetica", 7)
    c.drawString(40, y, "(*) Conforme Lei 4.591 de 16 de dezembro de 1964 e disposto na NBR 12.721 da ABNT.")


def pdf_boletim(titulo="Custo unitário básico no Estado de São Paulo*, outubro de 2026 em R$/m²", dados=OUTUBRO_2026) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica", 11)
    c.drawString(40, 800, "Boletim Econômico - Sinduscon-SP")
    c.drawString(40, 780, "Página de capa, sem o quadro.")
    c.showPage()
    c.setFont("Helvetica", 11)
    c.drawString(40, 800, "Outros indicadores do mês")
    c.drawString(40, 780, "INCC, IGP-M e tabela de insumos ficam aqui, antes do quadro.")
    desenhar_quadro(c, 640, titulo, dados)
    c.showPage()
    c.save()
    return buffer.getvalue()


@pytest.fixture
def pdf_outubro() -> bytes:
    return pdf_boletim()

"""Lê, do PDF do boletim, o quadro "Custo unitário básico no Estado de São Paulo".

O quadro tem três blocos lado a lado (Padrão Baixo, Normal e Alto), cada um com as colunas
tipo, custo por m² e variação do mês. A leitura é posicional: cada palavra do PDF é atribuída
ao bloco cujo título está mais perto no eixo x, e as linhas são agrupadas pela coordenada y.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pdfplumber

from .normaliza import chave, mes_referencia, numero_br

PADROES = ("baixo", "normal", "alto")
TIPOS = ("R-1", "PP-4", "R-8", "R-16", "PIS")
COMBINACOES: frozenset[tuple[str, str]] = frozenset({
    ("baixo", "R-1"), ("baixo", "PP-4"), ("baixo", "R-8"), ("baixo", "PIS"),
    ("normal", "R-1"), ("normal", "PP-4"), ("normal", "R-8"), ("normal", "R-16"),
    ("alto", "R-1"), ("alto", "R-8"), ("alto", "R-16"),
})

_RE_TITULO = re.compile(r"custo unitario basico no estado de sao paulo")
_RE_CUSTO = re.compile(r"^\d{1,3}(\.\d{3})+,\d{2}$|^\d{3,6},\d{2}$")
_RE_PCT = re.compile(r"^-?\d{1,3},\d{2}%?$")
_RE_TIPO = re.compile(r"^(R-1|PP-4|R-8|R-16|PIS)$", re.IGNORECASE)
_TOLERANCIA_LINHA = 3.0


class QuadroNaoEncontrado(Exception):
    """O PDF não tem o quadro, ou ele não pôde ser lido por inteiro."""


@dataclass(frozen=True)
class Valor:
    referencia: date
    padrao: str
    tipo: str
    custo_m2: Decimal
    variacao_mes: Decimal


@dataclass(frozen=True)
class Quadro:
    referencia: date
    valores: tuple[Valor, ...]
    pagina: int


def extrair_quadro(pdf: bytes | str) -> Quadro:
    """Procura o quadro página a página e devolve os 11 valores do mês."""
    origem = io.BytesIO(pdf) if isinstance(pdf, bytes) else pdf
    erros: list[str] = []
    with pdfplumber.open(origem) as doc:
        for numero, pagina in enumerate(doc.pages, start=1):
            texto = pagina.extract_text() or ""
            if not _RE_TITULO.search(chave(texto)):
                continue
            palavras = pagina.extract_words(x_tolerance=1.5, y_tolerance=2, keep_blank_chars=False)
            try:
                return quadro_das_palavras(palavras, numero)
            except QuadroNaoEncontrado as exc:
                erros.append(f"página {numero}: {exc}")
    detalhe = "; ".join(erros) if erros else "nenhuma página tem o título do quadro"
    raise QuadroNaoEncontrado(detalhe)


def _linhas(palavras: list[dict]) -> list[list[dict]]:
    """Agrupa palavras em linhas pela coordenada vertical e ordena cada linha da esquerda para a direita."""
    ordenadas = sorted(palavras, key=lambda p: (p["top"], p["x0"]))
    linhas: list[list[dict]] = []
    for p in ordenadas:
        if linhas and abs(p["top"] - linhas[-1][0]["top"]) <= _TOLERANCIA_LINHA:
            linhas[-1].append(p)
        else:
            linhas.append([p])
    for linha in linhas:
        linha.sort(key=lambda p: p["x0"])
    return linhas


def _centro(p: dict) -> float:
    return (p["x0"] + p["x1"]) / 2


def quadro_das_palavras(palavras: list[dict], pagina: int = 0) -> Quadro:
    """Monta o quadro a partir das palavras (dicts de pdfplumber: text, x0, x1, top)."""
    linhas = _linhas(palavras)

    indice_titulo = referencia = None
    for i, linha in enumerate(linhas):
        texto = " ".join(p["text"] for p in linha)
        if _RE_TITULO.search(chave(texto)):
            indice_titulo = i
            referencia = mes_referencia(texto) or (
                mes_referencia(" ".join(p["text"] for p in linhas[i + 1])) if i + 1 < len(linhas) else None
            )
            break
    if indice_titulo is None:
        raise QuadroNaoEncontrado("título do quadro não está nas palavras da página")
    if referencia is None:
        raise QuadroNaoEncontrado("título do quadro sem mês e ano reconhecíveis")

    colunas: dict[str, float] = {}
    indice_cabecalho = None
    for i in range(indice_titulo + 1, min(indice_titulo + 6, len(linhas))):
        achados = {chave(p["text"]): _centro(p) for p in linhas[i] if chave(p["text"]) in PADROES}
        if len(achados) == 3:
            colunas, indice_cabecalho = achados, i
            break
    if indice_cabecalho is None:
        raise QuadroNaoEncontrado("cabeçalho 'Padrão Baixo / Normal / Alto' não encontrado abaixo do título")

    valores: dict[tuple[str, str], Valor] = {}
    for linha in linhas[indice_cabecalho + 1:]:
        texto = chave(" ".join(p["text"] for p in linha))
        if texto.startswith("(*)") or "conforme lei" in texto:
            break
        por_coluna: dict[str, list[str]] = {padrao: [] for padrao in PADROES}
        for p in linha:
            padrao = min(colunas, key=lambda k: abs(colunas[k] - _centro(p)))
            por_coluna[padrao].append(p["text"])
        for padrao, tokens in por_coluna.items():
            valor = _valor_da_celula(referencia, padrao, tokens)
            if valor is not None:
                valores.setdefault((padrao, valor.tipo), valor)
        if len(valores) == len(COMBINACOES):
            break

    faltam = COMBINACOES - set(valores)
    sobram = set(valores) - COMBINACOES
    if faltam or sobram:
        raise QuadroNaoEncontrado(
            f"quadro incompleto: faltam {sorted(faltam)}, inesperados {sorted(sobram)}"
        )
    ordem = {c: n for n, c in enumerate(sorted(COMBINACOES, key=lambda c: (PADROES.index(c[0]), TIPOS.index(c[1]))))}
    return Quadro(referencia, tuple(sorted(valores.values(), key=lambda v: ordem[(v.padrao, v.tipo)])), pagina)


def _valor_da_celula(referencia: date, padrao: str, tokens: list[str]) -> Valor | None:
    """Reconhece a sequência tipo, custo, variação dentro de um bloco. Ignora o que não tiver esse formato."""
    tipo = custo = pct = None
    for t in tokens:
        if tipo is None and _RE_TIPO.match(t):
            tipo = t.upper()
        elif tipo is not None and custo is None and _RE_CUSTO.match(t):
            custo = numero_br(t)
        elif custo is not None and pct is None and _RE_PCT.match(t):
            pct = numero_br(t)
    if tipo is None or custo is None or pct is None:
        return None
    return Valor(referencia, padrao, tipo, custo, pct)

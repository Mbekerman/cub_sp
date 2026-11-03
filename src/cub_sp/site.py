"""Localiza, na página do Sinduscon-SP, o PDF do boletim econômico "sem desoneração" de cada mês."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from urllib.parse import unquote, urljoin

import requests
from bs4 import BeautifulSoup, Tag

from .normaliza import chave, mes_referencia

URL_CUB = "https://sindusconsp.com.br/servicos/cub/"
CABECALHOS = {"User-Agent": "Mozilla/5.0 (compatible; cub-sp-monitor/0.1; +https://github.com/Mbekerman/cub_sp)"}
TEMPO_LIMITE = 60

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Boletim:
    referencia: date
    url: str
    texto: str


def baixar_pagina(url: str = URL_CUB) -> str:
    resposta = requests.get(url, headers=CABECALHOS, timeout=TEMPO_LIMITE)
    resposta.raise_for_status()
    return resposta.text


def _contexto(a: Tag, niveis: int = 2) -> str:
    """Texto do link mais o dos elementos em volta (li, tr, p...), onde costuma estar o mês ou o 'sem desoneração'."""
    partes = [a.get_text(" ", strip=True), unquote(a.get("href", ""))]
    pai = a.parent
    for _ in range(niveis):
        if not isinstance(pai, Tag):
            break
        partes.append(pai.get_text(" ", strip=True))
        pai = pai.parent
    return chave(" ".join(partes))


def listar_boletins(html: str, base: str = URL_CUB) -> list[Boletim]:
    """Todos os PDFs 'sem desoneração' com mês identificável, do mais recente ao mais antigo.

    Se a página não rotula nada como 'sem desoneração', cai para os PDFs com 'boletim' no contexto
    que não sejam 'com desoneração'. Um mês que apareça mais de uma vez fica com o primeiro link.
    """
    soup = BeautifulSoup(html, "html.parser")
    candidatos: list[tuple[str, str, str]] = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"].strip())
        if not href.split("?", 1)[0].lower().endswith(".pdf"):
            continue
        candidatos.append((href, a.get_text(" ", strip=True), _contexto(a)))

    sem = [c for c in candidatos if "sem desonera" in c[2]]
    if sem:
        escolhidos = sem
    else:
        escolhidos = [c for c in candidatos if "boletim" in c[2] and "com desonera" not in c[2]]
        if escolhidos:
            log.warning("nenhum link marcado 'sem desoneração'; usando %d PDFs com 'boletim' no contexto", len(escolhidos))

    por_mes: dict[date, Boletim] = {}
    for href, texto, contexto in escolhidos:
        ref = mes_referencia(contexto)
        if ref is None:
            log.debug("PDF sem mês identificável, ignorado: %s", href)
            continue
        por_mes.setdefault(ref, Boletim(ref, href, texto))
    return [por_mes[k] for k in sorted(por_mes, reverse=True)]


def baixar_pdf(url: str) -> bytes:
    resposta = requests.get(url, headers=CABECALHOS, timeout=TEMPO_LIMITE)
    resposta.raise_for_status()
    conteudo = resposta.content
    if not conteudo.startswith(b"%PDF"):
        raise ValueError(f"o conteúdo de {url} não é um PDF (começa com {conteudo[:8]!r})")
    return conteudo

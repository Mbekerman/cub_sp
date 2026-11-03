"""Localiza no site do Sinduscon-SP o PDF do boletim econômico "sem desoneração" de um mês.

A página de serviços do CUB monta a lista de arquivos por JavaScript (WordPress Download Manager),
mas cada arquivo tem uma página própria com endereço previsível:

    https://sindusconsp.com.br/download/boletim-economico-<mês>-<ano>-sem-desoneracao/

Essa página traz o link de download (`?wpdmdl=<id>...`). Um mês que ainda não saiu responde 404.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .normaliza import MESES

URL_CUB = "https://sindusconsp.com.br/servicos/cub/"
URL_PACOTE = "https://sindusconsp.com.br/download/boletim-economico-{mes}-{ano}-sem-desoneracao/"
CABECALHOS = {"User-Agent": "Mozilla/5.0 (compatible; cub-sp-monitor/0.1; +https://github.com/Mbekerman/cub_sp)"}
TEMPO_LIMITE = 60

log = logging.getLogger(__name__)

_NOME_MES = {numero: nome for nome, numero in MESES.items()}


@dataclass(frozen=True)
class Boletim:
    referencia: date
    url: str
    titulo: str


@dataclass(frozen=True)
class Pagina:
    status: int
    html: str


def baixar_pagina(url: str) -> Pagina:
    resposta = requests.get(url, headers=CABECALHOS, timeout=TEMPO_LIMITE)
    if resposta.status_code not in (200, 404):
        resposta.raise_for_status()
    return Pagina(resposta.status_code, resposta.text)


def url_pacote(referencia: date) -> str:
    return URL_PACOTE.format(mes=_NOME_MES[referencia.month], ano=referencia.year)


def boletim_da_pagina(referencia: date, html: str, base: str) -> Boletim | None:
    """Acha o link de download (`wpdmdl`) na página do pacote. None se a página não tem o link."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "wpdmdl=" in href:
            titulo = soup.title.get_text(" ", strip=True).split("|")[0].strip() if soup.title else ""
            return Boletim(referencia, urljoin(base, href), titulo)
    return None


def localizar_boletim(referencia: date, baixar: Callable[[str], Pagina] = baixar_pagina) -> Boletim | None:
    """Boletim do mês, ou None se o Sinduscon-SP ainda não publicou (404) ou a página veio sem link."""
    url = url_pacote(referencia)
    pagina = baixar(url)
    if pagina.status == 404:
        log.debug("%s ainda não publicado (%s)", referencia.strftime("%m/%Y"), url)
        return None
    boletim = boletim_da_pagina(referencia, pagina.html, url)
    if boletim is None:
        log.warning("página de %s existe mas não tem link de download: %s", referencia.strftime("%m/%Y"), url)
    return boletim


def meses(desde: date, ate: date) -> list[date]:
    """Dia 1 de cada mês de `desde` até `ate`, do mais recente ao mais antigo."""
    saida = []
    ano, mes = ate.year, ate.month
    while (ano, mes) >= (desde.year, desde.month):
        saida.append(date(ano, mes, 1))
        ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    return saida


def baixar_pdf(url: str) -> bytes:
    resposta = requests.get(url, headers=CABECALHOS, timeout=TEMPO_LIMITE * 2)
    resposta.raise_for_status()
    conteudo = resposta.content
    if not conteudo.startswith(b"%PDF"):
        raise ValueError(f"o conteúdo de {url} não é um PDF (começa com {conteudo[:8]!r})")
    return conteudo

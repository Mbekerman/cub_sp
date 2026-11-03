"""Funções de normalização de texto e número no formato brasileiro."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
_ABREV = {nome[:3]: n for nome, n in MESES.items()}

_RE_MES_ANO = re.compile(
    r"\b(" + "|".join(MESES) + r")\b[\s_\-/]*(?:de)?[\s_\-/]*(\d{4})\b"
)
_RE_ABREV_ANO = re.compile(r"\b(" + "|".join(_ABREV) + r")[\s_\-/.]*(\d{2,4})\b")
_RE_NUMERICO = re.compile(r"\b(\d{4})[\s_\-/](\d{1,2})\b|\b(\d{1,2})[\s_\-/](\d{4})\b")


def sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def chave(texto: str) -> str:
    """Minúsculas, sem acento e com espaços colapsados. Para comparação."""
    return re.sub(r"\s+", " ", sem_acento(texto).lower()).strip()


def numero_br(texto: str) -> Decimal:
    """'2.199,84' -> Decimal('2199.84'); '-0,29' -> Decimal('-0.29')."""
    limpo = texto.strip().replace("%", "").replace(".", "").replace(",", ".")
    try:
        return Decimal(limpo)
    except InvalidOperation as exc:
        raise ValueError(f"não é número brasileiro: {texto!r}") from exc


def mes_referencia(texto: str) -> date | None:
    """Acha 'outubro de 2026', 'out/26', 'outubro-2026', '2026-10' ou '10/2026' e devolve o dia 1 do mês."""
    t = chave(texto)
    if m := _RE_MES_ANO.search(t):
        return date(int(m.group(2)), MESES[m.group(1)], 1)
    if m := _RE_ABREV_ANO.search(t):
        ano = int(m.group(2))
        ano = ano + 2000 if ano < 100 else ano
        return date(ano, _ABREV[m.group(1)], 1)
    if m := _RE_NUMERICO.search(t):
        ano, mes = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        if 1 <= int(mes) <= 12:
            return date(int(ano), int(mes), 1)
    return None

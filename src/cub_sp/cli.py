"""Linha de comando: cub-sp listar | coletar."""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
from datetime import date
from pathlib import Path

from . import site
from .quadro import Quadro, QuadroNaoEncontrado, extrair_quadro

log = logging.getLogger("cub_sp")
MESES_INICIAIS = 12  # quantos meses buscar quando o banco está vazio


def _mes(texto: str) -> date:
    ano, mes = texto.split("-")
    return date(int(ano), int(mes), 1)


def _mes_atual() -> date:
    return date.today().replace(day=1)


def _meses_atras(referencia: date, n: int) -> date:
    ano, mes = referencia.year, referencia.month - n
    while mes <= 0:
        ano, mes = ano - 1, mes + 12
    return date(ano, mes, 1)


def _pasta_pdfs() -> Path:
    pasta = Path(os.environ.get("CUB_PASTA_PDFS", "dados"))
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _imprimir(quadro: Quadro, url: str) -> None:
    print(f"{quadro.referencia:%m/%Y}  página {quadro.pagina}  {url}")
    for v in quadro.valores:
        print(f"  {v.padrao:<7}{v.tipo:<6}{v.custo_m2:>10,.2f}  {v.variacao_mes:>6}%")


def cmd_listar(args: argparse.Namespace) -> int:
    desde = args.desde or _meses_atras(_mes_atual(), args.meses - 1)
    achados = 0
    for referencia in site.meses(desde, _mes_atual()):
        boletim = site.localizar_boletim(referencia)
        if boletim:
            achados += 1
            print(f"{referencia:%m/%Y}  {boletim.url}  [{boletim.titulo}]")
        else:
            print(f"{referencia:%m/%Y}  (não publicado)")
    return 0 if achados else 1


def cmd_coletar(args: argparse.Namespace) -> int:
    banco = None
    if not args.dry_run:
        from .banco import Banco

        banco = Banco()

    if args.arquivo:
        conteudo = Path(args.arquivo).read_bytes()
        quadro = extrair_quadro(conteudo)
        return _gravar(banco, quadro, f"file://{Path(args.arquivo).resolve()}", conteudo, args.dry_run)

    if args.url:
        alvos = [site.Boletim(args.mes or _mes_atual(), args.url, "url informada")]
    else:
        alvos = _alvos(args, banco)
        if not alvos:
            log.info("nada a fazer")
            return 0

    falhas = 0
    for b in alvos:
        log.info("baixando %s (%s)", b.referencia.strftime("%m/%Y"), b.url)
        try:
            conteudo = site.baixar_pdf(b.url)
            quadro = extrair_quadro(conteudo)
            if quadro.referencia != b.referencia:
                log.warning(
                    "a página anuncia %s mas o quadro do PDF é de %s; usando o mês do PDF",
                    b.referencia.strftime("%m/%Y"), quadro.referencia.strftime("%m/%Y"),
                )
            _gravar(banco, quadro, b.url, conteudo, args.dry_run)
        except (QuadroNaoEncontrado, OSError, ValueError) as exc:
            falhas += 1
            log.error("%s: %s", b.referencia.strftime("%m/%Y"), exc)
            if banco:
                banco.registrar_falha(b.referencia, b.url, str(exc))
    return 1 if falhas else 0


def _alvos(args: argparse.Namespace, banco) -> list[site.Boletim]:
    """Quais meses baixar: um mês pedido, ou os publicados entre `desde` e o mês atual que faltam no banco."""
    if args.mes:
        boletim = site.localizar_boletim(args.mes)
        if boletim is None:
            print(f"boletim de {args.mes:%m/%Y} não publicado", file=sys.stderr)
            return []
        return [boletim]

    gravados = banco.referencias_extraidas() if banco else set()
    if args.desde:
        desde = args.desde
    elif gravados:
        desde = max(gravados) if args.todos else _proximo_mes(max(gravados))
    else:
        desde = _meses_atras(_mes_atual(), MESES_INICIAIS - 1)

    alvos = []
    for referencia in site.meses(desde, _mes_atual()):
        if referencia in gravados and not args.todos:
            continue
        boletim = site.localizar_boletim(referencia)
        if boletim is None:
            log.info("%s ainda não publicado", referencia.strftime("%m/%Y"))
            continue
        alvos.append(boletim)
    return alvos


def _proximo_mes(referencia: date) -> date:
    return date(referencia.year + (referencia.month == 12), referencia.month % 12 + 1, 1)


def _gravar(banco, quadro: Quadro, url: str, conteudo: bytes, dry_run: bool) -> int:
    sha = hashlib.sha256(conteudo).hexdigest()
    caminho = _pasta_pdfs() / f"cub-sp-{quadro.referencia:%Y-%m}.pdf"
    caminho.write_bytes(conteudo)  # sempre o último baixado, para o arquivo bater com o sha256 gravado
    _imprimir(quadro, url)
    if dry_run:
        return 0
    boletim_id = banco.gravar(quadro, url, sha)
    log.info("gravado %s (%d valores, boletim %s)", quadro.referencia.strftime("%m/%Y"), len(quadro.valores), boletim_id)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cub-sp", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_listar = sub.add_parser("listar", help="mostra quais meses têm boletim 'sem desoneração' publicado")
    p_listar.add_argument("--desde", type=_mes, help="primeiro mês a verificar, AAAA-MM")
    p_listar.add_argument("--meses", type=int, default=MESES_INICIAIS, help="quantos meses para trás (padrão 12)")
    p_listar.set_defaults(func=cmd_listar)

    p_coletar = sub.add_parser("coletar", help="baixa os boletins que faltam, lê o quadro e grava no Supabase")
    p_coletar.add_argument("--mes", type=_mes, help="só este mês, AAAA-MM")
    p_coletar.add_argument("--desde", type=_mes, help="começa neste mês em vez de continuar de onde parou, AAAA-MM")
    p_coletar.add_argument("--todos", action="store_true", help="regrava também os meses já gravados")
    p_coletar.add_argument("--url", help="PDF direto, sem procurar a página do mês")
    p_coletar.add_argument("--arquivo", help="PDF local, sem rede")
    p_coletar.add_argument("--dry-run", action="store_true", help="só mostra os valores, não grava")
    p_coletar.set_defaults(func=cmd_coletar)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)

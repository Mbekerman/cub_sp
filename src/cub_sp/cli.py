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


def _mes(texto: str) -> date:
    ano, mes = texto.split("-")
    return date(int(ano), int(mes), 1)


def _pasta_pdfs() -> Path:
    pasta = Path(os.environ.get("CUB_PASTA_PDFS", "dados"))
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _imprimir(quadro: Quadro, url: str) -> None:
    print(f"{quadro.referencia:%m/%Y}  página {quadro.pagina}  {url}")
    for v in quadro.valores:
        print(f"  {v.padrao:<7}{v.tipo:<6}{v.custo_m2:>10,.2f}  {v.variacao_mes:>6}%")


def cmd_listar(args: argparse.Namespace) -> int:
    boletins = site.listar_boletins(site.baixar_pagina(args.pagina), args.pagina)
    if not boletins:
        print("nenhum boletim 'sem desoneração' encontrado na página", file=sys.stderr)
        return 1
    for b in boletins:
        print(f"{b.referencia:%m/%Y}  {b.url}  [{b.texto}]")
    return 0


def cmd_coletar(args: argparse.Namespace) -> int:
    banco = None
    if not args.dry_run:
        from .banco import Banco

        banco = Banco()

    if args.arquivo:
        quadro = extrair_quadro(Path(args.arquivo).read_bytes())
        conteudo = Path(args.arquivo).read_bytes()
        return _gravar(banco, quadro, f"file://{Path(args.arquivo).resolve()}", conteudo, args.dry_run)

    if args.url:
        alvos = [site.Boletim(args.mes or date.today().replace(day=1), args.url, "url informada")]
    else:
        alvos = site.listar_boletins(site.baixar_pagina(args.pagina), args.pagina)
        if args.mes:
            alvos = [b for b in alvos if b.referencia == args.mes]
            if not alvos:
                print(f"mês {args.mes:%m/%Y} não está na página", file=sys.stderr)
                return 1
        elif not args.todos:
            ja = banco.referencias_extraidas() if banco else set()
            alvos = [b for b in alvos if b.referencia not in ja]
            if not alvos:
                log.info("nada novo: todos os meses da página já estão gravados")
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


def _gravar(banco, quadro: Quadro, url: str, conteudo: bytes, dry_run: bool) -> int:
    sha = hashlib.sha256(conteudo).hexdigest()
    caminho = _pasta_pdfs() / f"cub-sp-{quadro.referencia:%Y-%m}.pdf"
    if not caminho.exists():
        caminho.write_bytes(conteudo)
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

    p_listar = sub.add_parser("listar", help="mostra os boletins 'sem desoneração' achados na página")
    p_listar.add_argument("--pagina", default=site.URL_CUB)
    p_listar.set_defaults(func=cmd_listar)

    p_coletar = sub.add_parser("coletar", help="baixa os boletins, lê o quadro e grava no Supabase")
    p_coletar.add_argument("--pagina", default=site.URL_CUB)
    p_coletar.add_argument("--mes", type=_mes, help="só este mês, no formato AAAA-MM")
    p_coletar.add_argument("--todos", action="store_true", help="regrava todos os meses da página")
    p_coletar.add_argument("--url", help="PDF direto, sem passar pela página")
    p_coletar.add_argument("--arquivo", help="PDF local, sem rede")
    p_coletar.add_argument("--dry-run", action="store_true", help="só mostra os valores, não grava")
    p_coletar.set_defaults(func=cmd_coletar)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)

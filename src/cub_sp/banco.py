"""Grava boletins e valores nas tabelas cub_boletins e cub_valores do Supabase."""

from __future__ import annotations

import os
from datetime import date

from supabase import Client, create_client

from .quadro import Quadro


class Banco:
    def __init__(self, url: str | None = None, chave: str | None = None) -> None:
        url = url or os.environ.get("SUPABASE_URL")
        chave = chave or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not chave:
            raise RuntimeError("defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY")
        self.cliente: Client = create_client(url, chave)

    def referencias_extraidas(self) -> set[date]:
        resposta = (
            self.cliente.table("cub_boletins").select("referencia").eq("situacao", "extraido").execute()
        )
        return {date.fromisoformat(linha["referencia"]) for linha in resposta.data}

    def gravar(self, quadro: Quadro, url: str, sha256: str) -> str:
        """Upsert do boletim e dos 11 valores. Rodar de novo o mesmo mês sobrescreve. Devolve o id do boletim."""
        boletim = {
            "referencia": quadro.referencia.isoformat(),
            "url": url,
            "sha256": sha256,
            "situacao": "extraido",
            "erro": None,
            "valores": len(quadro.valores),
        }
        resposta = self.cliente.table("cub_boletins").upsert(boletim, on_conflict="referencia").execute()
        boletim_id = resposta.data[0]["id"]
        linhas = [
            {
                "boletim_id": boletim_id,
                "referencia": v.referencia.isoformat(),
                "padrao": v.padrao,
                "tipo": v.tipo,
                "custo_m2": str(v.custo_m2),
                "variacao_mes": str(v.variacao_mes),
            }
            for v in quadro.valores
        ]
        self.cliente.table("cub_valores").upsert(linhas, on_conflict="referencia,padrao,tipo").execute()
        return boletim_id

    def registrar_falha(self, referencia: date, url: str, erro: str, sha256: str | None = None) -> None:
        """Marca o mês como 'falhou' sem apagar valores já gravados de uma rodada anterior."""
        existente = (
            self.cliente.table("cub_boletins").select("situacao").eq("referencia", referencia.isoformat()).execute()
        )
        if existente.data and existente.data[0]["situacao"] == "extraido":
            return
        boletim = {
            "referencia": referencia.isoformat(),
            "url": url,
            "sha256": sha256,
            "situacao": "falhou",
            "erro": erro[:2000],
        }
        self.cliente.table("cub_boletins").upsert(boletim, on_conflict="referencia").execute()

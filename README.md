# CUB-SP

Monitor do **CUB/m² do Estado de São Paulo**. Todo dia ele abre a página
[sindusconsp.com.br/servicos/cub](https://sindusconsp.com.br/servicos/cub/), baixa o PDF do
**Boletim Econômico sem desoneração** de cada mês que ainda não está gravado, lê o quadro
"Custo unitário básico no Estado de São Paulo" e grava os 11 valores no Supabase
(projeto BKM_Desenvolvimento_Imobiliario).

| Padrão | Tipos                  |
| ------ | ---------------------- |
| Baixo  | R-1, PP-4, R-8, PIS    |
| Normal | R-1, PP-4, R-8, R-16   |
| Alto   | R-1, R-8, R-16         |

Para cada um: custo por m² (R$) e variação do mês (%).

## Onde os dados ficam

- `cub_boletins`: um por mês, com a URL do PDF, o hash e a situação (`baixado`, `extraido`, `falhou`).
- `cub_valores`: 11 linhas por mês (`referencia`, `padrao`, `tipo`, `custo_m2`, `variacao_mes`).
- `cub_serie`: view com `variacao_calculada` sobre o mês anterior, para conferir o que o boletim publica.

O SQL está em `supabase/migrations/`. Leitura liberada para usuários autenticados; escrita só com a chave `service_role`.

## Rodar

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # preencha SUPABASE_SERVICE_ROLE_KEY
```

```bash
cub-sp listar                                   # mostra os boletins achados na página
cub-sp coletar --dry-run                        # lê o que falta, só imprime
cub-sp coletar                                  # grava os meses que ainda não estão no banco
cub-sp coletar --mes 2026-10                    # só um mês
cub-sp coletar --todos                          # regrava todos os meses da página
cub-sp coletar --url https://.../boletim.pdf    # PDF direto
cub-sp coletar --arquivo boletim.pdf --dry-run  # PDF local, sem rede
```

A CLI lê `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` do ambiente (ou de um `.env` carregado
pelo shell). Os PDFs baixados ficam em `CUB_PASTA_PDFS` (padrão `./dados`).

Rodar de novo o mesmo mês sobrescreve os valores; nada é apagado. Um mês que falhe na leitura
fica marcado como `falhou` com o erro, e volta a ser tentado na próxima rodada.

## Deploy no Railway

`railway.json` configura o serviço como **cron diário às 12:00 UTC (09:00 em Brasília)**, rodando
`cub-sp coletar` e encerrando. Variáveis necessárias no serviço: `SUPABASE_URL` e
`SUPABASE_SERVICE_ROLE_KEY`. O boletim costuma sair na primeira quinzena; nos dias em que não
há mês novo o comando termina sem gravar nada.

## Testes

```bash
pytest
```

Os testes geram um PDF sintético com o mesmo desenho do quadro do boletim (três blocos lado a
lado) e leem os valores de outubro de 2026. Eles não acessam a internet.

## Como a leitura do PDF funciona

`cub_sp/quadro.py` acha a página cujo texto tem o título do quadro, extrai as palavras com
posição (`pdfplumber`), localiza a linha "Padrão Baixo / Normal / Alto" e usa o centro de cada
título como âncora de coluna. Cada palavra das linhas seguintes vai para a coluna mais próxima;
dentro da coluna, a sequência `tipo, custo, variação` vira um valor. A leitura só é aceita se
as 11 combinações aparecerem, sem sobras.

Se o Sinduscon-SP mudar o desenho do quadro, o lugar de ajustar é esse arquivo. Se mudar a
página de listagem, é `cub_sp/site.py` (`cub-sp listar` mostra o que ele está achando).

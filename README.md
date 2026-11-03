# CUB-SP

Monitor do **CUB/m² do Estado de São Paulo**. Todo dia ele procura no site do Sinduscon-SP o
**Boletim Econômico sem desoneração** de cada mês que ainda não está gravado, baixa o PDF, lê o
quadro "Custo unitário básico no Estado de São Paulo" e grava os 11 valores no Supabase
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
cub-sp listar                                   # quais dos últimos 12 meses têm boletim publicado
cub-sp listar --desde 2025-06                   # idem, a partir de um mês
cub-sp coletar --dry-run                        # lê o que falta, só imprime
cub-sp coletar                                  # grava os meses que ainda não estão no banco
cub-sp coletar --mes 2026-10                    # só um mês
cub-sp coletar --desde 2025-06                  # carga inicial a partir de um mês
cub-sp coletar --desde 2025-06 --todos          # regrava também os já gravados
cub-sp coletar --url https://.../boletim.pdf    # PDF direto
cub-sp coletar --arquivo boletim.pdf --dry-run  # PDF local, sem rede
```

Sem `--mes` nem `--desde`, `coletar` continua do mês seguinte ao último gravado até o mês atual.
Com o banco vazio, busca os últimos 12 meses.

A CLI lê `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` do ambiente (ou de um `.env` carregado
pelo shell). Os PDFs baixados ficam em `CUB_PASTA_PDFS` (padrão `./dados`).

Rodar de novo o mesmo mês sobrescreve os valores; nada é apagado. Um mês que falhe na leitura
fica marcado como `falhou` com o erro, e volta a ser tentado na próxima rodada.

## Deploy no Google Cloud Run

O monitor roda como **Cloud Run Job** disparado todo dia pelo **Cloud Scheduler**. O script
`deploy/cloud-run.sh` faz tudo com o `gcloud`: habilita as APIs, cria o repositório de imagens,
a conta de serviço, constrói a imagem com o Cloud Build, cria ou atualiza o job e o agendamento.

1. Guarde a chave `service_role` do Supabase no Secret Manager, uma vez:

   ```bash
   printf '%s' 'sb_secret_...' | gcloud secrets create cub-sp-supabase-key --data-file=- --project SEU_PROJETO
   ```

2. Publique:

   ```bash
   PROJECT_ID=SEU_PROJETO ./deploy/cloud-run.sh
   ```

3. Rode uma vez à mão para conferir:

   ```bash
   gcloud run jobs execute cub-sp --region southamerica-east1 --wait
   ```

O agendamento padrão é 09:00 de São Paulo, todo dia. O boletim costuma sair na primeira quinzena;
nos dias sem mês novo o job termina em segundos sem gravar nada. Os PDFs ficam em `/tmp` dentro do
container e são descartados ao fim; o que importa está no banco.

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

O boletim tem outro quadro com título quase igual (o do padrão R8-N, que abre mão de obra e
material); o leitor testa cada título e fica com o que tem os três blocos abaixo. Validado nos
17 boletins de junho de 2025 a outubro de 2026.

## Como o boletim é achado no site

A página [sindusconsp.com.br/servicos/cub](https://sindusconsp.com.br/servicos/cub/) monta a
lista de arquivos por JavaScript (WordPress Download Manager) e o Cloudflare barra as chamadas
AJAX feitas fora do navegador. Mas cada arquivo tem página própria com endereço previsível:

```
https://sindusconsp.com.br/download/boletim-economico-<mês>-<ano>-sem-desoneracao/
```

Exemplo: `boletim-economico-outubro-2026-sem-desoneracao`. Essa página tem o link de download
(`?wpdmdl=<id>...`), e um mês ainda não publicado responde 404. `cub_sp/site.py` faz só isso.
Se o Sinduscon-SP mudar o padrão do endereço, é ali que se ajusta.

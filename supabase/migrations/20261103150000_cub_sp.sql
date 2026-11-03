-- Monitor do CUB/m² do Estado de São Paulo (Sinduscon-SP, boletim "sem desoneração").
-- Aplicada no projeto BKM_Desenvolvimento_Imobiliario em 2026-11-03 com o nome "cub_sp".

create table public.cub_boletins (
  id           uuid primary key default gen_random_uuid(),
  referencia   date not null unique check (extract(day from referencia) = 1),
  url          text not null check (btrim(url) <> ''),
  sha256       text check (sha256 is null or sha256 ~ '^[0-9a-f]{64}$'),
  baixado_em   timestamptz not null default now(),
  situacao     text not null default 'baixado' check (situacao in ('baixado', 'extraido', 'falhou')),
  erro         text,
  valores      integer not null default 0 check (valores >= 0)
);
comment on table public.cub_boletins is
  'Boletim econômico mensal do Sinduscon-SP (sem desoneração). Uma linha por mês de referência.';
comment on column public.cub_boletins.referencia is 'Primeiro dia do mês a que o CUB se refere.';
comment on column public.cub_boletins.sha256 is 'Hash do PDF baixado, para detectar republicação.';
comment on column public.cub_boletins.valores is 'Quantidade de valores extraídos do quadro (esperado: 11).';

create table public.cub_valores (
  id            uuid primary key default gen_random_uuid(),
  boletim_id    uuid not null references public.cub_boletins(id) on delete cascade,
  referencia    date not null check (extract(day from referencia) = 1),
  padrao        text not null check (padrao in ('baixo', 'normal', 'alto')),
  tipo          text not null check (tipo in ('R-1', 'PP-4', 'R-8', 'R-16', 'PIS')),
  custo_m2      numeric(12, 2) not null check (custo_m2 > 0),
  variacao_mes  numeric(8, 4) not null,
  extraido_em   timestamptz not null default now(),
  unique (referencia, padrao, tipo),
  constraint cub_valores_combinacao check (
    (padrao = 'baixo'  and tipo in ('R-1', 'PP-4', 'R-8', 'PIS')) or
    (padrao = 'normal' and tipo in ('R-1', 'PP-4', 'R-8', 'R-16')) or
    (padrao = 'alto'   and tipo in ('R-1', 'R-8', 'R-16'))
  )
);
comment on table public.cub_valores is
  'CUB/m² por padrão e tipo, lido do quadro "Custo unitário básico no Estado de São Paulo" do boletim. 11 linhas por mês.';
comment on column public.cub_valores.custo_m2 is 'Custo unitário básico em R$/m², sem desoneração.';
comment on column public.cub_valores.variacao_mes is 'Variação mensal publicada, em pontos percentuais (0,29 = 0,29%).';

create index cub_valores_serie on public.cub_valores (padrao, tipo, referencia);

-- Série com a variação recalculada a partir do mês anterior, para conferir o que o boletim publica.
create view public.cub_serie with (security_invoker = true) as
select
  v.referencia,
  v.padrao,
  v.tipo,
  v.custo_m2,
  v.variacao_mes,
  round(
    (v.custo_m2 / lag(v.custo_m2) over (partition by v.padrao, v.tipo order by v.referencia) - 1) * 100,
    2
  ) as variacao_calculada
from public.cub_valores v;
comment on view public.cub_serie is
  'Série do CUB/m² com variacao_calculada = variação sobre o mês anterior gravado. Difere de variacao_mes quando falta um mês ou houve republicação.';

alter table public.cub_boletins enable row level security;
alter table public.cub_valores  enable row level security;
create policy cub_leitura on public.cub_boletins for select to authenticated using (true);
create policy cub_leitura on public.cub_valores  for select to authenticated using (true);

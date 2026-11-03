-- O CUB é dado público do Sinduscon-SP; a página do histórico (web/index.html) lê com a chave publishable.
-- Aplicada no projeto BKM_Desenvolvimento_Imobiliario em 2026-11-03 com o nome "cub_leitura_publica".
create policy cub_leitura_publica on public.cub_boletins for select to anon using (true);
create policy cub_leitura_publica on public.cub_valores  for select to anon using (true);

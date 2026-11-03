from datetime import date

from cub_sp.site import listar_boletins

PAGINA = """
<html><body>
<h2>Boletins Econômicos</h2>
<ul>
  <li>Outubro/2026: <a href="/wp-content/uploads/2026/11/boletim-outubro-2026-sem-desoneracao.pdf">Sem Desoneração</a>
      | <a href="/wp-content/uploads/2026/11/boletim-outubro-2026-com-desoneracao.pdf">Com Desoneração</a></li>
  <li>Setembro/2026: <a href="https://cdn.sindusconsp.com.br/boletim-setembro-2026-sem-desoneracao.pdf?download=1">Sem Desoneração</a>
      | <a href="/uploads/boletim-setembro-2026-com-desoneracao.pdf">Com Desoneração</a></li>
  <li><a href="/uploads/cartilha-cub.pdf">Cartilha do CUB</a></li>
  <li><a href="/servicos/cub/historico/">Série histórica</a></li>
</ul>
</body></html>
"""


def test_lista_so_os_sem_desoneracao_do_mais_novo_ao_mais_velho():
    boletins = listar_boletins(PAGINA, "https://sindusconsp.com.br/servicos/cub/")
    assert [b.referencia for b in boletins] == [date(2026, 10, 1), date(2026, 9, 1)]
    assert boletins[0].url == "https://sindusconsp.com.br/wp-content/uploads/2026/11/boletim-outubro-2026-sem-desoneracao.pdf"
    assert boletins[1].url.startswith("https://cdn.sindusconsp.com.br/boletim-setembro-2026-sem-desoneracao.pdf")


def test_sem_rotulo_cai_para_boletins_que_nao_sao_com_desoneracao(caplog):
    pagina = """
    <table>
      <tr><td>Boletim Econômico outubro de 2026</td><td><a href="/b/out26.pdf">PDF</a></td></tr>
      <tr><td>Boletim Econômico setembro de 2026 (com desoneração)</td><td><a href="/b/set26-com.pdf">PDF</a></td></tr>
    </table>
    """
    boletins = listar_boletins(pagina, "https://sindusconsp.com.br/")
    assert [(b.referencia, b.url) for b in boletins] == [(date(2026, 10, 1), "https://sindusconsp.com.br/b/out26.pdf")]
    assert "nenhum link marcado" in caplog.text


def test_pagina_sem_pdf_devolve_lista_vazia():
    assert listar_boletins("<html><a href='/x.html'>nada</a></html>") == []

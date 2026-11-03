from datetime import date

from cub_sp.site import Pagina, boletim_da_pagina, localizar_boletim, meses, url_pacote

PAGINA_PACOTE = """
<html><head><title>Boletim Econômico - Outubro 2026 - Sem Desoneração | Sinduscon-SP</title></head>
<body>
<a class="wpdm-download-link btn btn-primary"
   href="https://sindusconsp.com.br/download/boletim-economico-outubro-2026-sem-desoneracao/?wpdmdl=155661&amp;ind=1793705838886&amp;refresh=50c28168&amp;filename=Boletim_Economico_Outubro.pdf">Download</a>
</body></html>
"""


def test_url_do_pacote_usa_nome_do_mes_sem_acento():
    assert url_pacote(date(2026, 3, 1)) == "https://sindusconsp.com.br/download/boletim-economico-marco-2026-sem-desoneracao/"
    assert url_pacote(date(2026, 10, 1)).endswith("boletim-economico-outubro-2026-sem-desoneracao/")


def test_acha_o_link_de_download_na_pagina_do_pacote():
    b = boletim_da_pagina(date(2026, 10, 1), PAGINA_PACOTE, "https://sindusconsp.com.br/download/x/")
    assert b is not None
    assert b.url.startswith("https://sindusconsp.com.br/download/boletim-economico-outubro-2026-sem-desoneracao/?wpdmdl=155661&ind=")
    assert b.titulo == "Boletim Econômico - Outubro 2026 - Sem Desoneração"


def test_localizar_devolve_none_em_404_e_em_pagina_sem_link():
    assert localizar_boletim(date(2026, 12, 1), lambda url: Pagina(404, "<html>Página não encontrada</html>")) is None
    assert localizar_boletim(date(2026, 12, 1), lambda url: Pagina(200, "<html><a href='/x.pdf'>x</a></html>")) is None


def test_localizar_usa_a_url_do_mes():
    pedidas = []

    def baixar(url):
        pedidas.append(url)
        return Pagina(200, PAGINA_PACOTE)

    b = localizar_boletim(date(2026, 10, 1), baixar)
    assert pedidas == ["https://sindusconsp.com.br/download/boletim-economico-outubro-2026-sem-desoneracao/"]
    assert b.referencia == date(2026, 10, 1)


def test_meses_do_mais_novo_ao_mais_velho_cruzando_o_ano():
    assert meses(date(2025, 11, 1), date(2026, 2, 1)) == [
        date(2026, 2, 1), date(2026, 1, 1), date(2025, 12, 1), date(2025, 11, 1),
    ]
    assert meses(date(2026, 3, 1), date(2026, 2, 1)) == []

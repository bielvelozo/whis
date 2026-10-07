"""A foto de uma aula: o `og:image` (ou `twitter:image`) da página que ela usou como fonte."""

from __future__ import annotations

from whis.fotos_das_aulas import imagem_da_pagina


def test_og_image_vence_e_url_relativa_vira_absoluta():
    html = (
        '<html><head><meta property="og:image" content="/img/rx7.jpg">'
        '<meta name="twitter:image" content="https://x.com/t.jpg"></head></html>'
    )
    assert imagem_da_pagina(html, "https://en.wikipedia.org/wiki/Mazda_RX-7") == "https://en.wikipedia.org/img/rx7.jpg"


def test_sem_og_usa_twitter_image():
    html = '<meta name="twitter:image" content="https://cdn.exemplo.com/a.png">'
    assert imagem_da_pagina(html, "https://exemplo.com/p") == "https://cdn.exemplo.com/a.png"


def test_sem_meta_nenhuma_e_none():
    assert imagem_da_pagina("<html><body><img src='a.jpg'></body></html>", "https://exemplo.com") is None


def test_twitter_image_antes_do_og_na_pagina_nao_muda_a_prioridade():
    html = (
        '<meta name="twitter:image" content="https://x.com/t.jpg">'
        '<meta property="og:image" content="https://x.com/og.jpg">'
    )
    assert imagem_da_pagina(html, "https://x.com/p") == "https://x.com/og.jpg"


def test_vale_o_primeiro_og_image_da_pagina():
    html = (
        '<meta property="og:image" content="https://x.com/1.jpg">'
        '<meta property="og:image" content="https://x.com/2.jpg">'
    )
    assert imagem_da_pagina(html, "https://x.com/p") == "https://x.com/1.jpg"


def test_content_vazio_nao_trava_o_seguinte():
    html = (
        '<meta property="og:image" content="  ">'
        '<meta property="og:image" content="https://x.com/2.jpg">'
    )
    assert imagem_da_pagina(html, "https://x.com/p") == "https://x.com/2.jpg"


def test_url_sem_esquema_herda_o_da_pagina():
    html = '<meta property="og:image" content="//upload.wikimedia.org/a.jpg">'
    assert imagem_da_pagina(html, "https://en.wikipedia.org/wiki/X") == "https://upload.wikimedia.org/a.jpg"


def test_url_relativa_ao_caminho_da_pagina():
    html = '<meta property="og:image" content="foto.jpg">'
    assert imagem_da_pagina(html, "https://exemplo.com/blog/post") == "https://exemplo.com/blog/foto.jpg"


def test_og_que_nao_e_http_cai_no_twitter():
    html = (
        '<meta property="og:image" content="data:image/png;base64,AAAA">'
        '<meta name="twitter:image" content="https://x.com/t.jpg">'
    )
    assert imagem_da_pagina(html, "https://x.com/p") == "https://x.com/t.jpg"


def test_so_data_uri_e_none():
    html = '<meta property="og:image" content="data:image/png;base64,AAAA">'
    assert imagem_da_pagina(html, "https://x.com/p") is None


def test_ampersand_no_content_vem_desfeito():
    html = '<meta property="og:image" content="https://x.com/a.jpg?w=1&amp;h=2">'
    assert imagem_da_pagina(html, "https://x.com/p") == "https://x.com/a.jpg?w=1&h=2"


def test_atributos_em_maiuscula_e_aspas_simples():
    html = "<META PROPERTY='og:image' CONTENT='https://x.com/a.jpg'>"
    assert imagem_da_pagina(html, "https://x.com/p") == "https://x.com/a.jpg"


def test_html_quebrado_nao_levanta():
    assert imagem_da_pagina("<meta property=\"og:image\" content=\"https://x.com/a.jpg", "https://x.com/p") is None
    assert imagem_da_pagina("", "https://x.com/p") is None

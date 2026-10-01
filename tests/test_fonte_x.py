"""O leitor do X sem navegador: a leitura do HTML de um post, a URL da busca e o corte."""

from __future__ import annotations

import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from whis import fonte_x
from whis.fonte_x import PostDoX, candidatos_do_x, e_do_x, ler_post, url_da_busca
from whis.fontes_do_jornal import FonteDoX

FIXTURES = Path(__file__).parent / "fixtures" / "jornal" / "x"
AGORA = datetime(2026, 9, 30, 11, 20, tzinfo=UTC)


def fixture(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8-sig")


def post_de(autor: str, status: int, *, horas: float = 1, curtidas: int | None = 10, texto: str = "Uma dica") -> PostDoX:
    return PostDoX(
        link=f"https://x.com/{autor}/status/{status}",
        autor=autor,
        texto=texto,
        data=AGORA - timedelta(hours=horas),
        curtidas=curtidas,
    )


def test_le_link_autor_hora_texto_e_curtidas_do_post():
    assert ler_post(fixture("post.html")) == PostDoX(
        link="https://x.com/bcherny/status/1840000000000000001",
        autor="bcherny",
        texto="Tip: put your test command in CLAUDE.md so the agent runs it before every commit.",
        data=datetime(2026, 9, 30, 13, 5, tzinfo=UTC),
        curtidas=1234,
    )


def test_repost_vale_pelo_post_original():
    post = ler_post(fixture("repost.html"))

    assert post.autor == "simonw"
    assert post.link == "https://x.com/simonw/status/1840000000000000002"


def test_anuncio_fica_fora():
    assert ler_post(fixture("anuncio.html")) is None


def test_anuncio_sai_pelo_rotulo_mesmo_sem_rastreio():
    assert ler_post(fixture("anuncio_sem_rastreio.html")) is None


def test_post_organico_dentro_do_rastreio_do_x_continua_post():
    post = ler_post(fixture("rastreado.html"))

    assert post is not None
    assert post.link == "https://x.com/bcherny/status/1840000000000000001"


def test_post_longo_vem_com_o_texto_visivel_sem_o_show_more():
    post = ler_post(fixture("longo.html"))

    assert post.texto.startswith("Long thread on context engineering")
    assert "Show more" not in post.texto
    assert post.curtidas == 2345


def test_post_sem_curtida_tem_curtidas_none_e_o_emoji_no_texto():
    post = ler_post(fixture("sem_curtida.html"))

    assert post.curtidas is None
    assert post.texto == "My first CLAUDE.md, feedback welcome 🙏"


def test_curtidas_abreviadas_viram_numero():
    assert ler_post(fixture("curtidas_k.html")).curtidas == 1200


def test_post_que_cita_outro_fica_com_o_de_fora():
    post = ler_post(fixture("citacao.html"))

    assert post.autor == "steipete"
    assert post.texto == "This is the way: one agent per worktree."
    assert post.data == datetime(2026, 9, 30, 8, 0, tzinfo=UTC)


def test_post_longo_real_vem_sem_o_show_more():
    post = ler_post(fixture("real_longo.html"))

    assert (post.autor, post.curtidas) == ("0x_rody", 125)
    assert post.data == datetime(2026, 9, 30, 13, 59, 37, tzinfo=UTC)
    assert post.texto.startswith("Opus 5.5 makes this AI stack look")
    assert "Show more" not in post.texto


def test_citacao_real_fica_so_com_o_texto_de_fora():
    post = ler_post(fixture("real_citacao.html"))

    assert (post.autor, post.curtidas) == ("angeldot_", 1265)
    assert post.texto.startswith("ANTHROPIC HAS REVEALED THE TRICK")
    assert "GIVING AWAY" not in post.texto


def test_post_real_dentro_do_rastreio_e_o_mesmo_post():
    assert ler_post(fixture("real_rastreado.html")).link == ler_post(fixture("real_longo.html")).link


def test_impulsionado_real_fica_fora():
    assert ler_post(fixture("real_impulsionado.html")) is None


def test_rotulo_boosted_marca_anuncio_mesmo_com_hora():
    impulsionado = fixture("post.html").replace("<span>@bcherny</span>", "<span>@bcherny</span><span>Boosted</span>")

    assert ler_post(impulsionado) is None


def test_html_sem_permalink_nao_e_post():
    assert ler_post("<article data-testid=\"tweet\"><div data-testid=\"tweetText\">oi</div></article>") is None


def test_a_busca_acrescenta_filtro_de_respostas_since_e_aba_principais():
    url = url_da_busca('"claude code" min_faves:100', date(2026, 9, 30))

    consulta = parse_qs(urlsplit(url).query)
    assert url.startswith("https://x.com/search?")
    assert consulta["q"] == ['"claude code" min_faves:100 -filter:replies since:2026-09-29']
    assert consulta["f"] == ["top"]
    assert consulta["src"] == ["typed_query"]


def test_candidatos_cortam_24h_repetidos_ja_publicados_e_ordenam_por_curtidas():
    posts = [
        post_de("a", 1, horas=1, curtidas=10),
        post_de("b", 2, horas=2, curtidas=500),
        post_de("a", 1, horas=1, curtidas=10),
        post_de("c", 3, horas=30, curtidas=900),
        post_de("d", 4, horas=3, curtidas=None),
        post_de("e", 5, horas=1, curtidas=50),
    ]

    candidatos = candidatos_do_x("ia", posts, AGORA, frozenset({"https://x.com/e/status/5"}))

    assert [c.link.rsplit("/", 1)[-1] for c in candidatos] == ["2", "1", "4"]
    assert [c.id for c in candidatos] == ["ia-x1", "ia-x2", "ia-x3"]
    assert (candidatos[0].secao, candidatos[0].fonte, candidatos[0].curtidas) == ("ia", "@b", 500)
    assert candidatos[0].imagem is None


def test_dois_posts_que_comecam_igual_continuam_dois():
    iguais = [post_de("a", 1, texto="Claude Code tip: one"), post_de("b", 2, texto="Claude Code tip: two")]

    assert len(candidatos_do_x("ia", iguais, AGORA)) == 2


def test_teto_de_trinta_e_post_sem_texto_fora():
    muitos = [post_de(f"u{n}", n, curtidas=n) for n in range(1, 41)] + [post_de("vazio", 99, texto="")]

    candidatos = candidatos_do_x("ia", muitos, AGORA)

    assert len(candidatos) == 30
    assert candidatos[0].curtidas == 40
    assert all(c.fonte != "@vazio" for c in candidatos)


def test_titulo_curto_e_resumo_com_o_texto():
    longo = "palavra " * 100
    [candidato] = candidatos_do_x("ia", [post_de("a", 1, texto=longo.strip())], AGORA)

    assert len(candidato.titulo) <= 120 and candidato.titulo.endswith("…")
    assert len(candidato.resumo) <= 500


def test_candidato_herda_a_secao_da_linha():
    [candidato] = candidatos_do_x("tecnologia", [post_de("a", 1)], AGORA)

    assert candidato.id == "tecnologia-x1"


def test_e_do_x():
    assert e_do_x("https://x.com/a/status/1")
    assert e_do_x("https://twitter.com/a/status/1")
    assert not e_do_x("https://simonwillison.net/2026/x/")


class ProcessoDublê:
    def __init__(self, *, estoura: bool = False) -> None:
        self.estoura = estoura

    def wait(self, timeout=None):
        if self.estoura:
            raise subprocess.TimeoutExpired("chrome", timeout)
        return 0


def test_o_login_abre_um_chrome_comum_no_perfil_do_whis_e_confere_a_sessao(tmp_path, monkeypatch):
    monkeypatch.setattr(fonte_x, "caminho_do_chrome", lambda: Path("C:/Chrome/chrome.exe"))
    abertos: list[list[str]] = []
    conferidos: list[Path] = []

    ok = fonte_x.abrir_login(
        tmp_path / "perfil",
        abrir=lambda argv: abertos.append(argv) or ProcessoDublê(),
        conferir=lambda perfil: conferidos.append(perfil) or True,
    )

    assert ok is True
    [argv] = abertos
    assert Path(argv[0]).name == "chrome.exe"
    assert f"--user-data-dir={tmp_path / 'perfil'}" in argv
    assert argv[-1] == "https://x.com/login"
    assert not any("automation" in a or "remote-debugging" in a for a in argv)
    assert conferidos == [tmp_path / "perfil"]


def test_login_que_nao_fecha_a_tempo_nao_confere_a_sessao(tmp_path, monkeypatch):
    monkeypatch.setattr(fonte_x, "caminho_do_chrome", lambda: Path("C:/Chrome/chrome.exe"))
    conferidos: list[Path] = []

    ok = fonte_x.abrir_login(
        tmp_path / "perfil",
        abrir=lambda argv: ProcessoDublê(estoura=True),
        conferir=lambda perfil: conferidos.append(perfil) or True,
    )

    assert ok is False
    assert conferidos == []


def test_sem_chrome_o_login_nao_abre(tmp_path, monkeypatch):
    monkeypatch.setattr(fonte_x, "caminho_do_chrome", lambda: None)

    assert fonte_x.abrir_login(tmp_path / "perfil", abrir=lambda argv: pytest.fail("abriu sem Chrome")) is False


def test_sem_fonte_o_leitor_nao_abre_navegador():
    assert fonte_x.LeitorDoX().ler((), date(2026, 9, 30)).posts == {}


def test_a_suite_nunca_abre_o_navegador_de_verdade():
    with pytest.raises(AssertionError, match="navegador de verdade"):
        fonte_x.LeitorDoX().ler((FonteDoX("X · Seguindo", "seguindo"),), date(2026, 9, 30))

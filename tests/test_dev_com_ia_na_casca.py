"""Dev com IA na casca: os fakes do X, o `news --fakes`, o `x-login` e o toast do login do X."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from whis import fonte_x
from whis import jornal as _jornal
from whis.__main__ import main
from whis.efemeride import Efemeride
from whis.fakes import EditorFake, LeitorDoXFake
from whis.feeds import Coleta
from whis.fontes_do_jornal import FonteDoX
from whis.jornal import AVISO_DO_LOGIN_DO_X, Edicao, ResultadoDoJornal
from whis.palheta import resultado_do_jornal
from whis.placar_espn import Placar
from whis.portas import Candidato

BRT = timezone(timedelta(hours=-3))
HOJE = date(2026, 9, 30)
FONTES = (FonteDoX("X · Seguindo", "seguindo"), FonteDoX("X · Contexto", "busca", "context"))


def test_o_leitor_fake_traz_dois_posts_do_dia_por_pagina_de_autores_distintos():
    leitura = LeitorDoXFake().ler(FONTES, HOJE)

    posts = [post for nome in ("X · Seguindo", "X · Contexto") for post in leitura.posts[nome]]
    assert len(posts) == 4
    assert len({post.autor for post in posts}) == 4
    assert all(post.data.astimezone(BRT).date() == HOJE for post in posts)
    assert all(post.link.startswith("https://x.com/") for post in posts)
    assert leitura.falhas == {}


def test_o_leitor_fake_pode_falhar():
    with pytest.raises(fonte_x.LoginDoXVenceu):
        LeitorDoXFake(erro=fonte_x.LoginDoXVenceu("o X pediu login")).ler(FONTES, HOJE)


def test_o_editor_fake_faz_dica_do_primeiro_post_do_x_e_tira_da_lista():
    candidatos = {
        "ia": (
            Candidato("ia-1", "ia", "Blog", "Blog", "https://blog.exemplo.com/1"),
            Candidato("ia-x1", "ia", "@a", "Post A", "https://x.com/a/status/1"),
            Candidato("ia-x2", "ia", "@b", "Post B", "https://x.com/b/status/2"),
        )
    }

    escolha = EditorFake().escolher(candidatos, {"ia": (4, 6)}, ())

    assert escolha.dica.candidato.id == "ia-x1"
    assert "ia-x1" not in [item.candidato.id for item in escolha.secoes["ia"]]


@pytest.fixture
def coleta_sem_rede(monkeypatch):
    agora = datetime.now(BRT)
    candidato = Candidato("tecnologia-1", "tecnologia", "HN", "Notícia", "https://e.com/1", data=agora - timedelta(hours=1))
    coleta = Coleta(candidatos={"tecnologia": (candidato,)}, time=(), fontes_com_falha=())
    monkeypatch.setattr(_jornal, "coletar", lambda *a, **k: coleta)
    monkeypatch.setattr(_jornal, "buscar_placar", lambda agora, transporte=None: Placar(jogos=(), situacao="sem-jogo", texto="Sem jogo"))
    monkeypatch.setattr(_jornal, "buscar_efemeride", lambda agora, transporte=None: Efemeride(None, "x", None, None))
    monkeypatch.setattr(_jornal, "baixar_capas", lambda edicao, pasta, rede=None: {})


def test_news_com_fakes_traz_a_secao_do_x_sem_abrir_navegador(configuracao, coleta_sem_rede, capsys):
    codigo = main(["news", "--fakes"])

    saida = capsys.readouterr().out
    assert codigo in (0, 3)
    linha = next(linha for linha in saida.splitlines() if "Dev com IA" in linha)
    assert int(linha.rsplit(":", 1)[1]) > 0


@pytest.mark.parametrize(("conseguiu", "codigo", "mensagem"), [(True, 0, "Sessão do X salva"), (False, 1, "Login não concluído")])
def test_x_login_diz_se_a_sessao_ficou_salva(monkeypatch, capsys, conseguiu, codigo, mensagem):
    monkeypatch.setattr(fonte_x, "abrir_login", lambda: conseguiu)

    assert main(["x-login"]) == codigo
    assert mensagem in capsys.readouterr().out


def test_o_help_documenta_o_x_login(capsys):
    with pytest.raises(SystemExit):
        main(["x-login", "--help"])

    assert "x.com" in capsys.readouterr().out.lower()


def edicao_com(avisos: tuple[str, ...]) -> Edicao:
    return Edicao(data=HOJE, gerado_em=datetime(2026, 9, 30, 8, 20, tzinfo=BRT), secoes=(), avisos=avisos)


VENCIDO_NO_CLAUDE = (
    "Falha ao falar com o Claude na publicação (ResultError): Claude Code returned an error result: "
    "Failed to authenticate: OAuth session expired and could not be refreshed (exit code: 1)"
)


def test_com_pagina_e_login_do_x_vencido_o_toast_pede_o_x_login():
    resultado = ResultadoDoJornal(
        edicao=edicao_com((AVISO_DO_LOGIN_DO_X,)), nota=None, pagina=None, url="https://claude.ai/artifact/x", parcial=True
    )

    toast = resultado_do_jornal(resultado)

    assert toast.titulo == "O login do X venceu"
    assert toast.texto == "Rode 'python -m whis x-login' num terminal. O jornal saiu sem a parte do X."
    assert toast.link == "https://claude.ai/artifact/x"


def test_sem_pagina_e_login_do_x_vencido_o_toast_e_o_da_pagina_e_cita_o_x():
    resultado = ResultadoDoJornal(
        edicao=edicao_com((AVISO_DO_LOGIN_DO_X,)), nota=None, pagina=None, url=None, parcial=True,
        falha_da_publicacao="HTTP 500 do Artifact",
    )

    toast = resultado_do_jornal(resultado)

    assert toast.titulo == "O jornal não foi publicado"
    assert "o login do X também venceu" in toast.texto
    assert toast.texto.endswith("HTTP 500 do Artifact")


def test_o_login_do_claude_vencido_vence_o_do_x():
    resultado = ResultadoDoJornal(
        edicao=edicao_com((AVISO_DO_LOGIN_DO_X,)), nota=None, pagina=None, url=None, parcial=True,
        falha_da_publicacao=VENCIDO_NO_CLAUDE,
    )

    assert resultado_do_jornal(resultado).titulo == "O login do Claude venceu"

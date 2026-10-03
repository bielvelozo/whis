"""O LinkedIn da entrega 3, sem rede e sem Claude.

A API oficial é servida por `httpx.MockTransport`; o cofre cifra com uma
função de mentira (fora do Windows não há DPAPI). O que se prova é o aval: nada
é publicado sem o gesto dele, e o texto que ele editou é o que sai.
"""

from __future__ import annotations

import json
import zipfile
from datetime import date, datetime
from pathlib import Path

import httpx
import pytest

from whis import __main__ as cli
from whis.cofre import Cofre, senha_nova
from whis.configuracao import Configuracao
from whis.fakes_da_cacada import AnaliseDoPerfilFake, PostsFake
from whis.linkedin import (
    CAMINHO_DA_ANALISE,
    PUBLICADO,
    ErroDoLinkedIn,
    LinkedInAPI,
    escapar_commentary,
    escrever_rascunhos,
    ler_exportacao,
    ler_post,
    listar_posts,
    preparar_linkedin,
    publicar_post,
    versao_da_api,
)
from whis.palheta import ListaDePosts, resultado_do_linkedin

AGORA = 1_790_000_000.0


def _cofre(tmp_path: Path) -> Cofre:
    return Cofre(tmp_path / "cofre.bin", cifrar=lambda b: b[::-1], decifrar=lambda b: b[::-1])


def _api(tmp_path: Path, respostas: dict[str, httpx.Response] | None = None, pedidos: list | None = None) -> LinkedInAPI:
    def responder(pedido: httpx.Request) -> httpx.Response:
        if pedidos is not None:
            pedidos.append(pedido)
        for trecho, resposta in (respostas or {}).items():
            if trecho in str(pedido.url):
                return resposta
        return httpx.Response(404)

    return LinkedInAPI("id", "segredo", _cofre(tmp_path), rede=httpx.MockTransport(responder), agora=lambda: AGORA)


def _logado(api: LinkedInAPI) -> LinkedInAPI:
    api.cofre.guardar("linkedin", {"token": "tok", "expira_em": AGORA + 86_400 * 30, "pessoa": "urn:li:person:abc"})
    return api


# -- o export -------------------------------------------------------------------------------------


def test_o_export_e_lido_do_zip_mesmo_com_notas_antes_do_cabecalho(tmp_path: Path):
    pacote = tmp_path / "Basic_LinkedInDataExport.zip"
    with zipfile.ZipFile(pacote, "w") as zip_:
        zip_.writestr("Profile.csv", "First Name,Last Name,Headline\nGabriel,V,Dev\n")
        zip_.writestr("Positions.csv", "Notes:\nAlgo do LinkedIn\nCompany Name,Title,Started On\nAcme,Dev Web,Jan 2024\n")
        zip_.writestr("Connections.csv", "First Name\nNinguém\n")

    texto = ler_exportacao(pacote)

    assert "== Profile.csv ==" in texto and "Headline: Dev" in texto
    assert "Company Name: Acme | Title: Dev Web" in texto
    assert "Connections" not in texto


def test_sem_export_e_erro_claro(tmp_path: Path):
    with pytest.raises(ErroDoLinkedIn, match="exportacao"):
        ler_exportacao(tmp_path / "nao-existe.zip")


# -- a análise e os rascunhos ------------------------------------------------------------------------


def test_preparar_escreve_a_analise_e_os_rascunhos_e_nao_publica_nada(tmp_path: Path):
    pasta = tmp_path / "export"
    pasta.mkdir()
    (pasta / "Profile.csv").write_text("Headline\nDev\n", encoding="utf-8")
    vault = tmp_path / "vault"

    resultado = preparar_linkedin(
        vault, exportacao=pasta, analise=AnaliseDoPerfilFake(), posts=PostsFake(), quantos=3,
        evidencias="", perfil_do_whis="", procuro="", sobre_mim="", hoje=date(2026, 10, 3),
    )

    assert resultado.analise == CAMINHO_DA_ANALISE and resultado.falhas == ()
    analise = (vault / CAMINHO_DA_ANALISE).read_text(encoding="utf-8")
    assert "## Antes de mexer" in analise and "```text" in analise and "Nota de hoje: 55/100" in analise
    assert len(resultado.rascunhos) == 3
    posts = listar_posts(vault)
    assert all(post.rascunho for post in posts)
    assert posts[0].texto.startswith("Gancho do post")
    assert "Nada foi publicado" in resultado_do_linkedin(resultado).texto


def test_sem_export_os_rascunhos_saem_e_a_falta_e_dita(tmp_path: Path):
    resultado = preparar_linkedin(
        tmp_path, exportacao=None, analise=AnaliseDoPerfilFake(), posts=PostsFake(), quantos=1,
        evidencias="", perfil_do_whis="", procuro="", sobre_mim="", hoje=date(2026, 10, 3),
    )

    assert resultado.analise is None and len(resultado.rascunhos) == 1
    assert "Baixar seus dados" in resultado.falhas[0]


# -- publicar ----------------------------------------------------------------------------------------


def test_publicar_manda_o_texto_editado_escapado_e_marca_so_o_frontmatter(tmp_path: Path):
    vault = tmp_path / "vault"
    [caminho] = escrever_rascunhos(vault, [{"titulo": "Cache", "texto": "rascunho", "por_que": "x"}], date(2026, 10, 3))
    arquivo = vault / caminho
    editado = arquivo.read_text(encoding="utf-8").replace("rascunho\n", "Meu texto (editado) com #tag e @alguém\n")
    arquivo.write_bytes(editado.replace("\n", "\r\n").encode("utf-8"))
    pedidos: list[httpx.Request] = []
    api = _logado(_api(tmp_path, {"/rest/posts": httpx.Response(201, headers={"x-restli-id": "urn:li:share:99"})}, pedidos))

    url = publicar_post(vault, caminho, api, agora=datetime(2026, 10, 3, 9, 0))

    assert url == "https://www.linkedin.com/feed/update/urn:li:share:99/"
    corpo = json.loads(pedidos[0].content)
    assert corpo["commentary"] == r"Meu texto \(editado\) com \#tag e \@alguém"
    assert corpo["author"] == "urn:li:person:abc" and corpo["visibility"] == "PUBLIC"
    assert pedidos[0].headers["Authorization"] == "Bearer tok"
    assert pedidos[0].headers["LinkedIn-Version"].isdigit()
    depois = arquivo.read_bytes().decode("utf-8")
    assert "status: publicado" in depois and "url: \"https://www.linkedin.com/feed/update/urn:li:share:99/\"" in depois
    assert depois.endswith("Meu texto (editado) com #tag e @alguém\r\n"), "o corpo dele volta byte a byte"
    with pytest.raises(ErroDoLinkedIn, match="já foi publicado"):
        publicar_post(vault, caminho, api)


def test_sem_login_ou_login_vencido_nao_publica(tmp_path: Path):
    api = _api(tmp_path)
    with pytest.raises(ErroDoLinkedIn, match="linkedin-login"):
        api.publicar("oi")

    api.cofre.guardar("linkedin", {"token": "t", "expira_em": AGORA - 1, "pessoa": "urn:li:person:a"})
    with pytest.raises(ErroDoLinkedIn, match="linkedin-login"):
        api.publicar("oi")


def test_recusa_401_pede_login_de_novo(tmp_path: Path):
    api = _logado(_api(tmp_path, {"/rest/posts": httpx.Response(401)}))

    with pytest.raises(ErroDoLinkedIn, match="venceu"):
        api.publicar("oi")


def test_o_codigo_vira_token_no_cofre(tmp_path: Path):
    api = _api(
        tmp_path,
        {
            "accessToken": httpx.Response(200, json={"access_token": "novo", "expires_in": 5_184_000}),
            "userinfo": httpx.Response(200, json={"sub": "xyz", "name": "Gabriel"}),
        },
    )

    api.trocar_codigo("codigo")

    guardado = api.cofre.obter("linkedin")
    assert guardado["token"] == "novo" and guardado["pessoa"] == "urn:li:person:xyz"
    assert api.logado() and api.dias_restantes() == 60
    assert b"novo" not in (tmp_path / "cofre.bin").read_bytes()


def test_o_endereco_de_login_pede_so_publicar_e_identidade(tmp_path: Path):
    endereco = _api(tmp_path).endereco_de_login("estado")

    assert "scope=openid+profile+w_member_social" in endereco and "state=estado" in endereco
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8765%2Flinkedin" in endereco


def test_escape_e_versao():
    assert escapar_commentary("a_b*c~d|e") == r"a\_b\*c\~d\|e"
    assert versao_da_api(date(2026, 1, 15)) == "202511"
    assert versao_da_api(date(2026, 10, 3)) == "202608"


# -- o aval: a lista da palheta e o terminal ------------------------------------------------------------


def test_na_lista_de_posts_so_o_enter_publica(tmp_path: Path):
    vault = tmp_path / "vault"
    escrever_rascunhos(vault, [{"titulo": "Um", "texto": "Texto um", "por_que": ""}], date(2026, 10, 3))
    publicados: list[str] = []

    class ApiFake:
        def publicar(self, texto: str) -> str:
            publicados.append(texto)
            return "https://www.linkedin.com/feed/update/urn:li:share:1/"

    lista = ListaDePosts(Configuracao(vault=vault), api=lambda _c: ApiFake(), lancar=lambda _uri: None)
    linhas = lista.linhas("")

    assert [linha.titulo for linha in linhas] == ["Um"] and publicados == []
    efeito = lista.gestos[0].rodar(0, "")

    assert publicados == ["Texto um"] and "Published" in efeito.mensagem
    lista.linhas("")
    assert "Already published" in lista.gestos[0].rodar(0, "").mensagem


def test_linkedin_publicar_no_terminal_pergunta_antes(arquivo_de_configuracao: Path, caminho_do_vault: Path, monkeypatch, capsys):
    [caminho] = escrever_rascunhos(caminho_do_vault, [{"titulo": "T", "texto": "Olá rede", "por_que": ""}], date(2026, 10, 3))
    publicados: list[str] = []

    class ApiFake:
        def publicar(self, texto: str) -> str:
            publicados.append(texto)
            return "https://www.linkedin.com/feed/update/urn:li:share:2/"

    monkeypatch.setattr(cli, "montar_linkedin_api", lambda _c: ApiFake())
    monkeypatch.setattr("builtins.input", lambda _p: "n")
    assert cli.main(["linkedin-publicar", caminho]) == 0
    assert publicados == [] and "Nada publicado" in capsys.readouterr().out

    monkeypatch.setattr("builtins.input", lambda _p: "s")
    assert cli.main(["linkedin-publicar", caminho]) == 0
    assert publicados == ["Olá rede"]
    assert ler_post(caminho_do_vault, caminho).status == PUBLICADO


def test_whis_linkedin_fakes(arquivo_de_configuracao: Path, capsys, toasts):
    assert cli.main(["linkedin", "--fakes"]) == 3
    saida = capsys.readouterr().out
    assert saida.count("Rascunho: linkedin/posts/") == 3 and "Nada foi publicado" in saida
    assert toasts == []


def test_o_cofre_guarda_cifrado_e_a_senha_nova_e_forte(tmp_path: Path):
    cofre = Cofre(tmp_path / "c.bin", cifrar=lambda b: bytes(x ^ 7 for x in b), decifrar=lambda b: bytes(x ^ 7 for x in b))
    cofre.guardar("a", {"x": 1})

    assert cofre.obter("a") == {"x": 1} and b'"x"' not in (tmp_path / "c.bin").read_bytes()
    senha = senha_nova()
    assert len(senha) == 20 and any(c.isupper() for c in senha) and any(c.isdigit() for c in senha)

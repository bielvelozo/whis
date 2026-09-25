"""A costura do jornal: nota em `noticias/`, página, publicação e cada degradação.

A coleta, o placar e a efeméride entram trocados por dados fixos — cada um tem
o seu teste com amostras reais. Aqui se verifica o que a edição faz com eles.
"""

from __future__ import annotations

import io
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from PIL import Image

from whis import jornal as _jornal
from whis.configuracao import Configuracao
from whis.efemeride import Efemeride
from whis.feeds import Coleta
from whis.fontes_do_jornal import CAMINHO_DAS_FONTES, MODELO_DAS_FONTES
from whis.jornal import (
    AVISO_DA_ESCOLHA,
    AVISO_DA_FORMACAO,
    AVISO_DA_PUBLICACAO,
    CAMINHO_DA_TRILHA,
    JornalNaoNasceu,
    gerar_jornal,
    links_publicados,
    ultima_url,
)
from whis.placar_espn import Gol, Jogo, Placar
from whis.portas import (
    Aula,
    Candidato,
    ErroDeEditor,
    ErroDeFormacao,
    ErroDePublicacao,
    Escolha,
    Formacao,
    ItemEscolhido,
    Janelas,
    Medida,
    Publicacao,
)

BRT = timezone(timedelta(hours=-3))
AGORA = datetime(2026, 9, 25, 8, 20, tzinfo=BRT)
URL_DO_ARTIFACT = "https://claude.ai/artifact/AYhYVZDhevQdWv4YaNuoge"


def candidato(secao: str, n: int, fonte: str = "Fonte A", *, imagem: str | None = None, horas: int = 1) -> Candidato:
    return Candidato(
        id=f"{secao}-{n}",
        secao=secao,
        fonte=fonte,
        titulo=f"Original {secao} {n}",
        link=f"https://exemplo.com/{secao}/{n}",
        resumo=f"Resumo do feed {secao} {n}",
        data=AGORA - timedelta(hours=horas),
        imagem=imagem,
    )


def coleta_padrao() -> Coleta:
    return Coleta(
        candidatos={
            "tecnologia": (
                candidato("tecnologia", 1, imagem="https://img.exemplo.com/1.jpg"),
                candidato("tecnologia", 2, "Fonte B", horas=2),
                candidato("tecnologia", 3, "Fonte A", horas=3),
                candidato("tecnologia", 4, "Fonte A", horas=4),
            ),
            "mundo": (),
            "brasil": (candidato("brasil", 1),),
            "musica": (candidato("musica", 1),),
            "futebol": (candidato("futebol", 1),),
            "carros": (candidato("carros", 1),),
        },
        time=(candidato("time", 1, "ge · Corinthians"),),
        fontes_com_falha=("YouTube · Joe Satriani (HTTP 404)",),
    )


class EditorDublê:
    def __init__(self, *, erro: Exception | None = None) -> None:
        self.erro = erro
        self.recebido = None

    def escolher(self, candidatos, limites, time) -> Escolha:
        self.recebido = (candidatos, limites, time)
        if self.erro:
            raise self.erro
        secoes = {
            secao: tuple(ItemEscolhido(c, f"Título {c.id}", f"Resumo {c.id}.") for c in itens[:2])
            for secao, itens in candidatos.items()
        }
        return Escolha(
            secoes=secoes,
            time=tuple(ItemEscolhido(c, f"Time {c.id}", "") for c in time),
            medida=Medida(0.40, 42.0, Janelas(30, 61), Janelas(30, 61)),
        )


class FormacaoDublê:
    def __init__(self, *, erro: Exception | None = None) -> None:
        self.erro = erro
        self.trilha_recebida: str | None = None

    def ensinar(self, data: date, trilha: str) -> Formacao:
        self.trilha_recebida = trilha
        if self.erro:
            raise self.erro
        return Formacao(
            software=Aula("Dublês de teste", "Texto da aula.", ("https://martinfowler.com/x",), "software · dublês de teste"),
            carros=(
                Aula("O turbo", "Como funciona.", ("https://en.wikipedia.org/wiki/Turbocharger",), "carros · turbo"),
            ),
            medida=Medida(0.25, 60.0, Janelas(30, 61), Janelas(31, 61)),
        )


class PublicacaoDublê:
    def __init__(self, *, url: str = URL_DO_ARTIFACT, erro: Exception | None = None) -> None:
        self.url = url
        self.erro = erro
        self.chamadas: list[tuple[str, dict, str | None]] = []

    def publicar(self, html: Path, capas: dict[str, Path], url_atual: str | None) -> Publicacao:
        self.chamadas.append((html.read_text(encoding="utf-8"), dict(capas), url_atual))
        if self.erro:
            raise self.erro
        return Publicacao(self.url, Medida(0.07, 30.0, Janelas(31, 61), Janelas(31, 62)))


def _jpeg() -> bytes:
    saida = io.BytesIO()
    Image.new("RGB", (1200, 600), "red").save(saida, "JPEG")
    return saida.getvalue()


def rede_das_capas(request: httpx.Request) -> httpx.Response:
    if request.url.host == "img.exemplo.com":
        return httpx.Response(200, content=_jpeg(), headers={"content-type": "image/jpeg"})
    return httpx.Response(404)


@pytest.fixture
def cenario(tmp_path: Path, monkeypatch):
    estado = {"coletas": [coleta_padrao()], "ja_publicados": None}

    def coletar_fixo(fontes, agora, *, ja_publicados, transporte, espera_da_segunda_rodada_s):
        estado["ja_publicados"] = ja_publicados
        return estado["coletas"].pop(0) if len(estado["coletas"]) > 1 else estado["coletas"][0]

    placar = Placar(
        jogos=(Jogo("Série A", "Corinthians", "Fluminense", 1, 3, "16:00", (Gol("24'", "Hulk", "fora"),)),),
        situacao="ok",
        texto="",
    )
    monkeypatch.setattr(_jornal, "coletar", coletar_fixo)
    monkeypatch.setattr(_jornal, "buscar_placar", lambda agora, transporte=None: estado.get("placar", placar))
    monkeypatch.setattr(
        _jornal,
        "buscar_efemeride",
        lambda agora, transporte=None: Efemeride(1977, "O Corinthians é campeão paulista.", "https://pt.wikipedia.org/wiki/X", None),
    )
    vault = tmp_path / "vault"
    configuracao = Configuracao(vault=vault, gravacoes=tmp_path / "g")
    estado.update(vault=vault, configuracao=configuracao, pasta=tmp_path / "edicao")
    return estado


def gerar(cenario, *, editor=None, formacao=None, publicacao=None, agora=AGORA, **extras):
    return gerar_jornal(
        agora,
        cenario["configuracao"],
        editor=editor or EditorDublê(),
        formacao=formacao or FormacaoDublê(),
        publicacao=publicacao or PublicacaoDublê(),
        rede=httpx.MockTransport(rede_das_capas),
        pasta_da_edicao=cenario["pasta"],
        dormir=lambda _s: None,
        **extras,
    )


def nota_de(cenario, dia: str = "2026-09-25") -> str:
    return (cenario["vault"] / "noticias" / f"{dia}.md").read_text(encoding="utf-8")


def test_a_edicao_completa_escreve_a_nota_e_publica(cenario):
    publicacao = PublicacaoDublê()

    resultado = gerar(cenario, publicacao=publicacao)

    nota = nota_de(cenario)
    assert resultado.url == URL_DO_ARTIFACT
    assert resultado.parcial is False
    for campo in ("tipo: jornal", "data: 2026-09-25", "gerado_em:", f'artifact: "{URL_DO_ARTIFACT}"',
                  'plano_antes: "5h=30% 7d=61%"', 'plano_depois: "5h=31% 7d=62%"', 'custo_usd: "0.7200"',
                  "segundos:", "fontes_com_falha:"):
        assert campo in nota
    assert "## Aprender hoje" in nota and "### Dublês de teste" in nota
    assert "### [Título tecnologia-1](https://exemplo.com/tecnologia/1)" in nota
    assert "![](https://img.exemplo.com/1.jpg)" in nota
    assert "img/1.jpg" not in nota
    assert "Fontes que não responderam hoje: YouTube · Joe Satriani (HTTP 404)" in nota


def test_a_nota_segue_a_ordem_de_fontes_md_e_o_futebol_tem_time_placar_e_curiosidade(cenario):
    gerar(cenario)

    nota = nota_de(cenario)
    posicoes = [nota.index(f"## {titulo}\n") for titulo in ("Aprender hoje", "Tecnologia", "Mundo", "Política no Brasil", "Música", "Futebol", "Carros")]
    assert posicoes == sorted(posicoes)
    futebol = nota[nota.index("## Futebol"):nota.index("## Carros")]
    assert futebol.index("### Corinthians") < futebol.index("### Placares") < futebol.index("### Curiosidade do dia")
    assert "- Corinthians **1 x 3** Fluminense (16:00) — 24' Hulk" in futebol
    assert "1977: O Corinthians é campeão paulista." in futebol
    assert "### Para aprender" in nota[nota.index("## Carros"):]


def test_secao_sem_item_diz_nada_relevante_na_nota_e_na_pagina(cenario):
    publicacao = PublicacaoDublê()

    gerar(cenario, publicacao=publicacao)

    mundo = nota_de(cenario).split("## Mundo")[1].split("## ")[0]
    assert "_Nada relevante nas últimas 24 h._" in mundo
    assert "Nada relevante nas últimas 24 h." in publicacao.chamadas[0][0]


def test_a_pagina_nao_tem_script_e_usa_as_capas_locais(cenario):
    publicacao = PublicacaoDublê()

    gerar(cenario, publicacao=publicacao)

    pagina, capas, url_atual = publicacao.chamadas[0]
    assert "<script" not in pagina.lower()
    assert '<meta name="color-scheme" content="light">' in pagina
    assert "<title>Jornal do Whis</title>" in pagina
    assert 'src="img/1.jpg"' in pagina
    assert "img.exemplo.com" not in pagina
    assert list(capas) == ["img/1.jpg"]
    assert capas["img/1.jpg"].read_bytes()[:2] == b"\xff\xd8"
    assert Image.open(capas["img/1.jpg"]).width == 900
    assert url_atual is None


def test_a_proxima_edicao_republica_no_endereco_da_anterior(cenario):
    gerar(cenario)
    publicacao = PublicacaoDublê()

    gerar(cenario, publicacao=publicacao, agora=AGORA + timedelta(days=1))

    assert publicacao.chamadas[0][2] == URL_DO_ARTIFACT
    assert ultima_url(cenario["vault"]) == URL_DO_ARTIFACT


def test_o_que_saiu_nas_ultimas_edicoes_nao_volta(cenario):
    gerar(cenario)

    gerar(cenario, agora=AGORA + timedelta(days=1))

    assert "https://exemplo.com/tecnologia/1" in cenario["ja_publicados"]
    assert "https://img.exemplo.com/1.jpg" not in cenario["ja_publicados"]


def test_so_as_sete_edicoes_anteriores_contam_como_publicadas(tmp_path: Path):
    pasta = tmp_path / "noticias"
    pasta.mkdir()
    for dia in range(1, 11):
        (pasta / f"2026-09-{dia:02d}.md").write_text(f"### [x](https://e.com/{dia})\n", encoding="utf-8")

    links = links_publicados(tmp_path, date(2026, 9, 10))

    assert links == frozenset(f"https://e.com/{dia}" for dia in range(3, 10))


def test_escolha_que_falha_vira_os_mais_novos_sem_resumo_e_no_maximo_dois_por_fonte(cenario):
    resultado = gerar(cenario, editor=EditorDublê(erro=ErroDeEditor("sem saída estruturada")))

    tecnologia = next(s for s in resultado.edicao.secoes if s.id == "tecnologia")
    assert [i.link for i in tecnologia.itens] == [
        "https://exemplo.com/tecnologia/1",
        "https://exemplo.com/tecnologia/2",
        "https://exemplo.com/tecnologia/3",
    ]
    assert all(i.resumo == "" for i in tecnologia.itens)
    assert resultado.parcial is True
    assert AVISO_DA_ESCOLHA[1:] in nota_de(cenario)


def test_formacao_que_falha_tira_as_aulas_e_avisa(cenario):
    resultado = gerar(cenario, formacao=FormacaoDublê(erro=ErroDeFormacao("sem fonte")))

    nota = nota_de(cenario)
    assert "## Aprender hoje" not in nota and "### Para aprender" not in nota
    assert AVISO_DA_FORMACAO[1:] in nota
    assert resultado.parcial is True
    assert not (cenario["vault"] / CAMINHO_DA_TRILHA).exists()


def test_publicacao_que_falha_deixa_a_nota_com_o_endereco_anterior(cenario):
    gerar(cenario)

    resultado = gerar(
        cenario,
        publicacao=PublicacaoDublê(erro=ErroDePublicacao("sem URL na resposta")),
        agora=AGORA + timedelta(days=1),
    )

    nota = nota_de(cenario, "2026-09-26")
    assert resultado.url is None
    assert resultado.falha_da_publicacao == "sem URL na resposta"
    assert f'artifact: "{URL_DO_ARTIFACT}"' in nota
    assert AVISO_DA_PUBLICACAO[1:] in nota
    assert resultado.parcial is True


def test_a_trilha_so_ganha_linhas_no_fim(cenario):
    trilha = cenario["vault"] / CAMINHO_DA_TRILHA
    trilha.parent.mkdir(parents=True)
    antes = "# Minha trilha\r\n\r\n- 2026-09-24 · software · pirâmide de testes\r\n"
    trilha.write_bytes(antes.encode("utf-8"))
    formacao = FormacaoDublê()

    gerar(cenario, formacao=formacao)

    depois = trilha.read_bytes().decode("utf-8")
    assert formacao.trilha_recebida == antes
    assert depois.startswith(antes)
    assert depois[len(antes):] == "- 2026-09-25 · software · dublês de teste\n- 2026-09-25 · carros · turbo\n"


def test_fontes_md_nasce_do_modelo_na_primeira_edicao(cenario):
    gerar(cenario)

    assert (cenario["vault"] / CAMINHO_DAS_FONTES).read_text(encoding="utf-8") == MODELO_DAS_FONTES


def test_sem_nenhum_feed_o_jornal_espera_a_rede_e_nao_nasce(cenario):
    total = 100
    sem_rede = Coleta(
        candidatos={s: () for s in coleta_padrao().candidatos},
        time=(),
        fontes_com_falha=tuple(f"F{n} (ConnectError)" for n in range(total)),
    )
    cenario["coletas"] = [sem_rede]
    esperas: list[float] = []
    publicacao = PublicacaoDublê()

    with pytest.raises(JornalNaoNasceu):
        gerar_jornal(
            AGORA,
            cenario["configuracao"],
            editor=EditorDublê(),
            formacao=FormacaoDublê(),
            publicacao=publicacao,
            pasta_da_edicao=cenario["pasta"],
            dormir=esperas.append,
            espera_sem_rede_s=60,
        )

    assert esperas == [60, 60]
    assert not (cenario["vault"] / "noticias" / "2026-09-25.md").exists()
    assert publicacao.chamadas == []


def test_a_rede_que_volta_depois_da_espera_salva_a_edicao(cenario):
    sem_rede = Coleta(
        candidatos={s: () for s in coleta_padrao().candidatos},
        time=(),
        fontes_com_falha=tuple(f"F{n} (ConnectError)" for n in range(48)),
    )
    cenario["coletas"] = [sem_rede, coleta_padrao()]

    resultado = gerar(cenario)

    assert resultado.url == URL_DO_ARTIFACT


def test_simular_nao_escreve_no_vault_nem_publica(cenario):
    publicacao = PublicacaoDublê()

    resultado = gerar(cenario, publicacao=publicacao, simular=True)

    assert resultado.simulado is True
    assert publicacao.chamadas == []
    assert not cenario["vault"].exists()
    assert resultado.pagina.is_file() and resultado.nota.is_file()


def test_sem_leitura_do_plano_o_cabecalho_diz(cenario):
    class EditorSemPlano(EditorDublê):
        def escolher(self, candidatos, limites, time):
            return replace(super().escolher(candidatos, limites, time), medida=Medida(0.4, 1.0))

    class FormacaoSemPlano(FormacaoDublê):
        def ensinar(self, data, trilha):
            return replace(super().ensinar(data, trilha), medida=Medida(0.2, 1.0))

    class PublicacaoSemPlano(PublicacaoDublê):
        def publicar(self, html, capas, url_atual):
            return replace(super().publicar(html, capas, url_atual), medida=Medida(0.07, 1.0))

    publicacao = PublicacaoSemPlano()
    gerar(cenario, editor=EditorSemPlano(), formacao=FormacaoSemPlano(), publicacao=publicacao)

    assert "sem leitura do plano" in nota_de(cenario)
    assert "sem leitura do plano" in publicacao.chamadas[0][0]


def test_placar_indisponivel_diz_isso_e_a_secao_segue(cenario):
    cenario["placar"] = Placar(jogos=(), situacao="indisponivel", texto="Placar indisponível hoje")

    gerar(cenario)

    futebol = nota_de(cenario).split("## Futebol")[1].split("## Carros")[0]
    assert "_Placar indisponível hoje_" in futebol
    assert "### [Título futebol-1]" in futebol


def test_capa_que_nao_baixa_deixa_o_item_sem_capa(cenario):
    coleta = coleta_padrao()
    quebrada = replace(coleta.candidatos["brasil"][0], imagem="https://quebrado.exemplo.com/x.jpg")
    cenario["coletas"] = [replace(coleta, candidatos={**coleta.candidatos, "brasil": (quebrada,)})]
    publicacao = PublicacaoDublê()

    resultado = gerar(cenario, publicacao=publicacao)

    brasil = next(s for s in resultado.edicao.secoes if s.id == "brasil")
    assert brasil.itens[0].capa is None
    assert list(publicacao.chamadas[0][1]) == ["img/1.jpg"]

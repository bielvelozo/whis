"""A publicação do deck: Haiku, só a ferramenta Artifact, sempre no mesmo endereço.

A rede entra trocada por mensagens gravadas, uma lista por sessão do CLI. As
frases dos resultados de ferramenta são as que a sonda registrou em
`.scratch/daily-slides/research/01-slides-headless.md`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolResultBlock, UserMessage

from whis.deck_claude import TIPO_SLIDES, PublicacaoDoDeckClaude, pedido_de_criacao, pedido_de_preenchimento
from whis.portas import ErroDePublicacao, PortaPublicacaoDoDeck

URL = "https://claude.ai/artifact/DeckDaDaily123"
NOVA = "https://claude.ai/artifact/DeckNovo456"
ARQUIVOS = ("project/deck.json", "project/slides/falar.html", "project/slides/fiz.html")


def _resultado(texto: str = "", **extras) -> ResultMessage:
    campos = {
        "subtype": "success",
        "duration_ms": 1000,
        "duration_api_ms": 900,
        "is_error": False,
        "num_turns": 3,
        "session_id": "sessao-de-teste",
        "total_cost_usd": 0.05,
        "usage": {},
        "result": texto,
    }
    return ResultMessage(**{**campos, **extras})


def _ferramenta(conteudo: str) -> UserMessage:
    return UserMessage(content=[ToolResultBlock(tool_use_id="t1", content=conteudo)])


def _publicado(url: str) -> UserMessage:
    return _ferramenta(
        f"Updated the Artifact at {url} (Version 2) with C:\\tmp\\trabalho\\project\\deck.json (and any "
        f"`files` listed); own files not sent this time were kept. Its page comes from the Artifact "
        f"type {TIPO_SLIDES} (release 1790810190-bbd5) and can't be changed here."
    )


def _criado(url: str) -> UserMessage:
    return _ferramenta(
        f"Created a new Artifact at {url} (version 1790816110-1bca) from the Artifact type "
        f"{TIPO_SLIDES} (release 1790810190-bbd5). Its own files (add yours under `project/`): none."
    )


def _texto(texto: str) -> AssistantMessage:
    return AssistantMessage(content=[TextBlock(text=texto)], model="claude-haiku-4-5-20251001")


class PublicacaoGravada(PublicacaoDoDeckClaude):
    def __init__(self, *chamadas: list, **extras) -> None:
        super().__init__(**extras)
        self.chamadas = list(chamadas)
        self.prompts: list[str] = []
        self.opcoes: list = []

    async def _mensagens(self, prompt, opcoes):
        self.prompts.append(prompt)
        self.opcoes.append(opcoes)
        for mensagem in self.chamadas.pop(0):
            yield mensagem


@pytest.fixture(autouse=True)
def _sem_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for nome in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(nome, raising=False)


@pytest.fixture
def raiz(tmp_path: Path) -> Path:
    pasta = tmp_path / "trabalho"
    for caminho in ARQUIVOS:
        (pasta / caminho).parent.mkdir(parents=True, exist_ok=True)
        (pasta / caminho).write_text("x", encoding="utf-8")
    return pasta


def test_cumpre_a_porta():
    assert isinstance(PublicacaoDoDeckClaude(), PortaPublicacaoDoDeck)


def test_com_endereco_republica_numa_sessao_so(raiz: Path):
    publicacao = PublicacaoGravada([_publicado(URL), _resultado(URL)])

    feita = publicacao.publicar(raiz, ARQUIVOS, URL)

    assert feita.url == URL
    assert len(publicacao.prompts) == 1
    assert f"action read, url={URL}" in publicacao.prompts[0]


def test_sem_endereco_cria_pelo_tipo_slides_e_preenche_noutra_sessao(raiz: Path):
    publicacao = PublicacaoGravada(
        [_criado(NOVA), _resultado(NOVA)],
        [_publicado(NOVA), _resultado(NOVA)],
    )

    feita = publicacao.publicar(raiz, ARQUIVOS, None)

    assert feita.url == NOVA
    criar, preencher = publicacao.prompts
    assert f"type_url={TIPO_SLIDES}" in criar and "title 'Daily'" in criar
    assert f"url={NOVA}" in preencher


def test_a_frase_do_artifact_comum_tambem_conta_como_publicado(raiz: Path):
    publicacao = PublicacaoGravada([_ferramenta(f"Published C:/tmp/deck.json at {URL} (Version 4)"), _resultado(URL)])

    assert publicacao.publicar(raiz, ARQUIVOS, URL).url == URL


def test_a_criacao_nao_confunde_o_deck_com_a_url_do_tipo(raiz: Path):
    publicacao = PublicacaoGravada([_criado(NOVA), _resultado(NOVA)], [_publicado(NOVA), _resultado(NOVA)])

    publicacao.publicar(raiz, ARQUIVOS, None)

    assert f"url={NOVA}" in publicacao.prompts[1]
    assert f"url={TIPO_SLIDES}" not in publicacao.prompts[1]


def test_url_so_no_texto_nao_conta_como_publicado(raiz: Path):
    publicacao = PublicacaoGravada([_texto(URL), _resultado(URL)])

    with pytest.raises(ErroDePublicacao) as erro:
        publicacao.publicar(raiz, ARQUIVOS, URL)

    assert erro.value.url == URL


def test_listagem_de_arquivos_nao_conta_como_publicacao(raiz: Path):
    publicacao = PublicacaoGravada(
        [_ferramenta(f"Published files of {URL} (version 1), 3 files by path"), _resultado("nada")]
    )

    with pytest.raises(ErroDePublicacao):
        publicacao.publicar(raiz, ARQUIVOS, URL)


def test_falha_no_preenchimento_depois_de_criar_leva_o_endereco_criado(raiz: Path):
    publicacao = PublicacaoGravada(
        [_criado(NOVA), _resultado(NOVA)],
        [_texto("não consegui"), _resultado("não consegui")],
    )

    with pytest.raises(ErroDePublicacao) as erro:
        publicacao.publicar(raiz, ARQUIVOS, None)

    assert erro.value.url == NOVA


def test_erro_do_cli_no_preenchimento_tambem_leva_o_endereco(raiz: Path):
    publicacao = PublicacaoGravada(
        [_criado(NOVA), _resultado(NOVA)],
        [_resultado("boom", is_error=True, subtype="error_during_execution")],
    )

    with pytest.raises(ErroDePublicacao) as erro:
        publicacao.publicar(raiz, ARQUIVOS, None)

    assert erro.value.url == NOVA


def test_criacao_sem_endereco_num_resultado_de_ferramenta_e_erro_sem_url(raiz: Path):
    publicacao = PublicacaoGravada([_texto(NOVA), _resultado(NOVA)])

    with pytest.raises(ErroDePublicacao) as erro:
        publicacao.publicar(raiz, ARQUIVOS, None)

    assert erro.value.url is None


def test_pedido_de_preenchimento_le_lista_e_publica_sem_force(raiz: Path):
    pedido = pedido_de_preenchimento(raiz, ARQUIVOS, URL)

    leitura, listagem, publicar = (pedido.index("action read"), pedido.index("scope files"), pedido.index("action publish"))
    assert leitura < listagem < publicar
    base = raiz.as_posix()
    assert f"root={base}" in pedido and f"file_path={base}/project/deck.json" in pedido
    mapa = pedido.split("files com este mapa ", 1)[1].split(" mais uma", 1)[0]
    assert '"project/slides/fiz.html": "project/slides/fiz.html"' in mapa
    assert "project/deck.json" not in mapa
    assert "null" in pedido[publicar:] and "overwrite_unread" in pedido[publicar:]
    assert "SEM force" in pedido and "\\" not in pedido


def test_pedido_de_criacao_nao_leva_arquivo():
    pedido = pedido_de_criacao()

    assert f"type_url={TIPO_SLIDES}" in pedido and "sem file_path" in pedido and "claude.ai/artifact/Deck" not in pedido


def test_opcoes_haiku_com_artifact_e_read_na_pasta_de_trabalho(raiz: Path):
    publicacao = PublicacaoGravada([_publicado(URL), _resultado(URL)])

    publicacao.publicar(raiz, ARQUIVOS, URL)

    opcoes = publicacao.opcoes[0]
    assert opcoes.model == "haiku"
    assert opcoes.tools == ["Artifact", "Read"] and opcoes.allowed_tools == ["Artifact", "Read"]
    assert Path(opcoes.cwd) == raiz
    assert opcoes.env["CLAUDE_CODE_ARTIFACT"] == "1"

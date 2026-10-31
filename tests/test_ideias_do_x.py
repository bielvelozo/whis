"""A ideia de post do X: os dias, a conferência do tamanho e das regras dele, a nota e o celular."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from whis.api_do_x import NaoSaiu, SemConfirmacao
from whis.ideias_do_x import (
    CAMINHO_DAS_IDEIAS,
    ENVIADA,
    ENVIANDO,
    ESPERANDO,
    INCERTA,
    NAO_ACHEI,
    ROTULO_DO_BOTAO,
    Ideia,
    IdeiaFake,
    do_dia,
    imagens_da_arte,
    ja_usados,
    mensagem_no_celular,
    problemas_da_ideia,
    tamanho_no_x,
    tocou_publicar,
)

SEGUNDA = datetime(2026, 11, 2, 12, 30).astimezone()
TERCA = datetime(2026, 11, 3, 12, 30).astimezone()


class Porta:
    def __init__(self, bruto: dict | None = None) -> None:
        self.bruto = bruto
        self.recebidos: list[list[str]] = []

    def escrever(self, ja_usados, voz, contexto):
        self.recebidos.append(list(ja_usados))
        return self.bruto if self.bruto is not None else IdeiaFake().escrever(ja_usados, voz, contexto)


def _rodar(tmp_path: Path, porta: Porta, agora: datetime = SEGUNDA, forcar: bool = False):
    mandadas: list[str] = []
    resultado = do_dia(
        tmp_path / "vault", porta, estado=tmp_path / "x-ideias.json", avisar=lambda t: mandadas.append(t) is None,
        agora=agora, forcar=forcar,
    )
    return resultado, mandadas


def test_seg_qua_e_sex_sai_uma_ideia_por_dia_com_nota_e_celular(tmp_path: Path) -> None:
    porta = Porta()
    resultado, mandadas = _rodar(tmp_path, porta)
    assert resultado.ideia and resultado.caminho == CAMINHO_DAS_IDEIAS
    nota = (tmp_path / "vault" / CAMINHO_DAS_IDEIAS).read_text(encoding="utf-8")
    assert "## 02/11 · App esquecido pesa na loja" in nota and "velozo.dev/velocidade" in nota
    assert len(mandadas) == 1 and mandadas[0].count("<pre>") == 4
    assert _rodar(tmp_path, porta)[0].ja_feita
    assert _rodar(tmp_path, porta, TERCA)[0].motivo.startswith("hoje não é dia")
    assert len(porta.recebidos) == 1
    estado = json.loads((tmp_path / "x-ideias.json").read_text(encoding="utf-8"))
    assert estado["temas"] == ["App esquecido pesa na loja"]


def test_o_tema_ja_usado_e_os_posts_preparados_vao_ao_claude(tmp_path: Path) -> None:
    pasta = tmp_path / "vault" / "cacada" / "x"
    pasta.mkdir(parents=True)
    (pasta / "posts-semana-1.md").write_text("# Posts\n\n## 1. Portfólio (fixar no perfil)\n\n## 2. Inkly de 11,9 s para 3,5 s\n", encoding="utf-8")
    assert ja_usados(tmp_path / "vault", {"temas": ["Frete na sacola"]}) == [
        "Frete na sacola", "Portfólio (fixar no perfil)", "Inkly de 11,9 s para 3,5 s",
    ]


def test_ideia_fora_das_regras_nao_sai_nem_conta_o_dia(tmp_path: Path) -> None:
    ruim = {"tema": "t", "formato": "post", "posts": ["Check velozo.dev 🙂 I use ChatGPT for every store."], "resposta": ""}
    resultado, mandadas = _rodar(tmp_path, Porta(ruim))
    assert mandadas == [] and resultado.problemas
    assert not (tmp_path / "x-ideias.json").exists()


def test_problemas_contam_o_link_como_23_e_barram_o_que_ele_nao_quer() -> None:
    assert tamanho_no_x("See https://velozo.dev/velocidade/?utm_source=x now") == len("See ") + 23 + len(" now")
    boa = Ideia("t", "post", ("Photos straight from the camera slow a store down on a phone.",), resposta="More: velozo.dev")
    assert problemas_da_ideia(boa) == []
    assert problemas_da_ideia(Ideia("t", "post", ("a" * 281,))) == ["o post 1 passa de 280 caracteres"]
    assert "o post 1 tem link (vai na resposta)" in problemas_da_ideia(Ideia("t", "post", ("More at velozo.dev",)))
    assert "mais de 2 hashtags" in problemas_da_ideia(Ideia("t", "post", ("#a #b #c",)))
    assert "fala do preço dele" in problemas_da_ideia(Ideia("t", "post", ("My rates start low.",)))
    assert "diz que usa IA" in problemas_da_ideia(Ideia("t", "post", ("I build every theme with Claude.",)))
    assert problemas_da_ideia(Ideia("t", "post", ())) == ["sem post"]


def test_o_celular_numera_a_thread_e_escapa_o_html() -> None:
    ideia = Ideia("Tema <b>", "thread", ("one < two", "three"), resposta="r", fonte="https://ex.com", por_que="p", arte="print")
    mensagem = mensagem_no_celular(ideia)
    assert "Tema &lt;b&gt;" in mensagem and "1/2" in mensagem and "<pre>one &lt; two</pre>" in mensagem
    assert "Fonte: https://ex.com" in mensagem and "Imagem: print" in mensagem


def test_o_post_preparado_sai_antes_da_ideia_nova_e_o_publicado_fica_de_fora(tmp_path: Path) -> None:
    pasta = tmp_path / "vault" / "cacada" / "x"
    pasta.mkdir(parents=True)
    (pasta / "posts-semana-1.md").write_text(
        "# Posts\n\n## 1. Portfólio\n\n- Publicado: 31/10\n\n```\nI'm Gabriel.\n```\n\n"
        "## 2. Velocidade\n\nImagem: `velocidade.png`\n\n```\nInkly took 11.9 s.\n```\n\n"
        "Primeira resposta ao próprio post, com o link:\n\n```\nCheck yours: velozo.dev/velocidade\n```\n\n"
        "## 3. Thread\n\n```\nOne.\n```\n\n```\nTwo.\n```\n",
        encoding="utf-8",
    )
    porta = Porta()
    resultado, mandadas = _rodar(tmp_path, porta)
    assert resultado.ideia.tema == "Velocidade" and resultado.ideia.resposta == "Check yours: velozo.dev/velocidade"
    assert resultado.ideia.arte == "`velocidade.png`" and resultado.caminho == "" and porta.recebidos == []
    assert "Check yours" in mandadas[0]
    quarta = datetime(2026, 11, 4, 12, 30).astimezone()
    resultado, _ = _rodar(tmp_path, porta, quarta)
    assert resultado.ideia.tema == "Thread" and resultado.ideia.posts == ("One.", "Two.") and resultado.ideia.formato == "thread"
    sexta = datetime(2026, 11, 6, 12, 30).astimezone()
    resultado, _ = _rodar(tmp_path, porta, sexta)
    assert resultado.ideia.tema == "App esquecido pesa na loja" and len(porta.recebidos) == 1


# -- o toque "Publicar no X" ----------------------------------------------------------------------------

POSTS_PREPARADOS = (
    "# Posts\r\n\r\n## 1. Portfólio\r\n\r\n- Publicado: 31/10\r\n\r\n```\r\nI'm Gabriel.\r\n```\r\n\r\n"
    "## 3. Thread: o que deixa a loja lenta\r\n\r\nImagem: `peso.png`, no primeiro post\r\n\r\n"
    "```\r\nWhat makes a store slow.\r\n```\r\n\r\n```\r\n1. Photos.\r\n```\r\n\r\n```\r\n2. Apps.\r\n```\r\n\r\n"
    "Primeira resposta ao próprio post, com o link:\r\n\r\n```\r\nCheck yours: velozo.dev/velocidade\r\n```\r\n"
)


class XFake:
    """O X de mentira: guarda cada pedido e falha onde o teste mandar."""

    def __init__(self, *, falha_no_post: int | None = None, erro: Exception | None = None, erro_da_imagem: Exception | None = None) -> None:
        self.falha_no_post = falha_no_post
        self.erro = erro
        self.erro_da_imagem = erro_da_imagem
        self.imagens: list[str] = []
        self.posts: list[tuple[str, str | None, tuple[str, ...]]] = []

    def subir_imagem(self, arquivo: Path) -> str:
        if self.erro_da_imagem is not None:
            raise self.erro_da_imagem
        self.imagens.append(arquivo.name)
        return f"m{len(self.imagens)}"

    def postar(self, texto: str, *, responder_a: str | None = None, imagens=()) -> str:
        if self.falha_no_post == len(self.posts) + 1:
            raise self.erro
        self.posts.append((texto, responder_a, tuple(imagens)))
        return f"p{len(self.posts)}"


def _com_post_preparado(tmp_path: Path) -> tuple[str, Path]:
    pasta = tmp_path / "vault" / "cacada" / "x"
    pasta.mkdir(parents=True)
    (pasta / "posts-semana-1.md").write_bytes(POSTS_PREPARADOS.encode("utf-8"))
    artes = tmp_path / "artes"
    artes.mkdir()
    (artes / "peso.png").write_bytes(b"png")
    mandados: list = []
    do_dia(
        tmp_path / "vault", Porta(), estado=tmp_path / "x-ideias.json", agora=SEGUNDA, botao=True,
        avisar=lambda texto, botoes=(): mandados.append(botoes) is None,
    )
    [((rotulo, chave),)] = mandados
    assert rotulo == ROTULO_DO_BOTAO
    return chave, artes


def _tocar(tmp_path: Path, chave: str, artes: Path, x: XFake):
    return tocou_publicar(chave, cliente=x, estado=tmp_path / "x-ideias.json", vault=tmp_path / "vault", artes=artes, agora=SEGUNDA)


def _rascunho(tmp_path: Path, chave: str) -> dict:
    return json.loads((tmp_path / "x-ideias.json").read_text(encoding="utf-8"))["rascunhos"][chave]


def test_o_toque_publica_a_thread_encadeada_com_a_imagem_e_o_link_por_ultimo(tmp_path: Path) -> None:
    chave, artes = _com_post_preparado(tmp_path)
    x = XFake()

    resposta = _tocar(tmp_path, chave, artes, x)

    assert x.imagens == ["peso.png"]
    assert x.posts == [
        ("What makes a store slow.", None, ("m1",)),
        ("1. Photos.", "p1", ()),
        ("2. Apps.", "p2", ()),
        ("Check yours: velozo.dev/velocidade", "p3", ()),
    ]
    assert resposta.texto == "Publiquei no X (4 posts): https://x.com/i/web/status/p1" and resposta.tirar_botao
    salvo = _rascunho(tmp_path, chave)
    assert salvo["situacao"] == ENVIADA and salvo["ids"] == ["p1", "p2", "p3", "p4"]
    nota = (tmp_path / "vault" / "cacada" / "x" / "posts-semana-1.md").read_bytes().decode("utf-8")
    assert "## 3. Thread: o que deixa a loja lenta\r\n\r\n- Publicado: 02/11\r\n\r\nImagem:" in nota
    assert "\n" not in nota.replace("\r\n", "")


def test_nota_que_nao_abre_nao_estraga_a_resposta_do_que_ja_saiu(tmp_path: Path, caplog) -> None:
    chave, artes = _com_post_preparado(tmp_path)
    (tmp_path / "vault" / "cacada" / "x" / "posts-0.md").mkdir()

    resposta = _tocar(tmp_path, chave, artes, XFake())

    assert resposta.texto.startswith("Publiquei no X") and _rascunho(tmp_path, chave)["situacao"] == ENVIADA
    assert "não marquei" in caplog.text


def test_o_segundo_toque_nao_publica_de_novo(tmp_path: Path) -> None:
    chave, artes = _com_post_preparado(tmp_path)
    _tocar(tmp_path, chave, artes, XFake())
    x = XFake()

    resposta = _tocar(tmp_path, chave, artes, x)

    assert "já está no X" in resposta.texto and resposta.tirar_botao and x.posts == [] and x.imagens == []


def test_recusa_no_primeiro_post_nao_publicou_nada_e_deixa_tocar_de_novo(tmp_path: Path) -> None:
    chave, artes = _com_post_preparado(tmp_path)

    resposta = _tocar(tmp_path, chave, artes, XFake(falha_no_post=1, erro=NaoSaiu("HTTP 402: Your credits are depleted")))

    assert resposta.texto == "Não publiquei: HTTP 402: Your credits are depleted." and not resposta.tirar_botao
    assert _rascunho(tmp_path, chave)["situacao"] == ESPERANDO
    x = XFake()
    assert _tocar(tmp_path, chave, artes, x).texto.startswith("Publiquei no X") and len(x.posts) == 4


def test_primeiro_post_sem_confirmacao_vira_incerta_e_nunca_repete(tmp_path: Path) -> None:
    chave, artes = _com_post_preparado(tmp_path)

    resposta = _tocar(tmp_path, chave, artes, XFake(falha_no_post=1, erro=SemConfirmacao("a conexão caiu no meio (ReadTimeout)")))

    assert "não confirmou" in resposta.texto and "confira no perfil" in resposta.texto and resposta.tirar_botao
    assert _rascunho(tmp_path, chave)["situacao"] == INCERTA
    x = XFake()
    assert "não confirmou" in _tocar(tmp_path, chave, artes, x).texto and x.posts == []
    assert "- Publicado: 02/11" not in (tmp_path / "vault" / "cacada" / "x" / "posts-semana-1.md").read_text(encoding="utf-8")


def test_thread_que_para_no_meio_diz_quantos_sairam_e_marca_o_publicado(tmp_path: Path) -> None:
    chave, artes = _com_post_preparado(tmp_path)

    resposta = _tocar(tmp_path, chave, artes, XFake(falha_no_post=3, erro=NaoSaiu("HTTP 429: Too Many Requests")))

    assert resposta.texto.startswith("Saíram 2 de 4 (https://x.com/i/web/status/p1); o 3º não saiu") and resposta.tirar_botao
    assert "HTTP 429" in resposta.texto and "termine à mão" in resposta.texto
    salvo = _rascunho(tmp_path, chave)
    assert salvo["situacao"] == INCERTA and salvo["ids"] == ["p1", "p2"]
    assert "- Publicado: 02/11" in (tmp_path / "vault" / "cacada" / "x" / "posts-semana-1.md").read_text(encoding="utf-8")


def test_processo_que_morreu_no_meio_conta_como_nao_confirmado(tmp_path: Path) -> None:
    chave, artes = _com_post_preparado(tmp_path)
    estado = json.loads((tmp_path / "x-ideias.json").read_text(encoding="utf-8"))
    estado["rascunhos"][chave]["situacao"] = ENVIANDO
    (tmp_path / "x-ideias.json").write_text(json.dumps(estado), encoding="utf-8")
    x = XFake()

    assert "não confirmou" in _tocar(tmp_path, chave, artes, x).texto and x.posts == []


def test_imagem_que_falta_ou_nao_sobe_nao_publica_nada(tmp_path: Path) -> None:
    chave, artes = _com_post_preparado(tmp_path)
    (artes / "peso.png").unlink()
    x = XFake()

    resposta = _tocar(tmp_path, chave, artes, x)

    assert resposta.texto == f"Não publiquei: falta peso.png em {artes}." and x.posts == [] and not resposta.tirar_botao
    (artes / "peso.png").write_bytes(b"png")
    resposta = _tocar(tmp_path, chave, artes, XFake(erro_da_imagem=SemConfirmacao("HTTP 503")))
    assert resposta.texto.startswith("Não publiquei: a imagem não subiu (HTTP 503)")
    assert _rascunho(tmp_path, chave)["situacao"] == ESPERANDO


def test_a_ideia_nova_do_claude_vai_sem_imagem_e_sem_botao_sem_as_chaves(tmp_path: Path) -> None:
    mandadas: list = []
    do_dia(
        tmp_path / "vault", Porta(), estado=tmp_path / "x-ideias.json", agora=SEGUNDA,
        avisar=lambda texto, **opcoes: mandadas.append(opcoes) is None,
    )
    assert mandadas == [{}]
    [(chave, rascunho)] = json.loads((tmp_path / "x-ideias.json").read_text(encoding="utf-8"))["rascunhos"].items()
    assert rascunho["imagens"] == [] and rascunho["preparada"] is False and rascunho["situacao"] == ESPERANDO
    x = XFake()
    resposta = _tocar(tmp_path, chave, tmp_path / "sem-artes", x)
    assert resposta.texto == "Publiquei no X (4 posts): https://x.com/i/web/status/p1"
    assert x.imagens == [] and x.posts[-1] == ("Want to see how much your store weighs on a phone? velozo.dev/velocidade", "p3", ())


def test_toque_desconhecido_e_as_imagens_da_linha_imagem() -> None:
    assert tocou_publicar("xpost:nada", cliente=XFake(), estado=Path("nao-existe.json"), vault=Path("."), artes=Path(".")).texto == NAO_ACHEI
    assert imagens_da_arte("`portfolio-1.png`, `portfolio-2.png`, `portfolio-1.png`, `a.jpg`, `b.webp`") == (
        "portfolio-1.png", "portfolio-2.png", "a.jpg", "b.webp",
    )
    assert imagens_da_arte("Print do theme.liquid com o snippet esquecido.") == ()


def test_o_toque_sem_as_chaves_de_x_nao_tenta_publicar(tmp_path: Path) -> None:
    from whis.__main__ import _tocou_no_celular
    from whis.configuracao import Configuracao

    resposta = _tocou_no_celular(Configuracao(vault=tmp_path), "xpost:abc")

    assert resposta.texto == "Não publiquei: faltam as chaves de [x] no config.toml."


def test_problemas_pegam_encurtador_bandeira_preco_em_dolar_e_ia_na_primeira_pessoa() -> None:
    def barra(texto: str) -> list[str]:
        return problemas_da_ideia(Ideia("t", "post", (texto,)))

    for link in ("Grab the checklist at bit.ly/bf-shopify", "All my links: linktr.ee/velozo", "Try it at velozo.shop today"):
        assert "o post 1 tem link (vai na resposta)" in barra(link)
    assert tamanho_no_x("bit.ly/abcdefghijklmnopqrstuvwxyz0123456789") == 23
    assert "tem emoji" in barra("Black Friday is close 🇺🇸 get ready.")
    assert "tem emoji" in barra("Five tips ⭐ for your product page.")
    assert "fala do preço dele" in barra("Our stores start at $400 for a full theme.")
    assert "fala do preço dele" in barra("Full store from US$ 300, theme included.")
    assert "diz que usa IA" in barra("My AI workflow cuts build time in half.")
    assert barra("Shopify merchants sold $11.5 billion over Black Friday weekend last year.") == []

"""A vigia do X: as buscas da nota, o filtro de quem oferece, a hora de ler, as travas do rascunho e a rodada."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs

from whis import vigia_do_x
from whis.configuracao import carregar_texto
from whis.fonte_x import ErroDoX, LeituraDoX, LoginDoXVenceu, PostDoX
from whis.propostas_auto import Contexto
from whis.vigia_do_x import DM, RESPOSTA, Busca, Rascunho, ler_buscas, mensagem_no_celular, na_hora, oferece_servico, problemas, rodar
from whis.vigia_do_x_claude import interpretar

AGORA = datetime(2026, 10, 31, 15, 5, tzinfo=UTC)
CONTEXTO = Contexto(procuro="Shopify.", sobre_mim="- Inglês: intermediário", perfil="Full stack.", portfolio=(), exemplos=())
BUSCAS = (Busca("Dev EN", '"looking for a shopify developer"'),)
BOA = (
    "Hey Maya, I'm Gabriel, I build Shopify stores. Moving the candle shop off Etsy before Black Friday works if "
    "products and reviews come over first. Want me to send you how I'd plan it?"
)


def post(autor: str = "maya_candles", status: int = 1, *, horas: float = 2, texto: str = "") -> PostDoX:
    return PostDoX(
        link=f"https://x.com/{autor}/status/{status}",
        autor=autor,
        texto=texto or "Looking for someone to move my candle shop from Etsy to Shopify before Black Friday. Who do you recommend?",
        data=AGORA - timedelta(hours=horas),
    )


class LeitorFake:
    def __init__(self, *posts: PostDoX, erro: Exception | None = None) -> None:
        self.posts = posts
        self.erro = erro
        self.fontes: list = []

    def ler(self, fontes, hoje: date) -> LeituraDoX:
        self.fontes = list(fontes)
        if self.erro is not None:
            raise self.erro
        return LeituraDoX(posts={"Dev EN": self.posts}, falhas={"PT": "tempo esgotado"})


class EscritorFake:
    def __init__(self, texto: str = BOA, tipo: str = RESPOSTA) -> None:
        self.texto = texto
        self.tipo = tipo
        self.recebidos: list[PostDoX] = []

    def escrever(self, posts, contexto, voz):
        self.recebidos += posts
        return [Rascunho(vigia_do_x.id_do_post(p), self.tipo, self.texto, "Pede migração.") for p in posts]


class Celular(list):
    """As mensagens que chegariam ao celular; `botoes` guarda os botões de cada uma."""

    def __init__(self) -> None:
        super().__init__()
        self.botoes: list[tuple] = []

    def __call__(self, texto: str, botoes=()) -> bool:
        self.append(texto)
        self.botoes.append(tuple(botoes))
        return True


def _rodar(
    tmp_path: Path, leitor: LeitorFake, escritor: EscritorFake | None = None, *, por_dia: int = 5, agora: datetime = AGORA, botao: bool = True
):
    mandadas = Celular()
    rodada = rodar(
        BUSCAS,
        leitor=leitor,
        escritor=escritor or EscritorFake(),
        contexto=CONTEXTO,
        voz="",
        estado=tmp_path / "x.json",
        celular=mandadas,
        por_dia=por_dia,
        agora=agora,
        botao=botao,
    )
    return rodada, mandadas


def test_as_buscas_saem_da_nota_com_nome_e_consulta(tmp_path: Path) -> None:
    nota = tmp_path / vigia_do_x.CAMINHO_DAS_BUSCAS
    nota.parent.mkdir(parents=True)
    nota.write_text(
        "# Buscas\n\nTexto solto.\n\n"
        '- Dev EN: ("looking for a shopify developer" OR "need a shopify developer")\n'
        "- Loja PT: `(\"preciso de alguém\" shopify) lang:pt`\n",
        encoding="utf-8",
    )
    assert ler_buscas(tmp_path) == (
        Busca("Dev EN", '("looking for a shopify developer" OR "need a shopify developer")'),
        Busca("Loja PT", '("preciso de alguém" shopify) lang:pt'),
    )
    assert ler_buscas(tmp_path / "nada") == ()


def test_quem_oferece_servico_fica_de_fora_e_quem_contrata_fica() -> None:
    ofertas = [
        "Need a Shopify developer? I build high-converting stores in 7 days.",
        "I'm a freelance Shopify developer, open for work this month.",
        "Looking for a Shopify expert?\nLook no further, check my profile.",
        "We design Shopify stores that convert. Hire me!",
        "Faço sua loja Shopify completa, orçamento sem compromisso.",
    ]
    contratos = [
        "Looking for a Shopify developer to fix our cart drawer, budget available, DM me your portfolio.",
        "Paid gig: need a Shopify dev to speed up our store. Of course remote is fine.",
        "I design jewelry and need someone to build my Shopify store. Any recommendations?",
        "Preciso de alguém pra montar minha loja na Shopify, quem souber me chama.",
    ]
    assert all(oferece_servico(post(texto=t)) for t in ofertas)
    assert not any(oferece_servico(post(texto=t)) for t in contratos)
    assert oferece_servico(post(autor="ShopifyGuruDev", texto=contratos[0]))


def test_le_das_9_as_22_e_3_horas_depois_da_ultima_leitura(tmp_path: Path) -> None:
    estado = tmp_path / "x.json"
    local = datetime(2026, 10, 31, 9, 4).astimezone()
    assert na_hora(estado, local)
    assert not na_hora(estado, local.replace(hour=8))
    assert not na_hora(estado, local.replace(hour=23))
    estado.write_text(json.dumps({"ultima_leitura": local.isoformat()}), encoding="utf-8")
    assert not na_hora(estado, local + timedelta(hours=2))
    assert na_hora(estado, local + timedelta(hours=2, minutes=50))


def test_post_novo_vira_rascunho_no_celular_com_link_e_texto_no_pre(tmp_path: Path) -> None:
    leitor = LeitorFake(post())
    rodada, mandadas = _rodar(tmp_path, leitor)
    assert leitor.fontes[0].tipo == "recentes"
    assert [d["link"] for d in rodada.rascunhos] == ["https://x.com/maya_candles/status/1"]
    assert rodada.falhas == ("PT: tempo esgotado",)
    assert len(mandadas) == 1
    assert "https://x.com/maya_candles/status/1" in mandadas[0]
    assert f"<pre>{BOA}</pre>" in mandadas[0]
    assert "@maya_candles · há 2 h · responder no post" in mandadas[0]
    salvo = json.loads((tmp_path / "x.json").read_text(encoding="utf-8"))
    assert salvo["ultima_leitura"] and "1" in salvo["vistos"] and "maya_candles" in salvo["autores"]


def test_a_resposta_chega_com_o_link_que_abre_o_x_pronto_e_a_dm_sem_botao(tmp_path: Path) -> None:
    _, mandadas = _rodar(tmp_path, LeitorFake(post()))
    [(rotulo, link)] = mandadas.botoes[0]
    endereco, consulta = link.split("?", 1)
    assert rotulo == "Responder no X" and endereco == "https://x.com/intent/tweet"
    assert parse_qs(consulta) == {"in_reply_to": ["1"], "text": [BOA]}
    assert "+" not in consulta and "%20" in consulta

    _, mandadas = _rodar(tmp_path / "dm", LeitorFake(post()), EscritorFake(texto="Hey Maya, want me to send you a plan?", tipo=DM))
    assert len(mandadas) == 1 and mandadas.botoes == [()]


def test_o_botao_desligado_no_config_deixa_so_o_texto_para_copiar(tmp_path: Path) -> None:
    _, mandadas = _rodar(tmp_path, LeitorFake(post()), botao=False)
    assert mandadas.botoes == [()] and f"<pre>{BOA}</pre>" in mandadas[0]
    vault = f'vault = "{(tmp_path / "vault").as_posix()}"\n'
    assert carregar_texto(vault, origem=tmp_path / "config.toml").cacada_x_botao_responder is True
    desligado = carregar_texto(vault + "[cacada]\nx_botao_responder = false\n", origem=tmp_path / "config.toml")
    assert desligado.cacada_x_botao_responder is False


def test_visto_velho_curto_oferta_e_autor_da_semana_nao_vao_ao_claude(tmp_path: Path) -> None:
    _rodar(tmp_path, LeitorFake(post()))
    escritor = EscritorFake()
    _rodar(
        tmp_path,
        LeitorFake(
            post(status=1),
            post(autor="velho", status=2, horas=60),
            post(autor="curto", status=3, texto="need shopify dev"),
            post(autor="oferta", status=4, texto="Need a Shopify developer? I build stores in 3 days, DM me."),
            post(status=5),
            post(autor="novo", status=6),
        ),
        escritor,
        agora=AGORA + timedelta(hours=3),
    )
    assert [p.autor for p in escritor.recebidos] == ["novo"]


def test_a_cota_do_dia_para_os_rascunhos_e_a_leitura(tmp_path: Path) -> None:
    rodada, mandadas = _rodar(tmp_path, LeitorFake(post(), post(autor="b", status=2), post(autor="c", status=3)), por_dia=2)
    assert len(rodada.rascunhos) == 2 and len(mandadas) == 2
    leitor = LeitorFake(post(autor="d", status=4))
    rodada, _ = _rodar(tmp_path, leitor, por_dia=2, agora=AGORA + timedelta(hours=3))
    assert rodada.parou and leitor.fontes == []


def test_rascunho_fora_do_jeito_nao_chega_ao_celular(tmp_path: Path) -> None:
    rodada, mandadas = _rodar(tmp_path, LeitorFake(post()), EscritorFake(texto="Check velozo.dev, I can do it for $300?"))
    assert rodada.rascunhos == () and mandadas == []


def test_login_vencido_avisa_uma_vez_por_dia_e_espera_3_horas_para_abrir_o_chrome_de_novo(tmp_path: Path) -> None:
    rodada, mandadas = _rodar(tmp_path, LeitorFake(erro=LoginDoXVenceu("o X pediu login")))
    assert rodada.parou == "o X pediu login" and "x-login" in mandadas[0]
    assert not na_hora(tmp_path / "x.json", AGORA + timedelta(hours=1))
    _, mandadas = _rodar(tmp_path, LeitorFake(erro=LoginDoXVenceu("o X pediu login")), agora=AGORA + timedelta(hours=3))
    assert mandadas == []


def test_perfil_ocupado_nao_marca_a_leitura_e_tenta_na_hora_seguinte(tmp_path: Path) -> None:
    rodada, _ = _rodar(tmp_path, LeitorFake(erro=ErroDoX("o perfil do X está em uso por outro processo")))
    assert "em uso" in rodada.parou
    assert not (tmp_path / "x.json").exists()


def test_problemas_barram_tamanho_link_preco_ia_emoji_call_e_fim_sem_pergunta() -> None:
    p = post()
    assert problemas(Rascunho("1", RESPOSTA, BOA), p) == []
    assert problemas(Rascunho("1", RESPOSTA, "Hey " + "a" * 280 + "?"), p) == ["passa de 280 caracteres"]
    assert problemas(Rascunho("1", DM, "Hey " + "a" * 400 + "?"), p) == []
    assert "tem link (o velozo.dev fica no perfil)" in problemas(Rascunho("1", RESPOSTA, "See velozo.dev?"), p)
    assert "fala de preço" in problemas(Rascunho("1", RESPOSTA, "I can do it for $300?"), p)
    assert "fala de preço" in problemas(Rascunho("1", RESPOSTA, "Faço por R$ 400?"), p)
    assert problemas(Rascunho("1", RESPOSTA, "I use AI to go fast. Want an idea?"), p) == ["diz que usa IA"]
    assert "cita IA sem o post falar de IA" in problemas(Rascunho("1", RESPOSTA, "Hey, AI could write the copy. Want an idea?"), p)
    assert "tem emoji" in problemas(Rascunho("1", RESPOSTA, "Hey 🙂 want an idea?"), p)
    assert "pede call" in problemas(Rascunho("1", RESPOSTA, "Hey, quick call tomorrow?"), p)
    assert "não termina em pergunta" in problemas(Rascunho("1", RESPOSTA, "Hey, I can help."), p)
    assert "tem hashtag" in problemas(Rascunho("1", RESPOSTA, "Hey #shopify want an idea?"), p)


def test_o_celular_corta_o_post_longo_e_escapa_o_html() -> None:
    dados = {
        "link": "https://x.com/a/status/1", "autor": "a", "post": "<b>" + "x" * 500, "postado": (AGORA - timedelta(minutes=20)).isoformat(),
        "tipo": DM, "texto": "Hey <you>?", "motivo": "Pede DM.",
    }
    mensagem = mensagem_no_celular(dados, AGORA)
    assert "agora há pouco · mandar por DM" in mensagem
    assert "&lt;b&gt;" in mensagem and "…" in mensagem
    assert "<pre>Hey &lt;you&gt;?</pre>" in mensagem


def test_o_claude_devolve_so_o_que_tem_forma() -> None:
    assert interpretar(None) == []
    assert interpretar([{"post": " 1 ", "tipo": "resposta", "texto": " Oi? ", "motivo": "m"}, "lixo"]) == [
        Rascunho("1", "resposta", "Oi?", "m")
    ]


def test_a_configuracao_le_o_x_por_dia(tmp_path: Path) -> None:
    vault = f'vault = "{(tmp_path / "vault").as_posix()}"\n'
    assert carregar_texto(vault, origem=tmp_path / "config.toml").cacada_x_por_dia == 5
    assert carregar_texto(vault + "[cacada]\nx_por_dia = 0\n", origem=tmp_path / "config.toml").cacada_x_por_dia == 0


def test_toda_busca_falhando_avisa_uma_vez_por_dia(tmp_path: Path) -> None:
    class SoFalhas(LeitorFake):
        def ler(self, fontes, hoje):
            return LeituraDoX(falhas={"Dev EN": "a página do X mudou"})

    rodada, mandadas = _rodar(tmp_path, SoFalhas())
    assert rodada.lidos == 0 and len(mandadas) == 1 and "nenhuma busca" in mandadas[0]
    _, mandadas = _rodar(tmp_path, SoFalhas(), agora=AGORA + timedelta(hours=3))
    assert mandadas == []


def test_a_busca_da_vigia_abre_mais_recentes_e_a_tela_de_entrar_e_login_vencido() -> None:
    from urllib.parse import parse_qs, urlsplit

    from whis.fonte_x import pede_login, url_da_busca

    assert parse_qs(urlsplit(url_da_busca('"shopify developer"', date(2026, 10, 31), recentes=True)).query)["f"] == ["live"]
    assert parse_qs(urlsplit(url_da_busca('"shopify developer"', date(2026, 10, 31))).query)["f"] == ["top"]
    assert pede_login('<div role="dialog"><input autocomplete="username webauthn" name="username_or_email"></div>')
    assert not pede_login('<article data-testid="tweet"><input type="text" name="q"></article>')


def test_problemas_pegam_bandeira_encurtador_moeda_antes_calls_e_quem_diz_que_usa_ia() -> None:
    p = post()
    sobre_ia = post(texto="Looking for a Shopify dev to add an AI chatbot to our store, paid gig.")
    base = "Hey, I'm Gabriel, I build Shopify stores. "
    assert "tem emoji" in problemas(Rascunho("1", RESPOSTA, base + "\U0001F1E7\U0001F1F7 Want an idea?"), p)
    assert "tem emoji" in problemas(Rascunho("1", RESPOSTA, base + "\u2b50 Want an idea?"), p)
    for link in ("bit.ly/abc", "linktr.ee/velozo", "velozo.org", "discord.gg/abc"):
        assert "tem link (o velozo.dev fica no perfil)" in problemas(Rascunho("1", RESPOSTA, f"{base}See {link}. Want an idea?"), p)
    for preco in ("USD 300 flat", "30/h", "30 an hour"):
        assert "fala de preço" in problemas(Rascunho("1", RESPOSTA, f"{base}{preco} works. Want an idea?"), p)
    assert "pede call" in problemas(Rascunho("1", RESPOSTA, base + "Happy to jump on calls. Want an idea?"), p)
    assert "diz que usa IA" in problemas(Rascunho("1", RESPOSTA, base + "I use AI to build faster. Want an idea?"), sobre_ia)
    assert problemas(Rascunho("1", RESPOSTA, base + "I'd hook the AI chatbot into the cart drawer. Want an idea?"), sobre_ia) == []
    em_portugues = "Oi, tudo certo? Aqui é o Gabriel, faço lojas Shopify. Eu ia sugerir trazer os produtos antes. Posso te mandar uma ideia?"
    assert problemas(Rascunho("1", RESPOSTA, em_portugues), p) == []


def test_o_mesmo_autor_recebe_um_rascunho_so_na_rodada(tmp_path: Path) -> None:
    rodada, mandadas = _rodar(tmp_path, LeitorFake(post(status=1), post(status=2, horas=3)))
    assert [d["link"] for d in rodada.rascunhos] == ["https://x.com/maya_candles/status/1"] and len(mandadas) == 1

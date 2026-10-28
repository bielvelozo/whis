import json
from datetime import date, datetime, timedelta, timezone
from email import message_from_bytes, policy
from pathlib import Path

import pytest

from whis import sequencia_fria
from whis.sequencia_fria import (
    ANTIGA,
    CONVERSA,
    DIRETO,
    NOVA,
    Conta,
    Contas,
    Enviada,
    ErroDoEmail,
    Recebida,
)

BRT = timezone(timedelta(hours=-3))
TERCA = datetime(2026, 11, 3, 9, 0, tzinfo=BRT)
SABADO = datetime(2026, 10, 31, 10, 0, tzinfo=BRT)
CONTAS = Contas(Conta(NOVA, "gabriel@velozo.dev", "nova"), Conta(ANTIGA, "eu@gmail.com", "antiga"))
LINK_KIND = "https://velozo.dev/br/?r=kind&utm_source=email&utm_medium=frio&utm_campaign=2026-11&utm_content=conversa"
PRIMEIRO = (
    "Oi, pessoal da KIND, tudo certo?\n\n"
    "Aqui é o Gabriel, faço lojas Shopify. Dei uma olhada na loja de vocês pelo celular e reparei que a página "
    "inicial demora para aparecer: no 4G, a imagem principal levou 9 segundos.\n\n"
    "Trabalho com e-commerce há mais de 3 anos, com otimização e redesign, e agora tô me especializando em Shopify. "
    f"Dá uma olhada no meu portfólio: {LINK_KIND}\n\n"
    "Posso te mandar uma ideia do que eu mudaria?\n\n"
    "Abraço,\nGabriel"
)
SEGUNDO = (
    "Oi, pessoal da KIND, tudo certo?\n\n"
    "Pensei numa coisa para a página inicial de vocês: dá para fazer a imagem do topo chegar primeiro e o resto vir "
    "depois, sem mudar nada no visual.\n\n"
    "Posso te mandar como ficaria?\n\n"
    "Abraço,\nGabriel"
)
TERCEIRO = (
    "Oi, pessoal da KIND, tudo certo?\n\n"
    f"Juntei no meu portfólio umas lojas em que mexi na velocidade: {LINK_KIND}\n\n"
    "Se não for o momento, é só responder 'não' que eu não escrevo mais.\n\n"
    "Abraço,\nGabriel"
)


class Carteiro(list):
    def __call__(self, conta, mensagem):
        self.append((conta, mensagem))


class Eventos(list):
    def __call__(self, evento, codigo, propriedades):
        self.append((evento, codigo, propriedades))


class Celular(list):
    def __call__(self, texto, **opcoes):
        self.append((texto, opcoes))
        return True


class Escritor:
    def __init__(self, *corpos):
        self.corpos = list(corpos)
        self.pedidos = []

    def escrever(self, pedido, *, corrigir=""):
        self.pedidos.append((pedido, corrigir))
        return self.corpos.pop(0)


def _entregar(estado, email="hello@kindbeauty.com.br", passo=1, corpo=PRIMEIRO, agora=TERCA, por_dia=10, **extra):
    carteiro, eventos = extra.pop("carteiro", Carteiro()), extra.pop("eventos", Eventos())
    aviso = sequencia_fria.entregar(
        estado, email, passo, "KIND", corpo, contas=CONTAS, carteiro=carteiro, eventos=eventos, por_dia=por_dia, agora=agora, **extra
    )
    return aviso, carteiro, eventos


def _rodada(tmp_path, estado, *, recebidas=(), enviadas=(), escritor=None, agora=TERCA, por_dia=10):
    carteiro, eventos, celular = Carteiro(), Eventos(), Celular()
    feito = sequencia_fria.rodada(
        tmp_path / "vault",
        estado=estado,
        contas=CONTAS,
        carteiro=carteiro,
        leitor=lambda conta, desde: [r for qual, r in recebidas if qual == conta.qual],
        leitor_dos_enviados=lambda conta, desde: [e for qual, e in enviadas if qual == conta.qual],
        eventos=eventos,
        celular=celular,
        escritor=escritor or Escritor(),
        por_dia=por_dia,
        agora=agora,
    )
    return feito, carteiro, eventos, celular


def _bruto(cabecalhos: dict, texto: str = "Oi") -> bytes:
    linhas = [f"{k}: {v}" for k, v in cabecalhos.items()]
    return ("\r\n".join([*linhas, "Content-Type: text/plain; charset=utf-8", "", texto]) + "\r\n").encode("utf-8")


# -- código, variante e link -----------------------------------------------------------------------


def test_a_variante_alterna_e_o_codigo_e_o_slug_sem_repetir(tmp_path: Path):
    estado = tmp_path / "s.json"

    a = sequencia_fria.reservar(estado, "a@kind.com.br", "KIND", "loja", TERCA)
    b = sequencia_fria.reservar(estado, "b@outra.com.br", "KIND", "loja", TERCA)
    c = sequencia_fria.reservar(estado, "c@nori.com.br", "Casa Nori", "loja", TERCA)
    de_novo = sequencia_fria.reservar(estado, "A@kind.com.br", "KIND", "loja", TERCA)

    assert [a.variante, b.variante, c.variante] == [CONVERSA, DIRETO, CONVERSA]
    assert [a.codigo, b.codigo, c.codigo] == ["kind", "kind-2", "casa-nori"]
    assert de_novo == a
    assert a.link == LINK_KIND


def test_sem_estado_a_reserva_e_conversa_e_nao_guarda(tmp_path: Path):
    reserva = sequencia_fria.reservar(None, "a@kind.com.br", "KIND", "loja", TERCA)

    assert reserva.variante == CONVERSA and reserva.link == LINK_KIND and list(tmp_path.iterdir()) == []


# -- a mensagem ------------------------------------------------------------------------------------


def test_o_reenvio_entra_na_conversa_e_o_html_so_tem_paragrafos():
    mensagem = sequencia_fria.montar(
        "gabriel@velozo.dev", "hello@kind.com.br", "Re: KIND", PRIMEIRO, message_id="<3@velozo.dev>", anteriores=["<1@x>", "<2@x>"]
    )

    html = mensagem.get_body(("html",)).get_content()
    assert mensagem["Message-ID"] == "<3@velozo.dev>"
    assert mensagem["In-Reply-To"] == "<2@x>" and mensagem["References"] == "<1@x> <2@x>"
    assert mensagem["From"] == "Gabriel Velozo <gabriel@velozo.dev>"
    assert f'<a href="{LINK_KIND.replace("&", "&amp;")}">velozo.dev</a>' in html
    assert "<img" not in html and "style=" not in html and html.count("<p>") == 5
    assert LINK_KIND in mensagem.get_body(("plain",)).get_content()


def test_o_primeiro_nao_tem_cabecalho_de_conversa():
    mensagem = sequencia_fria.montar("a@b.dev", "c@d.com", "KIND", PRIMEIRO, message_id="<1@b.dev>")

    assert mensagem["In-Reply-To"] is None and mensagem["References"] is None


# -- a janela, o teto e a fila ---------------------------------------------------------------------


def test_na_janela_sai_agora_com_o_message_id_guardado_e_o_evento(tmp_path: Path):
    estado = tmp_path / "s.json"
    sequencia_fria.reservar(estado, "hello@kindbeauty.com.br", "KIND", "loja", TERCA)

    aviso, carteiro, eventos = _entregar(estado)

    (conta, mensagem), = carteiro
    alvo = sequencia_fria.ler(estado)["alvos"]["hello@kindbeauty.com.br"]
    assert aviso == "" and conta.qual == NOVA and mensagem["To"] == "hello@kindbeauty.com.br"
    assert alvo["situacao"] == "ativa" and alvo["enviados"][0]["message_id"] == mensagem["Message-ID"]
    assert mensagem["Message-ID"].endswith("@velozo.dev>")
    assert eventos == [
        ("email_enviado", "kind", {"variante": CONVERSA, "tipo": "novo", "segmento": "loja", "passo": 1, "assunto": "KIND"})
    ]


def test_fora_da_janela_fica_na_fila_e_diz_quando_sai(tmp_path: Path):
    estado = tmp_path / "s.json"

    aviso, carteiro, eventos = _entregar(estado, agora=SABADO)

    assert carteiro == [] and eventos == []
    assert aviso == "Ficou na fila e sai terça, 03/11, a partir das 08:00."
    assert sequencia_fria.ler(estado)["alvos"]["hello@kindbeauty.com.br"]["fila"]["passo"] == 1


def test_o_teto_do_dia_vale_so_para_a_caixa_nova(tmp_path: Path):
    estado = tmp_path / "s.json"
    _entregar(estado, "a@um.com.br", por_dia=1)
    memoria = sequencia_fria.ler(estado)
    memoria["alvos"]["b@dois.com.br"] = {**memoria["alvos"]["a@um.com.br"], "codigo": "dois", "conta": ANTIGA, "enviados": []}
    sequencia_fria.guardar(estado, memoria)

    nova, carteiro_nova, _ = _entregar(estado, "c@tres.com.br", por_dia=1)
    antiga, carteiro_antiga, _ = _entregar(estado, "b@dois.com.br", por_dia=1)

    assert carteiro_nova == [] and nova == "Ficou na fila e sai quarta, 04/11, a partir das 08:00."
    assert antiga == "" and carteiro_antiga[0][0].qual == ANTIGA


def test_sem_a_conta_antiga_no_config_nao_manda(tmp_path: Path):
    estado = tmp_path / "s.json"
    sequencia_fria.guardar(
        estado,
        {"alvos": {"x@y.com.br": {"nome": "Y", "codigo": "y", "variante": CONVERSA, "campanha": "2026-10", "conta": ANTIGA, "situacao": "ativa", "enviados": []}}, "lidas": {}},
    )

    with pytest.raises(ErroDoEmail, match="email_antigo"):
        sequencia_fria.entregar(
            estado, "x@y.com.br", 3, "", TERCEIRO, contas=Contas(CONTAS.nova), carteiro=Carteiro(), eventos=Eventos(), por_dia=10, agora=TERCA
        )


def test_a_rodada_manda_a_fila_na_janela_ate_tres_por_conta(tmp_path: Path):
    estado = tmp_path / "s.json"
    for n in range(4):
        _entregar(estado, f"loja{n}@loja{n}.com.br", agora=SABADO + timedelta(minutes=n))

    feito, carteiro, eventos, _ = _rodada(tmp_path, estado)

    assert feito.enviados == ["loja0@loja0.com.br", "loja1@loja1.com.br", "loja2@loja2.com.br"]
    assert len(carteiro) == 3 and len(eventos) == 3
    assert "fila" in sequencia_fria.ler(estado)["alvos"]["loja3@loja3.com.br"]


def test_a_proxima_janela_pula_para_o_dia_seguinte_quando_hoje_passou():
    quinta_tarde = datetime(2026, 11, 5, 14, 0, tzinfo=BRT)

    assert sequencia_fria.proxima_janela(quinta_tarde) == datetime(2026, 11, 10, 8, 0, tzinfo=BRT)
    assert sequencia_fria.proxima_janela(TERCA) == TERCA


# -- as respostas ----------------------------------------------------------------------------------


def _enviado(estado):
    _entregar(estado, agora=TERCA - timedelta(days=7))
    return sequencia_fria.ler(estado)["alvos"]["hello@kindbeauty.com.br"]["enviados"][0]["message_id"]


def test_a_resposta_para_a_sequencia_registra_e_avisa(tmp_path: Path):
    estado = tmp_path / "s.json"
    sequencia_fria.reservar(estado, "hello@kindbeauty.com.br", "KIND", "agencia", TERCA)
    message_id = _enviado(estado)
    resposta = Recebida("<r1@kind>", "marina@kindbeauty.com.br", "Re: KIND", (message_id,), quando=TERCA - timedelta(days=1))

    feito, _, eventos, celular = _rodada(tmp_path, estado, recebidas=[(NOVA, resposta)])

    assert feito.respostas == ["hello@kindbeauty.com.br"]
    assert sequencia_fria.ler(estado)["alvos"]["hello@kindbeauty.com.br"]["situacao"] == "respondeu"
    assert eventos == [("email_respondido", "kind", {"variante": CONVERSA, "passo": 1, "segmento": "agencia"})]
    assert "respondeu" in celular[0][0]


def test_a_resposta_automatica_nao_para_a_sequencia(tmp_path: Path):
    estado = tmp_path / "s.json"
    message_id = _enviado(estado)
    automatica = Recebida("<a1@kind>", "fin@kindbeauty.com.br", "Re: KIND", (message_id,), automatica=True)

    feito, _, eventos, _ = _rodada(tmp_path, estado, recebidas=[(NOVA, automatica)])

    alvo = sequencia_fria.ler(estado)["alvos"]["hello@kindbeauty.com.br"]
    assert feito.respostas == [] and eventos == [] and alvo["situacao"] == "ativa" and alvo["automaticas"] == 1


def test_a_devolucao_marca_que_voltou(tmp_path: Path):
    estado = tmp_path / "s.json"
    _enviado(estado)
    devolucao = Recebida("<d1@google>", "mailer-daemon@googlemail.com", "Delivery Status Notification", falhou_para=("hello@kindbeauty.com.br",))

    feito, _, eventos, _ = _rodada(tmp_path, estado, recebidas=[(NOVA, devolucao)])

    assert feito.voltaram == ["hello@kindbeauty.com.br"] and eventos[0][0] == "email_voltou"
    assert sequencia_fria.ler(estado)["alvos"]["hello@kindbeauty.com.br"]["situacao"] == "voltou"


def test_gmail_qualquer_e_mensagem_lida_nao_contam(tmp_path: Path):
    estado = tmp_path / "s.json"
    _enviado(estado)
    estranho = Recebida("<e1@gmail>", "alguem@gmail.com", "Oi")
    mesmo_dominio = Recebida("<m1@kind>", "marina@kindbeauty.com.br", "Oi", quando=TERCA - timedelta(days=1))
    memoria = sequencia_fria.ler(estado)
    memoria["lidas"][NOVA] = ["<m1@kind>"]
    sequencia_fria.guardar(estado, memoria)

    feito, _, eventos, _ = _rodada(tmp_path, estado, recebidas=[(NOVA, estranho), (NOVA, mesmo_dominio)])

    assert feito.respostas == [] and eventos == []


def test_a_mensagem_do_dominio_antes_do_envio_nao_e_resposta(tmp_path: Path):
    estado = tmp_path / "s.json"
    _enviado(estado)
    antiga = Recebida("<n1@kind>", "news@kindbeauty.com.br", "Novidades", quando=TERCA - timedelta(days=9))

    feito, *_ = _rodada(tmp_path, estado, recebidas=[(NOVA, antiga)])

    assert feito.respostas == []


def test_a_leitura_do_cabecalho_acha_automatica_e_devolucao():
    automatica = sequencia_fria.recebida(_bruto({"From": "Fin <fin@kind.com.br>", "Message-ID": "<1@k>", "Subject": "Re: KIND", "Auto-Submitted": "auto-replied", "In-Reply-To": "<0@velozo.dev>"}))
    pelo_texto = sequencia_fria.recebida(_bruto({"From": "a@kind.com.br", "Message-ID": "<2@k>", "Subject": "Re: KIND"}, "Oi! Sou o Fin e vou te ajudar."))
    gente = sequencia_fria.recebida(_bruto({"From": "Marina <marina@kind.com.br>", "Message-ID": "<3@k>", "Subject": "Re: KIND", "References": "<0@velozo.dev> <1@velozo.dev>"}))
    devolucao = sequencia_fria.recebida(_bruto({"From": "Mail Delivery Subsystem <mailer-daemon@googlemail.com>", "Message-ID": "<4@g>", "Subject": "Delivery Status Notification (Failure)", "X-Failed-Recipients": "contato@benuv.com.br"}))

    assert automatica.automatica and automatica.responde_a == ("<0@velozo.dev>",)
    assert pelo_texto.automatica
    assert not gente.automatica and gente.de == "marina@kind.com.br" and gente.responde_a == ("<0@velozo.dev>", "<1@velozo.dev>")
    assert devolucao.falhou_para == ("contato@benuv.com.br",)


# -- o 2º e o 3º e-mail ----------------------------------------------------------------------------


def test_o_proximo_e_escrito_tres_dias_depois_e_vai_ao_celular_com_o_botao(tmp_path: Path):
    estado = tmp_path / "s.json"
    sequencia_fria.reservar(estado, "hello@kindbeauty.com.br", "KIND", "loja", TERCA)
    _entregar(estado, agora=TERCA - timedelta(days=7))
    escritor = Escritor(SEGUNDO)

    cedo, *_ = _rodada(tmp_path, estado, escritor=escritor, agora=TERCA - timedelta(days=5))
    feito, _, _, celular = _rodada(tmp_path, estado, escritor=escritor, agora=TERCA - timedelta(days=4))

    (pedido, _), = escritor.pedidos
    texto, opcoes = celular[0]
    assert cedo.preparados == [] and feito.preparados == ["hello@kindbeauty.com.br"]
    assert pedido.passo == 2 and pedido.segmento == "loja" and pedido.anteriores == (PRIMEIRO,)
    assert opcoes["botoes"] == (("Enviar reenvio", sequencia_fria.chave_do_toque("hello@kindbeauty.com.br", 2)),)
    assert "Assunto: Re: KIND" in texto and SEGUNDO in texto
    assert (tmp_path / "vault" / "cacada" / "reenvios" / "kind-2.md").is_file()


def test_o_toque_manda_o_reenvio_na_mesma_conversa(tmp_path: Path):
    estado = tmp_path / "s.json"
    _entregar(estado, agora=TERCA - timedelta(days=7))
    _rodada(tmp_path, estado, escritor=Escritor(SEGUNDO), agora=TERCA - timedelta(days=4))
    primeiro_id = sequencia_fria.ler(estado)["alvos"]["hello@kindbeauty.com.br"]["enviados"][0]["message_id"]
    carteiro, eventos = Carteiro(), Eventos()

    resposta = sequencia_fria.tocou_enviar_reenvio(
        sequencia_fria.chave_do_toque("hello@kindbeauty.com.br", 2),
        vault=tmp_path / "vault", estado=estado, contas=CONTAS, carteiro=carteiro, eventos=eventos, por_dia=10, agora=TERCA,
    )

    (_, mensagem), = carteiro
    assert resposta.texto == "2º e-mail enviado para hello@kindbeauty.com.br (hello@kindbeauty.com.br), na mesma conversa."
    assert mensagem["Subject"] == "Re: KIND" and mensagem["In-Reply-To"] == primeiro_id
    assert eventos[0][2]["tipo"] == "reenvio" and eventos[0][2]["passo"] == 2
    assert "proximo" not in sequencia_fria.ler(estado)["alvos"]["hello@kindbeauty.com.br"]
    assert "status: enviado em 2026-11-03" in (tmp_path / "vault" / "cacada" / "reenvios" / "hello-kindbeauty-com-br-2.md").read_text(encoding="utf-8")


def test_quem_respondeu_nao_recebe_o_reenvio(tmp_path: Path):
    estado = tmp_path / "s.json"
    _entregar(estado, agora=TERCA - timedelta(days=7))
    _rodada(tmp_path, estado, escritor=Escritor(SEGUNDO), agora=TERCA - timedelta(days=4))
    memoria = sequencia_fria.ler(estado)
    memoria["alvos"]["hello@kindbeauty.com.br"]["situacao"] = "respondeu"
    sequencia_fria.guardar(estado, memoria)
    carteiro = Carteiro()

    resposta = sequencia_fria.tocou_enviar_reenvio(
        sequencia_fria.chave_do_toque("hello@kindbeauty.com.br", 2),
        vault=tmp_path / "vault", estado=estado, contas=CONTAS, carteiro=carteiro, eventos=Eventos(), por_dia=10, agora=TERCA,
    )

    assert carteiro == [] and "já respondeu" in resposta.texto


def test_o_terceiro_e_o_ultimo(tmp_path: Path):
    estado = tmp_path / "s.json"
    _entregar(estado, agora=TERCA - timedelta(days=14))
    _entregar(estado, passo=2, corpo=SEGUNDO, agora=TERCA - timedelta(days=7))
    escritor = Escritor(TERCEIRO)
    _rodada(tmp_path, estado, escritor=escritor, agora=TERCA - timedelta(days=4))
    sequencia_fria.tocou_enviar_reenvio(
        sequencia_fria.chave_do_toque("hello@kindbeauty.com.br", 3),
        vault=tmp_path / "vault", estado=estado, contas=CONTAS, carteiro=Carteiro(), eventos=Eventos(), por_dia=10, agora=TERCA,
    )

    feito, *_ = _rodada(tmp_path, estado, escritor=Escritor(), agora=TERCA + timedelta(days=10))

    assert escritor.pedidos[0][0].passo == 3 and feito.preparados == []


def test_o_reenvio_que_nao_passa_volta_ao_claude_uma_vez(tmp_path: Path):
    estado = tmp_path / "s.json"
    _entregar(estado, agora=TERCA - timedelta(days=7))
    ruim = SEGUNDO.replace("Posso te mandar como ficaria?", "Faz sentido pra vocês?")
    escritor = Escritor(ruim, SEGUNDO)

    feito, *_ = _rodada(tmp_path, estado, escritor=escritor)

    assert feito.preparados == ["hello@kindbeauty.com.br"] and "faz sentido" in escritor.pedidos[1][1].casefold()


# -- a conferência ---------------------------------------------------------------------------------


def test_o_primeiro_no_jeito_do_voz_passa():
    assert sequencia_fria.problemas_do_primeiro("KIND", PRIMEIRO) == []


@pytest.mark.parametrize(
    ("trocar", "por", "achado"),
    [
        ("Posso te mandar uma ideia do que eu mudaria?", "Quando o time aperta, vocês passam para alguém de fora?", "aperta"),
        ("Posso te mandar uma ideia do que eu mudaria?", "Faz sentido pra você?", "Faz sentido"),
        ("Abraço,\nGabriel", "Abraço,\nGabriel Velozo\ngithub.com/bielvelozo", "GitHub"),
        (LINK_KIND, "https://gabrielvelozo.pages.dev", "falta o link"),
        ("Posso te mandar", "Se não for o momento, é só responder que eu não escrevo mais. Posso te mandar", "não escrevo"),
    ],
)
def test_o_primeiro_fora_do_voz_volta(trocar, por, achado):
    problemas = sequencia_fria.problemas_do_primeiro("KIND", PRIMEIRO.replace(trocar, por))

    assert any(achado.casefold() in p.casefold() for p in problemas), problemas


def test_so_o_terceiro_tem_a_saida():
    assert sequencia_fria.problemas_do_reenvio(SEGUNDO, 2) == []
    assert sequencia_fria.problemas_do_reenvio(TERCEIRO, 3) == []
    assert any("saída" in p for p in sequencia_fria.problemas_do_reenvio(SEGUNDO, 3))
    assert any("só vai no último" in p for p in sequencia_fria.problemas_do_reenvio(TERCEIRO, 2))


# -- o PostHog -------------------------------------------------------------------------------------


def test_o_evento_vai_ao_posthog_com_o_codigo():
    pedidos = []

    class Resposta:
        def close(self):
            pass

    sequencia_fria.posthog("phc_x", abrir=lambda pedido, timeout: pedidos.append(pedido) or Resposta())("email_enviado", "kind", {"passo": 1})

    (pedido,) = pedidos
    assert pedido.full_url == "https://us.i.posthog.com/i/v0/e/" and pedido.get_method() == "POST"
    assert json.loads(pedido.data) == {"api_key": "phc_x", "event": "email_enviado", "distinct_id": "email:kind", "properties": {"passo": 1}}


def test_o_posthog_fora_do_ar_nao_derruba_e_sem_chave_nada_sai():
    def cai(pedido, timeout):
        raise OSError("sem rede")

    sequencia_fria.posthog("phc_x", abrir=cai)("email_enviado", "kind", {})
    sequencia_fria.posthog("", abrir=lambda *a, **k: pytest.fail("não devia chamar"))("email_enviado", "kind", {})


# -- os envios de 28/10 ----------------------------------------------------------------------------


TABELA = """---
tipo: envio
criado: 2026-10-28
---

| Código | Para | Conta | Tipo | Variante | Hora |
|---|---|---|---|---|---|
| nypets | atendimento@nypets.com.br | gmail | reenvio | conversa | 09:00 |
| kind | hello@kindbeauty.com.br | velozo.dev | novo | direto | 10:25 |
"""


def test_a_importacao_poe_cada_um_no_passo_certo_e_na_conta_certa(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "cacada").mkdir(parents=True)
    (vault / "cacada" / "envios.md").write_text(TABELA, encoding="utf-8")
    estado = tmp_path / "s.json"

    importados = sequencia_fria.importar_envios(
        vault, "cacada/envios.md", estado=estado, nomes={"hello@kindbeauty.com.br": ("KIND", "loja")}
    )
    de_novo = sequencia_fria.importar_envios(vault, "cacada/envios.md", estado=estado, nomes={})

    alvos = sequencia_fria.ler(estado)["alvos"]
    nypets, kind = alvos["atendimento@nypets.com.br"], alvos["hello@kindbeauty.com.br"]
    assert importados == ["atendimento@nypets.com.br", "hello@kindbeauty.com.br"] and de_novo == []
    assert nypets["conta"] == ANTIGA and [e["passo"] for e in nypets["enviados"]] == [1, 2] and nypets["variante"] == CONVERSA
    assert nypets["enviados"][1]["quando"].startswith("2026-10-28T09:00")
    assert kind["conta"] == NOVA and [e["passo"] for e in kind["enviados"]] == [1] and (kind["nome"], kind["segmento"]) == ("KIND", "loja")


def test_os_message_ids_que_faltam_vem_dos_enviados_e_o_terceiro_responde_aos_dois(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "cacada").mkdir(parents=True)
    (vault / "cacada" / "envios.md").write_text(TABELA, encoding="utf-8")
    estado = tmp_path / "s.json"
    sequencia_fria.importar_envios(vault, "cacada/envios.md", estado=estado, nomes={})
    enviadas = [
        (ANTIGA, Enviada("<2@gmail>", ("atendimento@nypets.com.br",), "Re: Loja da NY Pets", datetime(2026, 10, 28, 9, 0, tzinfo=BRT))),
        (ANTIGA, Enviada("<1@gmail>", ("atendimento@nypets.com.br",), "Loja da NY Pets", datetime(2026, 10, 20, 9, 0, tzinfo=BRT))),
        (ANTIGA, Enviada("<x@gmail>", ("outro@x.com",), "Outro", datetime(2026, 10, 21, 9, 0, tzinfo=BRT))),
    ]
    escritor = Escritor(TERCEIRO.replace("KIND", "NY Pets"))

    feito, *_ = _rodada(tmp_path, estado, enviadas=enviadas, escritor=escritor, agora=datetime(2026, 10, 31, 10, 0, tzinfo=BRT))
    carteiro = Carteiro()
    sequencia_fria.tocou_enviar_reenvio(
        sequencia_fria.chave_do_toque("atendimento@nypets.com.br", 3),
        vault=vault, estado=estado, contas=CONTAS, carteiro=carteiro, eventos=Eventos(), por_dia=0, agora=TERCA,
    )

    nypets = sequencia_fria.ler(estado)["alvos"]["atendimento@nypets.com.br"]
    (conta, mensagem), = carteiro
    assert "atendimento@nypets.com.br" in feito.preparados
    assert [e["message_id"] for e in nypets["enviados"][:2]] == ["<1@gmail>", "<2@gmail>"]
    assert nypets["enviados"][0]["quando"].startswith("2026-10-20") and nypets["assunto"] == "Loja da NY Pets"
    assert conta.qual == ANTIGA and mensagem["Subject"] == "Re: Loja da NY Pets"
    assert mensagem["References"] == "<1@gmail> <2@gmail>" and mensagem["In-Reply-To"] == "<2@gmail>"


# -- a ligação no Whis -----------------------------------------------------------------------------


def _config(tmp_path: Path) -> Path:
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "{(tmp_path / "vault").as_posix()}"\n[cacada]\nnicho_freela = "shopify"\n', encoding="utf-8")
    return arquivo


def test_o_toque_de_reenvio_vai_para_a_sequencia(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from whis.__main__ import _tocou_no_celular
    from whis.celular import Resposta
    from whis.configuracao import carregar

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    tocados = []
    monkeypatch.setattr(sequencia_fria, "tocou_enviar_reenvio", lambda dados, **opcoes: tocados.append((dados, opcoes)) or Resposta("ok"))

    resposta = _tocou_no_celular(carregar(_config(tmp_path)), sequencia_fria.chave_do_toque("a@b.com.br", 2))

    [(dados, opcoes)] = tocados
    assert resposta.texto == "ok" and dados.startswith("frio:")
    assert opcoes["estado"] == tmp_path / "local" / "whis" / "cacada" / "sequencia-fria.json" and opcoes["por_dia"] == 10


def test_o_comando_importa_com_o_nome_que_o_whis_ja_sabe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    from whis.__main__ import main

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    (tmp_path / "vault" / "cacada").mkdir(parents=True)
    (tmp_path / "vault" / "cacada" / "envios.md").write_text(TABELA, encoding="utf-8")
    pasta = tmp_path / "local" / "whis" / "cacada"
    pasta.mkdir(parents=True)
    (pasta / "lojas-emails.json").write_text(json.dumps({"emails": {"hello@kindbeauty.com.br": {"nome": "KIND"}}}), encoding="utf-8")

    assert main(["sequencia-fria", "--config", str(_config(tmp_path)), "--importar", "cacada/envios.md"]) == 0

    alvos = sequencia_fria.ler(pasta / "sequencia-fria.json")["alvos"]
    assert (alvos["hello@kindbeauty.com.br"]["nome"], alvos["hello@kindbeauty.com.br"]["segmento"]) == ("KIND", "loja")
    saida = capsys.readouterr().out
    assert "2 envio(s) entraram na sequência fria" in saida and "Sem nome no Whis" in saida and "atendimento@nypets.com.br" in saida


def test_importar_de_novo_completa_o_nome_de_quem_ficou_so_com_o_codigo(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "cacada").mkdir(parents=True)
    (vault / "cacada" / "envios.md").write_text(TABELA, encoding="utf-8")
    estado = tmp_path / "s.json"
    sequencia_fria.importar_envios(vault, "cacada/envios.md", estado=estado, nomes={})

    sequencia_fria.importar_envios(vault, "cacada/envios.md", estado=estado, nomes={"atendimento@nypets.com.br": ("New York Pets", "loja")})

    nypets = sequencia_fria.ler(estado)["alvos"]["atendimento@nypets.com.br"]
    assert (nypets["nome"], nypets["segmento"], [e["passo"] for e in nypets["enviados"]]) == ("New York Pets", "loja", [1, 2])

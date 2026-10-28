"""O e-mail para as agências: um por dia no celular, com o botão, e o toque passa à sequência fria."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from whis import agencias_email, funil
from whis.agencias_email import EmailEscrito, ErroDoEmail
from whis.sequencia_fria import Reserva
from whis.criterios_da_cacada import PecaDoPortfolio

AGORA = datetime(2026, 10, 18, 13, 0, tzinfo=timezone(timedelta(hours=-3)))

LISTA = """\
# Agências Shopify no Brasil

### Comece por estas dez

**1. Aloft** · Criciúma/SC · https://aloftagencia.com
- Contato: contato@aloftagencia.com (site), WhatsApp +55 48 99161-2650.
- Prova: Lojas: Juicy Sneakers (juicysneakers.com.br), Onça Preta (oncapreta.com.br).
- Nota: 100% Shopify.

**11. Check Commerce (CheckStore)** · Florianópolis/SC · https://www.checkcommerce.com.br
- Contato: comercial@checkcommerce.com.br (perfil de parceiro), telefone +55 48 98873-2337.
- Nota: sem página de carreiras.

**13. Buda Digital** · São Paulo/SP · https://budadigital.com.br
- Contato: formulário em /contato. Só e-mail pessoal visível: joao@budadigital.com.br, não usar.
- Nota: projetos a partir de US$ 8.000.

**14. Econverse** · São Paulo/SP · https://www.econverse.com.br
- Contato: contato@econverse.com.br (site), WhatsApp +55 11 91914-9870.
- Nota: tem vaga de dev Shopify.

### Reserva (sem contato verificável ou com prova fraca)

- **G2 Digital** (Joinville/SC): só achei e-mail pessoal.
"""

JA_PROGRAMADOS = """\
---
estado: programados no Gmail
---

## 1. Aloft (Criciúma/SC) · peça: tema

**Para:** contato@aloftagencia.com (site).
**Assunto:** Dev Shopify para seções sob medida

Oi, pessoal da Aloft,

Vi no site de vocês as lojas da Onça Preta e da Juicy Sneakers.

Abraço,
Gabriel Velozo
github.com/bielvelozo
"""

PORTFOLIO = "https://github.com/bielvelozo/inkly-shopify-theme"
LINK = (
    "https://velozo.dev/br/?r=check-commerce-checkstore&utm_source=email&utm_medium=frio&utm_campaign=2026-10"
    "&utm_content=conversa"
)
CORPO = (
    "Oi, pessoal da Check Commerce, tudo certo?\n\n"
    "Aqui é o Gabriel, faço lojas Shopify. Vi no site de vocês que cuidam de lojas Shopify Plus do começo ao fim.\n\n"
    "Trabalho com e-commerce há mais de 3 anos, com otimização e redesign, e agora tô me especializando em Shopify. "
    f"Dá uma olhada no meu portfólio: {LINK}\n\n"
    "Hoje vocês fazem o código das lojas com o time de vocês ou chamam algum dev de fora?\n\n"
    "Abraço,\nGabriel"
)
CORPO_DO_HTML = (
    "Oi, pessoal da Check Commerce,\n\n"
    "Vi que vocês fazem o diagnóstico da loja antes de começar e cuidam de lojas Shopify Plus do começo ao fim.\n\n"
    "Eu sou o Gabriel, desenvolvedor Shopify. Desde março cuido do tema de uma loja Shopify Plus, em "
    "Liquid, JavaScript e SCSS, e também escrevo extensões de checkout. O tema que montei para portfólio está aqui: "
    f"{PORTFOLIO}\n\n"
    "Pego tarefa de tema e de checkout. Hoje vocês fazem o código das lojas com o time de vocês ou chamam "
    "algum dev de fora?\n\n"
    "Abraço,\nGabriel Velozo\ngithub.com/bielvelozo"
)


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "cacada").mkdir(parents=True)
    (vault / "cacada" / "agencias-shopify.md").write_text(LISTA, encoding="utf-8")
    (vault / "cacada" / "emails-agencias.md").write_text(JA_PROGRAMADOS, encoding="utf-8")
    return vault


@dataclass
class EscritorFake:
    respostas: list[EmailEscrito] = field(default_factory=lambda: [EmailEscrito(assunto="Dev Shopify para a Check Commerce", corpo=CORPO)])
    pedidos: list[tuple[str, str]] = field(default_factory=list)
    vozes: list[str] = field(default_factory=list)
    reservas: list[Reserva] = field(default_factory=list)

    def escrever(self, alvo, voz, reserva, *, corrigir=""):
        self.pedidos.append((alvo.email, corrigir))
        self.vozes.append(voz)
        self.reservas.append(reserva)
        return self.respostas[min(len(self.pedidos), len(self.respostas)) - 1]


class CelularFake(list):
    def __init__(self) -> None:
        super().__init__()
        self.botoes: list[tuple] = []

    def __call__(self, texto: str, *, botoes=()) -> bool:
        self.append(texto)
        self.botoes.append(tuple(botoes))
        return True


def _preparar(
    tmp_path: Path, *, escritor: EscritorFake | None = None, por_dia: int = 1, agora: datetime = AGORA, sequencia: Path | None = None
):
    celular = CelularFake()
    escritor = escritor or EscritorFake()
    feitos = agencias_email.preparar(
        _vault_pronto(tmp_path),
        escritor=escritor,
        estado=tmp_path / "agencias-emails.json",
        celular=celular,
        por_dia=por_dia,
        sequencia=sequencia,
        agora=agora,
    )
    return feitos, celular, escritor


def _vault_pronto(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    return vault if (vault / "cacada" / "agencias-shopify.md").is_file() else _vault(tmp_path)


def _nota(tmp_path: Path) -> str:
    return (tmp_path / "vault" / "cacada" / "agencias-emails" / "check-commerce-checkstore.md").read_text(encoding="utf-8")


def _tocar(tmp_path: Path, enviados: list, *, dados: str | None = None, falha: Exception | None = None, fila: str = ""):
    def enviar(para: str, assunto: str, corpo: str, imagem=None) -> str:
        if falha is not None:
            raise falha
        enviados.append((para, assunto, corpo))
        return fila

    return agencias_email.tocou_enviar_email(
        dados or agencias_email.chave_do_toque("comercial@checkcommerce.com.br"),
        vault=tmp_path / "vault",
        estado=tmp_path / "agencias-emails.json",
        enviar=enviar,
        agora=AGORA + timedelta(minutes=30),
    )


def test_le_as_agencias_com_email_da_empresa_e_pula_as_ja_programadas(tmp_path: Path):
    alvos = agencias_email.ler_alvos(_vault(tmp_path))

    assert [(a.nome, a.cidade, a.site, a.email) for a in alvos] == [
        ("Check Commerce (CheckStore)", "Florianópolis/SC", "https://www.checkcommerce.com.br", "comercial@checkcommerce.com.br"),
        ("Econverse", "São Paulo/SP", "https://www.econverse.com.br", "contato@econverse.com.br"),
    ]
    assert "sem página de carreiras" in alvos[0].detalhes


def test_um_email_por_dia_chega_no_celular_com_o_botao(tmp_path: Path):
    feitos, celular, escritor = _preparar(tmp_path)
    de_novo, mesmo_dia, _ = _preparar(tmp_path, agora=AGORA + timedelta(hours=1))
    amanha, no_outro_dia, _ = _preparar(tmp_path, agora=AGORA + timedelta(days=1))

    assert [f.email for f in feitos] == ["comercial@checkcommerce.com.br"]
    assert celular[0].startswith("E-mail para a agência Check Commerce (CheckStore) (Florianópolis/SC), para você aprovar")
    assert "Para: comercial@checkcommerce.com.br" in celular[0] and "Assunto: Dev Shopify para a Check Commerce" in celular[0]
    assert "Variante: conversa" in celular[0]
    assert CORPO in celular[0]
    assert celular.botoes == [((agencias_email.ROTULO_DO_BOTAO, agencias_email.chave_do_toque("comercial@checkcommerce.com.br")),)]
    nota = _nota(tmp_path)
    assert "para: comercial@checkcommerce.com.br" in nota and "status: para aprovar em 2026-10-18" in nota and CORPO in nota
    assert de_novo == [] and mesmo_dia == []
    assert [f.email for f in amanha] == ["contato@econverse.com.br"]
    assert funil.ler_mandadas(tmp_path / "vault") == []


def test_texto_com_preco_colchete_ou_sem_portfolio_volta_ao_claude(tmp_path: Path):
    ruim = EmailEscrito(assunto="Oi", corpo=CORPO.replace(LINK, "[link do portfólio]").replace("Hoje", "Cobro R$ 80 a hora. Hoje"))
    escritor = EscritorFake(respostas=[ruim, EmailEscrito(assunto="Dev Shopify para a Check Commerce", corpo=CORPO)])

    feitos, _, _ = _preparar(tmp_path, escritor=escritor)

    motivo = escritor.pedidos[1][1]
    assert "colchete" in motivo and "preço" in motivo and "falta o link do velozo.dev" in motivo
    assert len(feitos) == 1


def test_texto_que_fala_do_horario_dele_volta_ao_claude(tmp_path: Path):
    ruim = EmailEscrito(
        assunto="Dev Shopify para a Check Commerce",
        corpo=CORPO.replace("Vi no site de vocês", "Trabalho à noite e nos fins de semana. Vi no site de vocês"),
    )
    escritor = EscritorFake(respostas=[ruim, EmailEscrito(assunto="Dev Shopify para a Check Commerce", corpo=CORPO)])

    feitos, _, _ = _preparar(tmp_path, escritor=escritor)

    assert "quando ele trabalha" in escritor.pedidos[1][1]
    assert len(feitos) == 1


def test_o_que_continua_ruim_fica_de_fora_e_nao_volta(tmp_path: Path):
    ruim = EmailEscrito(assunto="Oi", corpo="Oi, tudo bem? R$ 50.")
    escritor = EscritorFake(respostas=[ruim])

    feitos, celular, _ = _preparar(tmp_path, escritor=escritor)
    _preparar(tmp_path, escritor=escritor, agora=AGORA + timedelta(days=1))

    assert feitos == [] and celular == []
    estado = json.loads((tmp_path / "agencias-emails.json").read_text(encoding="utf-8"))
    assert estado["emails"]["comercial@checkcommerce.com.br"]["situacao"] == agencias_email.PULADO
    assert [p[0] for p in escritor.pedidos][-1] == "contato@econverse.com.br"


def test_o_toque_passa_o_texto_da_nota_a_sequencia_e_marca_enviado(tmp_path: Path):
    _preparar(tmp_path)
    arquivo = tmp_path / "vault" / "cacada" / "agencias-emails" / "check-commerce-checkstore.md"
    arquivo.write_text(
        arquivo.read_text(encoding="utf-8").replace("Oi, pessoal da Check Commerce,", "Oi, pessoal da Check,"), encoding="utf-8"
    )
    enviados: list = []

    resposta = _tocar(tmp_path, enviados)
    segunda = _tocar(tmp_path, enviados)

    [(para, assunto, corpo)] = enviados
    assert para == "comercial@checkcommerce.com.br" and assunto == "Dev Shopify para a Check Commerce"
    assert corpo.startswith("Oi, pessoal da Check, tudo certo?\n") and corpo.endswith("Abraço,\nGabriel")
    assert resposta.tirar_botao is True and "E-mail enviado para Check Commerce (CheckStore)" in resposta.texto
    assert "status: enviado em 2026-10-18" in _nota(tmp_path)
    assert segunda.tirar_botao is True and "já foi enviado" in segunda.texto


def test_fora_da_janela_o_toque_diz_quando_sai(tmp_path: Path):
    _preparar(tmp_path)

    resposta = _tocar(tmp_path, [], fila="Ficou na fila e sai terça, 20/10, a partir das 08:00.")

    assert resposta.tirar_botao is True and "Ficou na fila e sai terça" in resposta.texto
    assert "status: na fila desde 2026-10-18" in _nota(tmp_path)


def test_gmail_que_recusa_mantem_o_botao(tmp_path: Path):
    _preparar(tmp_path)

    resposta = _tocar(tmp_path, [], falha=ErroDoEmail("o Gmail recusou a senha de app"))

    assert resposta.tirar_botao is False and "senha de app" in resposta.texto
    assert "status: para aprovar" in _nota(tmp_path)


def test_toque_desconhecido_tira_o_botao(tmp_path: Path):
    _vault(tmp_path)

    resposta = _tocar(tmp_path, [], dados=agencias_email.PREFIXO_DO_TOQUE + "000000000000")

    assert resposta.tirar_botao is True and "Não achei" in resposta.texto


def test_sem_conta_no_config_o_gmail_nem_tenta():
    enviar = agencias_email.gmail("", "")

    with pytest.raises(ErroDoEmail, match="senha_de_app"):
        enviar("contato@example.com", "Oi", "Corpo")


def test_a_chave_do_botao_cabe_no_telegram():
    chave = agencias_email.chave_do_toque("comercial@checkcommerce.com.br")

    assert chave.startswith(agencias_email.PREFIXO_DO_TOQUE) and len(chave.encode()) <= 64



def test_a_fila_conta_as_agencias_que_ainda_nao_ganharam_email(tmp_path: Path):
    _vault(tmp_path)
    estado = tmp_path / "agencias-emails.json"

    antes = agencias_email.na_fila(tmp_path / "vault", estado)
    _preparar(tmp_path)

    assert antes == 2 and agencias_email.na_fila(tmp_path / "vault", estado) == 1


def test_o_pedido_leva_a_voz_a_variante_e_o_link():
    alvo = agencias_email.Alvo("Akag", "SP", "https://akag.digital", "comercial@akag.digital", "Contato: comercial@akag.digital")

    pedido = agencias_email.pedido(alvo, "Oi, Marina, tudo certo?", Reserva("akag", "direto", "https://velozo.dev/br/?r=akag"))

    assert "VOZ (cacada/voz.md):\nOi, Marina, tudo certo?" in pedido
    assert "VARIANTE: direto" in pedido and "LINK (copie exatamente, é o único link do e-mail): https://velozo.dev/br/?r=akag" in pedido
    assert "Hoje vocês fazem o código das lojas" in agencias_email.SISTEMA_DO_EMAIL


def test_a_agencia_de_marketing_ou_de_design_ganha_outro_pedido():
    alvo = agencias_email.Alvo(
        "Tráfego Bom", "Recife/PE", "https://trafegobom.com.br", "contato@trafegobom.com.br",
        "Contato: contato@trafegobom.com.br\nTipo: marketing e tráfego (sem desenvolvimento de loja à mostra)",
    )

    assert "Tipo: marketing e tráfego" in agencias_email.pedido(alvo, "", Reserva("t", "conversa", ""))
    assert "Tipo: marketing" in agencias_email.SISTEMA_DO_EMAIL and "Tipo: design" in agencias_email.SISTEMA_DO_EMAIL


@pytest.mark.parametrize(
    "trecho",
    [
        "em Matão (SP).",
        "parceiros da Shopify desde 2022.",
        "o que mais se parece com isso",
        "com o escopo combinado antes.",
        "Quando a fila aperta, vocês chamam alguém?",
        "Se aparecer um pico de demanda, me chamem.",
        "Quando entra mais projeto do que dá pra tocar, vocês chamam alguém?",
        "Faz sentido para vocês?",
        "pego uma tarefa pequena, com escopo fechado.",
    ],
)
def test_o_que_soa_como_modelo_ou_ele_recusou_volta_ao_claude(trecho: str):
    escrito = EmailEscrito(assunto="Dev Shopify", corpo=CORPO.replace("faço lojas Shopify.", f"faço lojas Shopify, {trecho}"))

    problemas = agencias_email.problemas_da_agencia(escrito)

    assert any("soa como modelo" in p or "ele recusou" in p for p in problemas), problemas


def test_o_primeiro_no_jeito_do_voz_passa():
    assert agencias_email.problemas_da_agencia(EmailEscrito("Dev Shopify para a Check Commerce", CORPO)) == []


def test_a_voz_vai_ao_claude_e_a_variante_alterna_entre_as_agencias(tmp_path: Path):
    vault = _vault(tmp_path)
    (vault / "cacada" / "voz.md").write_text("# Como o Gabriel escreve\n\nOi, Marina, tudo certo?\n", encoding="utf-8")
    sequencia = tmp_path / "sequencia-fria.json"
    direto = EmailEscrito("Dev Shopify para a Econverse", CORPO.replace("conversa", "direto").replace("check-commerce-checkstore", "econverse"))

    _, _, escritor = _preparar(tmp_path, sequencia=sequencia)
    _, _, outro = _preparar(tmp_path, sequencia=sequencia, agora=AGORA + timedelta(days=1), escritor=EscritorFake(respostas=[direto]))

    assert "Oi, Marina, tudo certo?" in escritor.vozes[0]
    assert [r.variante for r in escritor.reservas + outro.reservas] == ["conversa", "direto"]
    assert escritor.reservas[0].link == LINK
    assert "codigo: check-commerce-checkstore" in _nota(tmp_path) and "variante: conversa" in _nota(tmp_path)


def _imagem_do_tema(tmp_path: Path) -> agencias_email.ImagemDoEmail | None:
    vault = _vault(tmp_path)
    arquivo = vault / agencias_email.PASTA_DAS_IMAGENS / "tema-shopify-inkly.jpg"
    arquivo.parent.mkdir(parents=True)
    arquivo.write_bytes(b"\xff\xd8imagem")
    portfolio = (
        PecaDoPortfolio("Site do portfólio", "https://velozo.dev", "tudo"),
        PecaDoPortfolio("Tema Shopify Inkly", PORTFOLIO, "tema", "https://youtu.be/NEYUIo16DfA"),
    )
    return agencias_email.imagem_do_email(vault, CORPO_DO_HTML, portfolio)


def test_o_email_sai_em_html_com_a_imagem_da_peca_abrindo_o_video(tmp_path: Path):
    imagem = _imagem_do_tema(tmp_path)

    mensagem = agencias_email.montar_email("eu@gmail.com", "comercial@checkcommerce.com.br", "Oi", CORPO_DO_HTML, imagem)

    html = mensagem.get_body(("html",)).get_content()
    (anexo,) = [parte for parte in mensagem.walk() if parte.get_content_type() == "image/jpeg"]
    assert mensagem.get_body(("plain",)).get_content().strip() == CORPO_DO_HTML
    assert 'href="https://youtu.be/NEYUIo16DfA"' in html and f'src="cid:{anexo["Content-ID"].strip("<>")}"' in html
    assert html.index(">github.com/bielvelozo/inkly-shopify-theme</a>") < html.index("<img") < html.rindex("Pego tarefa")
    assert "Ver o vídeo" in html[html.index("<img"):html.rindex("Pego tarefa")]
    assert 'href="https://github.com/bielvelozo"' in html
    assert anexo.get_content() == b"\xff\xd8imagem"


def test_o_html_tem_a_marca_em_cima_a_assinatura_e_o_site_embaixo():
    html = agencias_email.html_do_email(CORPO_DO_HTML)

    corpo_visivel = html[html.index('class="cartao"'):]
    assert html.startswith("<!doctype html>")
    assert "Oi, pessoal da Check Commerce, Vi que vocês" in html[:html.index('class="cartao"')]
    assert html.index(agencias_email.CARGO) < html.index('class="cartao"')
    assert ">GV</div>" in corpo_visivel and corpo_visivel.count(agencias_email.CARGO) == 2
    assert html.rstrip().endswith("</html>") and 'href="https://velozo.dev"' in corpo_visivel


def test_sem_a_imagem_da_peca_o_html_sai_so_com_o_texto(tmp_path: Path):
    imagem = agencias_email.imagem_do_email(_vault(tmp_path), CORPO_DO_HTML, (PecaDoPortfolio("Tema Shopify Inkly", PORTFOLIO, "tema"),))

    mensagem = agencias_email.montar_email("eu@gmail.com", "comercial@checkcommerce.com.br", "Oi", CORPO_DO_HTML, imagem)

    assert imagem is None
    assert "<img" not in mensagem.get_body(("html",)).get_content()
    assert not [parte for parte in mensagem.walk() if parte.get_content_maintype() == "image"]


class SmtpFake:
    enviadas: list = []

    def __init__(self, servidor, porta, timeout):
        self.servidor, self.login_feito = servidor, ()

    def __enter__(self):
        return self

    def __exit__(self, *erro):
        return False

    def login(self, usuario, senha):
        self.login_feito = (usuario, senha)

    def send_message(self, mensagem):
        SmtpFake.enviadas.append((self.servidor, self.login_feito, mensagem["From"], mensagem["To"]))


class ImapFake:
    guardadas: list = []
    falha: Exception | None = None

    def __init__(self, servidor):
        self.servidor = servidor

    def login(self, usuario, senha):
        if ImapFake.falha is not None:
            raise ImapFake.falha

    def list(self):
        return "OK", [rb'(\HasNoChildren \All) "/" "[Gmail]/Todos os e-mails"', rb'(\HasNoChildren \Sent) "/" "[Gmail]/E-mails enviados"']

    def append(self, pasta, flags, quando, mensagem):
        ImapFake.guardadas.append((self.servidor, pasta, flags, mensagem))

    def logout(self):
        pass


@pytest.fixture
def servidores(monkeypatch: pytest.MonkeyPatch):
    SmtpFake.enviadas, ImapFake.guardadas, ImapFake.falha = [], [], None
    monkeypatch.setattr(agencias_email.smtplib, "SMTP_SSL", SmtpFake)
    monkeypatch.setattr(agencias_email.imaplib, "IMAP4_SSL", ImapFake)


def test_sem_a_chave_da_resend_sai_pelo_gmail_e_assina_com_o_remetente(servidores):
    agencias_email.gmail("eu@gmail.com", "senha", "gabriel@velozo.dev")("contato@example.com", "Oi", CORPO)
    agencias_email.gmail("eu@gmail.com", "senha")("contato@example.com", "Oi", CORPO)

    assert SmtpFake.enviadas == [
        ("smtp.gmail.com", ("eu@gmail.com", "senha"), "Gabriel Velozo <gabriel@velozo.dev>", "contato@example.com"),
        ("smtp.gmail.com", ("eu@gmail.com", "senha"), "Gabriel Velozo <eu@gmail.com>", "contato@example.com"),
    ]
    assert ImapFake.guardadas == []


def test_com_a_chave_sai_pela_resend_e_a_copia_entra_nos_enviados_do_gmail(servidores):
    agencias_email.gmail("eu@gmail.com", "senha", "gabriel@velozo.dev", "re_chave")("contato@example.com", "Oi", CORPO)

    assert SmtpFake.enviadas == [
        ("smtp.resend.com", ("resend", "re_chave"), "Gabriel Velozo <gabriel@velozo.dev>", "contato@example.com")
    ]
    ((servidor, pasta, flags, mensagem),) = ImapFake.guardadas
    assert (servidor, pasta, flags) == ("imap.gmail.com", '"[Gmail]/E-mails enviados"', r"(\Seen)")
    assert b"To: contato@example.com" in mensagem and b"Subject: Oi" in mensagem


def test_a_copia_que_nao_entra_nos_enviados_nao_desfaz_o_envio(servidores, caplog: pytest.LogCaptureFixture):
    ImapFake.falha = OSError("sem rede")

    agencias_email.gmail("eu@gmail.com", "senha", "gabriel@velozo.dev", "re_chave")("contato@example.com", "Oi", CORPO)

    assert len(SmtpFake.enviadas) == 1 and ImapFake.guardadas == []
    assert "não entrou nos Enviados" in caplog.text


def test_a_resend_que_recusa_a_chave_diz_qual_e(servidores, monkeypatch: pytest.MonkeyPatch):
    def recusa(self, usuario, senha):
        raise agencias_email.smtplib.SMTPAuthenticationError(535, b"bad key")

    monkeypatch.setattr(SmtpFake, "login", recusa)

    with pytest.raises(ErroDoEmail, match=r"a Resend recusou a chave de \[cacada\]\.resend_chave"):
        agencias_email.gmail("eu@gmail.com", "senha", "gabriel@velozo.dev", "re_ruim")("contato@example.com", "Oi", CORPO)
    assert ImapFake.guardadas == []


def test_o_jpg_parado_ganha_do_gif_e_o_gif_so_vai_sem_ele(tmp_path: Path):
    imagem = _imagem_do_tema(tmp_path)
    gif = imagem.arquivo.with_suffix(".gif")
    gif.write_bytes(b"GIF89a")
    peca = (PecaDoPortfolio("Tema Shopify Inkly", PORTFOLIO, "tema", "https://youtu.be/NEYUIo16DfA"),)

    com_os_dois = agencias_email.imagem_do_email(tmp_path / "vault", CORPO_DO_HTML, peca)
    imagem.arquivo.unlink()
    so_o_gif = agencias_email.imagem_do_email(tmp_path / "vault", CORPO_DO_HTML, peca)
    mensagem = agencias_email.montar_email("eu@gmail.com", "contato@example.com", "Oi", CORPO_DO_HTML, so_o_gif)

    assert com_os_dois.arquivo == imagem.arquivo and so_o_gif.arquivo == gif
    assert [p.get_content_type() for p in mensagem.walk() if p.get_content_maintype() == "image"] == ["image/gif"]


def test_o_html_nao_tem_hover_nem_animacao():
    html = agencias_email.html_do_email(CORPO)

    assert ":hover" not in html and "animation" not in html and ";transform:" not in html

"""O e-mail para as agências: um por dia no celular, com o botão, e o toque manda pelo Gmail dele."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from whis import agencias_email, funil
from whis.agencias_email import EmailEscrito, ErroDoEmail

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
CORPO = (
    "Oi, pessoal da Check Commerce,\n\n"
    "Vi que vocês fazem o diagnóstico da loja antes de começar e cuidam de lojas Shopify Plus do começo ao fim.\n\n"
    "Eu sou o Gabriel, desenvolvedor Shopify em Matão (SP). Desde março cuido do tema de uma loja Shopify Plus, em "
    "Liquid, JavaScript e SCSS, e também escrevo extensões de checkout. O tema que montei para portfólio está aqui: "
    f"{PORTFOLIO}\n\n"
    "Trabalho à noite e nos fins de semana, com o escopo combinado antes. Vocês costumam chamar alguém de fora quando "
    "uma seção ou um ajuste de checkout aperta o prazo?\n\n"
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

    def escrever(self, alvo, exemplos, portfolio, *, corrigir=""):
        self.pedidos.append((alvo.email, corrigir))
        return self.respostas[min(len(self.pedidos), len(self.respostas)) - 1]


class CelularFake(list):
    def __init__(self) -> None:
        super().__init__()
        self.botoes: list[tuple] = []

    def __call__(self, texto: str, *, botoes=()) -> bool:
        self.append(texto)
        self.botoes.append(tuple(botoes))
        return True


def _preparar(tmp_path: Path, *, escritor: EscritorFake | None = None, por_dia: int = 1, agora: datetime = AGORA):
    celular = CelularFake()
    escritor = escritor or EscritorFake()
    feitos = agencias_email.preparar(
        _vault_pronto(tmp_path),
        escritor=escritor,
        estado=tmp_path / "agencias-emails.json",
        celular=celular,
        por_dia=por_dia,
        agora=agora,
    )
    return feitos, celular, escritor


def _vault_pronto(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    return vault if (vault / "cacada" / "agencias-shopify.md").is_file() else _vault(tmp_path)


def _nota(tmp_path: Path) -> str:
    return (tmp_path / "vault" / "cacada" / "agencias-emails" / "check-commerce-checkstore.md").read_text(encoding="utf-8")


def _tocar(tmp_path: Path, enviados: list, *, dados: str | None = None, falha: Exception | None = None):
    def enviar(para: str, assunto: str, corpo: str) -> None:
        if falha is not None:
            raise falha
        enviados.append((para, assunto, corpo))

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
    assert CORPO in celular[0]
    assert celular.botoes == [((agencias_email.ROTULO_DO_BOTAO, agencias_email.chave_do_toque("comercial@checkcommerce.com.br")),)]
    nota = _nota(tmp_path)
    assert "para: comercial@checkcommerce.com.br" in nota and "status: para aprovar em 2026-10-18" in nota and CORPO in nota
    assert de_novo == [] and mesmo_dia == []
    assert [f.email for f in amanha] == ["contato@econverse.com.br"]
    assert funil.ler_mandadas(tmp_path / "vault") == []


def test_texto_com_preco_colchete_ou_sem_portfolio_volta_ao_claude(tmp_path: Path):
    ruim = EmailEscrito(assunto="Oi", corpo=CORPO.replace(PORTFOLIO, "[link do portfólio]") + "\nCobro R$ 80 a hora.")
    escritor = EscritorFake(respostas=[ruim, EmailEscrito(assunto="Dev Shopify para a Check Commerce", corpo=CORPO)])

    feitos, _, _ = _preparar(tmp_path, escritor=escritor)

    motivo = escritor.pedidos[1][1]
    assert "colchete" in motivo and "preço" in motivo and "portfólio" in motivo
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


def test_o_toque_manda_pelo_gmail_o_texto_da_nota_e_marca_enviado(tmp_path: Path):
    _preparar(tmp_path)
    arquivo = tmp_path / "vault" / "cacada" / "agencias-emails" / "check-commerce-checkstore.md"
    arquivo.write_text(arquivo.read_text(encoding="utf-8").replace("Oi, pessoal da Check Commerce,", "Oi, pessoal,"), encoding="utf-8")
    enviados: list = []

    resposta = _tocar(tmp_path, enviados)
    segunda = _tocar(tmp_path, enviados)

    [(para, assunto, corpo)] = enviados
    assert para == "comercial@checkcommerce.com.br" and assunto == "Dev Shopify para a Check Commerce"
    assert corpo.startswith("Oi, pessoal,\n") and corpo.endswith("github.com/bielvelozo")
    assert resposta.tirar_botao is True and "E-mail enviado para Check Commerce (CheckStore)" in resposta.texto
    assert "status: enviado em 2026-10-18" in _nota(tmp_path)
    assert segunda.tirar_botao is True and "já foi enviado" in segunda.texto


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


def test_o_pedido_do_email_lembra_do_site_do_portfolio():
    assert "Site do portfólio" in agencias_email.SISTEMA_DO_EMAIL

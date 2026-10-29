"""O e-mail para a loja Shopify lenta: medida de novo, um por dia no celular com o botão, e o toque passa à sequência fria."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from whis import lojas_email, sequencia_fria
from whis.agencias_email import EmailEscrito, ErroDoEmail
from whis.lojas_shopify import CAMINHO_DA_LISTA_DE_LOJAS
from whis.medida_no_celular import MedidaNoCelular
from whis.sequencia_fria import Reserva

AGORA = datetime(2026, 10, 18, 14, 0, tzinfo=timezone(timedelta(hours=-3)))
VELOCIDADE = "https://github.com/bielvelozo/inkly-shopify-theme#3-speed-measured"
LINK = "https://velozo.dev/br/?r=bela-pele&utm_source=email&utm_medium=frio&utm_campaign=2026-10&utm_content=conversa"

LISTA = """\
# Lojas Shopify lentas no Brasil

## Nunca contatar

- naoquero.com.br
- ramo: fotolivro

## Outubro de 2026 (busca de 18/10)

**1. Bela Pele** · Recife/PE · https://belapele.com.br
- Contato: contato@belapele.com.br
- Ramo: cosméticos
- Medida em 18/10: no celular em 4G, a maior imagem apareceu em 9,4 s (LCP); 3,2 MB em 140 pedidos; tema Dawn 15.0.0

**2. Não Quero** · São Paulo/SP · https://naoquero.com.br
- Contato: contato@naoquero.com.br

**3. Café Bom** · cidade não informada · https://cafebom.com.br
- Contato: sac@cafebom.com.br

**4. Foto Fácil** · Campinas/SP · https://fotofacil.com.br
- Contato: contato@fotofacil.com.br
- Ramo: fotolivros
"""

CRITERIOS = f"""\
## O que eu procuro

- Freela.

## Portfólio

- Velocidade da loja: {VELOCIDADE} — LCP de 11,9 s para 3,5 s no celular
- Site do portfólio: https://velozo.dev — o portfólio inteiro
"""


def _corpo(segundos: str = "9 segundos") -> str:
    return (
        "Oi, pessoal da Bela Pele, tudo certo?\n\n"
        "Aqui é o Gabriel, faço lojas Shopify. Dei uma olhada na loja de vocês pelo celular e reparei que a página "
        f"inicial demora para aparecer: no 4G, a imagem principal levou {segundos}.\n\n"
        "Trabalho com e-commerce há mais de 3 anos, com otimização e redesign, e agora tô me especializando em Shopify. "
        f"Dá uma olhada no meu portfólio: {LINK}\n\n"
        "Posso te mandar o que eu mudaria na página de vocês?\n\n"
        "Abraço,\nGabriel"
    )


@dataclass
class EscritorFake:
    respostas: list[EmailEscrito] = field(default_factory=lambda: [EmailEscrito("Página inicial da Bela Pele no celular", _corpo())])
    pedidos: list[tuple[str, float, str]] = field(default_factory=list)
    reservas: list[Reserva] = field(default_factory=list)

    def escrever(self, alvo, medida, voz, reserva, *, corrigir=""):
        self.pedidos.append((alvo.email, medida.lcp_s, corrigir))
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


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    if not vault.exists():
        (vault / "cacada").mkdir(parents=True)
        (vault / CAMINHO_DA_LISTA_DE_LOJAS).write_text(LISTA, encoding="utf-8")
        (vault / "cacada" / "criterios.md").write_text(CRITERIOS, encoding="utf-8")
    return vault


def _preparar(tmp_path: Path, *, escritor=None, medidas=None, agora: datetime = AGORA, por_dia: int = 1):
    celular = CelularFake()
    escritor = escritor or EscritorFake()
    fila = list(medidas) if medidas is not None else [MedidaNoCelular(9.2, 3.2, 140)]
    medidos: list[str] = []

    def medir(url: str):
        medidos.append(url)
        return fila.pop(0) if fila else MedidaNoCelular(9.2, 3.2, 140)

    feitos = lojas_email.preparar(
        _vault(tmp_path), escritor=escritor, estado=tmp_path / "lojas-emails.json", celular=celular, por_dia=por_dia,
        medir_no_celular=medir, agora=agora,
    )
    return feitos, celular, escritor, medidos


def _estado(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "lojas-emails.json").read_text(encoding="utf-8"))["emails"]


def _tocar(tmp_path: Path, enviados: list, *, falha: Exception | None = None, email: str = "contato@belapele.com.br"):
    def enviar(para: str, assunto: str, corpo: str, imagem=None) -> str:
        if falha is not None:
            raise falha
        enviados.append((para, assunto, corpo))
        return ""

    return lojas_email.tocou_enviar_email(
        lojas_email.chave_do_toque(email), vault=tmp_path / "vault", estado=tmp_path / "lojas-emails.json", enviar=enviar,
        agora=AGORA + timedelta(minutes=20),
    )


def test_os_alvos_sao_as_lojas_numeradas_com_email_da_empresa_menos_nunca_contatar(tmp_path: Path):
    alvos = lojas_email.ler_alvos(_vault(tmp_path))

    assert [(a.nome, a.cidade, a.site, a.email) for a in alvos] == [
        ("Bela Pele", "Recife/PE", "https://belapele.com.br", "contato@belapele.com.br"),
        ("Café Bom", "", "https://cafebom.com.br", "sac@cafebom.com.br"),
    ]


def test_um_email_por_dia_com_a_medida_de_agora_chega_no_celular_com_o_botao(tmp_path: Path):
    feitos, celular, escritor, medidos = _preparar(tmp_path)
    mesmo_dia, no_mesmo_dia, _, medidos_de_novo = _preparar(tmp_path, agora=AGORA + timedelta(hours=2))

    assert [f.email for f in feitos] == ["contato@belapele.com.br"] and medidos == ["https://belapele.com.br"]
    assert escritor.pedidos == [("contato@belapele.com.br", 9.2, "")]
    [mensagem] = celular
    assert mensagem.startswith("E-mail para a loja Bela Pele (Recife/PE), para você aprovar")
    assert "Medida de agora: LCP de 9,2 s no celular em 4G, 3,2 MB" in mensagem and _corpo() in mensagem
    assert "Variante: conversa" in mensagem and escritor.reservas[0].link == LINK
    assert celular.botoes == [((lojas_email.ROTULO_DO_BOTAO, lojas_email.chave_do_toque("contato@belapele.com.br")),)]
    nota = (tmp_path / "vault" / "cacada" / "lojas-emails" / "bela-pele.md").read_text(encoding="utf-8")
    assert "para: contato@belapele.com.br" in nota and "status: para aprovar em 2026-10-18" in nota and _corpo() in nota
    assert mesmo_dia == [] and no_mesmo_dia == [] and medidos_de_novo == []
    assert lojas_email.na_fila(tmp_path / "vault", tmp_path / "lojas-emails.json") == 1


def test_a_loja_que_ficou_rapida_sai_e_a_proxima_e_medida(tmp_path: Path):
    escritor = EscritorFake(respostas=[EmailEscrito("Página inicial do Café Bom", _corpo().replace("Bela Pele", "Café Bom"))])

    feitos, _, _, medidos = _preparar(tmp_path, escritor=escritor, medidas=[MedidaNoCelular(2.0, 0.8, 30), MedidaNoCelular(9.2, 3.2, 140)])

    assert medidos == ["https://belapele.com.br", "https://cafebom.com.br"]
    assert [f.email for f in feitos] == ["sac@cafebom.com.br"]
    estado = _estado(tmp_path)
    assert estado["contato@belapele.com.br"]["situacao"] == lojas_email.PULADO and "ficou rápida" in estado["contato@belapele.com.br"]["motivo"]


def test_a_medida_que_falha_tenta_de_novo_e_na_segunda_sai(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(lojas_email, "MEDIDAS_POR_RODADA", 1)

    _preparar(tmp_path, medidas=[None])
    primeira = _estado(tmp_path)["contato@belapele.com.br"]
    _preparar(tmp_path, medidas=[None], agora=AGORA + timedelta(hours=1))
    segunda = _estado(tmp_path)["contato@belapele.com.br"]

    assert primeira["situacao"] == lojas_email.MEDIDA_FALHOU and segunda["situacao"] == lojas_email.PULADO


def test_o_texto_sem_o_numero_medido_ou_com_a_saida_volta_ao_claude(tmp_path: Path):
    sem_numero = EmailEscrito("Oi", _corpo("uns segundos").replace("Posso", "Se não for o momento, é só responder que eu não escrevo mais. Posso"))
    escritor = EscritorFake(respostas=[sem_numero, EmailEscrito("Página inicial da Bela Pele no celular", _corpo())])

    feitos, _, _, _ = _preparar(tmp_path, escritor=escritor)

    motivo = escritor.pedidos[1][2]
    assert '"9 segundos"' in motivo and "não escrevo de novo" in motivo and "primeiro e-mail" in motivo
    assert len(feitos) == 1


def test_o_toque_passa_o_texto_da_nota_a_sequencia_e_marca_enviado(tmp_path: Path):
    _preparar(tmp_path)
    arquivo = tmp_path / "vault" / "cacada" / "lojas-emails" / "bela-pele.md"
    arquivo.write_text(arquivo.read_text(encoding="utf-8").replace("Oi, pessoal da Bela Pele,", "Oi, pessoal da Bela,"), encoding="utf-8")
    enviados: list = []

    resposta = _tocar(tmp_path, enviados)
    segunda = _tocar(tmp_path, enviados)

    [(para, assunto, corpo)] = enviados
    assert para == "contato@belapele.com.br" and assunto == "Página inicial da Bela Pele no celular"
    assert corpo.startswith("Oi, pessoal da Bela, tudo certo?\n") and corpo.endswith("Abraço,\nGabriel")
    assert resposta.tirar_botao is True and "E-mail enviado para a loja Bela Pele" in resposta.texto
    assert "status: enviado em 2026-10-18" in arquivo.read_text(encoding="utf-8")
    assert segunda.tirar_botao is True and "já foi enviado" in segunda.texto


def test_gmail_que_recusa_mantem_o_botao(tmp_path: Path):
    _preparar(tmp_path)

    resposta = _tocar(tmp_path, [], falha=ErroDoEmail("o Gmail recusou a senha de app"))

    assert resposta.tirar_botao is False and "senha de app" in resposta.texto


def test_toque_desconhecido_tira_o_botao(tmp_path: Path):
    _vault(tmp_path)

    resposta = _tocar(tmp_path, [], email="ninguem@nada.com.br")

    assert resposta.tirar_botao is True and "Não achei" in resposta.texto


def test_a_chave_do_botao_cabe_no_telegram_e_nao_cruza_com_a_das_agencias():
    from whis import agencias_email

    chave = lojas_email.chave_do_toque("contato@belapele.com.br")

    assert chave.startswith("loja:") and len(chave.encode()) <= 64
    assert not chave.startswith(agencias_email.PREFIXO_DO_TOQUE)


def test_o_pedido_leva_a_medida_o_jeito_de_escrever_o_tempo_a_variante_e_o_link():
    alvo = lojas_email.AlvoLoja("Bela Pele", "Recife/PE", "https://belapele.com.br", "contato@belapele.com.br")
    texto = lojas_email.pedido(alvo, MedidaNoCelular(9.2, 3.2, 140), "Oi, Marina, tudo certo?", Reserva("bela-pele", "direto", LINK))

    assert 'Escreva o tempo exatamente assim: "9 segundos"' in texto and "3,2 MB" in texto and LINK in texto
    assert "VARIANTE: direto" in texto and "Oi, Marina, tudo certo?" in texto
    assert "nunca invente a causa" in lojas_email.SISTEMA_DO_EMAIL_DA_LOJA


def test_o_primeiro_da_loja_no_jeito_do_voz_passa():
    assert lojas_email.problemas_da_loja(EmailEscrito("Bela Pele", _corpo()), MedidaNoCelular(9.2, 3.2, 140)) == []


DA_MEDIDA = (
    "https://velozo.dev/br/velocidade/?loja=belapele.com.br&r=bela-pele&utm_source=email&utm_medium=frio"
    "&utm_campaign=2026-10&utm_content=conversa"
)


def test_com_a_medida_do_site_o_link_abre_a_medida_da_propria_loja(tmp_path: Path):
    _, celular, escritor, _ = _preparar(tmp_path, medidas=[MedidaNoCelular(9.2, 3.2, 140, do_site=True)])

    assert escritor.reservas[0].link == DA_MEDIDA and len(celular) == 1


def test_o_primeiro_com_o_link_da_medida_passa_e_o_html_mostra_a_loja():
    corpo = (
        "Oi, pessoal da Bela Pele, tudo certo?\n\n"
        "Aqui é o Gabriel, faço lojas Shopify. Medi a página inicial de vocês num celular em 4G e a imagem principal "
        f"levou 9 segundos para aparecer. Deixei a medida completa aqui: {DA_MEDIDA}\n\n"
        "Trabalho com e-commerce há mais de 3 anos, com otimização e redesign, e agora tô me especializando em Shopify.\n\n"
        "Posso te mandar o que eu mudaria na página de vocês?\n\n"
        "Abraço,\nGabriel"
    )

    assert lojas_email.problemas_da_loja(EmailEscrito("Bela Pele", corpo), MedidaNoCelular(9.2, 3.2, 140, do_site=True)) == []
    html = sequencia_fria.html_simples(corpo)
    assert ">velozo.dev/br/velocidade/?loja=belapele.com.br</a>" in html and "utm_content=conversa" in html
    assert "velocidade/?loja=" in lojas_email.SISTEMA_DO_EMAIL_DA_LOJA


def _config(tmp_path: Path, extra: str = "") -> Path:
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(
        f'vault = "{(tmp_path / "vault").as_posix()}"\n[cacada]\nnicho_freela = "shopify"\nagencias_por_dia = 0\n{extra}', encoding="utf-8"
    )
    return arquivo


def test_a_vigia_prepara_o_email_do_dia_das_lojas_e_a_falha_nao_derruba(tmp_path: Path, monkeypatch, capsys):
    from whis import vigia_de_freelas
    from whis.__main__ import main

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho, **_opcoes: ())
    chamadas: list[dict] = []

    def preparar(vault, **opcoes):
        chamadas.append(opcoes)
        return [lojas_email.Preparado("contato@belapele.com.br", "Bela Pele", "cacada/lojas-emails/bela-pele.md")]

    monkeypatch.setattr(lojas_email, "preparar", preparar)

    assert main(["vigia-freelas", "--config", str(_config(tmp_path, "lojas_por_dia = 2\n"))]) == 0

    [opcoes] = chamadas
    assert opcoes["por_dia"] == 2 and opcoes["estado"] == lojas_email.caminho_do_estado() and callable(opcoes["medir_no_celular"])
    assert opcoes["por_dia_redesenho"] == 1 and callable(opcoes["conferir_tema"])
    assert opcoes["sequencia"] == tmp_path / "local" / "whis" / "cacada" / "sequencia-fria.json"
    assert "E-mail para a loja Bela Pele (contato@belapele.com.br) no celular" in capsys.readouterr().out

    monkeypatch.setattr(lojas_email, "preparar", lambda vault, **_opcoes: (_ for _ in ()).throw(RuntimeError("quebrou")))
    assert main(["vigia-freelas", "--config", str(_config(tmp_path))]) == 3
    monkeypatch.setattr(lojas_email, "preparar", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("rodou desligado")))
    assert main(["vigia-freelas", "--config", str(_config(tmp_path, "lojas_por_dia = 0\nlojas_redesenho_por_dia = 0\n"))]) == 0


def test_o_toque_de_loja_vai_para_o_email_das_lojas(tmp_path: Path, monkeypatch):
    from whis.__main__ import _tocou_no_celular
    from whis.celular import Resposta
    from whis.configuracao import carregar_texto

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    configuracao = carregar_texto(_config(tmp_path).read_text(encoding="utf-8"), origem=tmp_path / "config.toml")
    tocados: list[str] = []
    monkeypatch.setattr(lojas_email, "tocou_enviar_email", lambda dados, **_opcoes: tocados.append(dados) or Resposta("ok", tirar_botao=True))

    resposta = _tocou_no_celular(configuracao, lojas_email.chave_do_toque("contato@belapele.com.br"))

    assert resposta.texto == "ok" and tocados == [lojas_email.chave_do_toque("contato@belapele.com.br")]

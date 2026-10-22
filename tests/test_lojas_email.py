"""O e-mail para a loja Shopify lenta: medida de novo, um por dia no celular com o botão, e o toque manda pelo Gmail."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from whis import lojas_email
from whis.agencias_email import EmailEscrito, ErroDoEmail
from whis.lojas_shopify import CAMINHO_DA_LISTA_DE_LOJAS
from whis.medida_no_celular import MedidaNoCelular

AGORA = datetime(2026, 10, 18, 14, 0, tzinfo=timezone(timedelta(hours=-3)))
VELOCIDADE = "https://github.com/bielvelozo/inkly-shopify-theme#3-speed-measured"

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
        "Oi, pessoal da Bela Pele,\n\n"
        f"Testei a página inicial de vocês simulando um celular em 4G: a maior imagem levou {segundos} para aparecer, "
        "e a página baixou 3,2 MB.\n\n"
        "Sou o Gabriel, desenvolvedor Shopify em Matão (SP), e desde março cuido do tema de uma loja Shopify Plus. "
        f"Na minha loja de portfólio levei o mesmo tipo de página de 11,9 s para 3,5 s: {VELOCIDADE}\n\n"
        "Faço o ajuste com escopo, prazo e preço combinados antes, sem mexer no visual. Faz sentido eu mandar o que "
        "mudaria, com prazo e preço fechados?\n\n"
        "Se não for prioridade agora, é só responder que eu não escrevo de novo.\n\n"
        "Abraço,\nGabriel Velozo\ngithub.com/bielvelozo"
    )


@dataclass
class EscritorFake:
    respostas: list[EmailEscrito] = field(default_factory=lambda: [EmailEscrito("Página inicial da Bela Pele no celular", _corpo())])
    pedidos: list[tuple[str, float, str]] = field(default_factory=list)

    def escrever(self, alvo, medida, portfolio, *, corrigir=""):
        self.pedidos.append((alvo.email, medida.lcp_s, corrigir))
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
    def enviar(para: str, assunto: str, corpo: str) -> None:
        if falha is not None:
            raise falha
        enviados.append((para, assunto, corpo))

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


def test_o_texto_sem_o_numero_medido_ou_sem_a_saida_volta_ao_claude(tmp_path: Path):
    sem_numero = EmailEscrito("Oi", _corpo("uns segundos").replace("é só responder que eu não escrevo de novo", "me avise"))
    escritor = EscritorFake(respostas=[sem_numero, EmailEscrito("Página inicial da Bela Pele no celular", _corpo())])

    feitos, _, _, _ = _preparar(tmp_path, escritor=escritor)

    motivo = escritor.pedidos[1][2]
    assert '"9 segundos"' in motivo and "não escrevo de novo" in motivo
    assert len(feitos) == 1


def test_o_toque_manda_o_texto_da_nota_pelo_gmail_e_marca_enviado(tmp_path: Path):
    _preparar(tmp_path)
    arquivo = tmp_path / "vault" / "cacada" / "lojas-emails" / "bela-pele.md"
    arquivo.write_text(arquivo.read_text(encoding="utf-8").replace("Oi, pessoal da Bela Pele,", "Oi, pessoal,"), encoding="utf-8")
    enviados: list = []

    resposta = _tocar(tmp_path, enviados)
    segunda = _tocar(tmp_path, enviados)

    [(para, assunto, corpo)] = enviados
    assert para == "contato@belapele.com.br" and assunto == "Página inicial da Bela Pele no celular"
    assert corpo.startswith("Oi, pessoal,\n") and corpo.endswith("github.com/bielvelozo")
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


def test_o_pedido_leva_a_medida_e_o_jeito_de_escrever_o_tempo():
    from whis.criterios_da_cacada import PecaDoPortfolio

    alvo = lojas_email.AlvoLoja("Bela Pele", "Recife/PE", "https://belapele.com.br", "contato@belapele.com.br")
    texto = lojas_email.pedido(alvo, MedidaNoCelular(9.2, 3.2, 140), (PecaDoPortfolio("Velocidade da loja", VELOCIDADE, "LCP"),))

    assert 'Escreva o tempo exatamente assim: "9 segundos"' in texto and "3,2 MB" in texto and VELOCIDADE in texto
    assert lojas_email.FRASE_DE_SAIDA in lojas_email.SISTEMA_DO_EMAIL_DA_LOJA
    assert "nunca invente a causa" in lojas_email.SISTEMA_DO_EMAIL_DA_LOJA


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
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho: ())
    chamadas: list[dict] = []

    def preparar(vault, **opcoes):
        chamadas.append(opcoes)
        return [lojas_email.Preparado("contato@belapele.com.br", "Bela Pele", "cacada/lojas-emails/bela-pele.md")]

    monkeypatch.setattr(lojas_email, "preparar", preparar)

    assert main(["vigia-freelas", "--config", str(_config(tmp_path, "lojas_por_dia = 2\n"))]) == 0

    [opcoes] = chamadas
    assert opcoes["por_dia"] == 2 and opcoes["estado"] == lojas_email.caminho_do_estado() and callable(opcoes["medir_no_celular"])
    assert opcoes["por_dia_redesenho"] == 1 and callable(opcoes["conferir_tema"])
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

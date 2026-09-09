"""Comportamento do adaptador da Deepgram, sem rede.

As respostas vêm de fixtures JSON montadas a partir de exemplos reais da
documentação da Deepgram:

- `resposta_deepgram_codeswitching.json` é a resposta de exemplo **literal** de
  https://developers.deepgram.com/docs/multilingual-code-switching — sem
  `utterances`, e é ela que exercita o caminho de queda para o `transcript`.
- `resposta_deepgram_microfone.json` e `resposta_deepgram_sistema.json` usam
  esse mesmo envelope (`metadata` + `results.channels[].alternatives[]` com
  `languages`/`words[].language`), acrescido do bloco `results.utterances` no
  formato documentado em https://developers.deepgram.com/docs/utterances, com
  conteúdo em pt-BR e termos em inglês — que é o áudio real do usuário.

O HTTP é interceptado com `httpx.MockTransport`, então o código que monta a
requisição (URL, parâmetros, cabeçalhos, corpo) é exatamente o de produção.
Nenhuma fixture contém chave: a chave dos testes é literal e falsa.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

from fixtures.gravacao import criar_wav
from whis import pipeline
from whis.configuracao import Configuracao, ConfiguracaoInvalida, carregar
from whis.fakes import ResumoFake
from whis.portas import EU, OUTROS, CanaisDaGravacao, ErroDeSTT
from whis.stt_deepgram import (
    ENDPOINT,
    IDIOMA_PADRAO,
    MODELO_PADRAO,
    STTDeepgram,
    de_configuracao,
)

CHAVE_FALSA = "chave-de-teste-nao-e-segredo"
FIXTURES = Path(__file__).parent / "fixtures"

#: Variável que aponta uma pasta de gravação real para o teste marcado `rede`.
VARIAVEL_DA_GRAVACAO_REAL = "WHIS_GRAVACAO_DE_TESTE"


def carregar_fixture(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


@pytest.fixture
def canais(tmp_path: Path) -> CanaisDaGravacao:
    """Os dois canais de uma gravação, com o deslocamento do contrato."""
    criar_wav(tmp_path / "microfone.wav")
    criar_wav(tmp_path / "sistema.wav")
    return CanaisDaGravacao(
        microfone=tmp_path / "microfone.wav",
        sistema=tmp_path / "sistema.wav",
        taxa_microfone_hz=16000,
        taxa_sistema_hz=16000,
        metadados={
            "canais": {
                "microfone": {"arquivo": "microfone.wav", "offset_inicio_s": 0.0},
                "sistema": {"arquivo": "sistema.wav", "offset_inicio_s": 0.04},
            }
        },
    )


def adaptador(resposta, *, registro: list[httpx.Request] | None = None) -> STTDeepgram:
    """Adaptador com transporte falso.

    `resposta` pode ser um dicionário (mesma resposta para todo canal), uma
    lista de respostas na ordem das chamadas, um `httpx.Response` ou um
    callable que recebe a requisição.
    """
    pendentes = list(resposta) if isinstance(resposta, list) else None

    def responder(requisicao: httpx.Request) -> httpx.Response:
        if registro is not None:
            registro.append(requisicao)
        atual = pendentes.pop(0) if pendentes is not None else resposta
        if callable(atual):
            return atual(requisicao)
        if isinstance(atual, httpx.Response):
            return atual
        return httpx.Response(200, json=atual)

    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    return STTDeepgram(CHAVE_FALSA, cliente=cliente)


def adaptador_dos_dois_canais(registro: list[httpx.Request] | None = None) -> STTDeepgram:
    return adaptador(
        [
            carregar_fixture("resposta_deepgram_microfone.json"),
            carregar_fixture("resposta_deepgram_sistema.json"),
        ],
        registro=registro,
    )


# -- A requisição -----------------------------------------------------------


def test_envia_um_pedido_por_canal_para_o_endpoint_batch(canais: CanaisDaGravacao):
    registro: list[httpx.Request] = []

    adaptador_dos_dois_canais(registro).transcrever(canais)

    assert len(registro) == 2, "cada canal vai numa requisição própria"
    for requisicao in registro:
        assert requisicao.method == "POST"
        assert str(requisicao.url).startswith(ENDPOINT)


def test_requisicao_fixa_nova_3_multilingual_com_utterances(canais: CanaisDaGravacao):
    registro: list[httpx.Request] = []

    adaptador_dos_dois_canais(registro).transcrever(canais)

    parametros = registro[0].url.params
    assert parametros["model"] == MODELO_PADRAO == "nova-3"
    assert parametros["language"] == IDIOMA_PADRAO == "multi"
    assert parametros["smart_format"] == "true"
    assert parametros["utterances"] == "true"


def test_nao_pede_diarizacao_porque_os_canais_ja_separam_os_falantes(
    canais: CanaisDaGravacao,
):
    registro: list[httpx.Request] = []

    adaptador_dos_dois_canais(registro).transcrever(canais)

    parametros = registro[0].url.params
    assert "diarize" not in parametros
    assert "diarize_model" not in parametros


def test_autentica_com_a_chave_da_configuracao_e_manda_o_wav_no_corpo(
    canais: CanaisDaGravacao,
):
    registro: list[httpx.Request] = []

    adaptador_dos_dois_canais(registro).transcrever(canais)

    assert registro[0].headers["authorization"] == f"Token {CHAVE_FALSA}"
    assert registro[0].headers["content-type"] == "audio/wav"
    assert registro[0].content == (canais.microfone or Path()).read_bytes()
    assert registro[1].content == (canais.sistema or Path()).read_bytes()


# -- A tradução da resposta -------------------------------------------------


def test_microfone_vira_eu_e_sistema_vira_outros(canais: CanaisDaGravacao):
    transcricao = adaptador_dos_dois_canais().transcrever(canais)

    assert set(transcricao.falantes()) == {EU, OUTROS}
    do_eu = [fala.texto for fala in transcricao.falas if fala.falante == EU]
    dos_outros = [fala.texto for fala in transcricao.falas if fala.falante == OUTROS]
    assert any("Vamos começar pela daily?" in texto for texto in do_eu)
    assert any("terminei o deploy do pipeline novo." in texto for texto in dos_outros)


def test_falas_dos_dois_canais_saem_em_ordem_de_tempo(canais: CanaisDaGravacao):
    transcricao = adaptador_dos_dois_canais().transcrever(canais)

    falantes = [fala.falante for fala in transcricao.falas]
    inicios = [fala.inicio_s for fala in transcricao.falas]
    assert falantes == [EU, OUTROS, EU, OUTROS]
    assert inicios == sorted(inicios)


def test_deslocamento_do_canal_entra_no_tempo_da_fala(canais: CanaisDaGravacao):
    transcricao = adaptador_dos_dois_canais().transcrever(canais)

    primeira_dos_outros = next(fala for fala in transcricao.falas if fala.falante == OUTROS)
    # 3.2 s na resposta da Deepgram + 0.04 s de offset_inicio_s do gravacao.json.
    assert primeira_dos_outros.inicio_s == pytest.approx(3.24)


def test_termos_em_ingles_no_meio_do_portugues_sobrevivem(canais: CanaisDaGravacao):
    transcricao = adaptador_dos_dois_canais().transcrever(canais)

    texto = transcricao.texto_corrido()
    for termo in ("daily", "rollback", "code review", "deploy", "pipeline", "issue"):
        assert termo in texto, f"termo em inglês perdido: {termo}"
    assert "Bom dia, pessoal." in texto


def test_portugues_detectado_vira_pt_br_no_frontmatter(canais: CanaisDaGravacao):
    transcricao = adaptador_dos_dois_canais().transcrever(canais)

    assert transcricao.idioma == "pt-BR"


def test_resposta_sem_utterances_cai_para_o_transcript_do_canal(
    canais: CanaisDaGravacao,
):
    # A resposta literal da documentação de code-switching não traz utterances.
    exemplo = carregar_fixture("resposta_deepgram_codeswitching.json")

    transcricao = adaptador(exemplo).transcrever(canais)

    assert [fala.texto for fala in transcricao.falas] == [
        "No recuerdo mi bank password.",
        "No recuerdo mi bank password.",
    ]
    assert transcricao.idioma == "en+es", "sem português detectado, registra o que veio"


def test_canal_de_sistema_ausente_transcreve_so_o_microfone(tmp_path: Path):
    criar_wav(tmp_path / "microfone.wav")
    so_microfone = CanaisDaGravacao(microfone=tmp_path / "microfone.wav", sistema=None)
    registro: list[httpx.Request] = []

    transcricao = adaptador(
        carregar_fixture("resposta_deepgram_microfone.json"), registro=registro
    ).transcrever(so_microfone)

    assert len(registro) == 1
    assert transcricao.falantes() == (EU,)


def test_canal_declarado_mas_sumido_do_disco_e_ignorado(tmp_path: Path):
    criar_wav(tmp_path / "microfone.wav")
    canais = CanaisDaGravacao(
        microfone=tmp_path / "microfone.wav", sistema=tmp_path / "sistema.wav"
    )
    registro: list[httpx.Request] = []

    transcricao = adaptador(
        carregar_fixture("resposta_deepgram_microfone.json"), registro=registro
    ).transcrever(canais)

    assert len(registro) == 1
    assert transcricao.falantes() == (EU,)


# -- Falhas -----------------------------------------------------------------


def test_gravacao_sem_nenhum_canal_levanta_erro_de_stt():
    vazios = CanaisDaGravacao(microfone=None, sistema=None)

    with pytest.raises(ErroDeSTT, match="Nenhum canal de áudio"):
        adaptador({}).transcrever(vazios)


def test_audio_mudo_levanta_erro_de_stt_dizendo_o_que_conferir(
    canais: CanaisDaGravacao,
):
    vazia = {"metadata": {"request_id": "x"}, "results": {"channels": [], "utterances": []}}

    with pytest.raises(ErroDeSTT) as erro:
        adaptador(vazia).transcrever(canais)

    assert "não reconheceu nenhuma fala" in str(erro.value)
    assert "dispositivo_sistema" in str(erro.value)


@pytest.mark.parametrize(
    ("codigo", "corpo", "esperado"),
    [
        (401, {"err_code": "INVALID_AUTH", "err_msg": "Invalid credentials."}, "api_key"),
        (402, {"err_code": "ASR_PAYMENT_REQUIRED"}, "sem créditos"),
        (403, {"err_code": "INSUFFICIENT_PERMISSIONS"}, "acesso ao modelo"),
        (413, {}, "limite de tamanho"),
        (429, {"err_code": "TOO_MANY_REQUESTS"}, "limitou a taxa"),
        (504, {}, "tempo de processamento"),
        (503, {}, "fora do ar"),
    ],
)
def test_cada_status_http_vira_um_conselho_diferente(
    canais: CanaisDaGravacao, codigo: int, corpo: dict, esperado: str
):
    with pytest.raises(ErroDeSTT) as erro:
        adaptador(httpx.Response(codigo, json=corpo)).transcrever(canais)

    mensagem = str(erro.value)
    assert f"HTTP {codigo}" in mensagem
    assert esperado in mensagem
    assert "microfone.wav" in mensagem, "a mensagem diz em qual canal falhou"


def test_erro_da_deepgram_carrega_o_request_id_para_diagnostico(
    canais: CanaisDaGravacao,
):
    corpo = {
        "err_code": "INVALID_AUTH",
        "err_msg": "Invalid credentials.",
        "request_id": "b1c2d3e4-0000-4000-8000-abcdefabcdef",
    }

    with pytest.raises(ErroDeSTT) as erro:
        adaptador(httpx.Response(401, json=corpo)).transcrever(canais)

    assert "b1c2d3e4-0000-4000-8000-abcdefabcdef" in str(erro.value)


def test_rede_caida_vira_erro_de_stt_falando_em_conexao(canais: CanaisDaGravacao):
    def cair(requisicao: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rota para o host", request=requisicao)

    with pytest.raises(ErroDeSTT) as erro:
        adaptador(cair).transcrever(canais)

    assert "Falha de rede" in str(erro.value)
    assert "Confira a conexão" in str(erro.value)


def test_tempo_esgotado_vira_erro_de_stt_falando_em_upload(canais: CanaisDaGravacao):
    def demorar(requisicao: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("demorou demais", request=requisicao)

    with pytest.raises(ErroDeSTT) as erro:
        adaptador(demorar).transcrever(canais)

    assert "não respondeu a tempo" in str(erro.value)
    assert "upload lento" in str(erro.value)


def test_corpo_que_nao_e_json_vira_erro_de_stt(canais: CanaisDaGravacao):
    with pytest.raises(ErroDeSTT, match="não é JSON"):
        adaptador(httpx.Response(200, text="<html>oops</html>")).transcrever(canais)


def test_resposta_sem_results_vira_erro_de_stt(canais: CanaisDaGravacao):
    aceita = {"request_id": "a1b2c3d4-0000-4000-8000-abcdefabcdef"}

    with pytest.raises(ErroDeSTT) as erro:
        adaptador(aceita).transcrever(canais)

    assert "sem 'results'" in str(erro.value)
    assert "a1b2c3d4-0000-4000-8000-abcdefabcdef" in str(erro.value)


# -- Configuração -----------------------------------------------------------


def test_sem_chave_o_adaptador_recusa_ser_construido():
    with pytest.raises(ConfiguracaoInvalida) as erro:
        STTDeepgram("")

    assert "[deepgram].api_key" in str(erro.value)


def test_de_configuracao_le_a_chave_do_arquivo_local(
    tmp_path: Path, caminho_do_vault: Path, caminho_das_gravacoes: Path
):
    configuracao = Configuracao(
        vault=caminho_do_vault,
        gravacoes=caminho_das_gravacoes,
        deepgram_api_key=CHAVE_FALSA,
        origem=tmp_path / "config.toml",
    )
    registro: list[httpx.Request] = []
    resposta = carregar_fixture("resposta_deepgram_microfone.json")

    def responder(requisicao: httpx.Request) -> httpx.Response:
        registro.append(requisicao)
        return httpx.Response(200, json=resposta)

    stt = de_configuracao(
        configuracao,
        cliente=httpx.Client(transport=httpx.MockTransport(responder)),
    )
    criar_wav(tmp_path / "microfone.wav")
    stt.transcrever(CanaisDaGravacao(microfone=tmp_path / "microfone.wav", sistema=None))

    assert registro[0].headers["authorization"] == f"Token {CHAVE_FALSA}"


def test_de_configuracao_sem_chave_aponta_o_arquivo_a_corrigir(
    configuracao: Configuracao,
):
    # A configuração da costura tem `[deepgram] api_key = ""`.
    with pytest.raises(ConfiguracaoInvalida) as erro:
        de_configuracao(configuracao)

    assert str(configuracao.origem) in str(erro.value)


# -- Contra a API de verdade ------------------------------------------------
#
# Estes dois só rodam na máquina de destino, com a conta Deepgram criada e a
# chave na configuração local. Sem chave, pulam.


def chave_configurada() -> str:
    """A chave da configuração local de verdade — vazio quando não houver."""
    try:
        return carregar().deepgram_api_key
    except ConfiguracaoInvalida:
        return ""


@pytest.mark.rede
def test_rede_transcreve_o_audio_de_exemplo_da_deepgram(tmp_path: Path):
    """Prova ponta a ponta que chave, endpoint e parâmetros estão certos.

    Usa `https://dpgr.am/spacewalk.wav`, o áudio de exemplo da própria
    documentação (https://developers.deepgram.com/docs/pre-recorded-audio).
    """
    chave = chave_configurada()
    if not chave:
        pytest.skip("sem [deepgram].api_key na configuração local")

    exemplo = tmp_path / "microfone.wav"
    # `dpgr.am` é encurtador: sem seguir o redirect, o download vem vazio e a
    # Deepgram devolve 400 ("corrupt or unsupported data") em vez de transcrever.
    baixado = httpx.get(
        "https://dpgr.am/spacewalk.wav", timeout=60.0, follow_redirects=True
    )
    baixado.raise_for_status()
    exemplo.write_bytes(baixado.content)
    assert exemplo.stat().st_size > 100_000, "o áudio de exemplo não baixou"

    transcricao = STTDeepgram(chave).transcrever(
        CanaisDaGravacao(microfone=exemplo, sistema=None)
    )

    assert transcricao.falas, "a Deepgram devolveu falas"
    assert transcricao.falantes() == (EU,)
    assert transcricao.falas[0].inicio_s is not None


@pytest.mark.rede
def test_rede_gravacao_real_em_pt_br_vira_nota_no_vault(tmp_path: Path):
    """O critério de aceite completo, contra uma gravação de verdade.

    Aponte `WHIS_GRAVACAO_DE_TESTE` para uma pasta de gravação no
    formato do contrato (pt-BR com termos em inglês, os dois canais) e rode
    `pytest -m rede`. Escreve num vault temporário, nunca no vault real — e de
    propósito não usa a fixture `configuracao` da costura, que aponta
    `WHIS_CONFIG` para um arquivo de teste sem chave.
    """
    chave = chave_configurada()
    if not chave:
        pytest.skip("sem [deepgram].api_key na configuração local")
    pasta = os.environ.get(VARIAVEL_DA_GRAVACAO_REAL)
    if not pasta:
        pytest.skip(f"sem {VARIAVEL_DA_GRAVACAO_REAL} apontando uma gravação real")

    resultado = pipeline.processar(
        Path(pasta),
        configuracao=Configuracao(
            vault=tmp_path / "vault", gravacoes=Path(pasta).parent
        ),
        stt=STTDeepgram(chave),
        resumo=ResumoFake(),
        reprocessar=True,
    )

    texto = resultado.transcricao.read_text(encoding="utf-8")
    assert f"**{EU}:**" in texto
    assert f"**{OUTROS}:**" in texto
    assert resultado.nota.is_file()

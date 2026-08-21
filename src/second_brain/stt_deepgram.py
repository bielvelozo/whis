"""Adaptador real da porta de STT: Deepgram Nova-3 multilingual, em batch.

Cada canal da gravação vai para a API **separadamente** — `microfone.wav`
vira as falas de `EU`, `sistema.wav` vira as falas de `OUTROS`. É a separação
de canais que dá a distinção "eu vs. os outros"; nenhuma diarização é pedida
(o add-on custa por minuto e aqui não acrescenta nada). Depois as falas dos
dois canais são fundidas em ordem de tempo.

Parâmetros fixados contra a documentação oficial (conferida em 2026-08-20):

- endpoint batch `POST https://api.deepgram.com/v1/listen`, autenticado com
  `Authorization: Token <api_key>` e o áudio como corpo binário
  — https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded
  e https://developers.deepgram.com/docs/pre-recorded-audio
- `model=nova-3` — https://developers.deepgram.com/docs/models-languages-overview
- `language=multi` (code-switching; no nova-3 cobre português e inglês no
  mesmo áudio) — https://developers.deepgram.com/docs/multilingual-code-switching
- `smart_format=true` (pontuação e capitalização; dispensa `punctuate`)
  — https://developers.deepgram.com/docs/smart-format
- `utterances=true` (segmenta a fala em unidades com `start`/`end`, que é o
  que a fusão por tempo usa) — https://developers.deepgram.com/docs/utterances

A chave vem só da configuração local (`[deepgram].api_key`); nada de segredo
no repositório.
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

from .configuracao import VARIAVEL_DE_AMBIENTE, Configuracao, ConfiguracaoInvalida
from .portas import EU, OUTROS, CanaisDaGravacao, ErroDeSTT, Fala, Transcricao

_log = logging.getLogger("second_brain.stt")

#: Endpoint batch (pré-gravado) da Deepgram.
ENDPOINT = "https://api.deepgram.com/v1/listen"

#: Modelo e idioma do contrato da spec: Nova-3 multilingual.
MODELO_PADRAO = "nova-3"
IDIOMA_PADRAO = "multi"

#: Idioma registrado na transcrição quando a Deepgram detecta português.
IDIOMA_DO_VAULT = "pt-BR"

#: Tempos limite explícitos: uma reunião de uma hora é um upload grande
#: (WAV mono 48 kHz ≈ 350 MB), mas uma rede caída tem que aparecer rápido.
TEMPO_LIMITE_PADRAO = httpx.Timeout(connect=30.0, write=1800.0, read=1800.0, pool=30.0)

#: `Content-Type` por extensão; o gravador entrega WAV, o resto é cortesia.
_TIPOS_DE_AUDIO = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".webm": "audio/webm",
}


class STTDeepgram:
    """Porta de STT falando com a Deepgram por HTTP.

    `cliente` existe para os testes injetarem um `httpx.Client` com transporte
    falso: assim o caminho que monta a requisição é o mesmo em teste e em
    produção. Quando não vem, cada transcrição abre e fecha o seu cliente.
    """

    def __init__(
        self,
        api_key: str,
        *,
        modelo: str = MODELO_PADRAO,
        idioma: str = IDIOMA_PADRAO,
        tempo_limite: httpx.Timeout | float = TEMPO_LIMITE_PADRAO,
        endpoint: str = ENDPOINT,
        cliente: httpx.Client | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ConfiguracaoInvalida(
                "Chave da Deepgram ausente: preencha [deepgram].api_key na "
                f"configuração local (ou aponte {VARIAVEL_DE_AMBIENTE} para o "
                "arquivo certo). A chave sai da conta com o crédito de US$ 200 "
                "e nunca é versionada."
            )
        self._api_key = api_key.strip()
        self._modelo = modelo
        self._idioma = idioma
        self._tempo_limite = tempo_limite
        self._endpoint = endpoint
        self._cliente = cliente

    def transcrever(self, canais: CanaisDaGravacao) -> Transcricao:
        """Transcreve os canais e devolve as falas fundidas em ordem de tempo.

        Levanta `ErroDeSTT` em qualquer falha — o pipeline já cuida de
        preservar a gravação e não escrever nota parcial.
        """
        pendentes = list(_canais_presentes(canais))
        if not pendentes:
            raise ErroDeSTT(
                "Nenhum canal de áudio para transcrever: nem microfone.wav nem "
                "sistema.wav existem na pasta da gravação. A gravação foi "
                "preservada; confira o gravador antes de reprocessar."
            )
        if len(pendentes) == 1:
            _log.warning(
                "Só o canal '%s' existe nesta gravação — a transcrição vai sair "
                "com um lado só da conversa.",
                pendentes[0][0],
            )

        falas: list[Fala] = []
        idiomas: list[str] = []
        with self._sessao() as cliente:
            for falante, arquivo, deslocamento_s in pendentes:
                resposta = self._enviar(cliente, arquivo)
                do_canal = list(_falas_da_resposta(resposta, falante, deslocamento_s))
                _log.info(
                    "Canal '%s' transcrito: %d falas em %s.",
                    falante,
                    len(do_canal),
                    arquivo.name,
                )
                if not do_canal:
                    _log.warning(
                        "Canal '%s' (%s) voltou sem nenhuma fala — áudio mudo? "
                        "No canal do sistema isso costuma ser roteamento de "
                        "loopback errado na configuração.",
                        falante,
                        arquivo.name,
                    )
                falas.extend(do_canal)
                idiomas.extend(_idiomas_da_resposta(resposta))

        if not falas:
            raise ErroDeSTT(
                "A Deepgram respondeu, mas não reconheceu nenhuma fala em "
                f"{', '.join(arquivo.name for _, arquivo, _ in pendentes)}. "
                "O caso mais comum é canal mudo: confira 'dispositivo_sistema' "
                "e 'dispositivo_microfone' na configuração e ouça os WAV da "
                "pasta da gravação, que continua preservada."
            )

        falas.sort(key=lambda fala: (fala.inicio_s is None, fala.inicio_s or 0.0))
        detectados = _sem_repetir(idiomas)
        _log.info(
            "Transcrição fundida: %d falas, idiomas detectados: %s.",
            len(falas),
            ", ".join(detectados) or "nenhum",
        )
        return Transcricao(falas=tuple(falas), idioma=_idioma_da_transcricao(detectados))

    # -- HTTP ---------------------------------------------------------------

    @contextlib.contextmanager
    def _sessao(self) -> Iterator[httpx.Client]:
        """O cliente injetado (teste) ou um cliente próprio, fechado no fim."""
        if self._cliente is not None:
            yield self._cliente
            return
        with httpx.Client(timeout=self._tempo_limite) as cliente:
            yield cliente

    def _enviar(self, cliente: httpx.Client, arquivo: Path) -> dict[str, Any]:
        """Manda um canal para a Deepgram e devolve o JSON já validado."""
        try:
            audio = arquivo.read_bytes()
        except OSError as erro:
            raise ErroDeSTT(
                f"Não foi possível ler o áudio {arquivo}: {erro}. A gravação "
                "continua na pasta — confira permissões e disco antes de "
                "reprocessar."
            ) from erro

        _log.info(
            "Enviando %s (%.1f MB) para a Deepgram (model=%s, language=%s)...",
            arquivo.name,
            len(audio) / (1024 * 1024),
            self._modelo,
            self._idioma,
        )
        try:
            resposta = cliente.post(
                self._endpoint,
                params=self._parametros(),
                headers={
                    "Authorization": f"Token {self._api_key}",
                    "Content-Type": _tipo_do_audio(arquivo),
                },
                content=audio,
                timeout=self._tempo_limite,
            )
        except httpx.TimeoutException as erro:
            raise ErroDeSTT(
                f"A Deepgram não respondeu a tempo ao enviar {arquivo.name} "
                f"({len(audio) / (1024 * 1024):.1f} MB): {type(erro).__name__}. "
                "Em reunião longa isso costuma ser upload lento — tente "
                "reprocessar a pasta com a rede mais estável."
            ) from erro
        except httpx.HTTPError as erro:
            raise ErroDeSTT(
                f"Falha de rede ao falar com a Deepgram ({self._endpoint}): "
                f"{type(erro).__name__}: {erro}. Confira a conexão; a gravação "
                "foi preservada e pode ser reprocessada."
            ) from erro

        if resposta.status_code != httpx.codes.OK:
            raise _erro_de_http(resposta, arquivo)

        try:
            dados = resposta.json()
        except (json.JSONDecodeError, ValueError) as erro:
            raise ErroDeSTT(
                f"A Deepgram devolveu 200 mas o corpo não é JSON ao transcrever "
                f"{arquivo.name}: {erro}. Reprocesse a pasta; se repetir, é "
                "problema do lado da Deepgram."
            ) from erro

        if not isinstance(dados, dict) or "results" not in dados:
            raise ErroDeSTT(
                f"Resposta da Deepgram sem 'results' ao transcrever "
                f"{arquivo.name} (request_id={_request_id(dados)}). O adaptador "
                "não usa callback, então a resposta deveria vir com a "
                "transcrição — reprocesse a pasta."
            )
        return dados

    def _parametros(self) -> dict[str, str]:
        """Os parâmetros de query da requisição — todos fixados na documentação."""
        return {
            "model": self._modelo,
            "language": self._idioma,
            "smart_format": "true",
            "utterances": "true",
        }


def de_configuracao(configuracao: Configuracao, **extras: Any) -> STTDeepgram:
    """Monta o adaptador a partir da configuração local — o atalho da CLI.

    Levanta `ConfiguracaoInvalida` (que a CLI já trata) quando a chave da
    Deepgram não está preenchida, com uma mensagem que diz onde preenchê-la.
    """
    try:
        return STTDeepgram(configuracao.deepgram_api_key, **extras)
    except ConfiguracaoInvalida as erro:
        if configuracao.origem is None:
            raise
        raise ConfiguracaoInvalida(f"{erro} Arquivo: {configuracao.origem}") from erro


# -- Leitura da resposta ----------------------------------------------------


def _canais_presentes(canais: CanaisDaGravacao) -> Iterator[tuple[str, Path, float]]:
    """Os canais que existem no disco, com o rótulo e o deslocamento de cada um.

    O deslocamento (`offset_inicio_s` do `gravacao.json`) é o atraso do canal
    em relação ao início da gravação: somá-lo aos tempos da Deepgram é o que
    coloca as falas dos dois canais na mesma linha do tempo.
    """
    for falante, arquivo, chave in (
        (EU, canais.microfone, "microfone"),
        (OUTROS, canais.sistema, "sistema"),
    ):
        if arquivo is None:
            _log.info("Canal '%s' ausente nesta gravação.", falante)
            continue
        caminho = Path(arquivo)
        if not caminho.is_file():
            _log.warning("Canal '%s' declarado mas ausente em %s.", falante, caminho)
            continue
        yield falante, caminho, _deslocamento(canais.metadados, chave)


def _deslocamento(metadados: dict, chave: str) -> float:
    declarado = (metadados.get("canais") or {}).get(chave) or {}
    try:
        return float(declarado.get("offset_inicio_s") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _falas_da_resposta(
    resposta: dict[str, Any], falante: str, deslocamento_s: float
) -> Iterator[Fala]:
    """Traduz a resposta de um canal em falas daquele falante.

    O caminho normal são as `results.utterances` (pedidas com
    `utterances=true`), que já vêm segmentadas com `start`. Quando não vierem,
    cai para o `transcript` inteiro do canal, como uma fala só.
    """
    resultados = resposta.get("results") or {}
    utterances = resultados.get("utterances")
    if isinstance(utterances, list) and utterances:
        for trecho in utterances:
            texto = (trecho.get("transcript") or "").strip()
            if not texto:
                continue
            yield Fala(
                falante=falante,
                texto=texto,
                inicio_s=_instante(trecho.get("start"), deslocamento_s),
            )
        return

    for alternativa in _alternativas(resultados):
        texto = (alternativa.get("transcript") or "").strip()
        if texto:
            yield Fala(falante=falante, texto=texto, inicio_s=deslocamento_s)


def _alternativas(resultados: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """A primeira alternativa de cada canal da resposta (áudio nosso é mono)."""
    for canal in resultados.get("channels") or []:
        alternativas = canal.get("alternatives") or []
        if alternativas:
            yield alternativas[0]


def _idiomas_da_resposta(resposta: dict[str, Any]) -> Iterator[str]:
    """Os idiomas que o `language=multi` detectou, na ordem em que aparecem."""
    for alternativa in _alternativas(resposta.get("results") or {}):
        for idioma in alternativa.get("languages") or []:
            if isinstance(idioma, str):
                yield idioma


def _idioma_da_transcricao(idiomas: list[str]) -> str:
    """Qual idioma registrar no frontmatter da transcrição.

    Reunião do usuário é português com termos em inglês: assim que a Deepgram
    detecta português, o rótulo é `pt-BR`. Sem português detectado (ou sem
    detecção nenhuma), registra honestamente o que veio.
    """
    if not idiomas:
        return IDIOMA_DO_VAULT
    if any(idioma.lower().startswith("pt") for idioma in idiomas):
        return IDIOMA_DO_VAULT
    return "+".join(_sem_repetir(idiomas))


def _sem_repetir(itens: list[str]) -> list[str]:
    """Os itens distintos, na ordem em que apareceram."""
    unicos: list[str] = []
    for item in itens:
        if item not in unicos:
            unicos.append(item)
    return unicos


def _instante(bruto: Any, deslocamento_s: float) -> float | None:
    try:
        return float(bruto) + deslocamento_s
    except (TypeError, ValueError):
        return None


def _tipo_do_audio(arquivo: Path) -> str:
    return _TIPOS_DE_AUDIO.get(arquivo.suffix.lower(), "application/octet-stream")


# -- Erros ------------------------------------------------------------------


def _erro_de_http(resposta: httpx.Response, arquivo: Path) -> ErroDeSTT:
    """Traduz o status HTTP em uma mensagem que diz o que fazer.

    Chave inválida, crédito acabado, arquivo grande demais e serviço fora do ar
    são problemas diferentes e a mensagem precisa separá-los — é isso que torna
    o `estado.json` da gravação diagnosticável depois.
    """
    codigo = resposta.status_code
    detalhe = _detalhe_do_erro(resposta)
    tamanho_mb = _tamanho_mb(arquivo)
    conselhos = {
        400: (
            "A Deepgram recusou a requisição. Provavelmente um parâmetro ou um "
            "formato de áudio não aceito — confira o WAV da pasta da gravação."
        ),
        401: (
            "Chave da Deepgram inválida ou sem permissão. Confira "
            "[deepgram].api_key na configuração local e gere outra chave no "
            "painel da Deepgram se preciso."
        ),
        402: (
            "A conta Deepgram está sem créditos. Confira o saldo do crédito de "
            "US$ 200 no painel; a gravação fica preservada até você reprocessar."
        ),
        403: (
            "A conta Deepgram não tem acesso ao modelo pedido. Confira o plano "
            "e o modelo configurado."
        ),
        413: (
            f"O áudio {arquivo.name} ({tamanho_mb}) passou do limite de tamanho "
            "da Deepgram (2 GB por requisição). Corte a gravação antes de "
            "reprocessar."
        ),
        429: (
            "A Deepgram limitou a taxa de requisições. Espere alguns minutos e "
            "reprocesse a pasta da gravação."
        ),
        504: (
            f"A Deepgram estourou o tempo de processamento com {arquivo.name} "
            f"({tamanho_mb}). Reuniões muito longas podem precisar ser "
            "cortadas antes de reprocessar."
        ),
    }
    conselho = conselhos.get(codigo)
    if conselho is None:
        if codigo >= 500:
            conselho = (
                "A Deepgram está fora do ar ou instável. Reprocesse a pasta da "
                "gravação mais tarde."
            )
        else:
            conselho = (
                "A Deepgram recusou a requisição. Confira a configuração e "
                "reprocesse a pasta da gravação."
            )
    return ErroDeSTT(
        f"Deepgram respondeu HTTP {codigo} ao transcrever {arquivo.name} "
        f"({tamanho_mb}): {conselho}{detalhe}"
    )


def _detalhe_do_erro(resposta: httpx.Response) -> str:
    """O `err_code`/`err_msg`/`request_id` da Deepgram, quando houver."""
    try:
        corpo = resposta.json()
    except (json.JSONDecodeError, ValueError):
        texto = (resposta.text or "").strip()
        return f" Resposta: {texto[:200]}" if texto else ""
    if not isinstance(corpo, dict):
        return ""
    partes = [
        f"{chave}={corpo[chave]}"
        for chave in ("err_code", "err_msg", "request_id")
        if corpo.get(chave)
    ]
    return f" ({', '.join(partes)})" if partes else ""


def _tamanho_mb(arquivo: Path) -> str:
    try:
        return f"{arquivo.stat().st_size / (1024 * 1024):.1f} MB"
    except OSError:
        return "tamanho desconhecido"


def _request_id(dados: Any) -> str:
    if isinstance(dados, dict):
        metadados = dados.get("metadata")
        if isinstance(metadados, dict) and metadados.get("request_id"):
            return str(metadados["request_id"])
        if dados.get("request_id"):
            return str(dados["request_id"])
    return "desconhecido"

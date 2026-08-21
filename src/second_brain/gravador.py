"""Gravador WASAPI do coletor de reunião.

Captura **sob demanda** (glossário): grava apenas entre um `iniciar()` e um
`parar()` explícitos, nunca de forma contínua. Dois streams no mesmo processo —
o microfone e o loopback WASAPI (a voz dos outros no fone) — escrevem
**arquivos separados** dentro de uma pasta de gravação datada, no formato do
contrato (`.scratch/tracer-bullet/contrato-pasta-gravacao.md`).

A pasta produzida aqui é a matéria-prima do pipeline. Este módulo nunca escreve
`estado.json` (dono do pipeline) e nunca toca o vault.

Nenhum dispositivo é fixado no código: a escolha vem da configuração e, quando
ela está vazia, do padrão do sistema. O subcomando `dispositivos` é a ferramenta
para descobrir os nomes numa máquina desconhecida.

Linha de comando::

    python -m second_brain.gravador dispositivos
    python -m second_brain.gravador gravar --titulo "daily do time"
    python -m second_brain.gravador testar --segundos 8
    python -m second_brain.gravador conferir <pasta-da-gravacao>

Biblioteca (é o que a bandeja da camada 05 chama)::

    gravador = Gravador()
    pasta = gravador.iniciar("daily do time")
    ...
    pasta = gravador.parar()
"""

from __future__ import annotations

import argparse
import array
import json
import logging
import math
import os
import queue
import re
import sys
import tempfile
import threading
import time
import tomllib
import unicodedata
import wave
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

import pyaudiowpatch as pyaudio

log = logging.getLogger("second_brain.gravador")

VERSAO_CONTRATO = 1
CANAL_MICROFONE = "microfone"
CANAL_SISTEMA = "sistema"
SLUG_PADRAO = "reuniao"
NOME_METADADOS = "gravacao.json"

_FORMATO = pyaudio.paInt16
_LARGURA_AMOSTRA_BYTES = 2
_QUADROS_POR_BLOCO = 1024
_ESPERA_FILA_S = 0.2
_DEFICIT_MINIMO_S = 0.5        # só preenche silêncio quando o atraso passa disso
_LIMIAR_RMS_MUDO = 1.0         # RMS na escala int16; abaixo disso é silêncio digital
_SEGUNDOS_ATE_AVISO_MUDO = 20.0
_INTERVALO_LOG_NIVEL_S = 30.0
_BLOCO_DE_ANALISE = 65536      # quadros lidos por vez ao conferir um WAV
_MAXIMO_BLOCOS_ANALISADOS = 200


class ErroDeGravacao(RuntimeError):
    """Falha na captura de áudio da reunião."""


class DispositivoNaoEncontrado(ErroDeGravacao):
    """A configuração aponta para um dispositivo que não existe nesta máquina."""


# ---------------------------------------------------------------- configuração


@dataclass(frozen=True)
class ConfiguracaoGravador:
    """As chaves da configuração local que o gravador consome.

    `gravacoes` é a raiz das pastas de gravação (fora do vault). Os dois nomes de
    dispositivo vêm de `[audio]`; vazio significa "padrão do sistema".
    """

    gravacoes: Path
    dispositivo_microfone: str = ""
    dispositivo_sistema: str = ""
    origem: Path | None = None


def caminho_da_configuracao() -> Path:
    """Caminho do TOML: `SECOND_BRAIN_CONFIG` ou `%APPDATA%\\second-brain\\config.toml`."""
    override = os.environ.get("SECOND_BRAIN_CONFIG", "").strip()
    if override:
        return Path(override)
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "second-brain" / "config.toml"


def carregar_configuracao(caminho: str | os.PathLike[str] | None = None) -> ConfiguracaoGravador:
    """Lê o TOML local e devolve só as chaves que o gravador consome.

    Sem `gravacoes` não há onde gravar — e adivinhar uma pasta faria o gravador
    escrever num lugar que o pipeline não olha. Por isso a ausência é erro, com
    mensagem dizendo qual arquivo criar.
    """
    origem = Path(caminho) if caminho else caminho_da_configuracao()
    if not origem.is_file():
        raise ErroDeGravacao(
            f"configuração não encontrada em {origem}. Crie o arquivo com a chave "
            "'gravacoes' (e a seção [audio]), ou aponte SECOND_BRAIN_CONFIG para outro caminho."
        )
    try:
        dados = tomllib.loads(origem.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as erro:
        raise ErroDeGravacao(f"configuração inválida em {origem}: {erro}") from erro

    bruto = str(dados.get("gravacoes") or "").strip()
    if not bruto:
        raise ErroDeGravacao(
            f"a chave 'gravacoes' está ausente ou vazia em {origem} — é a pasta, fora do vault, "
            "onde as gravações são salvas."
        )
    audio = dados.get("audio") or {}
    return ConfiguracaoGravador(
        gravacoes=Path(bruto).expanduser(),
        dispositivo_microfone=str(audio.get("dispositivo_microfone") or "").strip(),
        dispositivo_sistema=str(audio.get("dispositivo_sistema") or "").strip(),
        origem=origem,
    )


# ---------------------------------------------------------------- dispositivos


@dataclass(frozen=True)
class Dispositivo:
    """Um dispositivo de entrada WASAPI — microfone físico ou loopback de saída."""

    indice: int
    nome: str
    taxa_hz: int
    canais: int
    loopback: bool
    padrao_microfone: bool = False
    padrao_sistema: bool = False

    @property
    def rotulo(self) -> str:
        """Linha legível para o usuário escolher o dispositivo certo."""
        marcas: list[str] = [
            "loopback (o que sai pelo fone/caixa)" if self.loopback else "entrada (microfone)"
        ]
        if self.padrao_microfone:
            marcas.append("PADRÃO do sistema para microfone")
        if self.padrao_sistema:
            marcas.append("PADRÃO do sistema para áudio de saída")
        return (
            f"{self.nome}\n        {self.taxa_hz} Hz · {self.canais} canal(is) · "
            + " · ".join(marcas)
        )


def listar_dispositivos() -> list[Dispositivo]:
    """Todos os dispositivos WASAPI que servem de entrada, com os padrões marcados."""
    portaudio = pyaudio.PyAudio()
    try:
        return _listar(portaudio)
    finally:
        portaudio.terminate()


def _indice_padrao(consulta) -> int | None:
    try:
        return int(consulta()["index"])
    except Exception:  # noqa: BLE001 — ausência de padrão não pode derrubar a listagem
        return None


def _listar(portaudio: "pyaudio.PyAudio") -> list[Dispositivo]:
    padrao_microfone = _indice_padrao(lambda: portaudio.get_default_wasapi_device(d_in=True))
    padrao_sistema = _indice_padrao(portaudio.get_default_wasapi_loopback)
    dispositivos: list[Dispositivo] = []
    for info in portaudio.get_device_info_generator_by_host_api(host_api_type=pyaudio.paWASAPI):
        if int(info["maxInputChannels"]) < 1:
            continue
        indice = int(info["index"])
        dispositivos.append(
            Dispositivo(
                indice=indice,
                nome=str(info["name"]),
                taxa_hz=int(info["defaultSampleRate"]),
                canais=int(info["maxInputChannels"]),
                loopback=bool(info.get("isLoopbackDevice")),
                padrao_microfone=indice == padrao_microfone,
                padrao_sistema=indice == padrao_sistema,
            )
        )
    return dispositivos


def _resolver_dispositivo(portaudio: "pyaudio.PyAudio", nome: str, *, sistema: bool) -> dict:
    """Traduz o nome configurado em "info dict" do PortAudio.

    Nome vazio = padrão do sistema. Nome preenchido casa primeiro exato e depois
    por trecho, sem privilegiar fabricante nenhum; ambiguidade vira erro com a
    lista dos candidatos, porque adivinhar aqui é o que faz gravar o canal errado.
    """
    alvo = (nome or "").strip()
    canal = CANAL_SISTEMA if sistema else CANAL_MICROFONE
    if not alvo:
        try:
            if sistema:
                return portaudio.get_default_wasapi_loopback()
            return portaudio.get_default_wasapi_device(d_in=True)
        except (OSError, LookupError) as erro:
            raise DispositivoNaoEncontrado(
                f"não há dispositivo padrão do sistema para o canal '{canal}' ({erro}). "
                f"{_dica_de_configuracao(canal)}"
            ) from erro

    disponiveis = _listar(portaudio)
    exatos = [d for d in disponiveis if d.nome.casefold() == alvo.casefold()]
    candidatos = exatos or [d for d in disponiveis if alvo.casefold() in d.nome.casefold()]
    if not candidatos:
        raise DispositivoNaoEncontrado(
            f"nenhum dispositivo de entrada casa com {alvo!r} (canal '{canal}'). "
            f"{_dica_de_configuracao(canal)}"
        )
    if len(candidatos) > 1:
        nomes = ", ".join(repr(d.nome) for d in candidatos)
        raise DispositivoNaoEncontrado(
            f"{alvo!r} casa com mais de um dispositivo (canal '{canal}'): {nomes}. "
            f"Use o nome completo. {_dica_de_configuracao(canal)}"
        )
    return portaudio.get_device_info_by_index(candidatos[0].indice)


def _chave_de_configuracao(canal: str) -> str:
    return "[audio].dispositivo_sistema" if canal == CANAL_SISTEMA else "[audio].dispositivo_microfone"


def _dica_de_configuracao(canal: str) -> str:
    return (
        "Rode 'python -m second_brain.gravador dispositivos', copie o nome do dispositivo certo "
        f"e ajuste {_chave_de_configuracao(canal)} em {caminho_da_configuracao()}."
    )


def _mensagem_canal_mudo(canal: str) -> str:
    if canal == CANAL_SISTEMA:
        pista = (
            "o áudio da reunião não passou pelo dispositivo capturado — com fone, o loopback "
            "precisa ser o dispositivo de saída que está de fato tocando o som"
        )
    else:
        pista = "o microfone capturado não recebeu voz (mudo, desconectado ou dispositivo errado)"
    return f"canal '{canal}' saiu MUDO: {pista}. {_dica_de_configuracao(canal)}"


# -------------------------------------------------------------------- captura


class _CanalEmGravacao:
    """Um stream WASAPI escrevendo um WAV mono PCM 16-bit na taxa nativa do dispositivo.

    O callback do PortAudio só enfileira bytes; uma thread escreve, mixa para mono
    e mede o nível. Quando o dispositivo para de entregar frames — o que acontece
    no loopback WASAPI enquanto nada está tocando — a thread preenche silêncio
    pelo relógio, para os dois arquivos não saírem desalinhados.
    """

    def __init__(
        self,
        canal: str,
        portaudio: "pyaudio.PyAudio",
        info: dict,
        destino: Path,
        inicio_da_gravacao: float,
    ) -> None:
        self.canal = canal
        self.dispositivo = str(info["name"])
        self.taxa_hz = int(info["defaultSampleRate"])
        self.offset_inicio_s = 0.0
        self.silencio_preenchido_s = 0.0
        self._portaudio = portaudio
        self._indice = int(info["index"])
        self._canais_do_dispositivo = max(1, int(info["maxInputChannels"]))
        self._destino = destino
        self._inicio_da_gravacao = inicio_da_gravacao
        self._fila: "queue.Queue[bytes]" = queue.Queue()
        self._ativo = threading.Event()
        self._arquivo: wave.Wave_write | None = None
        self._stream = None
        self._escritor: threading.Thread | None = None
        self._quadros = 0
        self._soma_quadrados = 0.0
        self._amostras = 0
        self._pico = 0
        self._avisou_mudo = False
        self._inicio = 0.0
        self._ultimo_log = 0.0

    # -- ciclo de vida

    def abrir(self) -> None:
        self._arquivo = wave.open(str(self._destino), "wb")
        self._arquivo.setnchannels(1)
        self._arquivo.setsampwidth(_LARGURA_AMOSTRA_BYTES)
        self._arquivo.setframerate(self.taxa_hz)
        try:
            self._stream = self._portaudio.open(
                format=_FORMATO,
                channels=self._canais_do_dispositivo,
                rate=self.taxa_hz,
                input=True,
                input_device_index=self._indice,
                frames_per_buffer=_QUADROS_POR_BLOCO,
                stream_callback=self._receber,
            )
        except Exception:
            self._arquivo.close()
            self._arquivo = None
            self._destino.unlink(missing_ok=True)
            raise
        self._inicio = time.monotonic()
        self._ultimo_log = self._inicio
        self.offset_inicio_s = round(max(0.0, self._inicio - self._inicio_da_gravacao), 3)
        self._ativo.set()
        self._escritor = threading.Thread(
            target=self._escrever, name=f"gravador-{self.canal}", daemon=True
        )
        self._escritor.start()
        log.info(
            "canal '%s': gravando de %r (%d Hz, %d canal(is) do dispositivo → mono) em %s",
            self.canal,
            self.dispositivo,
            self.taxa_hz,
            self._canais_do_dispositivo,
            self._destino.name,
        )

    def fechar(self) -> dict:
        """Fecha stream e arquivo e devolve o bloco de metadados do contrato."""
        if self._stream is not None:
            try:
                self._stream.stop_stream()
            finally:
                self._stream.close()
                self._stream = None
        self._ativo.clear()
        if self._escritor is not None:
            self._escritor.join(timeout=10.0)
            self._escritor = None
        while True:  # o que sobrou na fila depois do join
            try:
                self._gravar_bloco(self._fila.get_nowait())
            except queue.Empty:
                break
        if self._arquivo is not None:
            self._arquivo.close()
            self._arquivo = None
        return {
            "arquivo": self._destino.name,
            "taxa_hz": self.taxa_hz,
            "canais": 1,
            "dispositivo": self.dispositivo,
            "offset_inicio_s": self.offset_inicio_s,
        }

    # -- medição

    @property
    def rms(self) -> float:
        """Nível médio do que o dispositivo entregou (silêncio preenchido não conta)."""
        if not self._amostras:
            return 0.0
        return math.sqrt(self._soma_quadrados / self._amostras)

    @property
    def pico(self) -> int:
        return self._pico

    @property
    def duracao_s(self) -> float:
        return self._quadros / self.taxa_hz if self.taxa_hz else 0.0

    @property
    def mudo(self) -> bool:
        return self.rms < _LIMIAR_RMS_MUDO

    # -- internos

    def _receber(self, dados, quadros, info_tempo, estado):  # noqa: ARG002 — assinatura do PortAudio
        self._fila.put(dados)
        return (None, pyaudio.paContinue)

    def _escrever(self) -> None:
        while True:
            try:
                dados = self._fila.get(timeout=_ESPERA_FILA_S)
            except queue.Empty:
                if not self._ativo.is_set():
                    return
                self._preencher_silencio()
                self._avaliar_nivel()
                continue
            try:
                self._gravar_bloco(dados)
                self._avaliar_nivel()
            except Exception as erro:  # noqa: BLE001 — a gravação não pode morrer calada
                log.error("canal '%s': falha ao escrever bloco: %s", self.canal, erro)
                return

    def _gravar_bloco(self, dados: bytes) -> None:
        mono = self._para_mono(dados)
        if not len(mono):
            return
        if self._arquivo is not None:
            self._arquivo.writeframes(mono.tobytes())
        self._quadros += len(mono)
        self._soma_quadrados += sum(float(a) * a for a in mono)
        self._amostras += len(mono)
        self._pico = max(self._pico, max(mono), -min(mono))

    def _para_mono(self, dados: bytes) -> array.array:
        amostras = array.array("h")
        amostras.frombytes(dados)
        canais = self._canais_do_dispositivo
        if canais == 1:
            return amostras
        return array.array(
            "h",
            [
                sum(amostras[i : i + canais]) // canais
                for i in range(0, len(amostras) - canais + 1, canais)
            ],
        )

    def _preencher_silencio(self) -> None:
        """Pegadinha do loopback WASAPI: sem áudio tocando, o dispositivo pode não
        entregar frames. Sem isso, `sistema.wav` encolheria e sairia do lugar em
        relação a `microfone.wav`.
        """
        esperado = int((time.monotonic() - self._inicio) * self.taxa_hz)
        deficit = esperado - self._quadros
        if deficit < int(_DEFICIT_MINIMO_S * self.taxa_hz):
            return
        if self._arquivo is not None:
            self._arquivo.writeframes(b"\x00\x00" * deficit)
        self._quadros += deficit
        self.silencio_preenchido_s += deficit / self.taxa_hz

    def _avaliar_nivel(self) -> None:
        agora = time.monotonic()
        decorrido = agora - self._inicio
        if not self._avisou_mudo and decorrido >= _SEGUNDOS_ATE_AVISO_MUDO and self.mudo:
            self._avisou_mudo = True
            log.warning(
                "%s (detectado nos primeiros %.0f s)", _mensagem_canal_mudo(self.canal), decorrido
            )
        if agora - self._ultimo_log >= _INTERVALO_LOG_NIVEL_S:
            self._ultimo_log = agora
            log.info(
                "canal '%s': %.0f s gravados, nível RMS %.1f (pico %d)",
                self.canal,
                self.duracao_s,
                self.rms,
                self._pico,
            )


class Gravador:
    """A máquina de gravação da reunião — sob demanda, dois canais, arquivos separados.

    É a API que a bandeja (camada 05) chama; a bandeja não tem lógica própria::

        gravador = Gravador()
        pasta = gravador.iniciar("daily do time")
        gravador.gravando   # True
        pasta = gravador.parar()
    """

    def __init__(
        self,
        configuracao: ConfiguracaoGravador | None = None,
        *,
        titulo: str | None = None,
    ) -> None:
        self._configuracao = configuracao or carregar_configuracao()
        self._titulo = titulo
        self._pasta: Path | None = None
        self._portaudio: "pyaudio.PyAudio | None" = None
        self._canais: dict[str, _CanalEmGravacao] = {}
        self._inicio: datetime | None = None
        self._inicio_monotonico = 0.0
        self._trava = threading.Lock()

    # -- estado

    @property
    def configuracao(self) -> ConfiguracaoGravador:
        return self._configuracao

    @property
    def gravando(self) -> bool:
        return self._portaudio is not None

    @property
    def pasta(self) -> Path | None:
        """Pasta da gravação em andamento (ou `None` quando parado)."""
        return self._pasta

    def niveis(self) -> dict[str, float]:
        """RMS corrente de cada canal aberto — a bandeja usa para mostrar canal mudo."""
        return {nome: canal.rms for nome, canal in self._canais.items()}

    # -- comandos

    def iniciar(self, titulo: str | None = None) -> Path:
        """Abre os dois streams e começa a escrever. Devolve a pasta da gravação."""
        with self._trava:
            if self.gravando:
                raise ErroDeGravacao("já existe uma gravação em andamento")
            if titulo is not None:
                self._titulo = titulo
            agora = datetime.now().astimezone()
            self._pasta = _criar_pasta(self._configuracao.gravacoes, agora, self._titulo)
            self._inicio = agora
            self._portaudio = pyaudio.PyAudio()
            self._inicio_monotonico = time.monotonic()
            self._canais = {}
            alvos = (
                (CANAL_MICROFONE, self._configuracao.dispositivo_microfone, False),
                (CANAL_SISTEMA, self._configuracao.dispositivo_sistema, True),
            )
            for canal, nome_configurado, sistema in alvos:
                try:
                    info = _resolver_dispositivo(self._portaudio, nome_configurado, sistema=sistema)
                    em_gravacao = _CanalEmGravacao(
                        canal,
                        self._portaudio,
                        info,
                        self._pasta / f"{canal}.wav",
                        self._inicio_monotonico,
                    )
                    em_gravacao.abrir()
                except Exception as erro:  # noqa: BLE001 — um canal caído não derruba o outro
                    log.error("canal '%s' indisponível: %s", canal, erro)
                    continue
                self._canais[canal] = em_gravacao
            if not self._canais:
                self._portaudio.terminate()
                self._portaudio = None
                raise ErroDeGravacao(
                    "nenhum canal pôde ser aberto — a gravação não começou. Rode "
                    "'python -m second_brain.gravador dispositivos' e confira a configuração."
                )
            if CANAL_SISTEMA not in self._canais:
                log.warning(
                    "gravando só o microfone: a voz dos outros não será capturada. %s",
                    _dica_de_configuracao(CANAL_SISTEMA),
                )
            log.info("gravação iniciada em %s", self._pasta)
            return self._pasta

    def parar(self) -> Path:
        """Fecha os streams, escreve `gravacao.json` e devolve a pasta da gravação."""
        with self._trava:
            if not self.gravando:
                raise ErroDeGravacao("não há gravação em andamento")
            fim = datetime.now().astimezone()
            duracao_s = time.monotonic() - self._inicio_monotonico
            canais_metadados: dict[str, dict | None] = {CANAL_MICROFONE: None, CANAL_SISTEMA: None}
            for canal, em_gravacao in self._canais.items():
                try:
                    canais_metadados[canal] = em_gravacao.fechar()
                except Exception as erro:  # noqa: BLE001
                    log.error("canal '%s': falha ao encerrar: %s", canal, erro)
                    continue
                self._relatar(em_gravacao)
            if self._portaudio is not None:
                self._portaudio.terminate()
                self._portaudio = None
            pasta = self._pasta
            inicio = self._inicio
            if pasta is None or inicio is None:  # pragma: no cover — estado impossível
                raise ErroDeGravacao("estado inconsistente: gravação sem pasta ou sem início")
            metadados = {
                "versao": VERSAO_CONTRATO,
                "titulo": self._titulo or None,
                "inicio": inicio.isoformat(timespec="seconds"),
                "fim": fim.isoformat(timespec="seconds"),
                "duracao_s": round(duracao_s, 2),
                "canais": canais_metadados,
            }
            (pasta / NOME_METADADOS).write_text(
                json.dumps(metadados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            for canal, bloco in canais_metadados.items():
                if bloco is None:
                    log.warning("canal '%s' ausente na gravação %s", canal, pasta.name)
            log.info("gravação encerrada: %s (%.1f s)", pasta, duracao_s)
            self._canais = {}
            self._pasta = None
            self._inicio = None
            return pasta

    def _relatar(self, em_gravacao: _CanalEmGravacao) -> None:
        log.info(
            "canal '%s': %.1f s, %d Hz, RMS %.1f, pico %d%s",
            em_gravacao.canal,
            em_gravacao.duracao_s,
            em_gravacao.taxa_hz,
            em_gravacao.rms,
            em_gravacao.pico,
            f", {em_gravacao.silencio_preenchido_s:.1f} s de silêncio preenchido pelo relógio"
            if em_gravacao.silencio_preenchido_s
            else "",
        )
        if em_gravacao.mudo:
            log.warning(_mensagem_canal_mudo(em_gravacao.canal))


def criar_slug(titulo: str | None) -> str:
    """Slug do título para o nome da pasta; sem título, `reuniao` (contrato)."""
    texto = unicodedata.normalize("NFKD", titulo or "").encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^A-Za-z0-9]+", "-", texto).strip("-").lower()
    return texto[:60].strip("-") or SLUG_PADRAO


def _criar_pasta(raiz: Path, quando: datetime, titulo: str | None) -> Path:
    """`<gravacoes>/YYYY-MM-DD-HHMM-<slug>/`, com sufixo numérico se já existir."""
    raiz.mkdir(parents=True, exist_ok=True)
    prefixo = quando.strftime("%Y-%m-%d-%H%M")
    slug = criar_slug(titulo)
    pasta = raiz / f"{prefixo}-{slug}"
    contador = 2
    while pasta.exists():
        pasta = raiz / f"{prefixo}-{slug}-{contador}"
        contador += 1
    pasta.mkdir(parents=True)
    return pasta


# ---------------------------------------------------------------- conferência


def estatisticas_do_wav(caminho: Path) -> dict:
    """Taxa, canais, duração, RMS e pico de um WAV — a prova de que o canal não saiu mudo.

    Numa reunião longa o arquivo tem centenas de milhões de amostras; acima de
    `_MAXIMO_BLOCOS_ANALISADOS` o nível é medido por amostragem espalhada pelo
    arquivo inteiro, o que basta para dizer se o canal tem áudio ou é silêncio.
    """
    with wave.open(str(caminho), "rb") as arquivo:
        taxa = arquivo.getframerate()
        canais = arquivo.getnchannels()
        largura = arquivo.getsampwidth()
        quadros = arquivo.getnframes()
        soma_quadrados = 0.0
        amostras = 0
        pico = 0
        blocos = math.ceil(quadros / _BLOCO_DE_ANALISE) if quadros else 0
        passo = max(1, math.ceil(blocos / _MAXIMO_BLOCOS_ANALISADOS)) if blocos else 1
        if largura == _LARGURA_AMOSTRA_BYTES:
            for numero in range(0, blocos, passo):
                arquivo.setpos(numero * _BLOCO_DE_ANALISE)
                bloco = arquivo.readframes(_BLOCO_DE_ANALISE)
                if not bloco:
                    break
                valores = array.array("h")
                valores.frombytes(bloco)
                if not len(valores):
                    continue
                soma_quadrados += sum(float(v) * v for v in valores)
                amostras += len(valores)
                pico = max(pico, max(valores), -min(valores))
    return {
        "arquivo": caminho.name,
        "taxa_hz": taxa,
        "canais": canais,
        "largura_bytes": largura,
        "quadros": quadros,
        "duracao_s": quadros / taxa if taxa else 0.0,
        "rms": math.sqrt(soma_quadrados / amostras) if amostras else 0.0,
        "pico": pico,
        "amostrado": passo > 1,
    }


def conferir_pasta(pasta: Path) -> tuple[list[str], bool]:
    """Confere uma pasta de gravação contra o contrato. Devolve (linhas, tudo_ok)."""
    linhas = [f"Pasta: {pasta}"]
    tudo_ok = True

    metadados_caminho = pasta / NOME_METADADOS
    if not metadados_caminho.is_file():
        linhas.append(f"  FALTA {NOME_METADADOS}")
        tudo_ok = False
    else:
        try:
            metadados = json.loads(metadados_caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError as erro:
            linhas.append(f"  {NOME_METADADOS} inválido: {erro}")
            tudo_ok = False
        else:
            esperadas = ("versao", "titulo", "inicio", "fim", "duracao_s", "canais")
            faltando = [chave for chave in esperadas if chave not in metadados]
            if faltando:
                linhas.append(f"  {NOME_METADADOS} sem as chaves {faltando}")
                tudo_ok = False
            else:
                linhas.append(
                    f"  {NOME_METADADOS}: versao={metadados['versao']} "
                    f"titulo={metadados['titulo']!r} inicio={metadados['inicio']} "
                    f"fim={metadados['fim']} duracao_s={metadados['duracao_s']}"
                )

    for canal in (CANAL_MICROFONE, CANAL_SISTEMA):
        caminho = pasta / f"{canal}.wav"
        if not caminho.is_file():
            linhas.append(f"  FALTA {canal}.wav — {_dica_de_configuracao(canal)}")
            tudo_ok = False
            continue
        dados = estatisticas_do_wav(caminho)
        veredito = "OK"
        if dados["duracao_s"] <= 0:
            veredito, tudo_ok = "VAZIO", False
        elif dados["rms"] < _LIMIAR_RMS_MUDO:
            veredito, tudo_ok = "MUDO", False
        linhas.append(
            f"  {canal}.wav: {veredito} · {dados['taxa_hz']} Hz · {dados['canais']} canal(is) · "
            f"{dados['largura_bytes'] * 8} bits · {dados['duracao_s']:.1f} s · "
            f"RMS {dados['rms']:.1f} · pico {dados['pico']}"
            + (" (nível por amostragem)" if dados["amostrado"] else "")
        )
        if veredito == "MUDO":
            linhas.append(f"    {_mensagem_canal_mudo(canal)}")

    if (pasta / "estado.json").exists():
        linhas.append("  estado.json presente (do pipeline; o gravador nunca escreve esse arquivo)")
    return linhas, tudo_ok


# ------------------------------------------------------------------------ CLI


def _forcar_utf8_na_saida() -> None:
    """Faz `stdout`/`stderr` aguentarem o texto em português fora do console.

    Quando a saída não é um console interativo — pipe, redirecionamento para
    arquivo, captura por outro processo — o Python no Windows escolhe cp1252 e
    qualquer acento derruba o comando com `UnicodeEncodeError`. Isso morderia
    justamente `dispositivos`, que é o comando que o usuário roda (e cola em
    algum lugar) quando a captura já não está funcionando. Só a CLI mexe nos
    fluxos do processo: quem importa o módulo como biblioteca não é afetado.
    """
    for fluxo in (sys.stdout, sys.stderr):
        reconfigurar = getattr(fluxo, "reconfigure", None)
        if reconfigurar is None:
            continue
        try:
            reconfigurar(encoding="utf-8", errors="replace")
        except (OSError, ValueError):  # fluxo fechado ou não reconfigurável
            pass


def _configurar_log(verboso: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verboso else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )


def _configuracao_do_argumento(
    args: argparse.Namespace, *, tolerar_ausencia: bool = False
) -> ConfiguracaoGravador:
    """Configuração do TOML, com `--gravacoes` por cima.

    `tolerar_ausencia` existe para os comandos de diagnóstico (`dispositivos`,
    `testar`): eles precisam rodar numa máquina nova, antes de o config.toml existir.
    """
    pasta = getattr(args, "gravacoes", None)
    try:
        configuracao = carregar_configuracao(getattr(args, "config", None))
    except ErroDeGravacao as erro:
        if not tolerar_ausencia and not pasta:
            raise
        log.warning("%s — seguindo com os dispositivos padrão do sistema", erro)
        configuracao = ConfiguracaoGravador(
            gravacoes=Path(pasta).expanduser() if pasta else Path.cwd()
        )
    if pasta:
        configuracao = replace(configuracao, gravacoes=Path(pasta).expanduser())
    return configuracao


def _comando_dispositivos(args: argparse.Namespace) -> int:
    configuracao = _configuracao_do_argumento(args, tolerar_ausencia=True)
    print("Dispositivos de entrada WASAPI desta máquina:\n")
    for dispositivo in listar_dispositivos():
        print(f"  [{dispositivo.indice:>3}] {dispositivo.rotulo}\n")
    print(
        "Copie o NOME (não o índice: ele muda entre reinícios e entre máquinas) para o "
        f"config.toml em {configuracao.origem or caminho_da_configuracao()}:\n"
    )
    print("  [audio]")
    print('  dispositivo_microfone = "<nome do seu microfone>"')
    print('  dispositivo_sistema   = "<nome do dispositivo de saída, o que termina em [Loopback]>"')
    print("\nSeleção atual:")
    portaudio = pyaudio.PyAudio()
    try:
        for canal, nome, sistema in (
            (CANAL_MICROFONE, configuracao.dispositivo_microfone, False),
            (CANAL_SISTEMA, configuracao.dispositivo_sistema, True),
        ):
            origem = repr(nome) if nome else "vazio (padrão do sistema)"
            try:
                info = _resolver_dispositivo(portaudio, nome, sistema=sistema)
            except DispositivoNaoEncontrado as erro:
                print(f"  {canal}: {origem} → NÃO RESOLVE: {erro}")
            else:
                print(f"  {canal}: {origem} → {info['name']!r}")
    finally:
        portaudio.terminate()
    return 0


def _esperar_parada(duracao: float | None) -> None:
    if duracao:
        time.sleep(duracao)
        return
    if sys.stdin is not None and sys.stdin.isatty():
        sys.stdin.readline()
        return
    log.info("entrada não interativa — pare com Ctrl+C")
    while True:
        time.sleep(0.5)


def _comando_gravar(args: argparse.Namespace) -> int:
    gravador = Gravador(_configuracao_do_argumento(args))
    pasta = gravador.iniciar(args.titulo)
    print(f"\nGRAVANDO em {pasta}")
    print("Pressione ENTER (ou Ctrl+C) para parar.\n", flush=True)
    try:
        _esperar_parada(args.duracao)
    except KeyboardInterrupt:
        print()
    finally:
        pasta = gravador.parar()
    linhas, tudo_ok = conferir_pasta(pasta)
    print("\n".join(linhas))
    return 0 if tudo_ok else 1


def _comando_testar(args: argparse.Namespace) -> int:
    destino = (
        Path(args.gravacoes).expanduser()
        if args.gravacoes
        else Path(tempfile.mkdtemp(prefix="second-brain-teste-"))
    )
    configuracao = replace(
        _configuracao_do_argumento(args, tolerar_ausencia=True), gravacoes=destino
    )
    print(
        f"Teste de {args.segundos:.0f} s: FALE no microfone e deixe um áudio TOCANDO "
        "(vídeo, música) para o canal de sistema ter o que capturar.\n",
        flush=True,
    )
    gravador = Gravador(configuracao)
    gravador.iniciar(args.titulo or "teste de captura")
    try:
        time.sleep(args.segundos)
    finally:
        pasta = gravador.parar()
    linhas, tudo_ok = conferir_pasta(pasta)
    print("\n".join(linhas))
    return 0 if tudo_ok else 1


def _comando_conferir(args: argparse.Namespace) -> int:
    pasta = Path(args.pasta).expanduser()
    if not pasta.is_dir():
        print(f"pasta inexistente: {pasta}")
        return 1
    linhas, tudo_ok = conferir_pasta(pasta)
    print("\n".join(linhas))
    return 0 if tudo_ok else 1


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m second_brain.gravador",
        description=(
            "Gravador de reunião sob demanda: microfone e áudio do sistema em arquivos separados."
        ),
    )
    parser.add_argument("-v", "--verboso", action="store_true", help="log em nível DEBUG")
    parser.add_argument(
        "--config", help="caminho do config.toml (padrão: SECOND_BRAIN_CONFIG ou %%APPDATA%%)"
    )
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    listar = subcomandos.add_parser(
        "dispositivos", help="lista os dispositivos e mostra a seleção atual"
    )
    listar.set_defaults(funcao=_comando_dispositivos)

    gravar = subcomandos.add_parser("gravar", help="grava a reunião até você mandar parar")
    gravar.add_argument("--titulo", help="título da reunião (vira o slug da pasta)")
    gravar.add_argument("--duracao", type=float, help="para sozinho depois de N segundos")
    gravar.add_argument("--gravacoes", help="sobrescreve a pasta de gravações da configuração")
    gravar.set_defaults(funcao=_comando_gravar)

    testar = subcomandos.add_parser("testar", help="grava alguns segundos e confere os níveis")
    testar.add_argument("--segundos", type=float, default=8.0)
    testar.add_argument("--titulo")
    testar.add_argument("--gravacoes", help="onde salvar o teste (padrão: pasta temporária)")
    testar.set_defaults(funcao=_comando_testar)

    conferir = subcomandos.add_parser("conferir", help="confere uma pasta de gravação já existente")
    conferir.add_argument("pasta")
    conferir.set_defaults(funcao=_comando_conferir)
    return parser


def main(argv: list[str] | None = None) -> int:
    _forcar_utf8_na_saida()
    args = construir_parser().parse_args(argv)
    _configurar_log(args.verboso)
    try:
        return int(args.funcao(args))
    except ErroDeGravacao as erro:
        log.error("%s", erro)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

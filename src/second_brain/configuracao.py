r"""Configuração local em TOML.

Lida de `%APPDATA%\second-brain\config.toml`, com override pela variável de
ambiente `SECOND_BRAIN_CONFIG` — é assim que os testes apontam para um
diretório temporário. Nenhum segredo mora no repositório: a chave da Deepgram
vive só neste arquivo, que está no `.gitignore`.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

#: Variável de ambiente que sobrepõe o caminho padrão da configuração.
VARIAVEL_DE_AMBIENTE = "SECOND_BRAIN_CONFIG"

#: Nome do arquivo dentro de `%APPDATA%\second-brain\`.
NOME_DO_ARQUIVO = "config.toml"


class ConfiguracaoInvalida(RuntimeError):
    """A configuração não existe, não é TOML válido ou não tem os caminhos."""


@dataclass(frozen=True)
class Configuracao:
    """Os caminhos e opções da máquina do usuário.

    `vault` e `gravacoes` são obrigatórios; o resto tem padrão. Nenhum valor
    é derivado de hardware desta máquina — quem preenche é o usuário.

    `claude_modelo` vazio significa "o modelo padrão da conta do usuário": o
    coletor roda contra a assinatura dele, e o CLI já escolhe um modelo que
    aquela conta pode usar. Preencher é para quem quer fixar um id.
    """

    vault: Path
    gravacoes: Path
    retencao_dias: int = 7
    deepgram_api_key: str = ""
    claude_modelo: str = ""
    dispositivo_microfone: str = ""
    dispositivo_sistema: str = ""
    origem: Path | None = None


def caminho_padrao() -> Path:
    """Onde a configuração mora quando `SECOND_BRAIN_CONFIG` não está setada."""
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / "second-brain" / NOME_DO_ARQUIVO


def caminho_da_configuracao(caminho: Path | str | None = None) -> Path:
    """Resolve o caminho efetivo: argumento > variável de ambiente > padrão."""
    if caminho is not None:
        return Path(caminho)
    do_ambiente = os.environ.get(VARIAVEL_DE_AMBIENTE)
    if do_ambiente:
        return Path(do_ambiente)
    return caminho_padrao()


def carregar(caminho: Path | str | None = None) -> Configuracao:
    """Lê a configuração do disco e valida o mínimo.

    Levanta `ConfiguracaoInvalida` com uma mensagem que diz qual arquivo o
    usuário precisa criar ou corrigir.
    """
    arquivo = caminho_da_configuracao(caminho)
    if not arquivo.is_file():
        raise ConfiguracaoInvalida(
            f"Configuração não encontrada em {arquivo}. "
            f"Crie o arquivo com as chaves 'vault' e 'gravacoes', ou aponte "
            f"{VARIAVEL_DE_AMBIENTE} para outro caminho."
        )
    texto = arquivo.read_text(encoding="utf-8")
    try:
        dados = tomllib.loads(texto)
    except tomllib.TOMLDecodeError as erro:
        raise ConfiguracaoInvalida(
            f"Configuração inválida em {arquivo}: {erro}{_dica_de_barra_invertida(texto)}"
        ) from erro

    faltando = [chave for chave in ("vault", "gravacoes") if not dados.get(chave)]
    if faltando:
        raise ConfiguracaoInvalida(
            f"Configuração em {arquivo} sem as chaves obrigatórias: {', '.join(faltando)}."
        )

    retencao_dias = _dias_de_retencao(dados.get("retencao_dias", 7), arquivo)

    deepgram = dados.get("deepgram") or {}
    claude = dados.get("claude") or {}
    audio = dados.get("audio") or {}
    return Configuracao(
        vault=Path(dados["vault"]),
        gravacoes=Path(dados["gravacoes"]),
        retencao_dias=retencao_dias,
        deepgram_api_key=str(deepgram.get("api_key", "")),
        claude_modelo=str(claude.get("modelo", "")),
        dispositivo_microfone=str(audio.get("dispositivo_microfone", "")),
        dispositivo_sistema=str(audio.get("dispositivo_sistema", "")),
        origem=arquivo,
    )


def _dias_de_retencao(valor: object, arquivo: Path) -> int:
    """Valida `retencao_dias` antes que ele mande apagar áudio.

    A limpeza é irreversível e lê este número como "tudo mais velho que isto
    pode sumir": um valor negativo diria "apague tudo que já virou nota",
    incluindo a reunião de agora de manhã. Prazo inválido é erro de
    configuração, não um padrão silencioso.
    """
    try:
        dias = int(valor)
    except (TypeError, ValueError):
        raise ConfiguracaoInvalida(
            f"Configuração em {arquivo}: 'retencao_dias' precisa ser um número "
            f"inteiro de dias, e veio {valor!r}."
        ) from None
    if dias < 0:
        raise ConfiguracaoInvalida(
            f"Configuração em {arquivo}: 'retencao_dias' não pode ser negativo "
            f"(veio {dias}). Use 0 para apagar o áudio assim que ele virar nota."
        )
    return dias


def _dica_de_barra_invertida(texto: str) -> str:
    r"""A explicação que falta quando o TOML reclama de um caminho do Windows.

    O erro nativo é `Invalid hex value` — porque `"C:\Users\..."` faz o TOML
    ler `\U` como escape Unicode. É o primeiro tropeço de quem copia o caminho
    do Explorer, e a mensagem crua não ensina nada. Só aparece quando o arquivo
    realmente tem uma barra invertida dentro de aspas.
    """
    suspeitas = [
        linha.strip()
        for linha in texto.splitlines()
        if "\\" in linha and '"' in linha and not linha.lstrip().startswith("#")
    ]
    if not suspeitas:
        return ""
    exemplo = suspeitas[0]
    return (
        "\n\nParece um caminho do Windows com barra invertida: "
        f"{exemplo}\n"
        "No TOML a barra invertida é escape. Use barras normais — "
        'vault = "C:/Users/voce/second-brain-vault" — ou dobre as barras.'
    )

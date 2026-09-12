r"""Configuração local em TOML.

Lida de `%APPDATA%\whis\config.toml`, com override pela variável de
ambiente `WHIS_CONFIG` — é assim que os testes apontam para um
diretório temporário. Nenhum segredo mora no repositório: as chaves da
Deepgram, do Linear e do Slack vivem só neste arquivo, que está no
`.gitignore`.

Toda chave nova nasce com padrão: uma configuração escrita antes das fontes
passivas continua carregando sem edição nenhuma.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .fontes import INICIO_DO_DIA_PADRAO, analisar_hora

#: Variável de ambiente que sobrepõe o caminho padrão da configuração.
VARIAVEL_DE_AMBIENTE = "WHIS_CONFIG"

#: Nome do arquivo dentro de `%APPDATA%\whis\`.
NOME_DO_ARQUIVO = "config.toml"

#: As chaves aceitas em `[daily].horarios`, na ordem em que a semana anda.
#: Sem acento de propósito: é o que se digita num TOML sem pensar em escape.
DIAS_DA_SEMANA = ("segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo")


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

    As chaves das fontes passivas seguem a mesma regra: **vazia é fonte
    desligada**. É o que permite o diário nascer só com git e Linear enquanto o
    Slack espera aprovação do admin.

    `daily_referencias_pessoais` vazia significa **"tudo é trabalho"** — o
    comportamento de quem nunca mexeu no arquivo. Preencher é para quem tem
    projeto pessoal na mesma pasta de desenvolvimento e não quer falar dele na
    daily do time. Lista-se o que é **pessoal**, e não o que é do trabalho,
    porque trabalho novo aparece toda semana e sumir da daily em silêncio é pior
    do que aparecer demais.

    `daily_horarios` é a hora em que a daily deve nascer em cada dia da semana,
    como pares `(dia, "HH:MM")` na ordem segunda→domingo. Dia ausente é dia sem
    daily; tabela vazia é nada agendado — a tarefa do Windows nasce daqui.

    `obsidian_vault` é como o Obsidian chama o vault na URI `obsidian://` — o
    ID (o que *Copy vault ID* copia) ou o nome da pasta. Vazio usa o nome da
    pasta de `vault`, que é o que o Obsidian usa quando o vault foi aberto
    pela pasta.
    """

    vault: Path
    gravacoes: Path
    retencao_dias: int = 7
    deepgram_api_key: str = ""
    claude_modelo: str = ""
    dispositivo_microfone: str = ""
    dispositivo_sistema: str = ""
    diario_inicio_do_dia: str = INICIO_DO_DIA_PADRAO
    diario_hora_da_tarefa: str = "19:00"
    daily_referencias_pessoais: tuple[str, ...] = ()
    daily_contexto_do_time: str = ""
    daily_horarios: tuple[tuple[str, str], ...] = ()
    privacidade_excluir: tuple[str, ...] = ()
    privacidade_pastas_privadas: tuple[str, ...] = ()
    busca_maximo_de_notas: int = 40
    git_raiz: Path | None = None
    git_profundidade: int = 3
    git_excluir: tuple[str, ...] = ()
    git_autores: tuple[str, ...] = ()
    linear_api_key: str = ""
    slack_user_token: str = ""
    slack_conversas_excluidas: tuple[str, ...] = ()
    slack_so_com_mencao: tuple[str, ...] = ()
    slack_bot_token: str = ""
    slack_app_token: str = ""
    obsidian_vault: str = ""
    origem: Path | None = None


def caminho_padrao() -> Path:
    """Onde a configuração mora quando `WHIS_CONFIG` não está setada."""
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / "whis" / NOME_DO_ARQUIVO


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
    diario = dados.get("diario") or {}
    daily = dados.get("daily") or {}
    privacidade = dados.get("privacidade") or {}
    busca = dados.get("busca") or {}
    git = dados.get("git") or {}
    linear = dados.get("linear") or {}
    slack = dados.get("slack") or {}
    obsidian = dados.get("obsidian") or {}
    raiz_do_git = str(git.get("raiz", "")).strip()
    return Configuracao(
        vault=Path(dados["vault"]),
        gravacoes=Path(dados["gravacoes"]),
        retencao_dias=retencao_dias,
        deepgram_api_key=str(deepgram.get("api_key", "")),
        claude_modelo=str(claude.get("modelo", "")),
        dispositivo_microfone=str(audio.get("dispositivo_microfone", "")),
        dispositivo_sistema=str(audio.get("dispositivo_sistema", "")),
        diario_inicio_do_dia=_hora(
            diario.get("inicio_do_dia", INICIO_DO_DIA_PADRAO),
            "[diario].inicio_do_dia",
            arquivo,
        ),
        diario_hora_da_tarefa=_hora(
            diario.get("hora_da_tarefa", "19:00"), "[diario].hora_da_tarefa", arquivo
        ),
        daily_referencias_pessoais=_textos(daily.get("referencias_pessoais")),
        daily_contexto_do_time=str(daily.get("contexto_do_time", "")).strip(),
        daily_horarios=_horarios_da_daily(daily.get("horarios"), arquivo),
        privacidade_excluir=_textos(privacidade.get("excluir")),
        privacidade_pastas_privadas=_pastas_privadas(
            privacidade.get("pastas_privadas"), arquivo
        ),
        busca_maximo_de_notas=_maximo_de_notas(busca.get("maximo_de_notas", 40), arquivo),
        git_raiz=Path(raiz_do_git) if raiz_do_git else None,
        git_profundidade=_profundidade(git.get("profundidade", 3), arquivo),
        git_excluir=_textos(git.get("excluir")),
        git_autores=_textos(git.get("autores")),
        linear_api_key=str(linear.get("api_key", "")),
        slack_user_token=str(slack.get("user_token", "")),
        slack_conversas_excluidas=_textos(slack.get("conversas_excluidas")),
        slack_so_com_mencao=_textos(slack.get("so_com_mencao")),
        slack_bot_token=_token_do_slack(slack.get("bot_token", ""), "bot_token", "xoxb-", arquivo),
        slack_app_token=_token_do_slack(slack.get("app_token", ""), "app_token", "xapp-", arquivo),
        obsidian_vault=str(obsidian.get("vault", "")).strip(),
        origem=arquivo,
    )


def _hora(valor: object, chave: str, arquivo: Path) -> str:
    """Valida `HH:MM` em 24 horas — a janela do dia e a tarefa dependem disso."""
    texto = str(valor)
    try:
        analisar_hora(texto)
    except ValueError:
        raise ConfiguracaoInvalida(
            f"Configuração em {arquivo}: '{chave}' precisa ser uma hora no formato "
            f"HH:MM em 24 horas (por exemplo \"04:00\"), e veio {valor!r}."
        ) from None
    return texto.strip()


def _horarios_da_daily(valor: object, arquivo: Path) -> tuple[tuple[str, str], ...]:
    """A tabela `[daily].horarios` como pares ordenados pela semana.

    Uma chave desconhecida é erro, e não dia ignorado: `terça` com acento ou
    `seg` abreviado deixariam a daily sem nascer naquele dia em silêncio — o
    modo de falha que a tabela existe para evitar.
    """
    if valor is None:
        return ()
    if not isinstance(valor, dict):
        raise ConfiguracaoInvalida(
            f"Configuração em {arquivo}: '[daily].horarios' precisa ser uma tabela de "
            f'dia da semana para hora (por exemplo {{ segunda = "13:55" }}), e veio {valor!r}.'
        )
    desconhecidas = [chave for chave in valor if chave not in DIAS_DA_SEMANA]
    if desconhecidas:
        raise ConfiguracaoInvalida(
            f"Configuração em {arquivo}: '[daily].horarios' tem dia(s) que não existem: "
            f"{', '.join(repr(chave) for chave in desconhecidas)}. "
            f"Os aceitos são {', '.join(DIAS_DA_SEMANA)}."
        )
    return tuple(
        (dia, _hora(valor[dia], f"[daily].horarios.{dia}", arquivo))
        for dia in DIAS_DA_SEMANA
        if dia in valor
    )


def _textos(valor: object) -> tuple[str, ...]:
    """Uma lista do TOML como tupla — `Configuracao` é frozen."""
    if valor is None:
        return ()
    if isinstance(valor, str):
        return (valor,)
    return tuple(str(item) for item in valor)


def _pastas_privadas(valor: object, arquivo: Path) -> tuple[str, ...]:
    """Valida e normaliza as pastas que a busca nunca abre.

    Cada uma precisa apontar para **dentro** do vault: caminho absoluto ou com
    `..` não protege pasta nenhuma, e uma pasta privada que não protege nada é
    pior do que nenhuma — o usuário acharia que está coberto. Barras invertidas
    e a barra final são aceitas, porque é assim que o Explorer mostra o caminho.
    """
    pastas: list[str] = []
    for item in _textos(valor):
        texto = item.strip().replace("\\", "/")
        partes = [parte for parte in texto.split("/") if parte and parte != "."]
        if not partes or _absoluto(texto) or ".." in partes:
            raise ConfiguracaoInvalida(
                f"Configuração em {arquivo}: cada item de '[privacidade].pastas_privadas' "
                f"precisa ser uma pasta dentro do vault, relativa a ele (por exemplo "
                f'"notas/pessoal"), e veio {item!r}.'
            )
        pastas.append("/".join(partes))
    return tuple(pastas)


_NOMES_DOS_TOKENS = {
    "xoxb-": "o Bot User OAuth Token",
    "xapp-": "o App-Level Token",
    "xoxp-": "o User OAuth Token, que vai em [slack].user_token",
}


def _token_do_slack(valor: object, chave: str, prefixo: str, arquivo: Path) -> str:
    """Um token do atendente, conferido pelo prefixo.

    A página da app mostra três tokens parecidos, e colar o errado só se
    revelaria na primeira mensagem, com o atendente já no ar sem console.
    O prefixo diz qual é qual, e a mensagem diz onde cada um vai.
    """
    token = str(valor or "").strip()
    if not token or token.startswith(prefixo):
        return token
    veio = next(
        (nome for inicio, nome in _NOMES_DOS_TOKENS.items() if token.startswith(inicio)),
        "um token de outro tipo",
    )
    raise ConfiguracaoInvalida(
        f"Configuração em {arquivo}: '[slack].{chave}' precisa ser "
        f"{_NOMES_DOS_TOKENS[prefixo]} (começa com {prefixo}), e veio {veio}."
    )


def _absoluto(texto: str) -> bool:
    """`/fora` também é absoluto: no Windows `Path` só reconhece com a letra do drive."""
    return Path(texto).is_absolute() or texto.startswith("/")


def _maximo_de_notas(valor: object, arquivo: Path) -> int:
    try:
        maximo = int(valor)
    except (TypeError, ValueError):
        raise ConfiguracaoInvalida(
            f"Configuração em {arquivo}: '[busca].maximo_de_notas' precisa ser um número "
            f"inteiro de notas, e veio {valor!r}."
        ) from None
    if maximo < 1:
        raise ConfiguracaoInvalida(
            f"Configuração em {arquivo}: '[busca].maximo_de_notas' precisa ser pelo menos 1 "
            f"(veio {maximo}) — abaixo disso o agente não conseguiria ler nota nenhuma."
        )
    return maximo


def _profundidade(valor: object, arquivo: Path) -> int:
    try:
        niveis = int(valor)
    except (TypeError, ValueError):
        raise ConfiguracaoInvalida(
            f"Configuração em {arquivo}: '[git].profundidade' precisa ser um número "
            f"inteiro de níveis de pasta, e veio {valor!r}."
        ) from None
    if niveis < 1:
        raise ConfiguracaoInvalida(
            f"Configuração em {arquivo}: '[git].profundidade' precisa ser pelo menos 1 "
            f"(veio {niveis}) — abaixo disso a varredura não acharia repositório nenhum."
        )
    return niveis


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
        'vault = "C:/Users/voce/whis-vault" — ou dobre as barras.'
    )

r"""Configuração local em TOML.

Lida de `%APPDATA%\whis\config.toml`, com override pela variável de
ambiente `WHIS_CONFIG` — é assim que os testes apontam para um
diretório temporário. Nenhum segredo mora no repositório: as chaves do
Linear e do Slack vivem só neste arquivo, que está no `.gitignore`.

Toda chave nova nasce com padrão: uma configuração escrita antes das fontes
passivas continua carregando sem edição nenhuma. Chave que o Whis não lê mais
(`gravacoes`, `retencao_dias`, `[deepgram]`, `[audio]`, da gravação que saiu)
é ignorada, e some do arquivo quando o painel o reescreve.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from .atalho_global import ATALHO_PADRAO, AtalhoInvalido, analisar_atalho

_log = logging.getLogger("whis.configuracao")
from .fontes import INICIO_DO_DIA_PADRAO, analisar_hora

#: Variável de ambiente que sobrepõe o caminho padrão da configuração.
VARIAVEL_DE_AMBIENTE = "WHIS_CONFIG"

#: Nome do arquivo dentro de `%APPDATA%\whis\`.
NOME_DO_ARQUIVO = "config.toml"

#: As chaves aceitas em `[daily].horarios`, na ordem em que a semana anda.
#: Sem acento de propósito: é o que se digita num TOML sem pensar em escape.
DIAS_DA_SEMANA = ("segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo")

#: O `config.toml` que `whis init` escreve e que o painel regenera. Cada chave
#: carrega o comentário que explica o que preencher: é a única documentação que
#: o usuário lê na hora em que precisa. `{vault}` é o campo que `init`
#: preenche com o perfil do usuário; as chaves da tabela de horários vão com
#: chaves dobradas por causa do `format`.
MODELO_DE_CONFIGURACAO = """\
# Configuração do Whis. Use barras normais (/) nos caminhos:
# no TOML a barra invertida é escape e quebra o arquivo.

vault = "{vault}"            # a pasta do vault Obsidian: a memória durável do Whis

[claude]
modelo = ""                  # vazio = o modelo padrão da sua conta
cli = ""                     # caminho do claude.exe; vazio = acha sozinho

[diario]
inicio_do_dia = "04:00"      # o diário de um dia vai desta hora à mesma hora do dia seguinte
hora_da_tarefa = "19:00"     # quando a tarefa agendada gera o diário

[daily]
ativa = true                  # false = sem daily: a tarefa agendada não gera e a palheta esconde "Generate daily"
referencias_pessoais = []     # repositórios e canais que são seus, não do trabalho: ficam no vault mas fora do roteiro
contexto_do_time = ""         # como o seu processo funciona, para o roteiro não inventar bloqueio
horarios = {{ segunda = "13:55", terca = "13:55", quarta = "10:25", quinta = "13:55", sexta = "10:25" }}  # hora em que a daily nasce em cada dia (segunda..domingo, sem acento); dia ausente = sem daily

[noticias]
ativa = true                 # false = sem jornal: a tarefa agendada não gera e a palheta esconde "Generate news"
horario = "08:20"            # quando a tarefa agendada gera o jornal do dia

[palheta]
atalho = "ctrl+space"        # o atalho global que abre a palheta: ctrl, alt, shift, win e uma tecla (letra, dígito, space, f1..f12)

[privacidade]
excluir = []                 # trechos que nunca saem da máquina (substring, sem diferenciar maiúsculas)
pastas_privadas = []         # pastas do vault que a busca nunca abre, relativas a ele (ex.: "notas/pessoal")

[busca]
maximo_de_notas = 40         # teto de notas lidas numa pergunta, para uma pergunta não varrer o vault

[git]
raiz = ""                    # pasta onde varrer repositórios; vazio = fonte desligada
profundidade = 3             # quantos níveis de pasta a varredura desce a partir da raiz
excluir = []                 # pastas ignoradas na varredura
autores = []                 # vazio = deduz do git config user.email de cada repositório

[linear]
api_key = ""                 # Personal API Key read-only; vazio = fonte desligada

[slack]
user_token = ""              # user token xoxp da app interna; vazio = fonte desligada
conversas_excluidas = []     # canais e DMs que o coletor nunca lê
so_com_mencao = []           # canais em que só entra o que cita você (ex.: code review)
bot_token = ""               # Bot User OAuth Token xoxb da mesma app: o atendente responde na DM com ele
app_token = ""               # App-Level Token xapp com connections:write: a conexão do Socket Mode

[obsidian]
vault = "245833c11ad43e6e"   # o ID do vault (Copy vault ID no seletor de vaults) ou o nome da pasta; é o que o botão "Abrir no Obsidian" usa
"""


class ConfiguracaoInvalida(RuntimeError):
    """A configuração não existe, não é TOML válido ou não tem os caminhos."""


class Tipo(Enum):
    """Como uma chave se apresenta no painel e como é escrita no TOML."""

    TEXTO = "texto"
    SEGREDO = "segredo"
    CAMINHO = "caminho"
    INTEIRO = "inteiro"
    HORA = "hora"
    LISTA = "lista"
    HORARIOS = "horarios"
    BOOLEANO = "booleano"


@dataclass(frozen=True)
class Chave:
    """Uma chave do `config.toml`: onde mora no arquivo e em `Configuracao`."""

    secao: str
    nome: str
    atributo: str
    tipo: Tipo

    def caminho(self) -> str:
        return f"[{self.secao}].{self.nome}" if self.secao else self.nome


#: Toda chave do modelo, na ordem do arquivo. É o contrato entre o modelo, o
#: escritor e o painel: uma chave nova entra aqui e no modelo, e o teste
#: confere que os dois batem.
CHAVES: tuple[Chave, ...] = (
    Chave("", "vault", "vault", Tipo.CAMINHO),
    Chave("claude", "modelo", "claude_modelo", Tipo.TEXTO),
    Chave("claude", "cli", "claude_cli", Tipo.TEXTO),
    Chave("diario", "inicio_do_dia", "diario_inicio_do_dia", Tipo.HORA),
    Chave("diario", "hora_da_tarefa", "diario_hora_da_tarefa", Tipo.HORA),
    Chave("daily", "ativa", "daily_ativa", Tipo.BOOLEANO),
    Chave("daily", "referencias_pessoais", "daily_referencias_pessoais", Tipo.LISTA),
    Chave("daily", "contexto_do_time", "daily_contexto_do_time", Tipo.TEXTO),
    Chave("daily", "horarios", "daily_horarios", Tipo.HORARIOS),
    Chave("noticias", "ativa", "noticias_ativa", Tipo.BOOLEANO),
    Chave("noticias", "horario", "noticias_horario", Tipo.HORA),
    Chave("palheta", "atalho", "palheta_atalho", Tipo.TEXTO),
    Chave("privacidade", "excluir", "privacidade_excluir", Tipo.LISTA),
    Chave("privacidade", "pastas_privadas", "privacidade_pastas_privadas", Tipo.LISTA),
    Chave("busca", "maximo_de_notas", "busca_maximo_de_notas", Tipo.INTEIRO),
    Chave("git", "raiz", "git_raiz", Tipo.CAMINHO),
    Chave("git", "profundidade", "git_profundidade", Tipo.INTEIRO),
    Chave("git", "excluir", "git_excluir", Tipo.LISTA),
    Chave("git", "autores", "git_autores", Tipo.LISTA),
    Chave("linear", "api_key", "linear_api_key", Tipo.SEGREDO),
    Chave("slack", "user_token", "slack_user_token", Tipo.SEGREDO),
    Chave("slack", "conversas_excluidas", "slack_conversas_excluidas", Tipo.LISTA),
    Chave("slack", "so_com_mencao", "slack_so_com_mencao", Tipo.LISTA),
    Chave("slack", "bot_token", "slack_bot_token", Tipo.SEGREDO),
    Chave("slack", "app_token", "slack_app_token", Tipo.SEGREDO),
    Chave("obsidian", "vault", "obsidian_vault", Tipo.TEXTO),
)


@dataclass(frozen=True)
class Configuracao:
    """Os caminhos e opções da máquina do usuário.

    `vault` é obrigatório; o resto tem padrão. Nenhum valor
    é derivado de hardware desta máquina — quem preenche é o usuário.

    `claude_modelo` vazio significa "o modelo padrão da conta do usuário": o
    Whis roda contra a assinatura dele, e o CLI já escolhe um modelo que
    aquela conta pode usar. Preencher é para quem quer fixar um id.

    `claude_cli` vazio significa "achar o `claude.exe` sozinho"; preencher é
    para quando a tarefa agendada não enxerga o CLI pelo `PATH`.

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

    `daily_ativa` falso desliga a daily: a tarefa `Whis-Daily` continua no
    Agendador, mas sai sem gerar nada, e a palheta esconde `daily`. Desligar
    pelo painel vale na hora, sem mexer no Windows. `whis daily` no terminal
    não olha isto — é o jeito de gerar uma com ela desligada.

    `noticias_ativa` e `noticias_horario` são o mesmo par para o jornal: a
    tarefa `Whis-Noticias` roda todo dia em `noticias_horario` e sai sem gerar
    quando `noticias_ativa` é falso. Fontes, nomes e time não moram aqui, e sim
    em `noticias/fontes.md` no vault.

    `obsidian_vault` é como o Obsidian chama o vault na URI `obsidian://` — o
    ID (o que *Copy vault ID* copia) ou o nome da pasta. Vazio usa o nome da
    pasta de `vault`, que é o que o Obsidian usa quando o vault foi aberto
    pela pasta.

    `palheta_atalho` é a combinação de teclas que abre a palheta, já validada
    (`atalho_global.analisar_atalho` a entende); o padrão é `ctrl+space`.
    """

    vault: Path
    claude_modelo: str = ""
    claude_cli: str = ""
    diario_inicio_do_dia: str = INICIO_DO_DIA_PADRAO
    diario_hora_da_tarefa: str = "19:00"
    daily_ativa: bool = True
    daily_referencias_pessoais: tuple[str, ...] = ()
    daily_contexto_do_time: str = ""
    daily_horarios: tuple[tuple[str, str], ...] = ()
    noticias_ativa: bool = True
    noticias_horario: str = "08:20"
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
    palheta_atalho: str = ATALHO_PADRAO
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
            f"Crie o arquivo com a chave 'vault', ou aponte "
            f"{VARIAVEL_DE_AMBIENTE} para outro caminho."
        )
    return carregar_texto(arquivo.read_text(encoding="utf-8"), origem=arquivo)


def carregar_texto(texto: str, *, origem: Path) -> Configuracao:
    """Interpreta e valida o TOML já lido; `origem` é o arquivo que as mensagens citam.

    É o que o painel usa para validar o que o usuário digitou **antes** de
    escrever, com as mesmas mensagens que o arquivo daria.
    """
    arquivo = Path(origem)
    try:
        dados = tomllib.loads(texto)
    except tomllib.TOMLDecodeError as erro:
        raise ConfiguracaoInvalida(
            f"Configuração inválida em {arquivo}: {erro}{_dica_de_barra_invertida(texto)}"
        ) from erro

    if not dados.get("vault"):
        raise ConfiguracaoInvalida(
            f"Configuração em {arquivo} sem a chave obrigatória: vault."
        )

    claude = dados.get("claude") or {}
    diario = dados.get("diario") or {}
    daily = dados.get("daily") or {}
    noticias = dados.get("noticias") or {}
    privacidade = dados.get("privacidade") or {}
    busca = dados.get("busca") or {}
    git = dados.get("git") or {}
    linear = dados.get("linear") or {}
    slack = dados.get("slack") or {}
    obsidian = dados.get("obsidian") or {}
    palheta = dados.get("palheta") or {}
    raiz_do_git = str(git.get("raiz", "")).strip()
    return Configuracao(
        vault=Path(dados["vault"]),
        claude_modelo=str(claude.get("modelo", "")),
        claude_cli=str(claude.get("cli", "")).strip(),
        diario_inicio_do_dia=_hora(
            diario.get("inicio_do_dia", INICIO_DO_DIA_PADRAO),
            "[diario].inicio_do_dia",
            arquivo,
        ),
        diario_hora_da_tarefa=_hora(
            diario.get("hora_da_tarefa", "19:00"), "[diario].hora_da_tarefa", arquivo
        ),
        daily_ativa=_booleano(daily.get("ativa", True), "[daily].ativa", arquivo),
        daily_referencias_pessoais=_textos(daily.get("referencias_pessoais")),
        daily_contexto_do_time=str(daily.get("contexto_do_time", "")).strip(),
        daily_horarios=_horarios_da_daily(daily.get("horarios"), arquivo),
        noticias_ativa=_booleano(noticias.get("ativa", True), "[noticias].ativa", arquivo),
        noticias_horario=_hora(
            noticias.get("horario", "08:20"), "[noticias].horario", arquivo
        ),
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
        palheta_atalho=_atalho(palheta.get("atalho", ATALHO_PADRAO), arquivo),
        origem=arquivo,
    )


def _atalho(valor: object, arquivo: Path) -> str:
    """Valida `[palheta].atalho` antes de a bandeja tentar registrá-lo.

    Um atalho ilegível só se revelaria com a bandeja no ar e sem console; aqui
    ele vira erro com o formato aceito.
    """
    texto = str(valor).strip() or ATALHO_PADRAO
    try:
        return analisar_atalho(texto).texto
    except AtalhoInvalido as erro:
        raise ConfiguracaoInvalida(
            f"Configuração em {arquivo}: '[palheta].atalho' precisa ser modificadores e "
            f'uma tecla separados por "+" (por exemplo "ctrl+alt+space"), e veio {valor!r}: '
            f"{erro}"
        ) from None


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


def _booleano(valor: object, chave: str, arquivo: Path) -> bool:
    if not isinstance(valor, bool):
        raise ConfiguracaoInvalida(
            f"Configuração em {arquivo}: '{chave}' precisa ser true ou false, sem aspas, "
            f"e veio {valor!r}."
        )
    return valor


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


# -- escrever ---------------------------------------------------------------

#: Uma linha `chave = valor  # comentário` do modelo.
_LINHA_DE_CHAVE = re.compile(r"^(?P<chave>\w+) = (?P<valor>.*?)(?P<comentario>\s+#.*)?$")
_LINHA_DE_SECAO = re.compile(r"^\[(?P<secao>\w+)\]\s*$")


def valores_de(configuracao: Configuracao) -> dict[Chave, object]:
    """O valor de cada chave como `escrever` o escreve: caminhos em texto com `/`."""
    valores: dict[Chave, object] = {}
    for chave in CHAVES:
        valor = getattr(configuracao, chave.atributo)
        if chave.tipo is Tipo.CAMINHO:
            valor = Path(valor).as_posix() if valor else ""
        valores[chave] = valor
    return valores


def gerar_toml(valores: Mapping[Chave, object]) -> str:
    """O `config.toml` inteiro, regenerado do modelo com os valores dados.

    O modelo é a fonte dos comentários: cada linha `chave = valor  # ajuda`
    ganha o valor novo e mantém a ajuda, alinhada como estava. Preço aceito e
    registrado na spec: um comentário escrito à mão no arquivo se perde — o
    backup guarda.
    """
    modelo = MODELO_DE_CONFIGURACAO.format(vault="")
    por_caminho = {(chave.secao, chave.nome): chave for chave in CHAVES}
    linhas: list[str] = []
    secao = ""
    for linha in modelo.splitlines():
        cabecalho = _LINHA_DE_SECAO.match(linha)
        if cabecalho is not None:
            secao = cabecalho["secao"]
            linhas.append(linha)
            continue
        campo = _LINHA_DE_CHAVE.match(linha)
        chave = por_caminho.get((secao, campo["chave"])) if campo else None
        if campo is None or chave is None or chave not in valores:
            linhas.append(linha)
            continue
        prefixo = f"{campo['chave']} = {_toml(valores[chave], chave.tipo)}"
        comentario = campo["comentario"] or ""
        if comentario:
            coluna = len(campo["chave"]) + 3 + len(campo["valor"]) + len(comentario) - len(comentario.lstrip())
            comentario = " " * max(2, coluna - len(prefixo)) + comentario.lstrip()
        linhas.append(prefixo + comentario)
    return "\n".join(linhas) + "\n"


def escrever(configuracao: Configuracao, destino: Path, *, agora: datetime | None = None) -> Path:
    """Grava a configuração em `destino`, com backup do que estava lá.

    Escreve primeiro num `.tmp` ao lado e o relê com `carregar`: se o que
    saiu não carrega, nada é trocado e o erro sobe. Só então o arquivo atual
    vira `config.toml.bak-YYYYMMDD-HHMMSS` e o novo toma o lugar. UTF-8 sem
    BOM e `\\n`, como `init` escreve. Nenhum valor vai ao log: quatro deles são
    segredos.
    """
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".tmp")
    with temporario.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write(gerar_toml(valores_de(configuracao)))
    try:
        carregar(temporario)
    except ConfiguracaoInvalida:
        temporario.unlink(missing_ok=True)
        raise

    if destino.exists():
        momento = agora if agora is not None else datetime.now()
        backup = destino.with_name(f"{destino.name}.bak-{momento:%Y%m%d-%H%M%S}")
        shutil.copy2(destino, backup)
        _log.info("Backup da configuração em %s", backup)
    os.replace(temporario, destino)
    _log.info("Configuração escrita em %s", destino)
    return destino


def _toml(valor: object, tipo: Tipo) -> str:
    if tipo is Tipo.HORARIOS:
        return _tabela_de_horarios(valor)
    if tipo is Tipo.BOOLEANO and isinstance(valor, bool):
        return "true" if valor else "false"
    if tipo is Tipo.LISTA:
        itens = [valor] if isinstance(valor, str) else list(valor or ())
        return "[" + ", ".join(_texto_toml(str(item)) for item in itens) + "]"
    if tipo is Tipo.INTEIRO and isinstance(valor, int) and not isinstance(valor, bool):
        return str(valor)
    if tipo is Tipo.CAMINHO and valor:
        return _texto_toml(Path(str(valor)).as_posix())
    return _texto_toml("" if valor is None else str(valor))


def _tabela_de_horarios(valor: object) -> str:
    pares: Sequence[tuple[str, str]]
    if isinstance(valor, Mapping):
        pares = [(str(dia), str(hora)) for dia, hora in valor.items()]
    else:
        pares = [(str(dia), str(hora)) for dia, hora in (valor or ())]
    if not pares:
        return "{}"
    return "{ " + ", ".join(f"{dia} = {_texto_toml(hora)}" for dia, hora in pares) + " }"


def _texto_toml(texto: str) -> str:
    """Uma string básica do TOML: aspas e barra invertida escapadas, controle em `\\uXXXX`."""
    partes: list[str] = []
    for caractere in texto:
        if caractere == "\\":
            partes.append("\\\\")
        elif caractere == '"':
            partes.append('\\"')
        elif caractere == "\n":
            partes.append("\\n")
        elif caractere == "\t":
            partes.append("\\t")
        elif caractere == "\r":
            partes.append("\\r")
        elif ord(caractere) < 0x20 or caractere == "\x7f":
            partes.append(f"\\u{ord(caractere):04X}")
        else:
            partes.append(caractere)
    return '"' + "".join(partes) + '"'


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

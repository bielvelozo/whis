r"""As amarrações com o Windows: subir com o logon, limpar sozinho, avisar.

Enquanto a bandeja depender de alguém digitar um comando, ela não é "um clique
durante a reunião" — é um comando antes de cada reunião. E enquanto a limpeza
depender disso também, o áudio bruto se acumula (uma reunião de 40 min ocupa
~420 MB nos dois canais).

Este módulo faz poucas coisas, todas **explícitas e reversíveis**:

- `instalar_inicializacao()` põe um atalho na pasta de Inicialização do usuário,
  apontando para `pythonw.exe -m whis bandeja` (sem console piscando), e outro
  no Menu Iniciar com a AUMID — sem esse segundo, o Windows recusa qualquer
  toast de um app não empacotado;
- `agendar_limpeza()` registra uma tarefa diária no Agendador do Windows
  rodando `whis limpar`;
- `remover_legado()` tira da máquina o atalho e a tarefa do nome antigo do
  projeto, que apontam para um módulo que não existe mais.

Nada disso acontece sozinho: são subcomandos que o usuário chama, e cada um tem
o par `--remover`. Apagar áudio é irreversível, então a tarefa agendada nasce da
decisão do usuário, nunca de um efeito colateral de subir a bandeja.

O trabalho sujo (criar `.lnk`, falar com o `schtasks`) sai por `executar`, um
callable injetável — é o que permite provar o comando montado sem mexer no
Windows da máquina de teste.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger("whis.automacao")

NOME_DO_ATALHO = "Whis.lnk"
NOME_DO_ATALHO_DO_ATENDENTE = "Whis Atendente.lnk"
NOME_DO_ATALHO_DO_MENU = "Whis.lnk"
NOME_DA_TAREFA = "Whis-Limpeza"

#: O Application User Model ID do Whis. É a identidade que o Windows exige de um
#: app não empacotado para mostrar toast: precisa existir um atalho no Menu
#: Iniciar com esta propriedade, e o toast é disparado em nome dela.
AUMID = "Whis.Agente"

#: O script que grava o `.lnk` com a AUMID — o `WScript.Shell` não sabe fazê-lo.
SCRIPT_DO_ATALHO_COM_AUMID = Path(__file__).with_name("atalho_com_aumid.ps1")

#: Os nomes que o projeto usava antes de virar Whis, em 2026-09-09. O atalho e a
#: tarefa com esses nomes chamam `-m second_brain`, que não existe mais, e
#: falham calados desde então.
NOME_DO_ATALHO_LEGADO = "Second Brain.lnk"
NOME_DA_TAREFA_LEGADA = "SecondBrain-Limpeza"

#: Assinatura de quem executa um processo externo (injetável em teste).
Executor = Callable[[list[str]], subprocess.CompletedProcess]


class ErroDeAutomacao(RuntimeError):
    """O Windows recusou criar o atalho ou a tarefa agendada."""


def _rodar(comando: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(comando, capture_output=True, text=True, check=False)


# -- subir com o Windows ----------------------------------------------------


def pasta_de_inicializacao() -> Path:
    """`%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup`."""
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def caminho_do_atalho() -> Path:
    return pasta_de_inicializacao() / NOME_DO_ATALHO


def caminho_do_atalho_do_atendente() -> Path:
    return pasta_de_inicializacao() / NOME_DO_ATALHO_DO_ATENDENTE


def pasta_do_menu_iniciar() -> Path:
    """`%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs` — onde o toast procura a AUMID."""
    return pasta_de_inicializacao().parent


def caminho_do_atalho_do_menu() -> Path:
    return pasta_do_menu_iniciar() / NOME_DO_ATALHO_DO_MENU


def caminho_do_atalho_legado() -> Path:
    return pasta_de_inicializacao() / NOME_DO_ATALHO_LEGADO


def interpretador_sem_console() -> Path:
    """`pythonw.exe` do ambiente atual — o que não abre janela preta no logon.

    Cai para o `python.exe` corrente se o `pythonw` não existir: melhor uma
    bandeja com console piscando do que bandeja nenhuma.
    """
    atual = Path(sys.executable)
    sem_console = atual.with_name("pythonw.exe")
    return sem_console if sem_console.is_file() else atual


def instalar_inicializacao(*, executar: Executor = _rodar) -> Path:
    """Cria o atalho de inicialização da bandeja e devolve onde ele ficou.

    Cria também o atalho do Menu Iniciar com a AUMID. São dois porque servem a
    coisas diferentes: o da Inicialização faz a bandeja subir no logon; o do
    Menu Iniciar é o que autoriza o Whis a mostrar toast, e o usuário ainda
    ganha um "Whis" na busca do Windows.
    """
    atalho = _criar_atalho(
        caminho_do_atalho(),
        argumentos="-m whis bandeja",
        descricao="Whis — coletor de reunião na bandeja",
        executar=executar,
    )
    _criar_atalho_com_aumid(
        caminho_do_atalho_do_menu(),
        argumentos="-m whis bandeja",
        descricao="Whis — o agente na bandeja",
        executar=executar,
    )
    return atalho


def _criar_atalho_com_aumid(
    destino: Path, *, argumentos: str, descricao: str, executar: Executor
) -> Path:
    """Escreve um `.lnk` com `System.AppUserModel.ID` pelo script empacotado.

    O `WScript.Shell` não grava essa propriedade; é preciso abrir o atalho como
    `IPropertyStore`, e isso mora no `.ps1` ao lado deste módulo.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    resultado = executar(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT_DO_ATALHO_COM_AUMID),
            "-Atalho",
            str(destino),
            "-Alvo",
            str(interpretador_sem_console()),
            "-Argumentos",
            argumentos,
            "-Diretorio",
            str(Path(__file__).resolve().parents[2]),
            "-Descricao",
            descricao,
            "-Aumid",
            AUMID,
        ]
    )
    if resultado.returncode != 0:
        raise ErroDeAutomacao(
            f"não foi possível criar o atalho com AUMID em {destino}: "
            f"{(resultado.stderr or resultado.stdout or '').strip()}"
        )
    _log.info("Atalho do Menu Iniciar criado em %s (AUMID %s)", destino, AUMID)
    return destino


def instalar_atendente(*, executar: Executor = _rodar) -> Path:
    """Cria o atalho de inicialização do atendente, ao lado do da bandeja.

    É um atalho separado, e não um argumento a mais no da bandeja, porque são
    dois processos: o atendente tem trava própria e não sabe gravar reunião.
    """
    return _criar_atalho(
        caminho_do_atalho_do_atendente(),
        argumentos="-m whis atender",
        descricao="Whis — o agente na DM do Slack",
        executar=executar,
    )


def _criar_atalho(destino: Path, *, argumentos: str, descricao: str, executar: Executor) -> Path:
    """Escreve um `.lnk` na pasta de Inicialização apontando para o pacote.

    O `.lnk` é escrito pelo `WScript.Shell` via PowerShell: é a forma de criar
    atalho no Windows sem dependência nova (o ADR 0001 pede projeto fino), e o
    resultado é um atalho de verdade — o usuário vê, move e apaga pelo Explorer.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    interpretador = interpretador_sem_console()
    diretorio = Path(__file__).resolve().parents[2]

    script = (
        "$atalho = (New-Object -ComObject WScript.Shell)."
        f"CreateShortcut('{destino}'); "
        f"$atalho.TargetPath = '{interpretador}'; "
        f"$atalho.Arguments = '{argumentos}'; "
        f"$atalho.WorkingDirectory = '{diretorio}'; "
        f"$atalho.Description = '{descricao}'; "
        "$atalho.Save()"
    )
    resultado = executar(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
    )
    if resultado.returncode != 0:
        raise ErroDeAutomacao(
            f"não foi possível criar o atalho em {destino}: "
            f"{(resultado.stderr or resultado.stdout or '').strip()}"
        )
    _log.info("Atalho de inicialização criado em %s", destino)
    return destino


def remover_inicializacao() -> Path | None:
    """Tira os atalhos da bandeja (Inicialização e Menu Iniciar).

    Devolve o caminho do atalho de Inicialização removido, ou `None` se ele não
    existia — o do Menu Iniciar vai junto, em silêncio.
    """
    _remover_atalho(caminho_do_atalho_do_menu())
    return _remover_atalho(caminho_do_atalho())


def remover_atendente() -> Path | None:
    """Tira o atalho do atendente da inicialização. Devolve o caminho removido, ou `None`."""
    return _remover_atalho(caminho_do_atalho_do_atendente())


def _remover_atalho(destino: Path) -> Path | None:
    if not destino.exists():
        return None
    destino.unlink()
    _log.info("Atalho de inicialização removido de %s", destino)
    return destino


def inicializacao_instalada() -> bool:
    return caminho_do_atalho().exists()


def atendente_instalado() -> bool:
    return caminho_do_atalho_do_atendente().exists()


# -- limpeza agendada -------------------------------------------------------


def agendar_limpeza(
    *, hora: str = "12:00", executar: Executor = _rodar, config: Path | None = None
) -> str:
    """Registra a tarefa diária que apaga o áudio já vencido.

    Meio-dia por padrão, e não de madrugada, porque a máquina precisa estar
    ligada para a tarefa rodar — e um horário em que o usuário está usando o PC
    é o que garante isso.
    """
    comando = [
        f'"{interpretador_sem_console()}"',
        "-m",
        "whis",
        "limpar",
    ]
    if config is not None:
        comando += ["--config", f'"{config}"']

    resultado = executar(
        [
            "schtasks",
            "/Create",
            "/TN",
            NOME_DA_TAREFA,
            "/TR",
            " ".join(comando),
            "/SC",
            "DAILY",
            "/ST",
            hora,
            "/F",
        ]
    )
    if resultado.returncode != 0:
        raise ErroDeAutomacao(
            f"não foi possível agendar a limpeza: "
            f"{(resultado.stderr or resultado.stdout or '').strip()}"
        )
    _log.info("Limpeza diária agendada às %s como '%s'", hora, NOME_DA_TAREFA)
    return NOME_DA_TAREFA


def desagendar_limpeza(*, executar: Executor = _rodar) -> bool:
    """Remove a tarefa agendada. `False` se ela não existia."""
    resultado = executar(["schtasks", "/Delete", "/TN", NOME_DA_TAREFA, "/F"])
    if resultado.returncode == 0:
        _log.info("Tarefa '%s' removida do Agendador.", NOME_DA_TAREFA)
        return True
    return False


def limpeza_agendada(*, executar: Executor = _rodar) -> bool:
    return executar(["schtasks", "/Query", "/TN", NOME_DA_TAREFA]).returncode == 0


# -- o nome antigo ----------------------------------------------------------


@dataclass(frozen=True)
class Legado:
    """O que `remover_legado` encontrou e tirou da máquina."""

    atalho: Path | None
    tarefa: bool


def remover_legado(*, executar: Executor = _rodar) -> Legado:
    """Apaga o atalho `Second Brain.lnk` e a tarefa `SecondBrain-Limpeza`.

    Os dois chamam `-m second_brain`, módulo que morreu no rename: o atalho faz
    a bandeja não subir no logon e a tarefa falha todo dia ao meio-dia — ambos
    sem console, logo sem erro em lugar nenhum. Nenhum dos dois é recriado
    aqui; quem cria os novos é `instalar_inicializacao` e `agendar_limpeza`.
    """
    atalho = _remover_atalho(caminho_do_atalho_legado())
    resultado = executar(["schtasks", "/Delete", "/TN", NOME_DA_TAREFA_LEGADA, "/F"])
    tarefa = resultado.returncode == 0
    if tarefa:
        _log.info("Tarefa legada '%s' removida do Agendador.", NOME_DA_TAREFA_LEGADA)
    return Legado(atalho=atalho, tarefa=tarefa)

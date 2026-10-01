"""A casca do jornal: `[noticias]` e `[claude].cli` no config, o painel e a tarefa `Whis-Noticias`.

Tudo por executor espião ou função trocada — nenhuma tarefa é registrada e o
Agendador da máquina de teste não é tocado. O que se prova é a chave lida,
escrita e mostrada, o comando montado a partir da configuração e o que
`whis windows --news` pede à automação.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from functools import partial
from pathlib import Path

import pytest

from whis import automacao
from whis.__main__ import main
from whis.configuracao import (
    MODELO_DE_CONFIGURACAO,
    Configuracao,
    ConfiguracaoInvalida,
    carregar,
)
from whis.painel import CAMPOS, Painel, texto_do_valor, textos_de

ATIVA = next(campo for campo in CAMPOS if campo.caminho == "[noticias].ativa")
HORARIO = next(campo for campo in CAMPOS if campo.caminho == "[noticias].horario")
CLI = next(campo for campo in CAMPOS if campo.caminho == "[claude].cli")


class ExecutorEspiao:
    """Guarda os comandos; `codigo_por_trecho` responde diferente a cada comando."""

    def __init__(self, codigo: int = 0, **codigo_por_trecho: int) -> None:
        self.comandos: list[list[str]] = []
        self._codigo = codigo
        self._codigo_por_trecho = codigo_por_trecho

    def __call__(self, comando: list[str]) -> subprocess.CompletedProcess:
        self.comandos.append(comando)
        texto = " ".join(comando)
        for trecho, codigo in self._codigo_por_trecho.items():
            if trecho in texto:
                return subprocess.CompletedProcess(comando, codigo, "", "")
        return subprocess.CompletedProcess(comando, self._codigo, "", "")

    def registros(self) -> list[list[str]]:
        return [c for c in self.comandos if "-File" in c and "agendar_tarefa" in " ".join(c)]


class FormularioDublê:
    def __init__(self) -> None:
        self.textos: dict = {}
        self.erros: list[str] = []

    def mostrar(self, campos, textos) -> None:
        self.textos = dict(textos)

    def ler(self):
        return dict(self.textos)

    def mostrar_erro(self, mensagem: str) -> None:
        self.erros.append(mensagem)

    def mostrar_sucesso(self, mensagem: str) -> None:
        pass

    def fechar(self) -> None:
        pass


def escrever(tmp_path: Path, corpo: str) -> Path:
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "V"\n{corpo}', encoding="utf-8")
    return arquivo


def parametro(comando: list[str], nome: str) -> str:
    return comando[comando.index(nome) + 1]


# -- as chaves ----------------------------------------------------------------------


def test_sem_as_chaves_o_jornal_nasce_ativo_as_oito_e_vinte_e_o_cli_automatico(tmp_path: Path):
    configuracao = carregar(escrever(tmp_path, ""))

    assert configuracao.noticias_ativa is True
    assert configuracao.noticias_horario == "08:20"
    assert configuracao.claude_cli == ""


def test_as_chaves_preenchidas_sao_lidas(tmp_path: Path):
    configuracao = carregar(
        escrever(
            tmp_path,
            '[claude]\ncli = " C:/bin/claude.exe "\n[noticias]\nativa = false\nhorario = "07:45"\n',
        )
    )

    assert configuracao.noticias_ativa is False
    assert configuracao.noticias_horario == "07:45"
    assert configuracao.claude_cli == "C:/bin/claude.exe"


@pytest.mark.parametrize("hora", ['"8h20"', '"25:00"', '"08-20"'])
def test_horario_do_jornal_fora_de_hh_mm_e_recusado(tmp_path: Path, hora: str):
    with pytest.raises(ConfiguracaoInvalida, match=r"\[noticias\].horario.*HH:MM"):
        carregar(escrever(tmp_path, f"[noticias]\nhorario = {hora}\n"))


def test_jornal_ativo_que_nao_e_booleano_e_recusado(tmp_path: Path):
    with pytest.raises(ConfiguracaoInvalida, match=r"\[noticias\].ativa.*true ou false"):
        carregar(escrever(tmp_path, '[noticias]\nativa = "sim"\n'))


def test_o_modelo_traz_o_jornal_ligado_e_o_cli_vazio():
    dados = tomllib.loads(MODELO_DE_CONFIGURACAO.format(vault="V"))

    assert dados["noticias"] == {"ativa": True, "horario": "08:20"}
    assert dados["claude"]["cli"] == ""


# -- o painel -----------------------------------------------------------------------


def test_o_painel_mostra_o_jornal_e_o_cli():
    configuracao = Configuracao(
        vault=Path("V"), noticias_horario="07:45", claude_cli="C:/c.exe"
    )

    assert texto_do_valor(configuracao, ATIVA) == "true"
    assert texto_do_valor(configuracao, HORARIO) == "07:45"
    assert texto_do_valor(configuracao, CLI) == "C:/c.exe"


def test_o_painel_grava_jornal_desligado_horario_e_cli(tmp_path: Path):
    arquivo = escrever(tmp_path, "")
    formulario = FormularioDublê()
    painel = Painel(carregar(arquivo), formulario)
    painel.abrir()
    formulario.textos[ATIVA] = "false"
    formulario.textos[HORARIO] = " 06:30 "
    formulario.textos[CLI] = "C:/Users/x/.local/bin/claude.exe"

    painel.salvar()

    relida = carregar(arquivo)
    assert formulario.erros == []
    assert relida.noticias_ativa is False
    assert relida.noticias_horario == "06:30"
    assert relida.claude_cli == "C:/Users/x/.local/bin/claude.exe"


def test_o_painel_recusa_horario_invalido_sem_escrever(tmp_path: Path):
    arquivo = escrever(tmp_path, "")
    antes = arquivo.read_text(encoding="utf-8")
    formulario = FormularioDublê()
    painel = Painel(carregar(arquivo), formulario)
    formulario.textos = textos_de(painel.configuracao)
    formulario.textos[HORARIO] = "oito"

    assert painel.salvar() is None
    assert "[noticias].horario" in formulario.erros[0]
    assert arquivo.read_text(encoding="utf-8") == antes


# -- a tarefa -----------------------------------------------------------------------


def test_o_jornal_ganha_um_gatilho_diario_no_horario_e_roda_news_agendada(tmp_path: Path):
    configuracao = Configuracao(
        vault=Path("V"), noticias_horario="07:45",
        origem=tmp_path / "config.toml",
    )
    espiao = ExecutorEspiao()

    nome = automacao.agendar_noticias(configuracao, executar=espiao)

    [comando] = espiao.registros()
    assert nome == "Whis-Noticias"
    assert parametro(comando, "-Nome") == "Whis-Noticias"
    assert parametro(comando, "-Gatilhos") == "Daily=07:45"
    assert parametro(comando, "-Executavel") == str(automacao.interpretador_sem_console())
    assert parametro(comando, "-Argumentos") == (
        f'-m whis news --agendada --config "{tmp_path / "config.toml"}"'
    )


def test_sem_origem_o_jornal_aponta_o_caminho_padrao(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    espiao = ExecutorEspiao()

    automacao.agendar_noticias(Configuracao(vault=Path("V")), executar=espiao)

    assert parametro(espiao.registros()[0], "-Argumentos").endswith(
        f'--config "{tmp_path / "whis" / "config.toml"}"'
    )


def test_falha_do_agendador_no_jornal_vira_erro_legivel():
    with pytest.raises(automacao.ErroDeAutomacao, match="Whis-Noticias"):
        automacao.agendar_noticias(
            Configuracao(vault=Path("V")), executar=ExecutorEspiao(codigo=1)
        )


def test_desagendar_e_consultar_o_jornal():
    espiao = ExecutorEspiao()

    assert automacao.desagendar_noticias(executar=espiao) is True
    assert automacao.noticias_agendada(executar=espiao) is True
    assert automacao.desagendar_noticias(executar=ExecutorEspiao(codigo=1)) is False
    assert automacao.noticias_agendada(executar=ExecutorEspiao(codigo=1)) is False
    assert "Unregister-ScheduledTask -TaskName 'Whis-Noticias'" in parametro(
        espiao.comandos[0], "-Command"
    )
    assert "Get-ScheduledTask -TaskName 'Whis-Noticias'" in parametro(
        espiao.comandos[1], "-Command"
    )


def test_o_vigia_so_olha_o_jornal_se_ele_existe_no_agendador():
    sem_jornal = ExecutorEspiao(**{"'Whis-Noticias'": 1, "'Whis-Reunioes'": 1})
    com_jornal = ExecutorEspiao(**{"'Whis-Reunioes'": 1})

    assert automacao.tarefas_vigiadas(executar=sem_jornal) == ["Whis-Daily"]
    assert automacao.tarefas_vigiadas(executar=com_jornal) == ["Whis-Daily", "Whis-Noticias"]


def test_o_teto_da_tarefa_comporta_uma_edicao_de_quinze_minutos():
    texto = automacao.SCRIPT_DE_AGENDAMENTO.read_text(encoding="utf-8-sig")

    teto = re.search(r"-ExecutionTimeLimit \(New-TimeSpan -Minutes (\d+)\)", texto)

    assert teto is not None and int(teto.group(1)) >= 15


# -- whis windows --news ------------------------------------------------------------


class _Chamadas(list):
    """O que a automação trocada recebeu; `vigia` diz se o vigia já está agendado."""

    def __init__(self) -> None:
        super().__init__()
        self.vigia = {"agendado": True}


@pytest.fixture
def espiar_automacao(monkeypatch):
    chamadas = _Chamadas()
    vigia = chamadas.vigia
    monkeypatch.setattr(automacao, "instalar_inicializacao", lambda: Path("Whis.lnk"))
    monkeypatch.setattr(automacao, "remover_inicializacao", lambda: None)
    monkeypatch.setattr(
        automacao,
        "agendar_noticias",
        lambda configuracao: chamadas.append(("news", configuracao.noticias_horario)),
    )
    monkeypatch.setattr(
        automacao, "desagendar_noticias", lambda: chamadas.append(("-news", None)) or True
    )
    monkeypatch.setattr(automacao, "agendar_daily", lambda configuracao: chamadas.append(("daily", None)))
    monkeypatch.setattr(
        automacao,
        "agendar_vigia",
        lambda configuracao: chamadas.append(("vigia", None)) or ["Whis-Daily", "Whis-Noticias"],
    )
    monkeypatch.setattr(automacao, "desagendar_vigia", lambda: chamadas.append(("-vigia", None)) or True)
    monkeypatch.setattr(automacao, "desagendar_daily", lambda: chamadas.append(("-daily", None)) or True)
    monkeypatch.setattr(automacao, "vigia_agendado", lambda: vigia["agendado"])
    return chamadas


def test_windows_news_agenda_o_jornal_e_reagenda_o_vigia(tmp_path: Path, espiar_automacao, capsys):
    arquivo = escrever(tmp_path, '[noticias]\nhorario = "07:45"\n')

    codigo = main(["windows", "--news", "--config", str(arquivo)])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert espiar_automacao == [("news", "07:45"), ("vigia", None)]
    assert "Jornal agendado como 'Whis-Noticias': todo dia às 07:45" in saida
    assert "Vigia reagendado" in saida and "Whis-Noticias" in saida


def test_windows_news_sem_vigia_nao_cria_um_e_diz_como(tmp_path: Path, espiar_automacao, capsys):
    espiar_automacao.vigia["agendado"] = False

    main(["windows", "--news", "--config", str(escrever(tmp_path, ""))])

    assert espiar_automacao == [("news", "08:20")]
    assert "whis windows --daily" in capsys.readouterr().out


def test_windows_news_com_daily_agenda_o_jornal_antes_do_vigia(tmp_path: Path, espiar_automacao):
    arquivo = escrever(tmp_path, '[daily]\nhorarios = { segunda = "13:55" }\n')

    main(["windows", "--news", "--daily", "--config", str(arquivo)])

    assert [nome for nome, _ in espiar_automacao] == ["news", "daily", "vigia"]


def test_windows_remover_news_desagenda_e_tira_o_jornal_do_vigia(
    tmp_path: Path, espiar_automacao, capsys
):
    codigo = main(["windows", "--news", "--remover", "--config", str(escrever(tmp_path, ""))])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert [nome for nome, _ in espiar_automacao] == ["-news", "vigia"]
    assert "'Whis-Noticias' removida do Agendador" in saida


def test_windows_news_monta_o_comando_de_verdade_com_executor_falso(
    tmp_path: Path, monkeypatch, capsys
):
    espiao = ExecutorEspiao(**{"'Whis-Reunioes'": 1})
    monkeypatch.setattr(automacao, "instalar_inicializacao", lambda: Path("Whis.lnk"))
    for nome in ("agendar_noticias", "agendar_vigia"):
        monkeypatch.setattr(automacao, nome, partial(getattr(automacao, nome), executar=espiao))
    monkeypatch.setattr(automacao, "vigia_agendado", partial(automacao.vigia_agendado, executar=espiao))
    arquivo = escrever(tmp_path, '[noticias]\nhorario = "07:45"\n')

    assert main(["windows", "--news", "--config", str(arquivo)]) == 0

    jornal, vigia = espiao.registros()
    assert parametro(jornal, "-Nome") == "Whis-Noticias"
    assert parametro(jornal, "-Gatilhos") == "Daily=07:45"
    assert parametro(jornal, "-Argumentos") == f'-m whis news --agendada --config "{arquivo}"'
    assert parametro(vigia, "-Nome") == "Whis-Vigia"
    assert parametro(vigia, "-Argumentos").endswith("-Tarefas Whis-Daily,Whis-Noticias")


def test_o_help_do_windows_documenta_o_jornal(capsys):
    with pytest.raises(SystemExit):
        main(["windows", "--help"])

    ajuda = capsys.readouterr().out
    assert "--news" in ajuda and "[noticias].horario" in ajuda

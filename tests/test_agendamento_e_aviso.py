"""Camada 2 da interface: a daily agendada por dia da semana, o toast e o vigia.

Tudo por executor espião — nenhuma tarefa é registrada, nenhum toast sai, o
Agendador da máquina de teste não é tocado. O que se prova é o comando montado
a partir da configuração, o que o subcomando conta, e que os scripts existem no
pacote com o BOM que o PowerShell 5.1 exige.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest

from whis import automacao, avisos
from whis.__main__ import MODELO_DE_CONFIGURACAO, main
from whis.configuracao import DIAS_DA_SEMANA, Configuracao, ConfiguracaoInvalida, carregar

HORARIOS_DO_USUARIO = (
    'horarios = { segunda = "13:55", terca = "13:55", quarta = "10:25", '
    'quinta = "13:55", sexta = "10:25" }'
)


class ExecutorEspiao:
    """Guarda os comandos; `codigo_por_trecho` responde diferente a cada comando."""

    def __init__(self, codigo: int = 0, saida: str = "", **codigo_por_trecho: int) -> None:
        self.comandos: list[list[str]] = []
        self._codigo = codigo
        self._saida = saida
        self._codigo_por_trecho = codigo_por_trecho

    def __call__(self, comando: list[str]) -> subprocess.CompletedProcess:
        self.comandos.append(comando)
        texto = " ".join(comando)
        for trecho, codigo in self._codigo_por_trecho.items():
            if trecho in texto:
                return subprocess.CompletedProcess(comando, codigo, "", self._saida)
        return subprocess.CompletedProcess(comando, self._codigo, "", self._saida)

    def registros(self) -> list[list[str]]:
        return [c for c in self.comandos if "-File" in c and "agendar_tarefa" in " ".join(c)]


def escrever(tmp_path: Path, corpo: str) -> Path:
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "V"\ngravacoes = "G"\n[daily]\n{corpo}\n', encoding="utf-8")
    return arquivo


def parametro(comando: list[str], nome: str) -> str:
    return comando[comando.index(nome) + 1]


def configuracao_com(horarios: tuple[tuple[str, str], ...], origem: Path | None = None) -> Configuracao:
    return Configuracao(
        vault=Path("V"), gravacoes=Path("G"), daily_horarios=horarios, origem=origem
    )


# -- [daily].horarios -------------------------------------------------------


def test_horarios_chegam_na_ordem_da_semana_mesmo_fora_de_ordem_no_toml(tmp_path: Path):
    arquivo = escrever(
        tmp_path, 'horarios = { sexta = "10:25", segunda = "13:55", quarta = "10:25" }'
    )

    configuracao = carregar(arquivo)

    assert configuracao.daily_horarios == (
        ("segunda", "13:55"),
        ("quarta", "10:25"),
        ("sexta", "10:25"),
    )


def test_horarios_ausentes_e_tabela_vazia(tmp_path: Path):
    assert carregar(escrever(tmp_path, "")).daily_horarios == ()
    assert carregar(escrever(tmp_path, "horarios = {}")).daily_horarios == ()


@pytest.mark.parametrize("hora", ['"25:00"', '"treze"', '"13h55"', "1355"])
def test_hora_invalida_diz_o_dia_e_o_formato(tmp_path: Path, hora: str):
    with pytest.raises(ConfiguracaoInvalida) as erro:
        carregar(escrever(tmp_path, f"horarios = {{ terca = {hora} }}"))

    assert "[daily].horarios.terca" in str(erro.value)
    assert "HH:MM" in str(erro.value)


def test_dia_desconhecido_lista_os_aceitos(tmp_path: Path):
    with pytest.raises(ConfiguracaoInvalida) as erro:
        carregar(escrever(tmp_path, 'horarios = { "terça" = "13:55", seg = "13:55" }'))

    mensagem = str(erro.value)
    assert "'terça'" in mensagem and "'seg'" in mensagem
    assert ", ".join(DIAS_DA_SEMANA) in mensagem


def test_horarios_que_nao_e_tabela_e_configuracao_invalida(tmp_path: Path):
    with pytest.raises(ConfiguracaoInvalida, match=r"\[daily\]\.horarios.*tabela"):
        carregar(escrever(tmp_path, 'horarios = "13:55"'))


def test_o_modelo_de_configuracao_traz_a_tabela_do_usuario():
    dados = tomllib.loads(MODELO_DE_CONFIGURACAO.format(vault="V", gravacoes="G"))

    assert dados["daily"]["horarios"] == {
        "segunda": "13:55",
        "terca": "13:55",
        "quarta": "10:25",
        "quinta": "13:55",
        "sexta": "10:25",
    }


# -- a daily agendada -------------------------------------------------------


def test_a_daily_ganha_um_gatilho_semanal_por_dia_da_tabela(tmp_path: Path):
    configuracao = carregar(escrever(tmp_path, HORARIOS_DO_USUARIO))
    espiao = ExecutorEspiao()

    nome = automacao.agendar_daily(configuracao, executar=espiao)

    assert nome == "Whis-Daily"
    [comando] = espiao.registros()
    assert comando[:6] == [
        "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File"
    ]
    assert parametro(comando, "-File") == str(automacao.SCRIPT_DE_AGENDAMENTO)
    assert parametro(comando, "-Nome") == "Whis-Daily"
    assert parametro(comando, "-Gatilhos") == (
        "Monday=13:55,Tuesday=13:55,Wednesday=10:25,Thursday=13:55,Friday=10:25"
    )
    assert "python" in parametro(comando, "-Executavel").lower()
    assert parametro(comando, "-Argumentos") == f'-m whis daily --config "{tmp_path / "config.toml"}"'
    assert Path(parametro(comando, "-Diretorio")).is_dir()


def test_tabela_vazia_recusa_agendar_a_daily():
    espiao = ExecutorEspiao()

    with pytest.raises(automacao.ErroDeAutomacao, match=r"\[daily\]\.horarios.*vazia"):
        automacao.agendar_daily(configuracao_com(()), executar=espiao)

    assert espiao.comandos == []


def test_fim_de_semana_tambem_vira_gatilho():
    espiao = ExecutorEspiao()

    automacao.agendar_daily(
        configuracao_com((("sabado", "09:00"), ("domingo", "09:30"))), executar=espiao
    )

    assert parametro(espiao.registros()[0], "-Gatilhos") == "Saturday=09:00,Sunday=09:30"


def test_sem_origem_a_tarefa_aponta_o_caminho_padrao(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    espiao = ExecutorEspiao()

    automacao.agendar_daily(configuracao_com((("segunda", "13:55"),)), executar=espiao)

    argumentos = parametro(espiao.registros()[0], "-Argumentos")
    assert f'--config "{tmp_path / "whis" / "config.toml"}"' in argumentos


def test_falha_do_agendador_vira_erro_legivel():
    espiao = ExecutorEspiao(codigo=1, saida="Access is denied")

    with pytest.raises(automacao.ErroDeAutomacao, match="Whis-Daily.*Access is denied"):
        automacao.agendar_daily(configuracao_com((("segunda", "13:55"),)), executar=espiao)


def test_desagendar_a_daily_usa_o_modulo_e_nao_o_schtasks():
    espiao = ExecutorEspiao()

    assert automacao.desagendar_daily(executar=espiao) is True
    assert automacao.desagendar_daily(executar=ExecutorEspiao(codigo=1)) is False

    [comando] = espiao.comandos
    assert comando[0] == "powershell" and "-Command" in comando
    assert "Unregister-ScheduledTask -TaskName 'Whis-Daily' -Confirm:$false" in parametro(
        comando, "-Command"
    )
    assert "schtasks" not in " ".join(comando)


def test_daily_agendada_consulta_o_modulo():
    espiao = ExecutorEspiao()

    assert automacao.daily_agendada(executar=espiao) is True
    assert automacao.daily_agendada(executar=ExecutorEspiao(codigo=1)) is False
    assert "Get-ScheduledTask -TaskName 'Whis-Daily'" in parametro(espiao.comandos[0], "-Command")


def test_a_limpeza_migrou_para_o_mesmo_script(tmp_path: Path):
    espiao = ExecutorEspiao()

    automacao.agendar_limpeza(hora="12:00", executar=espiao, config=tmp_path / "c.toml")
    automacao.desagendar_limpeza(executar=espiao)
    automacao.limpeza_agendada(executar=espiao)

    assert "schtasks" not in " ".join(" ".join(c) for c in espiao.comandos)
    assert parametro(espiao.comandos[0], "-Gatilhos") == "Daily=12:00"
    assert "Unregister-ScheduledTask -TaskName 'Whis-Limpeza'" in parametro(
        espiao.comandos[1], "-Command"
    )
    assert "Get-ScheduledTask -TaskName 'Whis-Limpeza'" in parametro(
        espiao.comandos[2], "-Command"
    )


# -- o vigia ----------------------------------------------------------------


def test_o_vigia_roda_dez_minutos_depois_de_cada_daily_e_na_ronda_das_nove(tmp_path: Path):
    configuracao = carregar(escrever(tmp_path, HORARIOS_DO_USUARIO))
    espiao = ExecutorEspiao(**{"Get-ScheduledTask": 1})

    automacao.agendar_vigia(configuracao, executar=espiao)

    [comando] = espiao.registros()
    assert parametro(comando, "-Nome") == "Whis-Vigia"
    assert parametro(comando, "-Gatilhos") == (
        "Monday=14:05,Tuesday=14:05,Wednesday=10:35,Thursday=14:05,Friday=10:35,Daily=09:00"
    )


def test_o_vigia_e_um_powershell_autossuficiente_sem_python():
    espiao = ExecutorEspiao(**{"Get-ScheduledTask": 1})

    automacao.agendar_vigia(configuracao_com((("segunda", "13:55"),)), executar=espiao)

    [comando] = espiao.registros()
    assert "powershell" in parametro(comando, "-Executavel").lower()
    argumentos = parametro(comando, "-Argumentos")
    assert argumentos.startswith("-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ")
    assert f'"{automacao.SCRIPT_DO_VIGIA}"' in argumentos
    assert f"-Aumid {automacao.AUMID}" in argumentos
    assert "python" not in argumentos.lower()


def test_o_vigia_so_vigia_a_limpeza_se_ela_estiver_agendada():
    configuracao = configuracao_com((("segunda", "13:55"),))

    sem_limpeza = ExecutorEspiao(**{"Get-ScheduledTask": 1})
    assert automacao.agendar_vigia(configuracao, executar=sem_limpeza) == ["Whis-Daily"]
    assert parametro(sem_limpeza.registros()[0], "-Argumentos").endswith("-Tarefas Whis-Daily")

    com_limpeza = ExecutorEspiao()
    assert automacao.agendar_vigia(configuracao, executar=com_limpeza) == [
        "Whis-Daily",
        "Whis-Limpeza",
    ]
    assert parametro(com_limpeza.registros()[0], "-Argumentos").endswith(
        "-Tarefas Whis-Daily,Whis-Limpeza"
    )


def test_perto_da_meia_noite_o_vigia_fica_no_mesmo_dia_da_semana():
    """`23:55` + 10 min é `00:05` de segunda mesmo — antes da daily, não depois.

    É um caso que a tabela do usuário não tem; virar o gatilho para terça
    custaria mais do que vale, e a ronda das 09:00 pega a falha de qualquer jeito.
    """
    espiao = ExecutorEspiao(**{"Get-ScheduledTask": 1})

    automacao.agendar_vigia(configuracao_com((("segunda", "23:55"),)), executar=espiao)

    assert parametro(espiao.registros()[0], "-Gatilhos") == "Monday=00:05,Daily=09:00"


def test_desagendar_o_vigia():
    espiao = ExecutorEspiao()

    assert automacao.desagendar_vigia(executar=espiao) is True
    assert "Unregister-ScheduledTask -TaskName 'Whis-Vigia'" in parametro(
        espiao.comandos[0], "-Command"
    )


# -- os scripts no pacote ---------------------------------------------------


@pytest.mark.parametrize(
    ("script", "trecho"),
    [
        (automacao.SCRIPT_DE_AGENDAMENTO, "Register-ScheduledTask"),
        (automacao.SCRIPT_DO_VIGIA, "Get-ScheduledTaskInfo"),
        (avisos.SCRIPT_DO_AVISO, "ToastNotification"),
    ],
)
def test_os_scripts_existem_no_pacote_e_comecam_com_bom(script: Path, trecho: str):
    assert script.is_file()
    assert script.read_bytes()[:3] == b"\xef\xbb\xbf"
    assert trecho in script.read_text(encoding="utf-8-sig")


def test_o_agendamento_liga_o_que_o_schtasks_nao_liga():
    texto = automacao.SCRIPT_DE_AGENDAMENTO.read_text(encoding="utf-8-sig")

    for opcao in (
        "-StartWhenAvailable",
        "-WakeToRun",
        "-AllowStartIfOnBatteries",
        "-DontStopIfGoingOnBatteries",
        "-MultipleInstances IgnoreNew",
        "-Force",
    ):
        assert opcao in texto


def test_o_vigia_nao_depende_de_nada_do_whis():
    """Ele só consulta o Agendador e os processos; o toast está duplicado nele."""
    texto = automacao.SCRIPT_DO_VIGIA.read_text(encoding="utf-8-sig")
    codigo = "\n".join(l for l in texto.splitlines() if not l.lstrip().startswith("#"))

    assert "-m whis daily" not in codigo and "config.toml" not in codigo
    assert "avisar.ps1" not in codigo and "Import-Module" not in codigo
    assert "Get-ScheduledTaskInfo" in codigo and "NumberOfMissedRuns" in codigo
    assert "267011" in codigo and "267009" in codigo
    assert "-m whis bandeja" in codigo and "Win32_Process" in codigo
    assert "O Whis precisa de você" in codigo
    assert "CreateToastNotifier($Aumid)" in codigo


def test_o_toast_faz_o_escape_no_proprio_script():
    texto = avisos.SCRIPT_DO_AVISO.read_text(encoding="utf-8-sig")

    assert "[System.Security.SecurityElement]::Escape" in texto
    assert 'activationType=""protocol""' in texto


# -- o toast ----------------------------------------------------------------


def test_avisar_dispara_o_script_em_nome_da_aumid():
    espiao = ExecutorEspiao()

    assert avisos.avisar("Daily pronta", "A nota de hoje nasceu.", executar=espiao) is True

    [comando] = espiao.comandos
    assert comando[:6] == [
        "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File"
    ]
    assert parametro(comando, "-File") == str(avisos.SCRIPT_DO_AVISO)
    assert parametro(comando, "-Titulo") == "Daily pronta"
    assert parametro(comando, "-Texto") == "A nota de hoje nasceu."
    assert parametro(comando, "-Aumid") == automacao.AUMID
    assert "-RotuloDoBotao" not in comando and "-UriDoBotao" not in comando


def test_avisar_com_botao_passa_rotulo_e_uri():
    espiao = ExecutorEspiao()
    uri = "obsidian://open?vault=245833c11ad43e6e&file=daily%2Fatual"

    avisos.avisar("Daily pronta", "Abra a nota.", botao=("Abrir no Obsidian", uri), executar=espiao)

    [comando] = espiao.comandos
    assert parametro(comando, "-RotuloDoBotao") == "Abrir no Obsidian"
    assert parametro(comando, "-UriDoBotao") == uri


def test_avisar_entrega_o_texto_cru_e_deixa_o_escape_para_o_script():
    """Aspas, `&` e `<` chegam intactos: o escape XML é do `.ps1`, uma vez só."""
    espiao = ExecutorEspiao()
    texto = 'O "Ribeiro" pediu <revisão> & mais uma coisa'

    avisos.avisar("Título & cia", texto, executar=espiao)

    [comando] = espiao.comandos
    assert parametro(comando, "-Titulo") == "Título & cia"
    assert parametro(comando, "-Texto") == texto


def test_toast_que_falha_nao_derruba_quem_chamou(caplog):
    with caplog.at_level("WARNING", logger="whis.avisos"):
        saiu = avisos.avisar("x", "y", executar=ExecutorEspiao(codigo=1, saida="sem AUMID"))

    assert saiu is False
    assert "sem AUMID" in caplog.text


def test_executor_que_explode_tambem_nao_derruba(caplog):
    def sem_powershell(comando):
        raise FileNotFoundError("powershell não encontrado")

    with caplog.at_level("WARNING", logger="whis.avisos"):
        assert avisos.avisar("x", "y", executar=sem_powershell) is False

    assert "powershell não encontrado" in caplog.text


# -- o subcomando windows ---------------------------------------------------


@pytest.fixture
def espiar_automacao(monkeypatch):
    chamadas: list[tuple[str, object]] = []
    monkeypatch.setattr(automacao, "instalar_inicializacao", lambda: Path("Whis.lnk"))
    monkeypatch.setattr(
        automacao,
        "agendar_daily",
        lambda configuracao: chamadas.append(("daily", configuracao.daily_horarios)),
    )
    monkeypatch.setattr(
        automacao,
        "agendar_vigia",
        lambda configuracao: chamadas.append(("vigia", configuracao.daily_horarios))
        or ["Whis-Daily"],
    )
    monkeypatch.setattr(
        automacao,
        "agendar_limpeza",
        lambda hora, config: chamadas.append(("limpeza", (hora, config))),
    )
    monkeypatch.setattr(automacao, "remover_inicializacao", lambda: None)
    monkeypatch.setattr(
        automacao, "desagendar_daily", lambda: chamadas.append(("-daily", None)) or True
    )
    monkeypatch.setattr(
        automacao, "desagendar_vigia", lambda: chamadas.append(("-vigia", None)) or True
    )
    monkeypatch.setattr(
        automacao, "desagendar_limpeza", lambda: chamadas.append(("-limpeza", None)) or True
    )
    return chamadas


def test_windows_daily_agenda_a_daily_e_o_vigia_e_conta_os_horarios(
    tmp_path: Path, espiar_automacao, capsys
):
    arquivo = escrever(tmp_path, HORARIOS_DO_USUARIO)

    codigo = main(["windows", "--daily", "--config", str(arquivo)])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert [nome for nome, _ in espiar_automacao] == ["daily", "vigia"]
    assert "Daily agendada como 'Whis-Daily'" in saida
    assert "segunda 13:55, terça 13:55, quarta 10:25, quinta 13:55, sexta 10:25" in saida
    assert "Vigia agendado como 'Whis-Vigia'" in saida
    assert "10 minutos depois de cada daily" in saida and "09:00" in saida
    assert "desligado na hora" in saida


def test_windows_daily_com_tabela_vazia_recusa_sem_instalar_nada(
    tmp_path: Path, espiar_automacao, caplog
):
    arquivo = escrever(tmp_path, "")

    with caplog.at_level("ERROR", logger="whis"):
        codigo = main(["windows", "--daily", "--config", str(arquivo)])

    assert codigo == 1
    assert espiar_automacao == []
    assert "[daily].horarios" in caplog.text and "vazia" in caplog.text


def test_windows_daily_e_limpeza_agendam_a_limpeza_antes_do_vigia(
    tmp_path: Path, espiar_automacao
):
    arquivo = escrever(tmp_path, HORARIOS_DO_USUARIO)

    main(["windows", "--daily", "--limpeza", "--config", str(arquivo)])

    assert [nome for nome, _ in espiar_automacao] == ["limpeza", "daily", "vigia"]
    assert espiar_automacao[0][1] == ("12:00", arquivo)


def test_windows_limpeza_sem_config_aponta_o_caminho_padrao(
    tmp_path: Path, espiar_automacao, monkeypatch
):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    main(["windows", "--limpeza"])

    assert espiar_automacao == [("limpeza", ("12:00", tmp_path / "whis" / "config.toml"))]


def test_windows_remover_daily_desagenda_a_daily_e_o_vigia(espiar_automacao, capsys):
    codigo = main(["windows", "--remover", "--daily"])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert [nome for nome, _ in espiar_automacao] == ["-daily", "-vigia"]
    assert "'Whis-Daily' removida" in saida and "'Whis-Vigia' removida" in saida


def test_windows_remover_so_a_limpeza_avisa_que_o_vigia_continua(espiar_automacao, capsys):
    main(["windows", "--remover", "--limpeza"])

    saida = capsys.readouterr().out
    assert [nome for nome, _ in espiar_automacao] == ["-limpeza"]
    assert "continua vigiando a limpeza" in saida


def test_windows_sem_daily_nao_agenda_a_daily(espiar_automacao):
    main(["windows"])

    assert espiar_automacao == []


def test_o_help_do_windows_documenta_a_daily(capsys):
    with pytest.raises(SystemExit) as saida:
        main(["windows", "--help"])

    ajuda = capsys.readouterr().out
    assert saida.value.code == 0
    assert "--daily" in ajuda and "[daily].horarios" in ajuda
    assert "desligado" in ajuda

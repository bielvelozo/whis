"""Camada 5 da interface: o toast que abre a nota certa e o gesto da bandeja consertado.

Nenhum toast sai e nada é aberto de verdade: `avisos.avisar` entra espionado
no subcomando, e quem lança a URI no Windows entra injetado em
`abrir_no_windows`. O que se prova é a URI montada, o texto do toast nos dois
casos e que o gesto da bandeja passa pela URI quando a nota é do vault.
"""

from __future__ import annotations

import re
import tomllib
from datetime import date, datetime
from pathlib import Path

import pytest

from whis import __main__ as cli
from whis import avisos, vault
from whis import bandeja as _bandeja
from whis.__main__ import MODELO_DE_CONFIGURACAO, main, texto_do_toast_da_daily
from whis.bandeja import Bandeja
from whis.coletor import Coletor
from whis.configuracao import Configuracao, carregar
from whis.daily import JanelaDaDaily, ResultadoDaDaily
from whis.fakes import DailyFake, ResumoFake, STTFake
from whis.nota_viva import Mudancas
from whis.portas import ErroDeDaily
from test_bandeja import IconeDublê
from test_coletor import GravadorDublê

ID_DO_VAULT = "245833c11ad43e6e"


def configuracao_com(vault_do_obsidian: str = "", pasta: str = "C:/Users/x/whis-vault") -> Configuracao:
    return Configuracao(vault=Path(pasta), gravacoes=Path("G"), obsidian_vault=vault_do_obsidian)


# -- a URI do Obsidian ------------------------------------------------------


@pytest.mark.parametrize(
    ("caminho", "esperado"),
    [
        ("daily/atual.md", "daily%2Fatual"),
        ("notas/Minha Daily.md", "notas%2FMinha%20Daily"),
        ("reunioes/reunião de time.md", "reunioes%2Freuni%C3%A3o%20de%20time"),
    ],
)
def test_a_uri_escapa_barra_espaco_e_acento_sem_nunca_usar_mais(caminho: str, esperado: str):
    uri = vault.uri_do_obsidian(configuracao_com(ID_DO_VAULT), caminho)

    assert uri == f"obsidian://open?vault={ID_DO_VAULT}&file={esperado}"
    assert "+" not in uri


def test_sem_id_configurado_o_vault_e_o_nome_da_pasta():
    uri = vault.uri_do_obsidian(configuracao_com("", "C:/Users/x/Meu Vault"), "daily/atual.md")

    assert uri == "obsidian://open?vault=Meu%20Vault&file=daily%2Fatual"


def test_a_uri_aceita_o_caminho_como_o_windows_o_escreve():
    uri = vault.uri_do_obsidian(configuracao_com(ID_DO_VAULT), "daily\\atual.md")

    assert uri.endswith("&file=daily%2Fatual")


# -- [obsidian].vault -------------------------------------------------------


def escrever(tmp_path: Path, corpo: str) -> Path:
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "V"\ngravacoes = "G"\n{corpo}', encoding="utf-8")
    return arquivo


def test_obsidian_vault_chega_achatado_e_nasce_vazio(tmp_path: Path):
    assert carregar(escrever(tmp_path, "")).obsidian_vault == ""
    assert (
        carregar(escrever(tmp_path, f'\n[obsidian]\nvault = " {ID_DO_VAULT} "\n')).obsidian_vault
        == ID_DO_VAULT
    )


def test_o_modelo_traz_o_id_do_vault_desta_maquina():
    dados = tomllib.loads(MODELO_DE_CONFIGURACAO.format(vault="V", gravacoes="G"))

    assert dados["obsidian"]["vault"] == ID_DO_VAULT


# -- o texto do toast -------------------------------------------------------


def resultado_com(mudancas: Mudancas | None = None, falha: str | None = None) -> ResultadoDaDaily:
    agora = datetime(2026, 9, 11, 13, 55).astimezone()
    return ResultadoDaDaily(
        janela=JanelaDaDaily(data=date(2026, 9, 11), desde=agora, ate=agora),
        nota=Path("daily/2026-09-11.md"),
        eventos=(),
        excluidos=0,
        fontes_lidas=("git",),
        fontes_com_falha=(),
        reunioes=(),
        roteiro=None,
        nota_viva=Path("daily/atual.md"),
        secoes=(),
        mudancas=mudancas,
        falha_do_roteiro=falha,
    )


def test_o_texto_conta_os_novos_e_os_movidos():
    mudancas = Mudancas(acrescentadas=(("- a",), ("- b",), ("- c",)), movidas=(("- d",),))

    assert texto_do_toast_da_daily(resultado_com(mudancas)) == (
        "3 itens novos e 1 movido para 'O que eu fiz'."
    )
    assert texto_do_toast_da_daily(resultado_com(Mudancas(acrescentadas=(("- a",),)))) == (
        "1 item novo."
    )
    assert texto_do_toast_da_daily(resultado_com(Mudancas(movidas=(("- a",), ("- b",))))) == (
        "2 movidos para 'O que eu fiz'."
    )


def test_o_texto_diz_quando_nada_mudou():
    assert texto_do_toast_da_daily(resultado_com(Mudancas())) == "Nada mudou na nota viva."
    assert texto_do_toast_da_daily(resultado_com(None)) == "Nada mudou na nota viva."


def test_o_texto_diz_quando_a_nota_nasceu_parcial():
    assert texto_do_toast_da_daily(resultado_com(falha="o Claude não respondeu a tempo")) == (
        "A nota nasceu parcial: o Claude não respondeu a tempo. A nota viva ficou como estava."
    )


# -- o subcomando daily -----------------------------------------------------


class AvisoEspiao:
    def __init__(self, saiu: bool = True) -> None:
        self.avisos: list[tuple[str, str, tuple[str, str] | None]] = []
        self._saiu = saiu

    def __call__(self, titulo: str, texto: str, *, botao=None, executar=None) -> bool:
        self.avisos.append((titulo, texto, botao))
        return self._saiu


@pytest.fixture
def aviso(monkeypatch) -> AvisoEspiao:
    espiao = AvisoEspiao()
    monkeypatch.setattr(avisos, "avisar", espiao)
    return espiao


def test_quando_a_daily_nasce_sai_o_toast_com_o_botao_do_obsidian(
    configuracao_do_diario, caminho_do_vault: Path, aviso: AvisoEspiao
):
    configuracao_do_diario()

    codigo = main(["daily", "--fakes"])

    assert codigo == 0
    [(titulo, texto, botao)] = aviso.avisos
    assert titulo == "A daily está pronta"
    assert re.fullmatch(r"\d+ ite(m novo|ns novos)\.", texto), texto
    assert botao == (
        "Abrir no Obsidian",
        f"obsidian://open?vault={caminho_do_vault.name}&file=daily%2Fatual",
    )


def test_o_botao_usa_o_id_do_vault_quando_configurado(
    configuracao_do_diario, tmp_path: Path, aviso: AvisoEspiao, monkeypatch
):
    configuracao = configuracao_do_diario()
    arquivo = configuracao.origem
    arquivo.write_text(
        arquivo.read_text(encoding="utf-8") + f'\n[obsidian]\nvault = "{ID_DO_VAULT}"\n',
        encoding="utf-8",
    )

    main(["daily", "--fakes"])

    assert aviso.avisos[0][2][1] == f"obsidian://open?vault={ID_DO_VAULT}&file=daily%2Fatual"


def test_simular_nao_avisa(configuracao_do_diario, aviso: AvisoEspiao):
    configuracao_do_diario()

    main(["daily", "--fakes", "--simular"])

    assert aviso.avisos == []


def test_a_nota_parcial_avisa_que_ficou_como_estava(
    configuracao_do_diario, aviso: AvisoEspiao, monkeypatch, capsys
):
    configuracao_do_diario()
    main(["daily", "--fakes"])
    aviso.avisos.clear()
    monkeypatch.setattr(
        cli,
        "montar_roteiro_da_daily",
        lambda configuracao, *, fakes=False: DailyFake(erro=ErroDeDaily("o Claude caiu")),
    )

    codigo = main(["daily", "--fakes"])

    assert codigo == cli.SAIDA_PARCIAL
    [(titulo, texto, botao)] = aviso.avisos
    assert titulo == "A daily está pronta"
    assert texto == "A nota nasceu parcial: o Claude caiu. A nota viva ficou como estava."
    assert botao[0] == "Abrir no Obsidian"


def test_a_suite_nunca_mostra_um_toast_de_verdade(configuracao_do_diario, toasts):
    """A fixture autouse do `conftest` intercepta: rodar a suíte não enche a central de avisos.

    Sem ela, cada `main(["daily", ...])` dos testes chamava o PowerShell de
    `avisar` e deixava uma notificação real no Windows de quem roda a suíte —
    dezenas por execução, guardadas três dias.
    """
    configuracao_do_diario()

    main(["daily", "--fakes"])

    assert [titulo for titulo, _, _ in toasts] == ["A daily está pronta"]
    assert avisos.avisar.__module__ == "conftest", "o `avisar` de verdade não pode estar no caminho"


def test_o_toast_que_nao_saiu_nao_muda_o_codigo_de_saida(configuracao_do_diario, monkeypatch):
    configuracao_do_diario()
    monkeypatch.setattr(avisos, "avisar", AvisoEspiao(saiu=False))

    assert main(["daily", "--fakes"]) == 0


# -- o gesto da bandeja -----------------------------------------------------


class LancadorEspiao:
    def __init__(self) -> None:
        self.lancados: list[str] = []

    def __call__(self, alvo: str) -> None:
        self.lancados.append(alvo)


def test_nota_do_vault_abre_pela_uri(configuracao: Configuracao):
    espiao = LancadorEspiao()
    nota = Path(configuracao.vault) / "reunioes" / "2026-09-11-1400-daily do time.md"

    alvo = _bandeja.abrir_no_windows(nota, configuracao, lancar=espiao)

    assert alvo == (
        f"obsidian://open?vault={configuracao.vault.name}"
        f"&file=reunioes%2F2026-09-11-1400-daily%20do%20time"
    )
    assert espiao.lancados == [alvo]


def test_pasta_e_arquivo_fora_do_vault_continuam_por_caminho(
    configuracao: Configuracao, tmp_path: Path
):
    espiao = LancadorEspiao()
    pasta = Path(configuracao.gravacoes)
    fora = tmp_path / "outra" / "nota.md"

    assert _bandeja.abrir_no_windows(pasta, configuracao, lancar=espiao) == str(pasta)
    assert _bandeja.abrir_no_windows(fora, configuracao, lancar=espiao) == str(fora)
    assert _bandeja.abrir_no_windows(fora, lancar=espiao) == str(fora)
    assert espiao.lancados == [str(pasta), str(fora), str(fora)]


def test_se_o_startfile_recusa_a_uri_o_start_do_cmd_e_a_segunda_porta():
    comandos: list[list[str]] = []

    def recusa(alvo: str) -> None:
        raise OSError("protocolo desconhecido")

    _bandeja._lancar(
        "obsidian://open?vault=v&file=daily%2Fatual",
        iniciar=recusa,
        executar=lambda comando, **_: comandos.append(comando),
    )

    assert comandos == [["cmd", "/c", "start", "", "obsidian://open?vault=v&file=daily%2Fatual"]]


def test_um_caminho_que_o_startfile_recusa_so_vai_para_o_log(caplog):
    comandos: list[list[str]] = []

    def recusa(alvo: str) -> None:
        raise OSError("sem programa associado")

    with caplog.at_level("ERROR", logger="whis.bandeja"):
        _bandeja._lancar(
            r"C:\x\nota.md", iniciar=recusa, executar=lambda c, **_: comandos.append(c)
        )

    assert comandos == []
    assert "sem programa associado" in caplog.text


def test_quando_o_startfile_aceita_ninguem_mais_e_chamado():
    aceitos: list[str] = []
    comandos: list[list[str]] = []

    _bandeja._lancar("obsidian://open?vault=v&file=x", iniciar=aceitos.append, executar=lambda c, **_: comandos.append(c))

    assert aceitos == ["obsidian://open?vault=v&file=x"] and comandos == []


def test_abrir_a_ultima_nota_passa_a_configuracao_do_coletor(
    configuracao: Configuracao, caminho_das_gravacoes: Path, monkeypatch
):
    abertos: list[tuple[Path, Configuracao]] = []
    monkeypatch.setattr(
        _bandeja, "abrir_no_windows", lambda caminho, configuracao: abertos.append((caminho, configuracao))
    )
    coletor = Coletor(
        configuracao,
        portas=lambda: (STTFake(), ResumoFake()),
        gravador=GravadorDublê(caminho_das_gravacoes),
        em_segundo_plano=False,
    )
    bandeja = Bandeja(coletor, icone=IconeDublê())
    bandeja.alternar()
    bandeja.alternar()

    bandeja.abrir_ultima_nota()

    [(nota, recebida)] = abertos
    assert nota == coletor.situacao().nota
    assert recebida is configuracao
    assert _bandeja.alvo_para_abrir(nota, recebida).startswith("obsidian://open?vault=")

"""A última camada: o acompanhamento das candidaturas e o lembrete da véspera, sem rede."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from whis import acompanhamento, automacao, corrida
from whis.__main__ import main
from whis.acoes import CANDIDATURA, FEITO, Registro
from whis.cacada import cacar
from whis.cacada_claude import Plano
from whis.configuracao import Configuracao
from whis.fakes_da_cacada import portas_fake
from whis.lembrete import ja_lembrado, marcar_lembrado, proxima_virada, texto_do_lembrete

VIRADA = datetime(2026, 10, 5, 7, 0, tzinfo=UTC)


# -- acompanhamento -------------------------------------------------------------------------------


def test_a_cacada_deixa_pacotes_preparados_a_virada_e_as_candidaturas(configuracao: Configuracao, tmp_path: Path):
    portas = portas_fake()
    for porta in portas.todas():
        porta.ultimo_plano = Plano(sete_dias=40, vira_sete_dias=VIRADA)

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado")

    raiz = Path(configuracao.vault)
    pacote = next((raiz / "cacada" / resultado.corrida).glob("*.md")).read_text(encoding="utf-8")
    assert "status: preparada" in pacote and "titulo:" in pacote
    candidaturas = (raiz / acompanhamento.CAMINHO_DAS_CANDIDATURAS).read_text(encoding="utf-8")
    assert "## Preparadas, esperando você enviar (3)" in candidaturas
    assert corrida.ler_virada(tmp_path / "estado") == VIRADA


def test_o_status_que_ele_muda_no_pacote_e_a_resposta_do_gmail_aparecem(tmp_path: Path):
    pasta = tmp_path / "cacada" / "2026-10-03-0200"
    pasta.mkdir(parents=True)
    (pasta / "dev-acme.md").write_text(
        '---\ntipo: pacote\nstatus: entrevista\ntitulo: "Dev Web"\nempresa: "Acme Tech"\nlink: "https://jobs.acmetech.com/42"\n---\n# x\n',
        encoding="utf-8",
    )
    (pasta / "freela.md").write_text(
        '---\ntipo: pacote\nstatus: recusada\ntitulo: "Landing"\nempresa: ""\nlink: "https://www.workana.com/job/x"\n---\n',
        encoding="utf-8",
    )
    registro = Registro(tmp_path / "estado")
    id_ = registro.intencao(CANDIDATURA, "https://estudio.gupy.io/jobs/7", detalhe="Game Dev")
    registro.concluir(id_, FEITO, "ok")
    mensagens = [
        {"remetente": "rh@acmetech.com", "assunto": "Próxima etapa", "quando": "2026-10-04T10:00"},
        {"remetente": "noreply@gupy.io", "assunto": "Recebemos sua candidatura", "quando": "2026-10-04T11:00"},
    ]

    acompanhamento.atualizar(tmp_path, registro=registro, mensagens=mensagens, quando=datetime(2026, 10, 4, 12, 0))

    texto = (tmp_path / acompanhamento.CAMINHO_DAS_CANDIDATURAS).read_text(encoding="utf-8")
    andamento = texto.split("## Em andamento (2)")[1].split("## Preparadas")[0]
    assert "Dev Web" in andamento and "entrevista" in andamento and "2026-10-04 Próxima etapa" in andamento
    assert "Game Dev" in andamento and "| Whis |" in andamento
    assert "Recebemos sua candidatura" not in andamento, "o domínio da Gupy não identifica a empresa"
    assert "## Encerradas (1)" in texto and "Landing" in texto.split("## Encerradas")[1]


# -- lembrete -------------------------------------------------------------------------------------


def test_a_proxima_virada_anda_de_semana_em_semana():
    agora = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

    assert proxima_virada(VIRADA, agora) == datetime(2026, 10, 26, 7, 0, tzinfo=UTC)
    assert proxima_virada(datetime(2026, 12, 7, 7, 0, tzinfo=UTC), agora) == datetime(2026, 10, 26, 7, 0, tzinfo=UTC)


def test_so_lembra_nas_30_horas_antes():
    assert texto_do_lembrete(VIRADA, VIRADA - timedelta(hours=40)) is None
    texto = texto_do_lembrete(VIRADA, VIRADA - timedelta(hours=20))
    assert texto is not None and "Solte a caçada" in texto and f"às {VIRADA.astimezone():%H:%M}" in texto


def test_o_lembrete_sai_uma_vez_por_virada(tmp_path: Path):
    assert not ja_lembrado(tmp_path, VIRADA)
    marcar_lembrado(tmp_path, VIRADA)
    assert ja_lembrado(tmp_path, VIRADA) and not ja_lembrado(tmp_path, VIRADA + timedelta(days=7))


def test_whis_lembrete_agendado_avisa_uma_vez(arquivo_de_configuracao: Path, tmp_path: Path, monkeypatch, toasts):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    pasta = corrida.pasta_da_cacada()
    corrida.guardar_virada(pasta, datetime.now(UTC) + timedelta(hours=10) - timedelta(days=14))

    assert main(["lembrete", "--agendada"]) == 0
    assert main(["lembrete", "--agendada"]) == 0

    assert [titulo for titulo, _texto, _botao in toasts] == ["Véspera da virada do plano"]


def test_windows_hunt_agenda_o_lembrete(tmp_path: Path):
    comandos: list[list[str]] = []

    def executar(comando):
        comandos.append(comando)
        return subprocess.CompletedProcess(comando, 0, "", "")

    configuracao = Configuracao(vault=tmp_path, origem=tmp_path / "config.toml", cacada_hora_do_lembrete="21:30")
    nome = automacao.agendar_lembrete(configuracao, executar=executar)

    texto = " ".join(comandos[-1])
    assert nome == "Whis-Lembrete-Cacada" and "lembrete --agendada" in texto and "Daily=21:30" in texto


@pytest.fixture(autouse=True)
def _sem_portas_reais(monkeypatch):
    monkeypatch.setattr("whis.__main__.montar_leitura_da_caixa", lambda _c: None)
    yield


def test_whis_candidaturas_regenera_a_nota(arquivo_de_configuracao: Path, caminho_do_vault: Path, tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    assert main(["candidaturas"]) == 0
    assert (caminho_do_vault / acompanhamento.CAMINHO_DAS_CANDIDATURAS).is_file()
    assert "Candidaturas: cacada/candidaturas.md" in capsys.readouterr().out

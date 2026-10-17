"""A vigia de freelas: o projeto novo do nicho vira toast nas primeiras horas, sem Claude."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from whis import automacao
from whis.__main__ import main
from whis.configuracao import Configuracao
from whis.oportunidades import FREELA, Oportunidade
from whis.vigia_de_freelas import vigiar

AGORA = datetime(2026, 10, 17, 14, 0, tzinfo=timezone(timedelta(hours=-3)))


def _freela(titulo: str, link: str, *, horas: float = 1, faixa: str = "R$ 300 - 600", detalhes: str = "Propostas: 3") -> Oportunidade:
    return Oportunidade.nova(
        tipo=FREELA, fonte="99Freelas", titulo=titulo, link=link, faixa=faixa,
        publicada=AGORA - timedelta(hours=horas), descricao="Loja Shopify com tema Dawn.", detalhes=detalhes,
    )


TEMA = _freela("Ajuste no tema Shopify", "https://www.99freelas.com.br/project/tema-1")
CHECKOUT = _freela("Checkout Shopify com frete", "https://www.freelancer.com/projects/shopify/checkout-2", faixa="USD 100 - 250")
VELHO = _freela("Seção nova no tema Shopify", "https://www.99freelas.com.br/project/secao-3", horas=40)
REACT = Oportunidade.nova(
    tipo=FREELA, fonte="99Freelas", titulo="Painel em React", link="https://www.99freelas.com.br/project/painel-4",
    publicada=AGORA - timedelta(hours=1), descricao="Dashboard com gráficos.",
)


def _rodar(estado: Path, oportunidades, nicho: str = "shopify"):
    avisos: list[tuple[str, str, tuple[str, str] | None]] = []

    def avisar(titulo, texto, *, botao=None):
        avisos.append((titulo, texto, botao))
        return True

    rodada = vigiar(nicho, ler=lambda _nicho: list(oportunidades), estado=estado, avisar=avisar, agora=AGORA)
    return rodada, avisos


def test_a_primeira_rodada_so_guarda_o_que_ja_esta_la(tmp_path: Path):
    estado = tmp_path / "vigia.json"

    rodada, avisos = _rodar(estado, [TEMA, REACT])

    assert avisos == [] and rodada.avisados == () and rodada.guardados == 1
    assert TEMA.link in json.loads(estado.read_text(encoding="utf-8"))


def test_avisa_so_o_projeto_novo_e_recente_do_nicho_com_o_link(tmp_path: Path):
    estado = tmp_path / "vigia.json"
    _rodar(estado, [TEMA])

    rodada, avisos = _rodar(estado, [TEMA, CHECKOUT, VELHO, REACT])

    assert [o.link for o in rodada.avisados] == [CHECKOUT.link]
    [(titulo, texto, botao)] = avisos
    assert titulo == "Freela de Shopify novo: Checkout Shopify com frete"
    assert "USD 100 - 250" in texto and "Propostas: 3" in texto and "Freelancer.com" in texto
    assert botao == ("Abrir o projeto", CHECKOUT.link)
    _, de_novo = _rodar(estado, [TEMA, CHECKOUT])
    assert de_novo == []


def test_o_exclusivo_da_99freelas_diz_quando_abre(tmp_path: Path):
    estado = tmp_path / "vigia.json"
    estado.write_text("{}", encoding="utf-8")
    exclusivo = _freela(
        "Loja Shopify do zero", "https://www.99freelas.com.br/project/loja-5",
        detalhes="Projeto exclusivo para assinantes da 99Freelas: abre para quem não assina em 18/10 às 09:10 | Propostas: 0",
    )

    _, [(_, texto, _)] = _rodar(estado, [exclusivo])

    assert "abre para quem não assina em 18/10 às 09:10" in texto


def test_muitos_novos_viram_poucos_toasts(tmp_path: Path):
    estado = tmp_path / "vigia.json"
    estado.write_text("{}", encoding="utf-8")
    novos = [_freela(f"Tema Shopify {n}", f"https://www.99freelas.com.br/project/tema-{n}0") for n in range(6)]

    rodada, avisos = _rodar(estado, novos)

    assert len(rodada.avisados) == 6
    assert len(avisos) == 4
    assert avisos[-1][0] == "Mais 3 freelas de Shopify novos"
    assert "Tema Shopify 3" in avisos[-1][1] and "Tema Shopify 5" in avisos[-1][1]


def test_sem_nicho_a_vigia_nao_roda(arquivo_de_configuracao: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["vigia-freelas"]) != 0
    assert "[cacada].nicho_freela" in capsys.readouterr().out


def test_no_modo_de_teste_avisa_um_projeto_falso(
    arquivo_de_configuracao: Path, toasts, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    assert main(["vigia-freelas", "--fakes"]) == 0

    [(titulo, texto, botao)] = toasts
    assert titulo.startswith("Freela de Shopify novo:") and "(teste)" in titulo
    assert botao is not None and botao[1].startswith("https://")
    assert not (tmp_path / "local" / "whis" / "cacada" / "vigia-de-freelas.json").exists()


def test_whis_windows_liga_e_desliga_a_vigia_de_freelas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    chamadas: list[str] = []
    monkeypatch.setattr(automacao, "instalar_inicializacao", lambda: Path("Whis.lnk"))
    monkeypatch.setattr(automacao, "remover_inicializacao", lambda: None)
    monkeypatch.setattr(automacao, "agendar_vigia_de_freelas", lambda configuracao: chamadas.append("agendar") or "Whis-Vigia-Freelas")
    monkeypatch.setattr(automacao, "desagendar_vigia_de_freelas", lambda: chamadas.append("desagendar") or True)
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "{tmp_path.as_posix()}"\n[cacada]\nnicho_freela = "shopify"\n', encoding="utf-8")

    assert main(["windows", "--vigia-freelas", "--config", str(arquivo)]) == 0
    assert "Vigia de freelas agendada como 'Whis-Vigia-Freelas': todo dia às 08:00, 11:00" in capsys.readouterr().out
    assert main(["windows", "--remover", "--vigia-freelas"]) == 0
    assert "Tarefa 'Whis-Vigia-Freelas' removida do Agendador." in capsys.readouterr().out
    assert chamadas == ["agendar", "desagendar"]


def test_windows_vigia_freelas_agenda_a_tarefa_nos_horarios(tmp_path: Path):
    comandos: list[list[str]] = []

    def executar(comando):
        comandos.append(comando)
        return subprocess.CompletedProcess(comando, 0, "", "")

    configuracao = Configuracao(
        vault=tmp_path, origem=tmp_path / "config.toml", cacada_horarios_da_vigia_de_freelas=("08:00", "12:30")
    )
    nome = automacao.agendar_vigia_de_freelas(configuracao, executar=executar)

    texto = " ".join(comandos[-1])
    assert nome == "Whis-Vigia-Freelas" != automacao.NOME_DA_TAREFA_DO_VIGIA
    assert "vigia-freelas --agendada" in texto and "Daily=08:00,Daily=12:30" in texto

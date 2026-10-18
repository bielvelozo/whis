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


def _rodar(estado: Path, oportunidades, nicho: str = "shopify", celular: list[str] | None = None):
    avisos: list[tuple[str, str, tuple[str, str] | None]] = []

    def avisar(titulo, texto, *, botao=None):
        avisos.append((titulo, texto, botao))
        return True

    no_celular = (lambda texto: celular.append(texto) or True) if celular is not None else None
    rodada = vigiar(nicho, ler=lambda _nicho: list(oportunidades), estado=estado, avisar=avisar, celular=no_celular, agora=AGORA)
    return rodada, avisos


def test_o_projeto_novo_do_freelancer_vai_tambem_para_o_celular_e_o_da_99freelas_nao(tmp_path: Path):
    estado = tmp_path / "vigia.json"
    estado.write_text("{}", encoding="utf-8")
    celular: list[str] = []

    _, avisos = _rodar(estado, [TEMA, CHECKOUT], celular=celular)

    assert len(avisos) == 2
    [mensagem] = celular
    assert mensagem.splitlines()[0] == "Freela de Shopify novo no Freelancer.com"
    assert "Checkout Shopify com frete" in mensagem and "USD 100 - 250" in mensagem and "Propostas: 3" in mensagem
    assert mensagem.splitlines()[-1] == CHECKOUT.link


def test_no_celular_nao_ha_corte_de_poucos_por_rodada(tmp_path: Path):
    estado = tmp_path / "vigia.json"
    estado.write_text("{}", encoding="utf-8")
    novos = [
        _freela(f"Tema Shopify {n}", f"https://www.freelancer.com/projects/shopify/tema-{n}", faixa="USD 30 - 250") for n in range(5)
    ]
    celular: list[str] = []

    _rodar(estado, novos, celular=celular)

    assert len(celular) == 5


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
    arquivo_de_configuracao: Path, toasts, mensagens_no_celular, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    assert main(["vigia-freelas", "--fakes"]) == 0

    [ensaio] = mensagens_no_celular
    assert ensaio.startswith("Ensaio: esta proposta sairia agora na 99Freelas") and "(teste)" in ensaio

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
    assert "Vigia de freelas agendada como 'Whis-Vigia-Freelas': todo dia às 07:00, 08:00, 09:00" in capsys.readouterr().out
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


def _config_da_vigia(tmp_path: Path, extra: str = "") -> Path:
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "{(tmp_path / "vault").as_posix()}"\n[cacada]\nnicho_freela = "shopify"\n{extra}', encoding="utf-8")
    return arquivo


def test_com_o_envio_desligado_a_vigia_nao_chama_a_proposta_automatica(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from whis import propostas_auto, vigia_de_freelas

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho: (TEMA,))
    monkeypatch.setattr(propostas_auto, "rodar", lambda *_a, **_k: pytest.fail("a proposta automática rodou desligada"))

    assert main(["vigia-freelas", "--config", str(_config_da_vigia(tmp_path))]) == 0


def test_no_ensaio_a_vigia_passa_a_mesma_leitura_para_a_proposta_automatica(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    from whis import propostas_auto, vigia_de_freelas

    chamadas: list[dict] = []
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho: (TEMA, REACT))
    monkeypatch.setattr(propostas_auto, "rodar", lambda lidas, **opcoes: chamadas.append({"lidas": lidas, **opcoes}) or propostas_auto.Rodada())

    assert main(["vigia-freelas", "--config", str(_config_da_vigia(tmp_path, 'propostas_auto = "ensaio"\n'))]) == 0

    [chamada] = chamadas
    assert chamada["lidas"] == (TEMA, REACT) and chamada["modo"] == "ensaio"
    assert "nenhum projeto novo da 99Freelas passou nas travas" in capsys.readouterr().out


def test_falha_da_proposta_automatica_nao_derruba_a_vigia(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from whis import propostas_auto, vigia_de_freelas

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho: (TEMA,))

    def quebrar(*_a, **_k):
        raise RuntimeError("quebrou")

    monkeypatch.setattr(propostas_auto, "rodar", quebrar)

    assert main(["vigia-freelas", "--config", str(_config_da_vigia(tmp_path, 'propostas_auto = "ensaio"\n'))]) == 3


def test_com_o_toque_do_celular_no_chrome_a_proposta_fica_para_a_proxima_hora(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    from whis import propostas_auto, vigia_de_freelas
    from whis.corrida import pasta_da_cacada
    from whis.instancia import Trava

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho: (TEMA,))
    monkeypatch.setattr(propostas_auto, "rodar", lambda *_a, **_k: pytest.fail("a proposta automática rodou com o Chrome ocupado"))
    toque = Trava(pasta_da_cacada() / propostas_auto.NOME_DA_TRAVA).adquirir()
    try:
        assert main(["vigia-freelas", "--config", str(_config_da_vigia(tmp_path, 'propostas_auto = "ligado"\n'))]) == 0
    finally:
        toque.liberar()

    assert "o envio pelo celular está usando o Chrome da caçada" in capsys.readouterr().out

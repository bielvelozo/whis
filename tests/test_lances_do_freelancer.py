"""Os lances do Freelancer.com: a vigia olha uma vez por dia e avisa no celular quando eles voltam."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from whis import lances_do_freelancer
from whis.navegador_logado import (
    FREELANCER,
    PAGINAS_DE_CONFERENCIA,
    PERFIL_EM_USO,
    SemNavegador,
    SessaoLogada,
    ler_lances_do_freelancer,
    motivo_do_chrome,
)

AGORA = datetime(2026, 10, 18, 16, 0, tzinfo=timezone(timedelta(hours=-3)))
PROJETO = "https://www.freelancer.com/projects/shopify/Shopify-Single-Product-Site-40774598"
LOGADO = "<app-logged-in-shell></app-logged-in-shell>"


def _pagina(restantes: int, total: int = 6) -> str:
    return (
        f'{LOGADO}<div class="ReplenishmentData"><p class="RemainingBids mr-xxsmall">{restantes}/{total} restantes</p></div>'
        f'<div class="ReplenishmentData"><span><span class="font-medium"> {restantes} ofertas </span> restantes de {total} </span></div>'
    )


class SessaoFake(SessaoLogada):
    def __init__(self, paginas: dict[str, str], *, motivo: str = "") -> None:
        super().__init__()
        self.paginas = paginas
        self.motivo = motivo
        self.visitadas: list[str] = []

    def html(self, url: str) -> str:
        self.visitadas.append(url)
        if url not in self.paginas:
            raise SemNavegador(f"fora do fake: {url}")
        return self.paginas[url]


def _sessao(restantes: int = 0, **opcoes) -> SessaoFake:
    return SessaoFake({PAGINAS_DE_CONFERENCIA[FREELANCER]: LOGADO, PROJETO: _pagina(restantes)}, **opcoes)


def _conferir(tmp_path: Path, sessao: SessaoFake, *, agora: datetime = AGORA, projeto: str = PROJETO):
    celular: list[str] = []
    lances = lances_do_freelancer.conferir(
        abrir_sessao=lambda: sessao,
        estado=tmp_path / "lances.json",
        celular=lambda texto, **_opcoes: celular.append(texto) or True,
        projeto=projeto,
        pasta_do_formulario=tmp_path / "formulario",
        agora=agora,
    )
    return lances, celular


def test_le_os_lances_que_sobram_na_pagina_do_projeto():
    assert ler_lances_do_freelancer(_pagina(0)) == (0, 6)
    assert ler_lances_do_freelancer(_pagina(4)) == (4, 6)
    assert ler_lances_do_freelancer('<p class="RemainingBids">3/6 remaining</p>') == (3, 6)
    assert ler_lances_do_freelancer(LOGADO + "<p>nada aqui</p>") is None


def test_sem_lances_guarda_e_nao_avisa(tmp_path: Path):
    lances, celular = _conferir(tmp_path, _sessao(0))

    assert lances == (0, 6) and celular == []
    assert json.loads((tmp_path / "lances.json").read_text(encoding="utf-8"))["restantes"] == 0


def test_sem_lances_vale_so_com_a_contagem_zerada_de_ate_tres_dias(tmp_path: Path):
    estado = tmp_path / "lances.json"

    assert lances_do_freelancer.sem_lances(estado, AGORA) is False
    _conferir(tmp_path, _sessao(0))
    assert lances_do_freelancer.sem_lances(estado, AGORA + timedelta(days=2)) is True
    assert lances_do_freelancer.sem_lances(estado, AGORA + timedelta(days=4)) is False
    _conferir(tmp_path, _sessao(3), agora=AGORA + timedelta(days=1))
    assert lances_do_freelancer.sem_lances(estado, AGORA + timedelta(days=1)) is False


def test_olha_uma_vez_por_dia(tmp_path: Path):
    _conferir(tmp_path, _sessao(0))
    sessao = _sessao(2)

    de_novo, celular = _conferir(tmp_path, sessao, agora=AGORA + timedelta(hours=3))

    assert de_novo is None and celular == [] and sessao.visitadas == []


def test_quando_os_lances_voltam_avisa_e_guarda_o_formulario(tmp_path: Path):
    _conferir(tmp_path, _sessao(0))

    lances, celular = _conferir(tmp_path, _sessao(2), agora=AGORA + timedelta(days=1))
    _, no_outro_dia = _conferir(tmp_path, _sessao(1), agora=AGORA + timedelta(days=2))

    assert lances == (2, 6)
    [aviso] = celular
    assert aviso.startswith("Seus lances do Freelancer.com voltaram: 2 de 6.")
    assert (tmp_path / "formulario" / "projeto.html").read_text(encoding="utf-8") == _pagina(2)
    assert no_outro_dia == []


def test_deslogado_avisa_uma_vez_por_dia_para_entrar_de_novo(tmp_path: Path):
    sessao = SessaoFake({PAGINAS_DE_CONFERENCIA[FREELANCER]: "<a>Fazer Login</a>"})

    lances, celular = _conferir(tmp_path, sessao)

    assert lances is None
    [aviso] = celular
    assert "saiu do Freelancer.com" in aviso and "Remember me" in aviso


def test_chrome_que_nao_abre_tenta_na_proxima_rodada_sem_avisar(tmp_path: Path):
    lances, celular = _conferir(tmp_path, _sessao(0, motivo=PERFIL_EM_USO))
    depois, _ = _conferir(tmp_path, _sessao(0), agora=AGORA + timedelta(hours=1))

    assert lances is None and celular == [] and depois == (0, 6)


def test_sem_projeto_do_freelancer_na_leitura_nao_abre_o_chrome(tmp_path: Path):
    sessao = _sessao(3)

    lances, celular = _conferir(tmp_path, sessao, projeto="")

    assert lances is None and celular == [] and sessao.visitadas == []


def test_chrome_fechado_porque_o_perfil_estava_aberto_a_mao_e_perfil_em_uso():
    assert motivo_do_chrome("BrowserType.launch_persistent_context: Target page, context or browser has been closed") == PERFIL_EM_USO



def _config(tmp_path: Path) -> Path:
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "{(tmp_path / "vault").as_posix()}"\n[cacada]\nnicho_freela = "shopify"\n', encoding="utf-8")
    return arquivo


def test_a_vigia_olha_os_lances_num_projeto_do_freelancer_que_ela_leu(tmp_path: Path, monkeypatch):
    from whis import vigia_de_freelas
    from whis.__main__ import main
    from whis.oportunidades import FREELA, Oportunidade

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    da_99 = Oportunidade.nova(tipo=FREELA, fonte="99Freelas", titulo="Loja", link="https://www.99freelas.com.br/project/loja-1")
    do_freelancer = Oportunidade.nova(tipo=FREELA, fonte="Freelancer.com", titulo="Shopify", link=PROJETO)
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho: (da_99, do_freelancer))
    chamadas: list[dict] = []
    monkeypatch.setattr(lances_do_freelancer, "conferir", lambda **opcoes: chamadas.append(opcoes) or (1, 6))

    assert main(["vigia-freelas", "--config", str(_config(tmp_path))]) == 0

    [opcoes] = chamadas
    assert opcoes["projeto"] == PROJETO and opcoes["estado"] == lances_do_freelancer.caminho_do_estado()


def test_com_zero_lances_a_vigia_nao_manda_o_projeto_do_freelancer_ao_celular(tmp_path: Path, monkeypatch):
    from whis import celular, vigia_de_freelas
    from whis.__main__ import main
    from whis.corrida import pasta_da_cacada
    from whis.oportunidades import FREELA, Oportunidade

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    agora = datetime.now().astimezone()
    da_99 = Oportunidade.nova(tipo=FREELA, fonte="99Freelas", titulo="Tema Shopify", link="https://www.99freelas.com.br/project/tema-1", publicada=agora)
    do_freelancer = Oportunidade.nova(tipo=FREELA, fonte="Freelancer.com", titulo="Shopify theme", link=PROJETO, publicada=agora)
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho: (da_99, do_freelancer))
    monkeypatch.setattr(lances_do_freelancer, "conferir", lambda **_opcoes: None)
    mensagens: list[str] = []
    monkeypatch.setattr(celular, "avisar", lambda _configuracao, texto, **_opcoes: mensagens.append(texto) or True)
    pasta = pasta_da_cacada()
    pasta.mkdir(parents=True)
    (pasta / "vigia-de-freelas.json").write_text("{}", encoding="utf-8")
    (pasta / lances_do_freelancer.NOME_DO_ESTADO).write_text(
        json.dumps({"dia": agora.date().isoformat(), "restantes": 0, "total": 6, "visto": agora.isoformat(timespec="minutes")}),
        encoding="utf-8",
    )
    config = _config(tmp_path)
    config.write_text(config.read_text(encoding="utf-8") + "agencias_por_dia = 0\n", encoding="utf-8")

    assert main(["vigia-freelas", "--config", str(config)]) == 0

    assert not any(PROJETO in mensagem for mensagem in mensagens)


def test_sem_projeto_do_freelancer_a_vigia_nem_olha_os_lances(tmp_path: Path, monkeypatch):
    from whis import vigia_de_freelas
    from whis.__main__ import main

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho: ())
    monkeypatch.setattr(lances_do_freelancer, "conferir", lambda **_opcoes: (_ for _ in ()).throw(AssertionError("olhou os lances")))

    assert main(["vigia-freelas", "--config", str(_config(tmp_path))]) == 0

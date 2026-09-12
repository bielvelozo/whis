"""A palheta: registro, despacho e o contrato "dispara e some" — sem janela e sem Tk.

Cada comando roda pela costura de verdade contra um vault temporário, com as
portas fake (`DailyFake`, `BuscaFake`) e o thread de trabalho síncrono. O que
se prova é o que sobra: a nota no vault, o fio em `conversas.json`, o toast
montado (com e sem botão) e que nada escapa da zona `respostas/`. A janela
entra por dublê; o Tk de verdade tem um teste próprio no fim, que pula onde
não há tela.
"""

from __future__ import annotations

import json
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fixtures.leitura import arquivos_do_vault, corpo, ler_frontmatter
from whis import __main__ as cli
from whis import avisos
from whis import bandeja as _bandeja
from whis import palheta as modulo
from whis import vault as _vault
from whis.bandeja import Bandeja
from whis.busca import Citacao, Resposta
from whis.busca_claude import PROMPT_DA_BUSCA
from whis.coletor import Coletor
from whis.configuracao import MODELO_DE_CONFIGURACAO, ConfiguracaoInvalida, carregar
from whis.conversa import NOME_DO_ARQUIVO
from whis.fakes import (
    DAILY_PADRAO,
    RESPOSTA_PADRAO,
    BuscaFake,
    DailyFake,
    ResumoFake,
    STTFake,
    fontes_de_exemplo_da_daily,
)
from whis.palheta import (
    Comando,
    ComandoDesconhecido,
    Palheta,
    Resultado,
    comandos_padrao,
    interpretar,
)
from test_bandeja import IconeDublê
from test_coletor import GravadorDublê

FUSO = timezone(timedelta(hours=-3))
MOMENTO = datetime(2026, 9, 12, 14, 3, tzinfo=FUSO)
PERGUNTA = "o que ficou decidido sobre a retenção de 180 dias?"
NOTA_DA_RESPOSTA = "respostas/2026-09-12-1403-o-que-ficou-decidido-sobre-a-retencao-de-180-dias.md"


class AvisoEspiao:
    def __init__(self) -> None:
        self.avisos: list[tuple[str, str, tuple[str, str] | None]] = []

    def __call__(self, titulo: str, texto: str, *, botao=None, executar=None) -> bool:
        self.avisos.append((titulo, texto, botao))
        return True

    def ultimo(self) -> tuple[str, str, tuple[str, str] | None]:
        assert self.avisos, "nenhum toast saiu"
        return self.avisos[-1]


class JanelaDublê:
    """A porta da janela sem Tk: guarda se está visível e o que foi enviado."""

    def __init__(self) -> None:
        self.visivel = False
        self._callback = None

    def mostrar(self) -> None:
        self.visivel = True

    def esconder(self) -> None:
        self.visivel = False

    def ao_enviar(self, callback) -> None:
        self._callback = callback

    def digitar_e_enter(self, texto: str) -> None:
        """O que a janela de verdade faz no Enter: some e só então despacha."""
        self.esconder()
        self._callback(texto)

    def esc(self) -> None:
        self.esconder()


@pytest.fixture
def aviso() -> AvisoEspiao:
    return AvisoEspiao()


@pytest.fixture
def montar(configuracao_do_diario, aviso: AvisoEspiao):
    """Uma palheta com os comandos de verdade sobre as portas fake, síncrona."""

    def construir(*, busca=None, roteiro=None, lancados=None, abrir_painel=None, extras=()):
        configuracao = configuracao_do_diario()
        comandos = comandos_padrao(
            fontes_da_daily=lambda _atual: fontes_de_exemplo_da_daily(),
            roteiro_da_daily=lambda _atual: roteiro or DailyFake(),
            busca=lambda _atual: busca or BuscaFake(),
            lancar=(lancados if lancados is not None else []).append,
            relogio=lambda: MOMENTO,
        )
        return Palheta(
            (*comandos, *extras),
            configuracao,
            avisar=aviso,
            iniciar_thread=lambda alvo: alvo(),
            abrir_painel=abrir_painel,
        )

    return construir


# -- interpretar --------------------------------------------------------------


REGISTRO = (
    Comando("daily", "gera", lambda a, c: None),
    Comando("anotar", "anota", lambda a, c: None, parametro="texto"),
    Comando("ajuda", "lista", lambda a, c: None),
)


def test_interpretar_separa_o_comando_do_argumento():
    comando, argumento = interpretar("anotar puxar a retenção  de 180 dias ", REGISTRO)

    assert comando.nome == "anotar"
    assert argumento == "puxar a retenção  de 180 dias"


def test_interpretar_nao_diferencia_maiusculas():
    assert interpretar("DAILY", REGISTRO)[0].nome == "daily"
    assert interpretar("  Anotar x", REGISTRO)[0].nome == "anotar"


def test_texto_vazio_e_ajuda():
    comando, argumento = interpretar("   ", REGISTRO)

    assert comando.nome == "ajuda" and argumento == ""


def test_comando_desconhecido_lista_os_que_existem():
    with pytest.raises(ComandoDesconhecido) as erro:
        interpretar("voar alto", REGISTRO)

    mensagem = str(erro.value)
    assert "'voar'" in mensagem
    assert "daily" in mensagem and "anotar <texto>" in mensagem and "ajuda" in mensagem


# -- daily ----------------------------------------------------------------------


def test_daily_pela_palheta_gera_a_nota_viva_e_avisa_com_o_botao(montar, caminho_do_vault: Path, aviso):
    palheta = montar()

    assert palheta.despachar("daily") is True

    assert ler_frontmatter(caminho_do_vault / "daily" / "atual.md")["tipo"] == "daily-atual"
    assert f"- {DAILY_PADRAO.fiz[0].texto}" in (caminho_do_vault / "daily" / "atual.md").read_text(encoding="utf-8")
    titulo, texto, botao = aviso.ultimo()
    assert titulo == "A daily está pronta"
    assert "itens novos" in texto
    assert botao == ("Abrir no Obsidian", f"obsidian://open?vault={caminho_do_vault.name}&file=daily%2Fatual")


def test_o_toast_da_daily_e_o_mesmo_do_subcomando(montar, aviso, monkeypatch, capsys):
    """Um lugar só monta o toast: o subcomando e a palheta dizem a mesma coisa."""
    palheta = montar()
    palheta.despachar("daily")
    da_palheta = aviso.ultimo()
    monkeypatch.setattr(avisos, "avisar", aviso)

    cli.main(["daily", "--fakes"])

    do_subcomando = aviso.ultimo()
    assert do_subcomando[0] == da_palheta[0] == cli.TITULO_DO_TOAST_DA_DAILY
    assert do_subcomando[2] == da_palheta[2]


def test_daily_que_nao_nasce_avisa_sem_botao(montar, aviso):
    palheta = montar()
    palheta.comandos = tuple(
        Comando(c.nome, c.ajuda, (lambda a, cfg: modulo.resultado_da_daily(_vazio())) if c.nome == "daily" else c.rodar)
        for c in palheta.comandos
    )

    palheta.despachar("daily")

    titulo, texto, botao = aviso.ultimo()
    assert titulo == "A daily não nasceu"
    assert "Nada aconteceu" in texto
    assert botao is None


def _vazio():
    from whis.daily import JanelaDaDaily, ResultadoDaDaily

    return ResultadoDaDaily(
        janela=JanelaDaDaily(data=MOMENTO.date(), desde=MOMENTO, ate=MOMENTO),
        nota=None, eventos=(), excluidos=0, fontes_lidas=(), fontes_com_falha=(), reunioes=(),
        roteiro=None, nota_viva=None, secoes=(), mudancas=None, vazio=True,
    )


# -- anotar -----------------------------------------------------------------


def test_anotar_escreve_em_falar_pelo_mesmo_caminho_do_subcomando(montar, caminho_do_vault: Path, aviso):
    palheta = montar()

    palheta.despachar("anotar puxar a retenção de 180 dias")

    nota = (caminho_do_vault / "daily" / "atual.md").read_text(encoding="utf-8")
    assert nota.endswith("## Falar\n- puxar a retenção de 180 dias\n")
    titulo, texto, botao = aviso.ultimo()
    assert titulo == "Anotado em Falar"
    assert texto == "puxar a retenção de 180 dias"
    assert botao[1].endswith("&file=daily%2Fatual")


def test_anotar_sem_texto_pede_o_texto_e_nao_escreve(montar, caminho_do_vault: Path, aviso):
    palheta = montar()

    palheta.despachar("anotar")

    assert not (caminho_do_vault / "daily" / "atual.md").exists()
    titulo, _texto, botao = aviso.ultimo()
    assert titulo == "Anotar o quê?" and botao is None


# -- perguntar --------------------------------------------------------------


def test_perguntar_vira_nota_em_respostas_com_as_fontes_recolhidas(montar, caminho_do_vault: Path, aviso):
    palheta = montar()

    palheta.despachar(f"perguntar {PERGUNTA}")

    nota = caminho_do_vault / NOTA_DA_RESPOSTA
    assert nota.is_file()
    frontmatter = ler_frontmatter(nota)
    assert frontmatter["tipo"] == "resposta"
    assert frontmatter["pergunta"] == PERGUNTA
    assert "data" not in frontmatter, "campo `data` vira link da Daily notes do Obsidian"
    texto = corpo(nota).lstrip("\n")
    assert texto.startswith(f"# {PERGUNTA}\n\n{RESPOSTA_PADRAO.texto}\n")
    assert "> [!info]- Fontes\n> - `reunioes/2026-09-03-1403-reuniao.md` — retenção de 180 dias\n" in texto
    assert texto.index("[!info]- Fontes") > texto.index(RESPOSTA_PADRAO.texto)


def test_o_toast_da_pergunta_traz_o_comeco_da_resposta_e_o_botao_da_nota(montar, caminho_do_vault: Path, aviso):
    palheta = montar()

    palheta.despachar(f"perguntar {PERGUNTA}")

    titulo, texto, botao = aviso.ultimo()
    assert titulo == "Whis"
    assert texto == RESPOSTA_PADRAO.texto
    assert botao == (
        "Abrir no Obsidian",
        f"obsidian://open?vault={caminho_do_vault.name}&file="
        "respostas%2F2026-09-12-1403-o-que-ficou-decidido-sobre-a-retencao-de-180-dias",
    )


def test_resposta_longa_e_encurtada_no_toast_mas_inteira_na_nota(montar, caminho_do_vault: Path, aviso):
    longa = "Frase. " * 100
    palheta = montar(busca=BuscaFake(Resposta(texto=longa, citacoes=(Citacao("daily/x.md"),))))

    palheta.despachar("perguntar conta tudo")

    _titulo, texto, _botao = aviso.ultimo()
    assert len(texto) <= modulo.LIMITE_DO_TEXTO_DO_TOAST and texto.endswith("…")
    assert longa.strip() in corpo(caminho_do_vault / "respostas" / "2026-09-12-1403-conta-tudo.md")


def test_nao_achou_tambem_vira_nota_dizendo_que_nao_achou(montar, caminho_do_vault: Path, aviso):
    palheta = montar(busca=BuscaFake(Resposta(texto="", achou=False)))

    palheta.despachar("perguntar cadê o link coringa")

    nota = caminho_do_vault / "respostas" / "2026-09-12-1403-cade-o-link-coringa.md"
    assert ler_frontmatter(nota)["achou"] == "false"
    assert "Não achei nada no vault" in corpo(nota)
    assert "> [!info]- Fontes\n> _(nenhuma" in corpo(nota)
    titulo, _texto, botao = aviso.ultimo()
    assert titulo == "Não achei"
    assert botao is not None


def test_o_fio_da_palheta_guarda_a_pergunta_e_a_resposta(montar, caminho_do_vault: Path):
    busca = BuscaFake()
    palheta = montar(busca=busca)
    palheta.despachar(f"perguntar {PERGUNTA}")

    palheta.despachar("perguntar e quem levantou isso?")

    arquivo = palheta.configuracao.origem.parent / NOME_DO_ARQUIVO
    fios = json.loads(arquivo.read_text(encoding="utf-8"))["conversas"]
    assert [turno["texto"] for turno in fios["palheta"]] == [
        PERGUNTA, RESPOSTA_PADRAO.texto, "e quem levantou isso?", RESPOSTA_PADRAO.texto,
    ]
    assert [turno.texto for turno in busca.historico_recebido] == [PERGUNTA, RESPOSTA_PADRAO.texto]
    assert not list(Path(caminho_do_vault).rglob(NOME_DO_ARQUIVO))


def test_perguntar_so_escreve_em_respostas(montar, caminho_do_vault: Path):
    palheta = montar()
    _vault.preparar(caminho_do_vault)
    antes = arquivos_do_vault(caminho_do_vault)

    palheta.despachar(f"perguntar {PERGUNTA}")

    assert arquivos_do_vault(caminho_do_vault) - antes == {NOTA_DA_RESPOSTA}


def test_a_zona_das_respostas_nao_alcanca_nenhuma_outra_pasta(caminho_do_vault: Path):
    raiz = _vault.preparar(caminho_do_vault)
    assert (raiz / "respostas").is_dir()

    for fora in ("notas/x.md", "daily/atual.md", "respostas/../notas/x.md", "diario/x.md"):
        with pytest.raises(_vault.ForaDaZonaDePropriedade):
            _vault.escrever(raiz, fora, "x", zonas=_vault.ZONAS_DAS_RESPOSTAS)
    assert _vault.escrever(raiz, "respostas/ok.md", "x", zonas=_vault.ZONAS_DAS_RESPOSTAS).is_file()


def test_perguntar_sem_pergunta_nao_chama_a_busca(montar, aviso):
    busca = BuscaFake()
    palheta = montar(busca=busca)

    palheta.despachar("perguntar")

    assert busca.perguntas_recebidas == []
    assert aviso.ultimo()[0] == "Perguntar o quê?"


# -- abrir, configurar, ajuda ---------------------------------------------------


def test_abrir_lanca_a_uri_da_nota_viva_sem_toast(montar, caminho_do_vault: Path, aviso):
    lancados: list[str] = []
    palheta = montar(lancados=lancados)

    palheta.despachar("abrir")

    assert lancados == [f"obsidian://open?vault={caminho_do_vault.name}&file=daily%2Fatual"]
    assert aviso.avisos == []


def test_configurar_abre_o_painel_injetado_sem_toast(montar, aviso):
    aberturas: list[str] = []
    palheta = montar(abrir_painel=lambda: aberturas.append("painel"))

    palheta.despachar("configurar")

    assert aberturas == ["painel"]
    assert aviso.avisos == []


def test_o_painel_e_preenchido_depois_por_quem_hospeda(montar, aviso):
    palheta = montar()
    palheta.despachar("configurar")
    assert aviso.ultimo()[0] == "O comando falhou"
    aberturas: list[str] = []

    palheta.abrir_painel = lambda: aberturas.append("painel")
    palheta.despachar("configurar")

    assert aberturas == ["painel"]


def test_ajuda_lista_uma_linha_por_comando(montar, aviso):
    palheta = montar()

    palheta.despachar("ajuda")

    titulo, texto, botao = aviso.ultimo()
    assert titulo == "Comandos da palheta" and botao is None
    linhas = texto.splitlines()
    assert [linha.split(" — ")[0] for linha in linhas] == [
        "daily", "anotar <texto>", "perguntar <pergunta>", "abrir", "configurar", "ajuda",
    ]


def test_enter_vazio_e_ajuda_e_comando_desconhecido_diz_o_que_existe(montar, aviso):
    palheta = montar()

    palheta.despachar("")
    assert aviso.ultimo()[0] == "Comandos da palheta"

    palheta.despachar("vagas python remoto")
    titulo, texto, _ = aviso.ultimo()
    assert titulo == "Não entendi"
    assert "'vagas'" in texto and "perguntar <pergunta>" in texto


def test_nenhum_dos_comandos_futuros_esta_registrado(montar):
    nomes = {comando.nome for comando in montar().comandos}

    assert nomes == {"daily", "anotar", "perguntar", "abrir", "configurar", "ajuda"}


# -- o contrato: um por vez, falha vira toast ----------------------------------


def test_um_despacho_enquanto_outro_roda_e_recusado_com_toast(montar, aviso):
    resultados: list[bool] = []
    palheta = montar()

    def lento(_argumento, _configuracao):
        resultados.append(palheta.despachar("ajuda"))
        assert palheta.ocupada()
        return Resultado("Lento", "terminei")

    palheta.comandos = (*palheta.comandos, Comando("lento", "demora", lento))

    assert palheta.despachar("lento") is True

    assert resultados == [False]
    titulos = [titulo for titulo, _, _ in aviso.avisos]
    assert titulos == ["Ainda estou no comando anterior", "Lento"]
    assert "ajuda" in aviso.avisos[0][1]
    assert not palheta.ocupada()


def test_erro_do_comando_vira_toast_e_libera_a_palheta(montar, aviso, caplog):
    def quebra(_argumento, _configuracao):
        raise RuntimeError("o Claude não respondeu em 240s")

    palheta = montar(extras=(Comando("quebra", "falha", quebra),))

    palheta.despachar("quebra")  # não levanta

    titulo, texto, botao = aviso.ultimo()
    assert titulo == "O comando falhou"
    assert texto == "o Claude não respondeu em 240s"
    assert botao is None
    assert not palheta.ocupada()
    assert "falhou" in caplog.text


def test_a_falha_da_busca_chega_ao_usuario_pela_mensagem_dela(montar, aviso):
    from whis.busca import ErroDeBusca

    palheta = montar(busca=BuscaFake(erro=ErroDeBusca("sem conta logada")))

    palheta.despachar("perguntar x")

    assert aviso.ultimo()[:2] == ("O comando falhou", "sem conta logada")


# -- a janela -------------------------------------------------------------------


def test_a_janela_some_no_enter_e_o_comando_e_despachado(montar, aviso):
    palheta = montar()
    janela = JanelaDublê()
    janela.ao_enviar(palheta.despachar)
    janela.mostrar()

    janela.digitar_e_enter("ajuda")

    assert not janela.visivel
    assert aviso.ultimo()[0] == "Comandos da palheta"


def test_a_janela_some_no_esc_sem_despachar_nada(montar, aviso):
    palheta = montar()
    janela = JanelaDublê()
    janela.ao_enviar(palheta.despachar)
    janela.mostrar()

    janela.esc()

    assert not janela.visivel
    assert aviso.avisos == []


def test_a_janela_de_verdade_some_no_enter_e_no_esc():
    """Tk de verdade, quando há tela: só o ciclo mostrar → Enter/Esc → sumir."""
    tk = pytest.importorskip("tkinter")
    from whis.janela_da_palheta import JanelaDaPalheta

    try:
        janela = JanelaDaPalheta()
    except tk.TclError as erro:  # sem display
        pytest.skip(f"sem tela para o Tk: {erro}")
    enviados: list[str] = []
    janela.ao_enviar(enviados.append)
    try:
        janela.mostrar()
        janela.raiz.update()
        assert janela.visivel()
        janela._campo.insert(0, "daily")
        janela._enviar()
        assert not janela.visivel() and enviados == ["daily"]

        janela.mostrar()
        janela.raiz.update()
        janela._campo.event_generate("<Escape>")
        janela.raiz.update()
        assert not janela.visivel() and enviados == ["daily"]

        chamadas: list[str] = []
        janela.pedir(lambda: chamadas.append("de outro thread"))
        janela._sondar()
        assert chamadas == ["de outro thread"]
    finally:
        janela.raiz.destroy()


# -- a configuração e o prompt ----------------------------------------------------


def _config_com(tmp_path: Path, corpo_do_toml: str) -> Path:
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "V"\ngravacoes = "G"\n{corpo_do_toml}', encoding="utf-8")
    return arquivo


def test_o_atalho_da_palheta_vem_da_configuracao_com_padrao(tmp_path: Path):
    assert carregar(_config_com(tmp_path, "")).palheta_atalho == "ctrl+alt+w"
    assert carregar(_config_com(tmp_path, '[palheta]\natalho = "Ctrl + Shift + K"\n')).palheta_atalho == "ctrl+shift+k"


def test_atalho_invalido_e_configuracao_invalida(tmp_path: Path):
    with pytest.raises(ConfiguracaoInvalida) as erro:
        carregar(_config_com(tmp_path, '[palheta]\natalho = "space"\n'))

    assert "[palheta].atalho" in str(erro.value) and "modificador" in str(erro.value)


def test_o_modelo_traz_o_atalho_padrao_comentado():
    dados = tomllib.loads(MODELO_DE_CONFIGURACAO.format(vault="V", gravacoes="G"))

    assert dados["palheta"]["atalho"] == "ctrl+alt+w"
    assert "# o atalho global" in MODELO_DE_CONFIGURACAO


def test_o_prompt_tem_a_voz_do_whis_e_um_teto_estrutural_sem_fontes_no_texto():
    assert "Whis" in PROMPT_DA_BUSCA and "sereno" in PROMPT_DA_BUSCA and "sem firula" in PROMPT_DA_BUSCA
    assert "TRÊS frases ou 400 caracteres" in PROMPT_DA_BUSCA
    assert 'O campo "resposta" NÃO traz lista de fontes' in PROMPT_DA_BUSCA
    assert 'As fontes vão SÓ em "citacoes"' in PROMPT_DA_BUSCA
    assert "celular" not in PROMPT_DA_BUSCA


# -- a bandeja hospeda a palheta --------------------------------------------------


class IconeDestacavel(IconeDublê):
    def __init__(self) -> None:
        super().__init__()
        self.destacado = False

    def run_detached(self) -> None:
        self.destacado = True


class HospedeiroDublê:
    def __init__(self) -> None:
        self.executou = False

    def executar(self) -> None:
        self.executou = True


@pytest.fixture
def coletor(configuracao, caminho_das_gravacoes: Path) -> Coletor:
    return Coletor(
        configuracao,
        portas=lambda: (STTFake(), ResumoFake()),
        gravador=GravadorDublê(caminho_das_gravacoes),
        em_segundo_plano=False,
    )


def rotulos(bandeja: Bandeja) -> list[str]:
    return [
        item.rotulo if isinstance(item.rotulo, str) else item.rotulo()
        for item in bandeja.itens_do_menu()
        if not item.separador
    ]


def test_o_menu_ganha_abrir_a_palheta_logo_abaixo_do_gesto_e_configurar_antes_de_sair(coletor):
    abertos: list[str] = []
    bandeja = Bandeja(
        coletor,
        icone=IconeDestacavel(),
        abrir_palheta=lambda: abertos.append("palheta"),
        abrir_configuracao=lambda: abertos.append("configuracao"),
    )

    nomes = rotulos(bandeja)

    assert nomes[0] == "Gravar reunião" and nomes[2] == "Abrir a palheta"
    assert nomes[-2:] == ["Configurar", "Sair"]
    bandeja.abrir_palheta()
    bandeja.abrir_configuracao()
    assert abertos == ["palheta", "configuracao"]


def test_sem_palheta_o_menu_e_o_de_sempre(coletor):
    nomes = rotulos(Bandeja(coletor, icone=IconeDublê()))

    assert "Abrir a palheta" not in nomes and "Configurar" not in nomes
    assert nomes[0] == "Gravar reunião" and nomes[-1] == "Sair"


def test_com_hospedeiro_o_icone_vai_para_o_thread_secundario_e_sair_encerra_os_tres(coletor):
    icone = IconeDestacavel()
    hospedeiro = HospedeiroDublê()
    encerrados: list[str] = []
    bandeja = Bandeja(coletor, icone=icone, abrir_palheta=lambda: None, ao_sair=lambda: encerrados.append("atalho e janela"))

    bandeja.executar(hospedeiro=hospedeiro)
    assert icone.destacado and not icone.rodou and hospedeiro.executou

    bandeja.sair()
    assert icone.parou and encerrados == ["atalho e janela"]


def test_sem_hospedeiro_o_icone_roda_no_thread_principal_como_sempre(coletor):
    icone = IconeDublê()

    Bandeja(coletor, icone=icone).executar()

    assert icone.rodou


def test_o_subcomando_bandeja_monta_a_palheta_com_os_fakes_e_o_atalho(configuracao_do_diario, monkeypatch, caminho_do_vault: Path):
    configuracao_do_diario()
    chamadas: list[dict] = []
    monkeypatch.setattr(_bandeja, "executar", lambda configuracao, **extras: chamadas.append(extras) or 0)

    assert cli.main(["bandeja", "--fakes"]) == 0

    [extras] = chamadas
    palheta = extras["palheta"]
    assert isinstance(palheta, Palheta)
    assert extras["atalho"].texto == "ctrl+alt+w"
    daily = next(comando for comando in palheta.comandos if comando.nome == "daily")
    resultado = daily.rodar("", palheta.configuracao)
    assert resultado.nota == "daily/atual.md"
    assert (caminho_do_vault / "daily" / "atual.md").is_file()

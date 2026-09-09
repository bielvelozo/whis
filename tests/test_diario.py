"""Comportamento da costura do diário: as fontes do dia viram nota em `diario/`.

Nada aqui olha para dentro de `gerar_diario`: os testes leem o vault, como o
usuário leria no Obsidian. As fontes e o resumo entram como fakes pelas portas.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from fixtures.leitura import arquivos_do_vault, corpo, ler_frontmatter
from whis import vault as modulo_vault
from whis.configuracao import Configuracao
from whis.diario import TodasAsFontesFalharam, gerar_diario
from whis.fakes import RESUMO_DO_DIA_PADRAO, FonteFake, ResumoDoDiaFake
from whis.fontes import ErroDeFonte, Evento, data_do_diario
from whis.portas import ErroDeResumoDoDia, ResumoDoDia

DIA = date(2026, 9, 3)


def evento(
    hora: int,
    minuto: int = 0,
    *,
    fonte: str = "git",
    titulo: str = "commit do dia",
    dia: date = DIA,
    **extras,
) -> Evento:
    """Um evento no horário local de um dia — o que uma fonte devolveria."""
    momento = datetime.combine(dia, time(hora, minuto)).astimezone()
    return Evento(fonte=fonte, momento=momento, titulo=titulo, **extras)


@pytest.fixture
def resumo_do_dia() -> ResumoDoDiaFake:
    """Porta de resumo do dia fake — guarda o que recebeu, para o teste do filtro."""
    return ResumoDoDiaFake()


@pytest.fixture
def gerar(configuracao_do_diario, resumo_do_dia: ResumoDoDiaFake):
    """Roda a costura com as portas fake: `gerar(fontes=[...])`."""

    def executar(*, fontes=(), configuracao: Configuracao | None = None, **extras):
        return gerar_diario(
            extras.pop("data", DIA),
            configuracao=configuracao or configuracao_do_diario(),
            fontes=list(fontes),
            resumo=extras.pop("resumo", resumo_do_dia),
            **extras,
        )

    return executar


def nota_do_dia(vault: Path, dia: date = DIA) -> Path:
    return vault / "diario" / f"{dia.isoformat()}.md"


def criar_nota_de_reuniao(vault: Path, basename: str) -> Path:
    """Uma nota de reunião já no vault, como o pipeline de reunião a deixaria."""
    modulo_vault.preparar(vault)
    arquivo = vault / "reunioes" / f"{basename}.md"
    arquivo.write_text(f"# {basename}\n", encoding="utf-8")
    return arquivo


# -- Caminho feliz ----------------------------------------------------------


def test_gerar_diario_escreve_a_nota_do_dia_no_vault(gerar, caminho_do_vault: Path):
    resultado = gerar(fontes=[FonteFake("git", (evento(9, 12),))])

    assert nota_do_dia(caminho_do_vault).is_file()
    assert resultado.nota == nota_do_dia(caminho_do_vault)


def test_frontmatter_do_diario_tem_os_campos_do_contrato(gerar, caminho_do_vault: Path):
    gerar(
        fontes=[
            FonteFake("git", (evento(9, 12),)),
            FonteFake("linear", (evento(11, 20, fonte="linear"),)),
        ]
    )

    campos = ler_frontmatter(nota_do_dia(caminho_do_vault))
    assert campos["data"] == "2026-09-03"
    assert campos["tipo"] == "diario"
    assert campos["fontes"] == ["git", "linear"]
    assert campos["fontes_com_falha"] == []
    assert campos["temas"] == list(RESUMO_DO_DIA_PADRAO.temas)
    assert "2026-09-03T04:00" in str(campos["janela"])


def test_diario_traz_o_resumo_vindo_da_porta(gerar, caminho_do_vault: Path):
    gerar(fontes=[FonteFake("git", (evento(9, 12),))])

    texto = corpo(nota_do_dia(caminho_do_vault))
    assert "# Diário — 3 de setembro de 2026 (quinta-feira)" in texto
    assert RESUMO_DO_DIA_PADRAO.narrativa in texto
    for destaque in RESUMO_DO_DIA_PADRAO.destaques:
        assert destaque in texto
    for pendencia in RESUMO_DO_DIA_PADRAO.pendencias:
        assert pendencia in texto


def test_listas_cruas_saem_por_fonte_e_por_referencia(gerar, caminho_do_vault: Path):
    fontes = [
        FonteFake(
            "git",
            (
                evento(9, 12, titulo="`a1b2c3d` Fecha a camada 01", referencia="whis"),
                evento(17, 45, titulo="`d4e5f6a` Corrige o frete", referencia="loja"),
            ),
        ),
        FonteFake(
            "linear",
            (
                evento(
                    11,
                    20,
                    fonte="linear",
                    titulo="FN-123 Corrigir o frete",
                    detalhe="Subiu em produção.",
                    referencia="Plataforma",
                    url="https://linear.app/exemplo/issue/FN-123",
                ),
            ),
        ),
    ]

    gerar(fontes=fontes)

    texto = corpo(nota_do_dia(caminho_do_vault))
    assert "## Git" in texto and "## Linear" in texto
    assert "### whis" in texto and "### loja" in texto
    assert "- 09:12 `a1b2c3d` Fecha a camada 01" in texto
    assert "- 11:20 [FN-123 Corrigir o frete](https://linear.app/exemplo/issue/FN-123)" in texto
    assert "  > Subiu em produção." in texto


def test_fonte_sem_nada_no_dia_ganha_secao_vazia(gerar, caminho_do_vault: Path):
    """Seção vazia distingue "não houve nada" de "a fonte não está ligada"."""
    gerar(fontes=[FonteFake("git", (evento(9, 12),)), FonteFake("linear", ())])

    texto = corpo(nota_do_dia(caminho_do_vault))
    assert "## Linear\n\n_(nada registrado)_" in texto


def test_fonte_desligada_nao_aparece_na_nota(gerar, caminho_do_vault: Path):
    gerar(fontes=[FonteFake("git", (evento(9, 12),))])

    nota = nota_do_dia(caminho_do_vault)
    assert "## Slack" not in corpo(nota)
    assert ler_frontmatter(nota)["fontes"] == ["git"]


def test_eventos_saem_em_ordem_cronologica(gerar, caminho_do_vault: Path):
    fontes = [
        FonteFake(
            "git",
            (
                evento(17, 45, titulo="commit da tarde", referencia="repo"),
                evento(9, 12, titulo="commit da manhã", referencia="repo"),
            ),
        )
    ]

    gerar(fontes=fontes)

    texto = corpo(nota_do_dia(caminho_do_vault))
    assert texto.index("commit da manhã") < texto.index("commit da tarde")


# -- Reuniões do dia --------------------------------------------------------


def test_diario_linka_as_reunioes_da_janela(gerar, caminho_do_vault: Path):
    criar_nota_de_reuniao(caminho_do_vault, "2026-09-03-1430-daily-do-time")

    resultado = gerar(fontes=[FonteFake("git", (evento(9, 12),))])

    texto = corpo(nota_do_dia(caminho_do_vault))
    assert "- [[reunioes/2026-09-03-1430-daily-do-time]]" in texto
    assert ler_frontmatter(nota_do_dia(caminho_do_vault))["reunioes"] == [
        "[[reunioes/2026-09-03-1430-daily-do-time]]"
    ]
    assert resultado.reunioes == ("reunioes/2026-09-03-1430-daily-do-time.md",)


def test_reuniao_da_madrugada_cai_no_diario_do_dia_anterior(gerar, caminho_do_vault: Path):
    criar_nota_de_reuniao(caminho_do_vault, "2026-09-04-0030-planejamento")

    gerar(fontes=[FonteFake("git", (evento(9, 12),))])

    assert "[[reunioes/2026-09-04-0030-planejamento]]" in corpo(nota_do_dia(caminho_do_vault))


def test_reuniao_de_outro_dia_nao_entra(gerar, caminho_do_vault: Path):
    criar_nota_de_reuniao(caminho_do_vault, "2026-09-01-1000-outra")

    resultado = gerar(fontes=[FonteFake("git", (evento(9, 12),))])

    assert resultado.reunioes == ()
    assert "2026-09-01-1000-outra" not in corpo(nota_do_dia(caminho_do_vault))


def test_arquivo_com_nome_fora_do_padrao_nao_quebra_o_diario(gerar, caminho_do_vault: Path):
    criar_nota_de_reuniao(caminho_do_vault, "anotacoes-soltas")
    criar_nota_de_reuniao(caminho_do_vault, "2026-13-45-9999-data-impossivel")

    resultado = gerar(fontes=[FonteFake("git", (evento(9, 12),))])

    assert resultado.reunioes == ()
    assert nota_do_dia(caminho_do_vault).is_file()


def test_dia_so_com_reuniao_ainda_vira_diario(gerar, caminho_do_vault: Path):
    criar_nota_de_reuniao(caminho_do_vault, "2026-09-03-1430-daily-do-time")

    resultado = gerar(fontes=[FonteFake("git", ())])

    assert resultado.vazio is False
    assert nota_do_dia(caminho_do_vault).is_file()


# -- Degradação graciosa ----------------------------------------------------


def test_fonte_que_falha_deixa_o_diario_nascer_marcado(gerar, caminho_do_vault: Path):
    fontes = [
        FonteFake("git", (evento(9, 12),)),
        FonteFake("slack", erro=ErroDeFonte("token do Slack ausente em [slack].user_token")),
    ]

    resultado = gerar(fontes=fontes)

    nota = nota_do_dia(caminho_do_vault)
    campos = ler_frontmatter(nota)
    texto = corpo(nota)
    assert campos["fontes"] == ["git"]
    assert campos["fontes_com_falha"] == ["slack"]
    assert "> [!warning] Slack não entrou neste diário: token do Slack ausente" in texto
    assert "## Slack" in texto
    assert "_Não foi possível ler esta fonte: token do Slack ausente" in texto
    assert resultado.fontes_com_falha[0].fonte == "slack"


def test_todas_as_fontes_falhando_nao_escreve_nada(gerar, caminho_do_vault: Path):
    fontes = [
        FonteFake("git", erro=ErroDeFonte("raiz de desenvolvimento não encontrada")),
        FonteFake("linear", erro=ErroDeFonte("HTTP 401 no Linear")),
    ]

    with pytest.raises(TodasAsFontesFalharam) as erro:
        gerar(fontes=fontes)

    assert not nota_do_dia(caminho_do_vault).exists()
    assert "git" in str(erro.value) and "linear" in str(erro.value)


def test_dia_vazio_nao_vira_nota(gerar, caminho_do_vault: Path):
    resultado = gerar(fontes=[FonteFake("git", ()), FonteFake("linear", ())])

    assert resultado.vazio is True
    assert resultado.nota is None
    assert not nota_do_dia(caminho_do_vault).exists()


def test_resumo_que_falha_ainda_deixa_as_listas_cruas(gerar, caminho_do_vault: Path):
    """As listas cruas não existem em nenhum outro lugar — perdê-las é perder o dia."""
    resumo = ResumoDoDiaFake(erro=ErroDeResumoDoDia("o Claude não respondeu a tempo"))

    resultado = gerar(
        fontes=[FonteFake("git", (evento(9, 12, titulo="commit que precisa sobreviver"),))],
        resumo=resumo,
    )

    nota = nota_do_dia(caminho_do_vault)
    texto = corpo(nota)
    assert "commit que precisa sobreviver" in texto
    assert "## Destaques" not in texto and "## Pendências" not in texto
    assert "o Claude não respondeu a tempo" in texto
    assert ler_frontmatter(nota)["temas"] == []
    assert resultado.resumo is None


def test_simulacao_nao_escreve_nem_chama_o_resumo(
    gerar, caminho_do_vault: Path, resumo_do_dia: ResumoDoDiaFake
):
    resultado = gerar(fontes=[FonteFake("git", (evento(9, 12),))], simular=True)

    assert resultado.simulado is True
    assert resultado.nota is None
    assert resultado.eventos
    assert not nota_do_dia(caminho_do_vault).exists()
    assert resumo_do_dia.eventos_recebidos == ()


# -- Idempotência -----------------------------------------------------------


def test_gerar_duas_vezes_deixa_um_arquivo_so(gerar, caminho_do_vault: Path):
    gerar(fontes=[FonteFake("git", (evento(9, 12),))])
    gerar(fontes=[FonteFake("git", (evento(9, 12),))])

    assert len(list((caminho_do_vault / "diario").glob("*.md"))) == 1


def test_segunda_execucao_reflete_o_que_mudou(gerar, caminho_do_vault: Path):
    gerar(fontes=[FonteFake("git", (evento(9, 12, titulo="commit da manhã"),))])

    gerar(
        fontes=[
            FonteFake(
                "git",
                (
                    evento(9, 12, titulo="commit da manhã"),
                    evento(22, 30, titulo="commit da noite"),
                ),
            )
        ]
    )

    texto = corpo(nota_do_dia(caminho_do_vault))
    assert "commit da manhã" in texto
    assert "commit da noite" in texto


def test_reuniao_processada_depois_entra_na_regeneracao(gerar, caminho_do_vault: Path):
    gerar(fontes=[FonteFake("git", (evento(9, 12),))])
    criar_nota_de_reuniao(caminho_do_vault, "2026-09-03-1430-daily-do-time")

    gerar(fontes=[FonteFake("git", (evento(9, 12),))])

    assert "[[reunioes/2026-09-03-1430-daily-do-time]]" in corpo(nota_do_dia(caminho_do_vault))


# -- A janela do dia --------------------------------------------------------


def test_madrugada_do_dia_seguinte_cai_no_diario_de_ontem(
    gerar, configuracao_do_diario, caminho_do_vault: Path
):
    da_madrugada = evento(1, 0, dia=DIA + timedelta(days=1), titulo="commit da uma da manhã")

    gerar(
        fontes=[FonteFake("git", (da_madrugada,))],
        configuracao=configuracao_do_diario(inicio_do_dia="04:00"),
    )

    assert "commit da uma da manhã" in corpo(nota_do_dia(caminho_do_vault))


@pytest.mark.parametrize(
    ("agora", "esperado"),
    [
        (datetime(2026, 9, 4, 2, 0), date(2026, 9, 3)),
        (datetime(2026, 9, 4, 3, 59), date(2026, 9, 3)),
        (datetime(2026, 9, 4, 4, 0), date(2026, 9, 4)),
        (datetime(2026, 9, 4, 19, 0), date(2026, 9, 4)),
    ],
)
def test_o_dia_do_diario_e_deduzido_do_relogio(agora: datetime, esperado: date):
    """O que a CLI usa quando o usuário não passa data."""
    assert data_do_diario(agora.astimezone(), "04:00") == esperado


def test_evento_na_virada_pertence_so_ao_diario_seguinte(
    gerar, configuracao_do_diario, caminho_do_vault: Path
):
    """O fim da janela é exclusivo — senão a virada apareceria em dois diários."""
    na_virada = evento(4, 0, dia=DIA + timedelta(days=1), titulo="commit das quatro em ponto")
    fontes = [FonteFake("git", (na_virada,))]

    de_hoje = gerar(fontes=fontes, configuracao=configuracao_do_diario(inicio_do_dia="04:00"))
    gerar(
        fontes=fontes,
        data=DIA + timedelta(days=1),
        configuracao=configuracao_do_diario(inicio_do_dia="04:00"),
    )

    assert de_hoje.vazio is True
    assert not nota_do_dia(caminho_do_vault).exists()
    assert "commit das quatro em ponto" in corpo(
        nota_do_dia(caminho_do_vault, DIA + timedelta(days=1))
    )


def test_com_dia_civil_a_madrugada_fica_de_fora(
    gerar, configuracao_do_diario, caminho_do_vault: Path
):
    da_madrugada = evento(1, 0, dia=DIA + timedelta(days=1), titulo="commit da uma da manhã")

    resultado = gerar(
        fontes=[FonteFake("git", (da_madrugada,))],
        configuracao=configuracao_do_diario(inicio_do_dia="00:00"),
    )

    assert resultado.vazio is True
    assert not nota_do_dia(caminho_do_vault).exists()


# -- O filtro de exclusão ---------------------------------------------------


def test_evento_excluido_nao_entra_no_vault_nem_chega_ao_resumo(
    gerar, configuracao_do_diario, caminho_do_vault: Path, resumo_do_dia: ResumoDoDiaFake
):
    """A promessa do filtro é que o excluído não sai da máquina — nem para o Claude."""
    fontes = [
        FonteFake(
            "git",
            (
                evento(9, 12, titulo="commit do trabalho", referencia="whis"),
                evento(21, 0, titulo="commit da terapia", referencia="diario-pessoal"),
            ),
        )
    ]

    resultado = gerar(
        fontes=fontes, configuracao=configuracao_do_diario(excluir=("TERAPIA",))
    )

    texto = nota_do_dia(caminho_do_vault).read_text(encoding="utf-8")
    assert "terapia" not in texto.casefold()
    assert "commit do trabalho" in texto
    assert resultado.excluidos == 1
    recebidos = [evento_recebido.titulo for evento_recebido in resumo_do_dia.eventos_recebidos]
    assert recebidos == ["commit do trabalho"]


def test_filtro_alcanca_referencia_e_pessoas(
    gerar, configuracao_do_diario, caminho_do_vault: Path, resumo_do_dia: ResumoDoDiaFake
):
    fontes = [
        FonteFake(
            "slack",
            (
                evento(10, 0, fonte="slack", titulo="mensagem", referencia="#pessoal"),
                evento(11, 0, fonte="slack", titulo="outra", pessoas=("Terapeuta",)),
                evento(12, 0, fonte="slack", titulo="a que fica", referencia="#time"),
            ),
        )
    ]

    resultado = gerar(
        fontes=fontes, configuracao=configuracao_do_diario(excluir=("#pessoal", "terapeuta"))
    )

    assert resultado.excluidos == 2
    assert [e.titulo for e in resumo_do_dia.eventos_recebidos] == ["a que fica"]


def test_sem_filtro_nada_e_removido(gerar, caminho_do_vault: Path):
    resultado = gerar(fontes=[FonteFake("git", (evento(9, 12), evento(10, 0)))])

    assert resultado.excluidos == 0
    assert len(resultado.eventos) == 2


# -- Zona de propriedade ----------------------------------------------------


def test_o_diario_escreve_apenas_em_diario(gerar, caminho_do_vault: Path):
    modulo_vault.preparar(caminho_do_vault)
    (caminho_do_vault / "notas" / "ideias.md").write_text("não encoste", encoding="utf-8")
    criar_nota_de_reuniao(caminho_do_vault, "2026-09-03-1430-daily-do-time")
    antes = arquivos_do_vault(caminho_do_vault)

    gerar(fontes=[FonteFake("git", (evento(9, 12),))])

    novos = arquivos_do_vault(caminho_do_vault) - antes
    assert novos, "o coletor de diário não escreveu nada"
    assert all(arquivo.startswith("diario/") for arquivo in novos), sorted(novos)


def test_notas_e_reunioes_permanecem_intactas(gerar, caminho_do_vault: Path):
    modulo_vault.preparar(caminho_do_vault)
    ideias = caminho_do_vault / "notas" / "ideias.md"
    ideias.write_text("# Minhas ideias\n", encoding="utf-8")
    reuniao = criar_nota_de_reuniao(caminho_do_vault, "2026-09-03-1430-daily-do-time")
    conteudo_da_reuniao = reuniao.read_text(encoding="utf-8")

    gerar(fontes=[FonteFake("git", (evento(9, 12),))])

    assert ideias.read_text(encoding="utf-8") == "# Minhas ideias\n"
    assert reuniao.read_text(encoding="utf-8") == conteudo_da_reuniao


@pytest.mark.parametrize(
    "destino", ["reunioes/roubada.md", "transcricoes/roubada.md", "notas/roubada.md"]
)
def test_a_zona_do_diario_nao_alcanca_as_outras_pastas(caminho_do_vault: Path, destino: str):
    modulo_vault.preparar(caminho_do_vault)

    with pytest.raises(modulo_vault.ForaDaZonaDePropriedade):
        modulo_vault.escrever(
            caminho_do_vault, destino, "não deveria existir", zonas=modulo_vault.ZONAS_DO_DIARIO
        )

    assert not (caminho_do_vault / destino).exists()


@pytest.mark.parametrize("fuga", ["../notas/invadida.md", "../reunioes/invadida.md"])
def test_traversal_para_fora_da_zona_do_diario_e_recusado(caminho_do_vault: Path, fuga: str):
    modulo_vault.preparar(caminho_do_vault)

    with pytest.raises(modulo_vault.ForaDaZonaDePropriedade):
        modulo_vault.escrever(
            caminho_do_vault,
            f"diario/{fuga}",
            "ESCRITA INDEVIDA",
            zonas=modulo_vault.ZONAS_DO_DIARIO,
        )

    assert list((caminho_do_vault / "notas").iterdir()) == []
    assert list((caminho_do_vault / "reunioes").iterdir()) == []


# -- Registro ---------------------------------------------------------------


def test_fonte_que_falha_deixa_o_motivo_no_log(gerar, caplog: pytest.LogCaptureFixture):
    fontes = [
        FonteFake("git", (evento(9, 12),)),
        FonteFake("slack", erro=ErroDeFonte("token do Slack ausente")),
    ]

    with caplog.at_level("ERROR", logger="whis.diario"):
        gerar(fontes=fontes)

    assert "token do Slack ausente" in caplog.text


def test_resumo_do_dia_recebe_as_reunioes(
    gerar, caminho_do_vault: Path, resumo_do_dia: ResumoDoDiaFake
):
    criar_nota_de_reuniao(caminho_do_vault, "2026-09-03-1430-daily-do-time")

    gerar(fontes=[FonteFake("git", (evento(9, 12),))])

    assert resumo_do_dia.reunioes_recebidas == ("reunioes/2026-09-03-1430-daily-do-time.md",)


def test_narrativa_vazia_nao_deixa_secao_solta(gerar, caminho_do_vault: Path):
    resumo = ResumoDoDiaFake(ResumoDoDia(destaques=("só um destaque",)))

    gerar(fontes=[FonteFake("git", (evento(9, 12),))], resumo=resumo)

    texto = corpo(nota_do_dia(caminho_do_vault))
    assert "## Destaques" in texto
    assert "## Pendências\n\n_(nada registrado)_" in texto

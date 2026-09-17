"""Comportamento da costura da daily: a janela desde a última fala mantém a nota viva.

Nada aqui olha para dentro de `gerar_daily`: os testes leem o vault, como o
usuário leria no Obsidian, e passam `agora` explicitamente — é o relógio que
define a janela, e ele precisa ser controlável para a segunda-feira que cobre o
fim de semana ser testável.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from fixtures.leitura import arquivos_do_vault, corpo, ler_frontmatter
from whis import vault as modulo_vault
from whis.coleta import TodasAsFontesFalharam
from whis.configuracao import Configuracao
from whis.daily import gerar_daily
from whis.fakes import DAILY_PADRAO, ITEM_ABERTO_DE_EXEMPLO, DailyFake, FonteFake
from whis.fontes import ErroDeFonte, Evento
from whis.nota_viva import (
    SECAO_DUVIDAS,
    SECAO_FALAR,
    SECAO_FAZENDO,
    SECAO_FAZER,
    SECAO_FIZ,
    SECAO_PONTOS,
    NotaViva,
)
from whis.portas import Daily, ErroDeDaily, ItemNovo

QUINTA = date(2026, 9, 3)
SEXTA = date(2026, 9, 4)
SABADO = date(2026, 9, 5)
DOMINGO = date(2026, 9, 6)
SEGUNDA = date(2026, 9, 7)


def momento(dia: date, hora: int, minuto: int = 0) -> datetime:
    """Um instante local — o relógio da máquina do usuário."""
    return datetime.combine(dia, time(hora, minuto)).astimezone()


def evento(
    dia: date,
    hora: int,
    minuto: int = 0,
    *,
    fonte: str = "git",
    titulo: str = "commit qualquer",
    **extras,
) -> Evento:
    return Evento(fonte=fonte, momento=momento(dia, hora, minuto), titulo=titulo, **extras)


@pytest.fixture
def roteiro() -> DailyFake:
    """Porta de daily fake — guarda o que recebeu, para o teste do filtro."""
    return DailyFake()


@pytest.fixture
def gerar(configuracao_do_diario, roteiro: DailyFake):
    """Roda a costura com as portas fake: `gerar(agora=..., fontes=[...])`."""

    def executar(*, agora: datetime, fontes=(), configuracao: Configuracao | None = None, **extras):
        return gerar_daily(
            agora,
            configuracao=configuracao or configuracao_do_diario(),
            fontes=list(fontes),
            roteiro=extras.pop("roteiro", roteiro),
            **extras,
        )

    return executar


def nota_da_daily(vault: Path, dia: date) -> Path:
    return vault / "daily" / f"{dia.isoformat()}.md"


def criar_nota_de_reuniao(vault: Path, basename: str) -> Path:
    modulo_vault.preparar(vault)
    arquivo = vault / "reunioes" / f"{basename}.md"
    arquivo.write_text(f"# {basename}\n", encoding="utf-8")
    return arquivo


def nota_viva(vault: Path) -> Path:
    return vault / "daily" / "atual.md"


def escrever_nota_viva(vault: Path, conteudo: str) -> Path:
    """A nota viva como o usuário a deixaria no Obsidian — bytes, sem tradução."""
    modulo_vault.preparar(vault)
    arquivo = nota_viva(vault)
    arquivo.write_bytes(conteudo.encode("utf-8"))
    return arquivo


def hash_de(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def trecho(texto: str, titulo: str) -> str:
    """O texto de uma seção, do título até o próximo `## `."""
    inicio = texto.index(f"## {titulo}")
    fim = texto.find("\n## ", inicio + 1)
    return texto[inicio:] if fim == -1 else texto[inicio:fim]


#: Uma nota viva no formato das dailies à mão: `1.` com sub-itens por tab, um
#: item com espaço à direita, e as duas seções do usuário preenchidas.
NOTA_DO_USUARIO = (
    "---\n"
    "tipo: daily-atual\n"
    "---\n"
    "\n"
    "## O que eu fiz\n"
    "\n"
    "1. Planejei e ativei o pix transparente da AppMax no checkout\n"
    "\n"
    "## O que estou fazendo\n"
    "\n"
    "1. Estou fazendo mais correções dos achados do ribeiro\n"
    "\t1. FN-1786: a foto extra do Porta Retrato não será cobrada de novo no hub.\n"
    "\t2. Card \"A pagar agora\" e adicionais do porta-retrato (FN-1784)\n"
    "\t\t1. Problema A, adicionais de outros itens \n"
    "2. Testando no android  \n"
    "\n"
    "## Dúvidas\n"
    "\n"
    "- o pix pendente expira sozinho?\n"
    "\n"
    "## Falar\n"
    "\n"
    "- avisar que sexta eu saio mais cedo\n"
)


def id_na_nota(vault: Path, comeco: str) -> str:
    nota = NotaViva.de_texto(nota_viva(vault).read_bytes().decode("utf-8"))
    return next(item.id for item in nota.itens(SECAO_FAZENDO) if item.texto.startswith(comeco))


def abrir_a_janela(gerar, dia: date) -> None:
    """Uma geração de manhã, sem resposta, para a execução seguinte cair na mesma janela."""
    gerar(agora=momento(dia, 8, 30), fontes=[FonteFake("git", (evento(dia, 8),))], roteiro=DailyFake(Daily()))


# -- Caminho feliz ----------------------------------------------------------


def test_gerar_daily_escreve_a_nota_do_dia_no_vault(gerar, caminho_do_vault: Path):
    resultado = gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    assert nota_da_daily(caminho_do_vault, SEXTA).is_file()
    assert resultado.nota == nota_da_daily(caminho_do_vault, SEXTA)


def test_a_primeira_geracao_faz_a_nota_viva_nascer_do_modelo_com_os_itens_do_fake(
    gerar, caminho_do_vault: Path
):
    resultado = gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    texto = nota_viva(caminho_do_vault).read_text(encoding="utf-8")
    assert resultado.nota_viva == nota_viva(caminho_do_vault)
    assert texto.startswith("---\ntipo: daily-atual\n---\n")
    for item in DAILY_PADRAO.fiz:
        assert f"- {item.texto}" in trecho(texto, SECAO_FIZ)
    assert f"- {ITEM_ABERTO_DE_EXEMPLO}\n\t- FN-130" in trecho(texto, SECAO_FAZENDO)
    assert trecho(texto, SECAO_DUVIDAS) == "## Dúvidas\n"
    assert trecho(texto, SECAO_FALAR) == "## Falar\n"


def test_frontmatter_da_daily_tem_os_campos_do_contrato(gerar, caminho_do_vault: Path):
    agora = momento(SEXTA, 9, 5)

    gerar(
        agora=agora,
        fontes=[
            FonteFake("git", (evento(SEXTA, 8, referencia="whis"),)),
            FonteFake("linear", (evento(SEXTA, 8, 30, fonte="linear", referencia="Plataforma"),)),
        ],
    )

    campos = ler_frontmatter(nota_da_daily(caminho_do_vault, SEXTA))
    assert campos["tipo"] == "daily"
    assert campos["data"] == "2026-09-04"
    assert campos["ate"] == agora.isoformat()
    assert campos["desde"] == (agora - timedelta(hours=24)).isoformat()
    assert campos["fontes"] == ["git", "linear"]
    assert campos["fontes_com_falha"] == []
    assert campos["temas"] == ["whis", "Plataforma"]


def test_a_nota_datada_registra_o_que_mudou_na_nota_viva(gerar, caminho_do_vault: Path):
    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    texto = corpo(nota_da_daily(caminho_do_vault, SEXTA))
    assert "# Daily — 4 de setembro de 2026 (sexta-feira)" in texto
    mudancas = trecho(texto, "Mudanças na nota viva")
    assert "**Acrescentado:**" in mudancas
    for item in (*DAILY_PADRAO.fiz, *DAILY_PADRAO.fazendo):
        assert f"- {item.texto}" in mudancas
    assert "## O que eu fiz\n" not in texto, "o roteiro vive na nota viva, não aqui"


def test_as_listas_cruas_ficam_embaixo_do_roteiro(gerar, caminho_do_vault: Path):
    """É o que faz da daily o registro durável do vault, e não só um roteiro."""
    fontes = [
        FonteFake("git", (evento(SEXTA, 8, titulo="`a1b2c3d` Fecha a camada 07", referencia="whis"),)),
        FonteFake(
            "linear",
            (
                evento(
                    SEXTA,
                    8,
                    30,
                    fonte="linear",
                    titulo="FN-123 Corrigir o frete",
                    detalhe="Subiu em produção.",
                    referencia="Plataforma",
                    url="https://linear.app/exemplo/issue/FN-123",
                ),
            ),
        ),
    ]

    gerar(agora=momento(SEXTA, 9, 5), fontes=fontes)

    texto = corpo(nota_da_daily(caminho_do_vault, SEXTA))
    assert "## Git" in texto and "## Linear" in texto
    assert "### whis" in texto and "### Plataforma" in texto
    assert "- 08:00 `a1b2c3d` Fecha a camada 07" in texto
    assert "- 08:30 [FN-123 Corrigir o frete](https://linear.app/exemplo/issue/FN-123)" in texto
    assert "  > Subiu em produção." in texto
    assert texto.index("## Mudanças na nota viva") < texto.index("## Git")


def test_a_daily_linka_as_reunioes_da_janela(gerar, caminho_do_vault: Path):
    criar_nota_de_reuniao(caminho_do_vault, "2026-09-04-0830-daily-do-time")

    resultado = gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    texto = corpo(nota_da_daily(caminho_do_vault, SEXTA))
    assert "- [[reunioes/2026-09-04-0830-daily-do-time]]" in texto
    assert resultado.reunioes == ("reunioes/2026-09-04-0830-daily-do-time.md",)


# -- A janela: o coração desta camada ---------------------------------------


def test_a_primeira_daily_cobre_24h_e_diz_que_foi_a_primeira(gerar, caminho_do_vault: Path):
    agora = momento(SEXTA, 9, 5)

    resultado = gerar(agora=agora, fontes=[FonteFake("git", (evento(QUINTA, 20),))])

    assert resultado.janela.primeira is True
    assert resultado.janela.desde == agora - timedelta(hours=24)
    texto = corpo(nota_da_daily(caminho_do_vault, SEXTA))
    assert "Cobre de quinta, 03/09 09:05, até agora" in texto
    assert "primeira daily" in texto


def test_a_janela_ancora_no_ate_da_daily_anterior(gerar, caminho_do_vault: Path):
    """A âncora mora no frontmatter da nota anterior, não num estado escondido."""
    gerar(agora=momento(QUINTA, 9, 12), fontes=[FonteFake("git", (evento(QUINTA, 8),))])

    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    campos = ler_frontmatter(nota_da_daily(caminho_do_vault, SEXTA))
    assert campos["desde"] == momento(QUINTA, 9, 12).isoformat()
    assert campos["ate"] == momento(SEXTA, 9, 5).isoformat()


def test_o_que_ficou_antes_da_ultima_daily_nao_volta(gerar, caminho_do_vault: Path):
    gerar(
        agora=momento(QUINTA, 9, 12),
        fontes=[FonteFake("git", (evento(QUINTA, 8, titulo="commit ja falado"),))],
    )

    gerar(
        agora=momento(SEXTA, 9, 5),
        fontes=[
            FonteFake(
                "git",
                (
                    evento(QUINTA, 8, titulo="commit ja falado"),
                    evento(QUINTA, 18, titulo="commit de depois da daily"),
                ),
            )
        ],
    )

    texto = corpo(nota_da_daily(caminho_do_vault, SEXTA))
    assert "commit ja falado" not in texto
    assert "commit de depois da daily" in texto


def test_na_segunda_a_janela_cobre_o_fim_de_semana(gerar, caminho_do_vault: Path):
    """Nada do fim de semana pode cair no vão entre duas falas."""
    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])
    do_fim_de_semana = (
        evento(SABADO, 15, titulo="commit de sábado"),
        evento(DOMINGO, 21, titulo="commit de domingo"),
    )

    resultado = gerar(agora=momento(SEGUNDA, 9, 2), fontes=[FonteFake("git", do_fim_de_semana)])

    texto = corpo(nota_da_daily(caminho_do_vault, SEGUNDA))
    assert "commit de sábado" in texto and "commit de domingo" in texto
    assert resultado.janela.desde == momento(SEXTA, 9, 5)
    assert "Cobre de sexta, 04/09 09:05, até agora." in texto


def test_rodar_de_novo_no_mesmo_dia_mantem_o_desde_e_estende_o_ate(
    gerar, caminho_do_vault: Path
):
    gerar(agora=momento(QUINTA, 9, 0), fontes=[FonteFake("git", (evento(QUINTA, 8),))])
    gerar(agora=momento(SEXTA, 9, 0), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    gerar(
        agora=momento(SEXTA, 17, 30),
        fontes=[
            FonteFake(
                "git",
                (evento(SEXTA, 8), evento(SEXTA, 16, titulo="commit da tarde")),
            )
        ],
    )

    campos = ler_frontmatter(nota_da_daily(caminho_do_vault, SEXTA))
    assert campos["desde"] == momento(QUINTA, 9, 0).isoformat()
    assert campos["ate"] == momento(SEXTA, 17, 30).isoformat()
    assert "commit da tarde" in corpo(nota_da_daily(caminho_do_vault, SEXTA))
    assert len(list((caminho_do_vault / "daily").glob("2026-*.md"))) == 2


def test_rodar_de_novo_mantem_o_desde_ate_na_primeira_daily_de_todas(
    gerar, caminho_do_vault: Path
):
    """Sem âncora, recalcular as 24h faria a janela escorregar entre as execuções."""
    primeira = gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    de_novo = gerar(agora=momento(SEXTA, 17, 30), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    assert de_novo.janela.desde == primeira.janela.desde
    assert de_novo.janela.ate == momento(SEXTA, 17, 30)
    assert de_novo.janela.primeira is True
    assert "primeira daily" in corpo(nota_da_daily(caminho_do_vault, SEXTA))


def test_nada_cai_no_vao_entre_duas_execucoes_do_mesmo_dia(gerar, caminho_do_vault: Path):
    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])
    no_comeco_da_janela = evento(QUINTA, 9, 30, titulo="commit do sobejo")

    gerar(
        agora=momento(SEXTA, 17, 30),
        fontes=[FonteFake("git", (no_comeco_da_janela, evento(SEXTA, 8)))],
    )

    assert "commit do sobejo" in corpo(nota_da_daily(caminho_do_vault, SEXTA))


def test_daily_anterior_com_frontmatter_editado_a_mao_nao_quebra_a_janela(
    gerar, caminho_do_vault: Path
):
    modulo_vault.preparar(caminho_do_vault)
    (caminho_do_vault / "daily" / SEXTA.isoformat()).with_suffix(".md").write_text(
        "# rabisco sem frontmatter\n", encoding="utf-8"
    )

    resultado = gerar(agora=momento(SABADO, 9, 0), fontes=[FonteFake("git", (evento(SABADO, 8),))])

    assert resultado.janela.primeira is True
    assert resultado.janela.desde == momento(SABADO, 9, 0) - timedelta(hours=24)


# -- A nota viva: carregar sem reescrever -----------------------------------


def test_item_aberto_que_continua_aberto_sai_byte_a_byte_igual(gerar, caminho_do_vault: Path):
    """O conserto do motivo pelo qual o usuário parou de usar: as palavras são dele."""
    escrever_nota_viva(caminho_do_vault, NOTA_DO_USUARIO)
    roteiro = DailyFake(Daily(fazendo=(ItemNovo("Revisar o flow de pix pendente que o Lucas pediu"),)))

    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))], roteiro=roteiro)

    texto = nota_viva(caminho_do_vault).read_bytes().decode("utf-8")
    assert trecho(texto, SECAO_FAZENDO) == (
        trecho(NOTA_DO_USUARIO, SECAO_FAZENDO).rstrip("\n")
        + "\n- Revisar o flow de pix pendente que o Lucas pediu\n"
    )
    assert "\t\t1. Problema A, adicionais de outros itens \n" in texto
    assert "2. Testando no android  \n" in texto


def test_item_movido_chega_em_fiz_byte_a_byte_com_a_subarvore_e_some_de_fazendo(
    gerar, caminho_do_vault: Path
):
    abrir_a_janela(gerar, SEXTA)
    escrever_nota_viva(caminho_do_vault, NOTA_DO_USUARIO)
    roteiro = DailyFake(Daily(mover=(id_na_nota(caminho_do_vault, "Testando"),)))

    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))], roteiro=roteiro)

    texto = nota_viva(caminho_do_vault).read_bytes().decode("utf-8")
    assert trecho(texto, SECAO_FIZ).endswith(
        "1. Planejei e ativei o pix transparente da AppMax no checkout\n2. Testando no android  \n"
    )
    assert "Testando no android" not in trecho(texto, SECAO_FAZENDO)


def test_item_aninhado_movido_leva_o_ancestral_como_cabecalho_literal(gerar, caminho_do_vault: Path):
    abrir_a_janela(gerar, SEXTA)
    escrever_nota_viva(caminho_do_vault, NOTA_DO_USUARIO)
    roteiro = DailyFake(Daily(mover=(id_na_nota(caminho_do_vault, 'Card "A pagar'),)))

    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))], roteiro=roteiro)

    texto = nota_viva(caminho_do_vault).read_bytes().decode("utf-8")
    assert trecho(texto, SECAO_FIZ).endswith(
        "1. Estou fazendo mais correções dos achados do ribeiro\n"
        "\t2. Card \"A pagar agora\" e adicionais do porta-retrato (FN-1784)\n"
        "\t\t1. Problema A, adicionais de outros itens \n"
    )
    assert trecho(texto, SECAO_FAZENDO) == (
        "## O que estou fazendo\n"
        "\n"
        "1. Estou fazendo mais correções dos achados do ribeiro\n"
        "\t1. FN-1786: a foto extra do Porta Retrato não será cobrada de novo no hub.\n"
        "2. Testando no android  \n"
    )


@pytest.mark.parametrize(
    "resposta",
    [
        DAILY_PADRAO,
        Daily(fiz=(ItemNovo("item sob a dúvida", sob="ffffff"),)),
        Daily(mover=("ffffff",)),
    ],
    ids=["resposta normal", "sob um id que não existe", "mover um id que não existe"],
)
def test_duvidas_e_falar_ficam_intactas_seja_qual_for_a_resposta(
    gerar, caminho_do_vault: Path, resposta: Daily
):
    """As seções do usuário são fronteira: o agente lê, e nenhuma escrita as alcança."""
    escrever_nota_viva(caminho_do_vault, NOTA_DO_USUARIO)
    antes = {secao: trecho(NOTA_DO_USUARIO, secao) for secao in (SECAO_DUVIDAS, SECAO_FALAR)}

    gerar(
        agora=momento(SEXTA, 9, 5),
        fontes=[FonteFake("git", (evento(SEXTA, 8),))],
        roteiro=DailyFake(resposta),
    )

    texto = nota_viva(caminho_do_vault).read_bytes().decode("utf-8")
    assert {secao: trecho(texto, secao) for secao in antes} == antes


def test_o_modelo_recebe_a_nota_viva_com_os_ids_e_as_secoes_do_usuario(
    gerar, caminho_do_vault: Path, roteiro: DailyFake
):
    escrever_nota_viva(caminho_do_vault, NOTA_DO_USUARIO)

    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    assert roteiro.nota_recebida is not None
    assert roteiro.nota_recebida.itens(SECAO_FAZENDO)
    assert roteiro.nota_recebida.conteudo(SECAO_DUVIDAS) == ("- o pix pendente expira sozinho?",)
    assert roteiro.nota_recebida.conteudo(SECAO_FALAR) == ("- avisar que sexta eu saio mais cedo",)


def test_rodar_de_novo_na_mesma_janela_nao_duplica_nem_arquiva(gerar, caminho_do_vault: Path):
    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])
    depois_da_primeira = nota_viva(caminho_do_vault).read_text(encoding="utf-8")

    gerar(agora=momento(SEXTA, 17, 30), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    texto = nota_viva(caminho_do_vault).read_text(encoding="utf-8")
    for item in DAILY_PADRAO.fiz:
        assert texto.count(item.texto) == 1
    assert texto.count(ITEM_ABERTO_DE_EXEMPLO) == 1
    assert trecho(texto, SECAO_FIZ) != trecho(depois_da_primeira, SECAO_FIZ), "o fake pediu o movimento"
    assert ITEM_ABERTO_DE_EXEMPLO in trecho(texto, SECAO_FIZ)
    datada = corpo(nota_da_daily(caminho_do_vault, SEXTA))
    assert "## O que eu fiz na daily anterior\n\n_(nada registrado)_\n\n---\n" in datada
    assert datada.count("Daqui para baixo, tudo que a janela trouxe") == 1


def test_janela_nova_arquiva_o_que_eu_fiz_na_nota_datada_e_recomeca(gerar, caminho_do_vault: Path):
    """É o que as dailies à mão mostram: a de hoje não repete a de ontem."""
    gerar(agora=momento(QUINTA, 9, 0), fontes=[FonteFake("git", (evento(QUINTA, 8),))])
    escrever_nota_viva(caminho_do_vault, NOTA_DO_USUARIO)
    roteiro = DailyFake(Daily(fiz=(ItemNovo("Corrigi o toast da reordenação"),)))

    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))], roteiro=roteiro)

    texto = nota_viva(caminho_do_vault).read_bytes().decode("utf-8")
    assert trecho(texto, SECAO_FIZ) == "## O que eu fiz\n- Corrigi o toast da reordenação\n"
    assert trecho(texto, SECAO_FAZENDO) == trecho(NOTA_DO_USUARIO, SECAO_FAZENDO)
    assert (
        "## O que eu fiz na daily anterior\n\n"
        "1. Planejei e ativei o pix transparente da AppMax no checkout\n"
    ) in corpo(nota_da_daily(caminho_do_vault, SEXTA))
    assert "Planejei e ativei o pix" not in corpo(nota_da_daily(caminho_do_vault, QUINTA))


def test_o_arquivo_sobrevive_a_segunda_execucao_do_dia(gerar, caminho_do_vault: Path):
    gerar(agora=momento(QUINTA, 9, 0), fontes=[FonteFake("git", (evento(QUINTA, 8),))])
    escrever_nota_viva(caminho_do_vault, NOTA_DO_USUARIO)
    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    gerar(agora=momento(SEXTA, 17, 30), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    texto = corpo(nota_da_daily(caminho_do_vault, SEXTA))
    assert texto.count("## O que eu fiz na daily anterior") == 1
    assert texto.count("Daqui para baixo, tudo que a janela trouxe") == 1
    assert (
        "## O que eu fiz na daily anterior\n\n"
        "1. Planejei e ativei o pix transparente da AppMax no checkout\n\n---\n"
    ) in texto
    assert "Planejei e ativei" not in nota_viva(caminho_do_vault).read_text(encoding="utf-8")


# -- Degradação graciosa ----------------------------------------------------


def test_fonte_que_falha_deixa_a_daily_nascer_marcada(gerar, caminho_do_vault: Path):
    fontes = [
        FonteFake("git", (evento(SEXTA, 8),)),
        FonteFake("slack", erro=ErroDeFonte("token do Slack ausente em [slack].user_token")),
    ]

    resultado = gerar(agora=momento(SEXTA, 9, 5), fontes=fontes)

    nota = nota_da_daily(caminho_do_vault, SEXTA)
    campos = ler_frontmatter(nota)
    texto = corpo(nota)
    assert campos["fontes"] == ["git"]
    assert campos["fontes_com_falha"] == ["slack"]
    assert "> [!warning] Slack não entrou nesta daily: token do Slack ausente" in texto
    assert "_Não foi possível ler esta fonte: token do Slack ausente" in texto
    assert resultado.fontes_com_falha[0].fonte == "slack"


def test_todas_as_fontes_falhando_nao_escreve_nada(gerar, caminho_do_vault: Path):
    fontes = [
        FonteFake("git", erro=ErroDeFonte("raiz de desenvolvimento não encontrada")),
        FonteFake("linear", erro=ErroDeFonte("HTTP 401 no Linear")),
    ]

    with pytest.raises(TodasAsFontesFalharam) as erro:
        gerar(agora=momento(SEXTA, 9, 5), fontes=fontes)

    assert not nota_da_daily(caminho_do_vault, SEXTA).exists()
    assert "git" in str(erro.value) and "linear" in str(erro.value)


def test_periodo_vazio_nao_vira_nota(gerar, caminho_do_vault: Path):
    resultado = gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", ()), FonteFake("linear", ())])

    assert resultado.vazio is True
    assert resultado.nota is None
    assert not nota_da_daily(caminho_do_vault, SEXTA).exists()


def test_resposta_ilegivel_deixa_a_nota_viva_intacta_e_a_datada_marcada(
    gerar, caminho_do_vault: Path
):
    """Falhar no Claude não custa a nota: nem a viva, nem as listas cruas."""
    arquivo = escrever_nota_viva(caminho_do_vault, NOTA_DO_USUARIO)
    antes = hash_de(arquivo)
    roteiro = DailyFake(erro=ErroDeDaily("o Claude não respondeu a tempo"))

    resultado = gerar(
        agora=momento(SEXTA, 9, 5),
        fontes=[FonteFake("git", (evento(SEXTA, 8, titulo="commit que precisa sobreviver"),))],
        roteiro=roteiro,
    )

    texto = corpo(nota_da_daily(caminho_do_vault, SEXTA))
    assert hash_de(arquivo) == antes
    assert "commit que precisa sobreviver" in texto
    assert "> [!warning] A nota viva ficou como estava: o Claude não respondeu a tempo" in texto
    assert "## Mudanças na nota viva" not in texto
    assert "## O que eu fiz na daily anterior" not in texto
    assert resultado.roteiro is None and resultado.mudancas is None
    assert resultado.falha_do_roteiro == "o Claude não respondeu a tempo"


def test_depois_de_uma_falha_a_reexecucao_arquiva_enfim(gerar, caminho_do_vault: Path):
    """A janela abriu de verdade na primeira execução; a segunda não pode fingir que não."""
    gerar(agora=momento(QUINTA, 9, 0), fontes=[FonteFake("git", (evento(QUINTA, 8),))])
    escrever_nota_viva(caminho_do_vault, NOTA_DO_USUARIO)
    gerar(
        agora=momento(SEXTA, 9, 5),
        fontes=[FonteFake("git", (evento(SEXTA, 8),))],
        roteiro=DailyFake(erro=ErroDeDaily("o Claude não respondeu a tempo")),
    )

    gerar(agora=momento(SEXTA, 9, 20), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    texto = nota_viva(caminho_do_vault).read_text(encoding="utf-8")
    assert "Planejei e ativei" not in trecho(texto, SECAO_FIZ)
    assert "1. Planejei e ativei o pix transparente da AppMax no checkout" in corpo(
        nota_da_daily(caminho_do_vault, SEXTA)
    )


def test_periodo_so_com_o_que_o_fake_ja_conhece_registra_nada_nas_mudancas(
    gerar, caminho_do_vault: Path
):
    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])
    gerar(agora=momento(SEXTA, 12, 0), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    resultado = gerar(agora=momento(SEXTA, 17, 30), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    assert resultado.mudancas is not None and resultado.mudancas.vazia()
    assert "## Mudanças na nota viva\n\n_(nada)_" in corpo(nota_da_daily(caminho_do_vault, SEXTA))


def test_simulacao_nao_escreve_nem_chama_o_claude(
    gerar, caminho_do_vault: Path, roteiro: DailyFake
):
    resultado = gerar(
        agora=momento(SEXTA, 9, 5),
        fontes=[FonteFake("git", (evento(SEXTA, 8),))],
        simular=True,
    )

    assert resultado.simulado is True
    assert resultado.nota is None
    assert resultado.eventos
    assert not nota_da_daily(caminho_do_vault, SEXTA).exists()
    assert roteiro.eventos_recebidos == ()


# -- O filtro de exclusão ---------------------------------------------------


def test_evento_excluido_nao_entra_no_vault_nem_chega_ao_claude(
    gerar, configuracao_do_diario, caminho_do_vault: Path, roteiro: DailyFake
):
    fontes = [
        FonteFake(
            "git",
            (
                evento(SEXTA, 8, titulo="commit do trabalho", referencia="whis"),
                evento(SEXTA, 8, 30, titulo="commit da terapia", referencia="diario-pessoal"),
            ),
        )
    ]

    resultado = gerar(
        agora=momento(SEXTA, 9, 5),
        fontes=fontes,
        configuracao=configuracao_do_diario(excluir=("TERAPIA",)),
    )

    texto = nota_da_daily(caminho_do_vault, SEXTA).read_text(encoding="utf-8")
    assert "terapia" not in texto.casefold()
    assert "commit do trabalho" in texto
    assert resultado.excluidos == 1
    assert [e.titulo for e in roteiro.eventos_recebidos] == ["commit do trabalho"]


# -- Zona de propriedade ----------------------------------------------------


def test_a_daily_escreve_apenas_em_daily(gerar, caminho_do_vault: Path):
    modulo_vault.preparar(caminho_do_vault)
    criar_nota_de_reuniao(caminho_do_vault, "2026-09-04-0830-daily-do-time")
    antes = arquivos_do_vault(caminho_do_vault)

    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    novos = arquivos_do_vault(caminho_do_vault) - antes
    assert novos == {"daily/atual.md", "daily/2026-09-04.md"}


def test_a_nota_viva_so_alcanca_daily(caminho_do_vault: Path, monkeypatch: pytest.MonkeyPatch):
    """Mesmo que alguém mude o caminho, a escrita da nota viva não sai de `daily/`."""
    modulo_vault.preparar(caminho_do_vault)
    monkeypatch.setattr(modulo_vault, "CAMINHO_DA_NOTA_VIVA", "notas/atual.md")

    with pytest.raises(modulo_vault.ForaDaZonaDePropriedade):
        modulo_vault.anotar_ponto(caminho_do_vault, "escrita indevida")

    assert list((caminho_do_vault / "notas").iterdir()) == []


def test_notas_reunioes_e_diario_permanecem_intactos(gerar, caminho_do_vault: Path):
    modulo_vault.preparar(caminho_do_vault)
    ideias = caminho_do_vault / "notas" / "ideias.md"
    ideias.write_text("# Minhas ideias\n", encoding="utf-8")
    diario = caminho_do_vault / "diario" / "2026-09-03.md"
    diario.write_text("# Diário de quinta\n", encoding="utf-8")
    reuniao = criar_nota_de_reuniao(caminho_do_vault, "2026-09-04-0830-daily-do-time")
    conteudo_da_reuniao = reuniao.read_text(encoding="utf-8")

    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    assert ideias.read_text(encoding="utf-8") == "# Minhas ideias\n"
    assert diario.read_text(encoding="utf-8") == "# Diário de quinta\n"
    assert reuniao.read_text(encoding="utf-8") == conteudo_da_reuniao


@pytest.mark.parametrize(
    "destino",
    ["reunioes/roubada.md", "transcricoes/roubada.md", "notas/roubada.md", "diario/roubada.md"],
)
def test_a_zona_da_daily_nao_alcanca_as_outras_pastas(caminho_do_vault: Path, destino: str):
    modulo_vault.preparar(caminho_do_vault)

    with pytest.raises(modulo_vault.ForaDaZonaDePropriedade):
        modulo_vault.escrever(
            caminho_do_vault, destino, "não deveria existir", zonas=modulo_vault.ZONAS_DA_DAILY
        )

    assert not (caminho_do_vault / destino).exists()


@pytest.mark.parametrize("fuga", ["../notas/invadida.md", "../diario/invadida.md"])
def test_traversal_para_fora_da_zona_da_daily_e_recusado(caminho_do_vault: Path, fuga: str):
    modulo_vault.preparar(caminho_do_vault)

    with pytest.raises(modulo_vault.ForaDaZonaDePropriedade):
        modulo_vault.escrever(
            caminho_do_vault, f"daily/{fuga}", "ESCRITA INDEVIDA", zonas=modulo_vault.ZONAS_DA_DAILY
        )

    assert list((caminho_do_vault / "notas").iterdir()) == []
    assert list((caminho_do_vault / "diario").iterdir()) == []


# -- Registro ---------------------------------------------------------------


def test_fonte_que_falha_deixa_o_motivo_no_log(gerar, caplog: pytest.LogCaptureFixture):
    fontes = [
        FonteFake("git", (evento(SEXTA, 8),)),
        FonteFake("slack", erro=ErroDeFonte("token do Slack ausente")),
    ]

    with caplog.at_level("ERROR"):
        gerar(agora=momento(SEXTA, 9, 5), fontes=fontes)

    assert "token do Slack ausente" in caplog.text


def test_o_claude_recebe_as_reunioes_da_janela(
    gerar, caminho_do_vault: Path, roteiro: DailyFake
):
    criar_nota_de_reuniao(caminho_do_vault, "2026-09-04-0830-daily-do-time")

    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    assert roteiro.reunioes_recebidas == ("reunioes/2026-09-04-0830-daily-do-time.md",)


def test_o_resultado_traz_as_seis_secoes_como_ficaram(gerar, caminho_do_vault: Path):
    """É o que o terminal imprime: a nota viva depois da execução, na ordem de falar."""
    abrir_a_janela(gerar, SEXTA)
    escrever_nota_viva(caminho_do_vault, NOTA_DO_USUARIO)
    roteiro = DailyFake(Daily(fiz=(ItemNovo("fechei a camada 07"),)))

    resultado = gerar(
        agora=momento(SEXTA, 9, 5),
        fontes=[FonteFake("git", (evento(SEXTA, 8),))],
        roteiro=roteiro,
    )

    secoes = dict(resultado.secoes)
    assert list(secoes) == [SECAO_FIZ, SECAO_FAZENDO, SECAO_FAZER, SECAO_DUVIDAS, SECAO_PONTOS, SECAO_FALAR]
    assert secoes[SECAO_FIZ] == (
        "1. Planejei e ativei o pix transparente da AppMax no checkout",
        "- fechei a camada 07",
    )
    assert secoes[SECAO_FALAR] == ("- avisar que sexta eu saio mais cedo",)

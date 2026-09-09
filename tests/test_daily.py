"""Comportamento da costura da daily: a janela desde a última fala vira nota.

Nada aqui olha para dentro de `gerar_daily`: os testes leem o vault, como o
usuário leria no Obsidian, e passam `agora` explicitamente — é o relógio que
define a janela, e ele precisa ser controlável para a segunda-feira que cobre o
fim de semana ser testável.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from fixtures.leitura import arquivos_do_vault, corpo, ler_frontmatter
from whis import vault as modulo_vault
from whis.coleta import TodasAsFontesFalharam
from whis.configuracao import Configuracao
from whis.daily import gerar_daily
from whis.fakes import DAILY_PADRAO, DailyFake, FonteFake
from whis.fontes import ErroDeFonte, Evento
from whis.portas import Daily, ErroDeDaily

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


def escrever_pontos(vault: Path, conteudo: str) -> Path:
    """O arquivo da zona do usuário, como ele o deixaria no Obsidian."""
    modulo_vault.preparar(vault)
    arquivo = vault / "notas" / "daily.md"
    arquivo.write_text(conteudo, encoding="utf-8")
    return arquivo


# -- Caminho feliz ----------------------------------------------------------


def test_gerar_daily_escreve_a_nota_do_dia_no_vault(gerar, caminho_do_vault: Path):
    resultado = gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    assert nota_da_daily(caminho_do_vault, SEXTA).is_file()
    assert resultado.nota == nota_da_daily(caminho_do_vault, SEXTA)


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


def test_o_roteiro_vem_da_porta_na_ordem_de_falar(gerar, caminho_do_vault: Path):
    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    texto = corpo(nota_da_daily(caminho_do_vault, SEXTA))
    assert "# Daily — 4 de setembro de 2026 (sexta-feira)" in texto
    for batida in ("## Entreguei", "## Sigo em", "## Preciso de", "## Dúvidas"):
        assert batida in texto
    assert texto.index("## Entreguei") < texto.index("## Sigo em")
    assert texto.index("## Sigo em") < texto.index("## Preciso de")
    assert texto.index("## Preciso de") < texto.index("## Dúvidas")
    for item in (*DAILY_PADRAO.entreguei, *DAILY_PADRAO.sigo_em, *DAILY_PADRAO.preciso_de):
        assert item in texto


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
    assert texto.index("## Entreguei") < texto.index("## Git")


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
    assert len(list((caminho_do_vault / "daily").glob("*.md"))) == 2


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


# -- Os pontos do usuário ---------------------------------------------------


def test_item_desmarcado_entra_e_item_marcado_nao(gerar, caminho_do_vault: Path):
    escrever_pontos(
        caminho_do_vault,
        "# Daily — meus pontos\n\n"
        "## Dúvidas\n- [ ] o link coringa muda para todo mundo?\n"
        "- [x] duvida ja falada\n\n"
        "## Off-topic\n- [ ] staging caiu duas vezes ontem\n\n"
        "## Pontos\n- [ ] quero puxar a retenção de 180 dias\n- [x] ponto ja falado\n",
    )

    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    texto = corpo(nota_da_daily(caminho_do_vault, SEXTA))
    assert "o link coringa muda para todo mundo?" in texto
    assert "staging caiu duas vezes ontem" in texto
    assert "quero puxar a retenção de 180 dias" in texto
    assert "ja falada" not in texto and "ja falado" not in texto


def test_as_duvidas_do_claude_e_as_do_usuario_ficam_na_mesma_secao(
    gerar, caminho_do_vault: Path
):
    escrever_pontos(
        caminho_do_vault, "# Daily\n\n## Dúvidas\n- [ ] dúvida que eu escrevi\n"
    )

    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    texto = corpo(nota_da_daily(caminho_do_vault, SEXTA))
    depois_das_duvidas = texto.split("## Dúvidas", 1)[1]
    assert "dúvida que eu escrevi" in depois_das_duvidas.split("##", 1)[0]
    assert DAILY_PADRAO.duvidas[0] in depois_das_duvidas.split("##", 1)[0]


def test_secao_manual_vazia_nao_aparece(gerar, caminho_do_vault: Path):
    """O roteiro não pode ter buraco para o usuário pular em voz alta."""
    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    texto = corpo(nota_da_daily(caminho_do_vault, SEXTA))
    assert "## Meus pontos" not in texto
    assert "## Off-topic" not in texto


def test_so_um_ponto_do_usuario_ja_faz_a_daily_existir(gerar, caminho_do_vault: Path):
    """O ponto escrito à mão não se recupera de lugar nenhum depois."""
    escrever_pontos(caminho_do_vault, "# Daily\n\n## Pontos\n- [ ] falar da retenção\n")

    resultado = gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", ())])

    assert resultado.vazio is False
    assert "falar da retenção" in corpo(nota_da_daily(caminho_do_vault, SEXTA))


def test_arquivo_de_pontos_ausente_nao_e_erro(gerar, caminho_do_vault: Path):
    resultado = gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    assert resultado.pontos.tem_algo() is False
    assert nota_da_daily(caminho_do_vault, SEXTA).is_file()


def test_gerar_a_daily_nunca_marca_nem_reescreve_os_pontos(gerar, caminho_do_vault: Path):
    """Quem marca é o usuário, no Obsidian, depois de falar."""
    original = "# Daily\n\n## Pontos\n- [ ] ponto por falar\n- [x] ponto ja falado\n"
    arquivo = escrever_pontos(caminho_do_vault, original)

    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    assert arquivo.read_text(encoding="utf-8") == original


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


def test_roteiro_que_falha_ainda_deixa_as_listas_cruas_e_os_pontos(
    gerar, caminho_do_vault: Path
):
    escrever_pontos(caminho_do_vault, "# Daily\n\n## Pontos\n- [ ] meu ponto sobrevive\n")
    roteiro = DailyFake(erro=ErroDeDaily("o Claude não respondeu a tempo"))

    resultado = gerar(
        agora=momento(SEXTA, 9, 5),
        fontes=[FonteFake("git", (evento(SEXTA, 8, titulo="commit que precisa sobreviver"),))],
        roteiro=roteiro,
    )

    texto = corpo(nota_da_daily(caminho_do_vault, SEXTA))
    assert "commit que precisa sobreviver" in texto
    assert "meu ponto sobrevive" in texto
    assert "o Claude não respondeu a tempo" in texto
    assert "## Entreguei" not in texto and "## Preciso de" not in texto
    assert resultado.roteiro is None


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
    escrever_pontos(caminho_do_vault, "# Daily\n\n## Pontos\n- [ ] um ponto\n")
    criar_nota_de_reuniao(caminho_do_vault, "2026-09-04-0830-daily-do-time")
    antes = arquivos_do_vault(caminho_do_vault)

    gerar(agora=momento(SEXTA, 9, 5), fontes=[FonteFake("git", (evento(SEXTA, 8),))])

    novos = arquivos_do_vault(caminho_do_vault) - antes
    assert novos, "o coletor de daily não escreveu nada"
    assert all(arquivo.startswith("daily/") for arquivo in novos), sorted(novos)


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


def test_batida_vazia_do_claude_vira_nada_registrado(gerar, caminho_do_vault: Path):
    """"Nada esperando ninguém" é uma daily boa de ouvir, e precisa ser dita."""
    roteiro = DailyFake(Daily(entreguei=("fechei a camada 07",)))

    gerar(
        agora=momento(SEXTA, 9, 5),
        fontes=[FonteFake("git", (evento(SEXTA, 8),))],
        roteiro=roteiro,
    )

    texto = corpo(nota_da_daily(caminho_do_vault, SEXTA))
    assert "## Preciso de\n\n_(nada registrado)_" in texto

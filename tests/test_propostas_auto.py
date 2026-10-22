"""A proposta automática na 99Freelas: travas em Python, o ensaio que não envia e o envio conferido."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from whis import funil, propostas_auto
from whis.instancia import Trava
from whis.configuracao import ConfiguracaoInvalida, carregar_texto
from whis.navegador_logado import (
    NOVENTA_E_NOVE,
    PAGINAS_DE_CONFERENCIA,
    Preenchimento,
    SemNavegador,
    SessaoLogada,
    ler_99freelas,
    ler_proposta_da_99freelas,
)
from whis.oportunidades import FREELA, Oportunidade
from whis.propostas_auto import (
    ENSAIO,
    LIGADO,
    Contexto,
    Escrita,
    Travas,
    contexto_do_vault,
    problemas_do_texto,
    rodar,
)

FIXTURES = Path(__file__).parent / "fixtures" / "cacada_logada"
AGORA = datetime(2026, 10, 10, 10, 0, tzinfo=timezone(timedelta(hours=-3)))
LINK = "https://www.99freelas.com.br/project/sistema-web-para-gerar-mapas-numerologicos-790517"
FORMULARIO = "https://www.99freelas.com.br/project/bid/sistema-web-para-gerar-mapas-numerologicos-790517"
TEXTO = (
    "Olá, Natacha! Mapa pitagórico e triângulo cabalístico saem de regras fixas, então o cuidado maior é "
    "conferir cada cálculo contra os exemplos que você vai mandar. Eu começaria montando o formulário e o "
    "cálculo do mapa pitagórico, te mostro com três nomes de teste e depois sigo para o triângulo.\n\n"
    "Trabalho com JavaScript e PHP todo dia desde 2023, inclusive em páginas que geram resultado na hora. "
    "Começo no dia seguinte ao aceite, com duas rodadas de revisão incluídas.\n\n"
    "Os exemplos que você tem já vêm com o resultado esperado de cada número?\n\nGabriel"
)
INICIO_E_REVISOES = " Começo no dia seguinte ao aceite, com duas rodadas de revisão incluídas."


def _fixture(nome: str) -> str:
    return (FIXTURES / f"99freelas_{nome}.html").read_text(encoding="utf-8")


def _projeto(propostas: int = 7) -> str:
    return _fixture("aberto").replace("<td>200</td>", f"<td>{propostas}</td>", 1)


def _ja_proposto() -> str:
    return _projeto().replace(">Enviar proposta", ">Melhorar proposta", 1)


def _formulario(restantes: int = 14) -> str:
    return _fixture("bid").replace("<b>14 conexões</b>", f"<b>{restantes} conexões</b>", 1)


def _freela(
    link: str = LINK,
    *,
    titulo: str = "Sistema web para gerar mapas numerológicos",
    horas: float = 14,
    propostas: int = 7,
    detalhes: str = "",
    descricao: str = "Cálculo numerológico personalizado com formulário de nome e data de nascimento.",
) -> Oportunidade:
    return Oportunidade.nova(
        tipo=FREELA, fonte="99Freelas", titulo=titulo, link=link, publicada=AGORA - timedelta(hours=horas),
        descricao=descricao, detalhes=detalhes or f"Desenvolvimento Web | Intermediário | Propostas: {propostas} | Interessados: 9",
    )


class SessaoFake(SessaoLogada):
    def __init__(self, paginas: dict[str, str], *, depois_de_enviar: dict[str, str] | None = None) -> None:
        super().__init__()
        self.paginas = dict(paginas)
        self.depois_de_enviar = depois_de_enviar or {}
        self.visitadas: list[str] = []
        self.preenchidos: list[tuple[str, int, int, str, bool]] = []

    def html(self, url: str) -> str:
        self.visitadas.append(url)
        if url not in self.paginas:
            raise SemNavegador(f"fora do fake: {url}")
        return self.paginas[url]

    def preencher_proposta_da_99freelas(self, url, *, oferta, dias, texto, enviar, pasta_das_fotos=None):
        self.preenchidos.append((url, oferta, dias, texto, enviar))
        if enviar:
            self.paginas.update(self.depois_de_enviar)
        return Preenchimento(oferta=f"{oferta},00", dias=str(dias), caracteres=len(texto), enviada=enviar)


def _logada(projeto: str | None = None, formulario: str | None = None, **opcoes) -> SessaoFake:
    return SessaoFake(
        {
            PAGINAS_DE_CONFERENCIA[NOVENTA_E_NOVE]: _fixture("aberto"),
            LINK: projeto if projeto is not None else _projeto(),
            FORMULARIO: formulario if formulario is not None else _formulario(),
        },
        **opcoes,
    )


@dataclass
class EscritorFake:
    respostas: list[Escrita] = field(default_factory=lambda: [Escrita(entrega=True, motivo="dá", texto=TEXTO, prazo_dias=3, preco=50)])
    pedidos: list[tuple[str, str, str]] = field(default_factory=list)
    contextos: list[Contexto] = field(default_factory=list)

    def escrever(self, oportunidade, pagina, contexto, *, corrigir=""):
        self.pedidos.append((oportunidade.link, pagina, corrigir))
        self.contextos.append(contexto)
        return self.respostas[min(len(self.pedidos), len(self.respostas)) - 1]


CONTEXTO = Contexto(procuro="Freela por projeto.", sobre_mim="- Anos: 3", perfil="Full stack.", portfolio=(), exemplos=())


class CelularFake(list):
    """As mensagens que iriam ao Telegram, e os botões de cada uma em `botoes`."""

    def __init__(self) -> None:
        super().__init__()
        self.botoes: list[tuple[tuple[str, str], ...]] = []

    def __call__(self, texto: str, *, botoes=()) -> bool:
        self.append(texto)
        self.botoes.append(tuple(botoes))
        return True


def _rodar(
    tmp_path: Path,
    oportunidades,
    *,
    modo: str = ENSAIO,
    sessao: SessaoLogada | None = None,
    escritor: EscritorFake | None = None,
    travas: Travas | None = None,
    agora: datetime = AGORA,
    publica=None,
    contexto: Contexto = CONTEXTO,
    medir=None,
):
    celular = CelularFake()
    escritor = escritor or EscritorFake()
    rodada = rodar(
        list(oportunidades),
        modo=modo,
        travas=travas or Travas(),
        vault=tmp_path / "vault",
        escritor=escritor,
        contexto=contexto,
        sessao=sessao,
        publica=publica or (lambda url: (_ for _ in ()).throw(AssertionError(f"página pública pedida: {url}"))),
        estado=tmp_path / "propostas-auto.json",
        celular=celular,
        agora=agora,
        dormir=lambda _segundos: None,
        medir=medir or (lambda _texto: None),
    )
    return rodada, celular, escritor


def _nota(tmp_path: Path) -> str:
    return (tmp_path / "vault" / "cacada" / "propostas-auto" / "sistema-web-para-gerar-mapas-numerologicos-790517.md").read_text(
        encoding="utf-8"
    )


# -- os leitores das páginas -------------------------------------------------------------------


def test_a_pagina_do_projeto_diz_orcamento_valor_minimo_data_e_cliente():
    pagina = ler_99freelas(_fixture("aberto"))

    assert (pagina.orcamento, pagina.valor_minimo, pagina.cliente) == ("Aberto", 50, "Natacha")
    assert pagina.publicada == datetime(2026, 10, 9, 19, 32)


def test_o_formulario_diz_a_oferta_minima():
    assert ler_proposta_da_99freelas(_fixture("bid")).oferta_minima == 50


# -- o ensaio ---------------------------------------------------------------------------------------


def test_o_ensaio_escreve_a_nota_preenche_sem_clicar_e_avisa_no_celular(tmp_path: Path):
    sessao = _logada()

    rodada, celular, escritor = _rodar(tmp_path, [_freela()], sessao=sessao)

    [resultado] = rodada.resultados
    assert resultado.situacao == propostas_auto.NO_ENSAIO and resultado.preco == 50 and resultado.prazo_dias == 3
    assert sessao.preenchidos == [(FORMULARIO, 50, 3, TEXTO, False)]
    nota = _nota(tmp_path)
    assert "status: ensaio em 2026-10-10 (R$ 50, 3 dias)" in nota and 'preco: "R$ 50"' in nota and TEXTO in nota
    [mensagem] = celular
    assert mensagem.startswith("Ensaio: esta proposta sairia agora na 99Freelas (1 de 3 hoje)")
    assert "Sistema web para gerar mapas numerológicos" in mensagem and "Orçamento: Aberto" in mensagem
    assert "7 propostas até agora" in mensagem and "R$ 50 em 3 dias" in mensagem and LINK in mensagem and TEXTO in mensagem
    assert "Natacha" in escritor.pedidos[0][1]
    assert funil.ler_mandadas(tmp_path / "vault") == []


def test_o_ensaio_deslogado_le_a_pagina_publica_e_nao_preenche(tmp_path: Path):
    publicas: list[str] = []

    def publica(url: str) -> str:
        publicas.append(url)
        return _projeto().replace("header-menu-logged", "header-menu")

    rodada, celular, _ = _rodar(tmp_path, [_freela()], sessao=None, publica=publica)

    assert [r.situacao for r in rodada.resultados] == [propostas_auto.NO_ENSAIO]
    assert publicas == [LINK] and rodada.resultados[0].preco == 50
    assert len(celular) == 1


# -- o envio ----------------------------------------------------------------------------------------


def test_ligado_envia_e_so_grava_enviada_depois_do_melhorar_proposta(tmp_path: Path):
    sessao = _logada(depois_de_enviar={LINK: _ja_proposto()})

    rodada, celular, _ = _rodar(tmp_path, [_freela()], modo=LIGADO, sessao=sessao)

    assert [r.situacao for r in rodada.resultados] == [propostas_auto.ENVIADA]
    assert sessao.preenchidos[0][-1] is True
    assert "status: enviada em 2026-10-10 (R$ 50, 3 dias)" in _nota(tmp_path)
    assert celular[0].startswith("Proposta enviada na 99Freelas (1 de 3 hoje)")
    [mandada] = funil.ler_mandadas(tmp_path / "vault")
    assert mandada.link == LINK and mandada.esperando


def test_sem_confirmacao_vira_incerta_avisa_e_nunca_reenvia(tmp_path: Path):
    sessao = _logada()

    rodada, celular, _ = _rodar(tmp_path, [_freela()], modo=LIGADO, sessao=sessao)
    _rodar(tmp_path, [_freela()], modo=LIGADO, sessao=sessao)

    assert [r.situacao for r in rodada.resultados] == [propostas_auto.INCERTA]
    assert len(sessao.preenchidos) == 1
    assert "confira" in celular[0] and LINK in celular[0]
    assert "status: incerta" in _nota(tmp_path)


def test_ligado_deslogado_nao_envia_e_avisa_uma_vez_por_dia(tmp_path: Path):
    sessao = SessaoFake({PAGINAS_DE_CONFERENCIA[NOVENTA_E_NOVE]: _fixture("deslogado"), LINK: _projeto()})

    rodada, celular, escritor = _rodar(tmp_path, [_freela()], modo=LIGADO, sessao=sessao)
    _, de_novo, _ = _rodar(tmp_path, [_freela()], modo=LIGADO, sessao=sessao)

    assert rodada.resultados == () and "deslogado" in rodada.parou
    assert escritor.pedidos == [] and sessao.preenchidos == []
    assert len(celular) == 1 and "whis navegador" in celular[0] and de_novo == []


# -- as travas --------------------------------------------------------------------------------------


def test_velho_cheio_de_propostas_ou_exclusivo_nem_abre_a_pagina(tmp_path: Path):
    sessao = _logada()
    velho = _freela("https://www.99freelas.com.br/project/velho-1", horas=50)
    cheio = _freela("https://www.99freelas.com.br/project/cheio-2", propostas=80)
    exclusivo = _freela(
        "https://www.99freelas.com.br/project/exclusivo-3",
        detalhes="Projeto exclusivo para assinantes da 99Freelas: abre para quem não assina em 11/10 às 08:00 | Propostas: 0",
    )
    do_freelancer = Oportunidade.nova(
        tipo=FREELA, fonte="Freelancer.com", titulo="Shopify", link="https://www.freelancer.com/projects/shopify/x", detalhes="Propostas: 1"
    )

    rodada, celular, escritor = _rodar(tmp_path, [velho, cheio, exclusivo, do_freelancer], sessao=sessao)

    assert rodada.resultados == () and escritor.pedidos == [] and sessao.visitadas == [] and celular == []


def test_as_horas_contam_de_quando_o_projeto_abre_para_quem_nao_assina(tmp_path: Path):
    aberto_ha_pouco = _freela("https://www.99freelas.com.br/project/aberto-1", horas=40)
    aberto_ha_muito = _freela("https://www.99freelas.com.br/project/aberto-2", horas=49)
    sessao = SessaoFake({PAGINAS_DE_CONFERENCIA[NOVENTA_E_NOVE]: _fixture("aberto")})

    candidatos = propostas_auto._candidatos(
        [aberto_ha_pouco, aberto_ha_muito], Travas(), propostas_auto._Estado(tmp_path / "e.json"), tmp_path / "vault", AGORA, ""
    )
    assinante = propostas_auto._candidatos(
        [aberto_ha_pouco], Travas(exclusivos=True), propostas_auto._Estado(tmp_path / "e.json"), tmp_path / "vault", AGORA, ""
    )

    assert [o.link for o in candidatos] == [aberto_ha_pouco.link] and assinante == [] and sessao.visitadas == []


def test_a_pagina_confere_de_novo_as_propostas(tmp_path: Path):
    sessao = _logada(projeto=_projeto(propostas=85))

    rodada, _, escritor = _rodar(tmp_path, [_freela(propostas=3)], sessao=sessao)

    assert rodada.resultados == () and escritor.pedidos == []


def test_ja_proposto_na_pagina_e_pulado_sem_claude(tmp_path: Path):
    rodada, _, escritor = _rodar(tmp_path, [_freela()], sessao=_logada(projeto=_ja_proposto()))

    assert [(r.situacao, r.motivo) for r in rodada.resultados] == [(propostas_auto.PULADA, "você já propôs")]
    assert escritor.pedidos == []


def test_ja_mandada_no_vault_nem_abre_a_pagina(tmp_path: Path):
    pasta = tmp_path / "vault" / "cacada" / "2026-10-12-1832-propostas"
    pasta.mkdir(parents=True)
    (pasta / "mapas.md").write_text(f"---\nplataforma: 99Freelas\nlink: {LINK}\nstatus: enviada em 2026-10-09 (R$ 50, 2 dias)\n---\n\nOlá!\n", encoding="utf-8")
    sessao = _logada()

    rodada, _, escritor = _rodar(tmp_path, [_freela()], sessao=sessao)

    assert rodada.resultados == () and escritor.pedidos == [] and sessao.visitadas == []


def test_no_maximo_tantas_por_dia_e_o_dia_seguinte_libera(tmp_path: Path):
    outro = "https://www.99freelas.com.br/project/landing-page-de-advocacia-790999"
    sessao = _logada()
    sessao.paginas[outro] = (
        _projeto()
        .replace("sistema-web-para-gerar-mapas-numerologicos-790517", "landing-page-de-advocacia-790999")
        .replace("09/10/2026 às 19:32", "10/10/2026 às 23:30")
    )
    sessao.paginas[outro.replace("/project/", "/project/bid/")] = _formulario()
    travas = Travas(por_dia=1)

    primeira, _, _ = _rodar(tmp_path, [_freela(), _freela(outro)], sessao=sessao, travas=travas)
    mesmo_dia, _, escritor = _rodar(tmp_path, [_freela(outro)], sessao=sessao, travas=travas, agora=AGORA + timedelta(hours=1))
    amanha, _, _ = _rodar(tmp_path, [_freela(outro, horas=1)], sessao=sessao, travas=travas, agora=AGORA + timedelta(hours=16))

    assert len(primeira.resultados) == 1 and "cota" in primeira.parou
    assert mesmo_dia.resultados == () and escritor.pedidos == []
    assert [r.link for r in amanha.resultados] == [outro]


def test_conexoes_abaixo_da_reserva_param_antes_do_claude_com_um_aviso_por_dia(tmp_path: Path):
    sessao = _logada(formulario=_formulario(restantes=2))

    rodada, celular, escritor = _rodar(tmp_path, [_freela()], sessao=sessao)
    _, de_novo, _ = _rodar(tmp_path, [_freela()], sessao=sessao)

    assert rodada.resultados == () and "conexões" in rodada.parou and escritor.pedidos == []
    assert len(celular) == 1 and "2 conexões" in celular[0] and de_novo == []


def test_o_que_ele_nao_entrega_fica_guardado_e_nao_volta_ao_claude(tmp_path: Path):
    escritor = EscritorFake(respostas=[Escrita(entrega=False, motivo="é vídeo com avatar, não é desenvolvimento")])

    rodada, celular, _ = _rodar(tmp_path, [_freela()], sessao=_logada(), escritor=escritor)
    _rodar(tmp_path, [_freela()], sessao=_logada(), escritor=escritor)

    assert [r.situacao for r in rodada.resultados] == [propostas_auto.NAO_ENTREGA]
    assert len(escritor.pedidos) == 1 and celular == []


def test_texto_com_problema_volta_uma_vez_ao_claude_com_o_motivo(tmp_path: Path):
    ruim = Escrita(entrega=True, motivo="dá", texto=TEXTO.replace("Gabriel", "Gabriel\ngabriel@exemplo.com"), prazo_dias=3, preco=50)
    escritor = EscritorFake(respostas=[ruim, Escrita(entrega=True, motivo="dá", texto=TEXTO, prazo_dias=3, preco=50)])

    rodada, _, _ = _rodar(tmp_path, [_freela()], sessao=_logada(), escritor=escritor)

    assert [r.situacao for r in rodada.resultados] == [propostas_auto.NO_ENSAIO]
    assert escritor.pedidos[0][2] == "" and "e-mail" in escritor.pedidos[1][2]


def test_texto_que_continua_com_problema_e_pulado(tmp_path: Path):
    ruim = Escrita(entrega=True, motivo="dá", texto=TEXTO + " Valor: R$ 50.", prazo_dias=3, preco=50)

    rodada, celular, _ = _rodar(tmp_path, [_freela()], sessao=_logada(), escritor=EscritorFake(respostas=[ruim]))

    [resultado] = rodada.resultados
    assert resultado.situacao == propostas_auto.PULADA and "preço" in resultado.motivo and celular == []


def test_o_texto_do_claude_sem_pergunta_no_fim_sem_revisoes_ou_sem_inicio_volta_com_o_motivo(tmp_path: Path):
    sem_nada = TEXTO.replace(INICIO_E_REVISOES, "").replace("de cada número?", "de cada número.")
    escritor = EscritorFake(
        respostas=[Escrita(entrega=True, motivo="dá", texto=sem_nada, prazo_dias=3, preco=50), EscritorFake().respostas[0]]
    )

    rodada, _, _ = _rodar(tmp_path, [_freela()], sessao=_logada(), escritor=escritor)

    assert [r.situacao for r in rodada.resultados] == [propostas_auto.NO_ENSAIO]
    motivo = escritor.pedidos[1][2]
    assert "pergunta" in motivo and "revisões" in motivo and "quando começa" in motivo


def test_o_texto_do_claude_com_mais_de_250_palavras_volta(tmp_path: Path):
    longo = TEXTO.replace("Os exemplos", "palavra " * 200 + "Os exemplos")
    escritor = EscritorFake(respostas=[Escrita(entrega=True, motivo="dá", texto=longo, prazo_dias=3, preco=50)])

    rodada, _, _ = _rodar(tmp_path, [_freela()], sessao=_logada(), escritor=escritor)

    [resultado] = rodada.resultados
    assert resultado.situacao == propostas_auto.PULADA and "250 palavras" in resultado.motivo


def test_sem_loja_medida_o_texto_nao_pode_dizer_o_que_viu_na_loja(tmp_path: Path):
    inventado = TEXTO.replace("Olá, Natacha! ", "Olá, Natacha! Abri a sua loja e o PageSpeed deu 34 no celular. ")
    escritor = EscritorFake(respostas=[Escrita(entrega=True, motivo="dá", texto=inventado, prazo_dias=3, preco=50)])

    rodada, _, _ = _rodar(tmp_path, [_freela()], sessao=_logada(), escritor=escritor)

    [resultado] = rodada.resultados
    assert resultado.situacao == propostas_auto.PULADA and "o Whis não mediu a loja" in resultado.motivo
    do_portfolio = TEXTO.replace("todo dia", "todo dia, e no meu portfólio medi o PageSpeed antes e depois")
    assert propostas_auto.problemas_do_jeito(do_portfolio, CONTEXTO) == []
    aceite_antes = TEXTO.replace("Começo no dia seguinte ao aceite", "Depois do aceite, começo no mesmo dia")
    assert propostas_auto.problemas_do_jeito(aceite_antes, CONTEXTO) == []


def test_a_loja_do_anuncio_e_medida_e_vai_ao_claude(tmp_path: Path):
    from whis.loja_do_cliente import Loja

    loja = Loja(endereco="lojadamaria.com.br", segundos=2.8, kb=410, scripts=37, tema="Dawn 9.0.0")
    medidos: list[str] = []
    abertura = TEXTO.replace("Olá, Natacha! ", "Olá, Natacha! Abri a lojadamaria.com.br: a página inicial carrega 37 scripts. ")
    escritor = EscritorFake(respostas=[Escrita(entrega=True, motivo="dá", texto=abertura, prazo_dias=3, preco=50)])
    projeto = _freela(descricao="Ajustar o carrinho da minha loja lojadamaria.com.br, tema Dawn.")

    rodada, _, _ = _rodar(
        tmp_path, [projeto], sessao=_logada(), escritor=escritor, medir=lambda texto: medidos.append(texto) or loja
    )

    assert [r.situacao for r in rodada.resultados] == [propostas_auto.NO_ENSAIO] and len(escritor.pedidos) == 1
    [medido] = medidos
    assert "lojadamaria.com.br" in medido and "sistema de cálculo numerológico" in medido
    assert "Valor Mínimo" not in medido and "Propostas (199)" not in medido
    assert escritor.contextos[0].loja == loja


def test_o_pedido_ao_claude_traz_a_loja_medida_e_o_jeito_novo():
    from whis.loja_do_cliente import Loja
    from whis.propostas_auto_claude import SISTEMA_DA_PROPOSTA, pedido

    loja = Loja(endereco="lojadamaria.com.br", segundos=2.8, kb=410, scripts=37, tema="Dawn 9.0.0", com_senha=True)
    contexto = Contexto(procuro="", sobre_mim="", perfil="", portfolio=(), exemplos=(), loja=loja)

    com_loja = pedido(_freela(), "", contexto)
    sem_loja = pedido(_freela(), "", CONTEXTO)

    assert "LOJA DO CLIENTE" in com_loja and "37 scripts" in com_loja and "2,8 s" in com_loja and "fechada com senha" in com_loja
    assert "LOJA DO CLIENTE" not in sem_loja
    assert "250 palavras" in SISTEMA_DA_PROPOSTA and "10 segundos" in SISTEMA_DA_PROPOSTA
    assert "aceite" in SISTEMA_DA_PROPOSTA and "2 rodadas de revisão" in SISTEMA_DA_PROPOSTA and "UTC−3" in SISTEMA_DA_PROPOSTA


def test_a_conferencia_do_texto():
    projeto = _freela()
    portfolio = contexto_do_portfolio()

    assert problemas_do_texto(TEXTO, projeto, "", portfolio) == []
    editado_por_ele = TEXTO.replace(INICIO_E_REVISOES, "").replace("de cada número?", "de cada número.")
    assert problemas_do_texto(editado_por_ele, projeto, "", portfolio) == []
    com_link = TEXTO.replace("todo dia", "todo dia (https://github.com/bielvelozo/inkly-shopify-theme)")
    assert problemas_do_texto(com_link, projeto, "", portfolio) == []
    assert "link fora do portfólio" in problemas_do_texto(TEXTO + " https://meusite.com.br", projeto, "", portfolio)[0]
    assert "telefone" in problemas_do_texto(TEXTO + " (16) 99123-4567", projeto, "", portfolio)[0]
    assert "IA" in problemas_do_texto(TEXTO.replace("todo dia", "com IA todo dia"), projeto, "", portfolio)[0]
    com_ia = _freela(titulo="Criação de gêmeo digital com HeyGen e IA")
    assert problemas_do_texto(TEXTO.replace("todo dia", "com IA todo dia"), com_ia, "", portfolio) == []
    assert "3000" in problemas_do_texto("a" * 3001, projeto, "", portfolio)[0]


def contexto_do_portfolio():
    from whis.criterios_da_cacada import PecaDoPortfolio

    return (PecaDoPortfolio("Tema Shopify Inkly", "https://github.com/bielvelozo/inkly-shopify-theme", "tema"),)


# -- o resumo e o contexto ------------------------------------------------------------------------


def test_o_resumo_do_dia_lista_o_que_saiu(tmp_path: Path):
    escritor = EscritorFake(respostas=[Escrita(entrega=True, motivo="dá", texto=TEXTO, prazo_dias=3, preco=50)])
    _rodar(tmp_path, [_freela()], sessao=_logada(), escritor=escritor)

    resumo = (tmp_path / "vault" / "cacada" / "propostas-auto.md").read_text(encoding="utf-8")

    assert "## 10/10/2026 (sábado)" in resumo
    assert "ensaio" in resumo and "[Sistema web para gerar mapas numerológicos](" in resumo and "R$ 50 em 3 dias" in resumo
    assert "[[cacada/propostas-auto/sistema-web-para-gerar-mapas-numerologicos-790517|nota]]" in resumo


def test_o_contexto_usa_as_propostas_que_deram_certo_como_exemplo(tmp_path: Path):
    vault = tmp_path / "vault"
    pasta = vault / "cacada" / "2026-10-12-1832-propostas"
    pasta.mkdir(parents=True)
    (vault / "cacada" / "criterios.md").write_text("## O que eu procuro\n\n- Freela.\n\n## Sobre mim\n\n- Anos: 3\n", encoding="utf-8")
    (vault / "cacada" / "perfil-freelas.md").write_text("---\ntipo: perfil-da-cacada\n---\n\nFaz Shopify.\n", encoding="utf-8")
    for nome, status in (("a", "enviada em 2026-10-13 (R$ 50, 7 dias)"), ("b", "respondida em 2026-10-17 (R$ 50, 2 dias)"), ("c", "escrita")):
        (pasta / f"{nome}.md").write_text(
            f"---\nplataforma: 99Freelas\nlink: https://www.99freelas.com.br/project/{nome}-1\nstatus: {status}\n---\n\nOlá! Texto {nome}.\n\nGabriel\n",
            encoding="utf-8",
        )

    contexto = contexto_do_vault(vault, "shopify", valor_hora=45)
    assert contexto.valor_hora == 45

    assert contexto.exemplos[0].startswith("Olá! Texto b.") and len(contexto.exemplos) == 2
    assert "Faz Shopify." in contexto.perfil and "Freela." in contexto.procuro


# -- a configuração ----------------------------------------------------------------------------------


def test_a_vigia_roda_de_hora_em_hora_e_o_envio_nasce_desligado(tmp_path: Path):
    configuracao = carregar_texto(f'vault = "{tmp_path.as_posix()}"\n', origem=tmp_path / "config.toml")

    assert configuracao.cacada_horarios_da_vigia_de_freelas == tuple(f"{hora:02d}:00" for hora in range(7, 24))
    assert configuracao.cacada_propostas_auto == "desligado"
    assert Travas.da_configuracao(configuracao) == Travas(horas=24, max_propostas=40, por_dia=3, reserva=3, exclusivos=False, para_aprovar=5)
    assert configuracao.cacada_propostas_auto_valor_hora == 40


def test_modo_desconhecido_e_erro_de_configuracao(tmp_path: Path):
    with pytest.raises(ConfiguracaoInvalida, match="propostas_auto"):
        carregar_texto(f'vault = "{tmp_path.as_posix()}"\n[cacada]\npropostas_auto = "sim"\n', origem=tmp_path / "config.toml")


def test_o_estado_guarda_o_que_aconteceu_com_cada_projeto(tmp_path: Path):
    _rodar(tmp_path, [_freela()], sessao=_logada())

    estado = json.loads((tmp_path / "propostas-auto.json").read_text(encoding="utf-8"))

    assert estado["projetos"][LINK]["situacao"] == propostas_auto.NO_ENSAIO


# -- o Claude -----------------------------------------------------------------------------------------


def _claude_gravado(dados: dict):
    from claude_agent_sdk import ResultMessage

    from whis.propostas_auto_claude import PropostaClaude

    class Gravado(PropostaClaude):
        prompts: list[str] = []

        async def _mensagens(self, prompt, opcoes):
            Gravado.prompts.append(prompt)
            yield ResultMessage(
                subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1, session_id="s",
                total_cost_usd=0.01, structured_output=dados,
            )

    return Gravado()


def test_o_claude_le_os_exemplos_o_portfolio_e_o_motivo_da_correcao():
    claude = _claude_gravado(
        {"entrega": True, "motivo": "dá", "proposta": TEXTO, "prazo_dias": 4, "preco": 900, "preco_motivo": "uns R$ 1.100 no mercado"}
    )
    contexto = Contexto(
        procuro="Freela.",
        sobre_mim="- Anos: 3",
        perfil="Full stack.",
        portfolio=contexto_do_portfolio(),
        exemplos=("Olá! Exemplo.",),
        valor_hora=55,
    )

    escrita = claude.escrever(_freela(), "Cliente: Natacha", contexto, corrigir="tem e-mail")

    assert escrita == Escrita(entrega=True, motivo="dá", texto=TEXTO, prazo_dias=4, preco=900, motivo_do_preco="uns R$ 1.100 no mercado")
    [prompt] = type(claude).prompts
    assert "Olá! Exemplo." in prompt and "https://github.com/bielvelozo/inkly-shopify-theme" in prompt
    assert "Cliente: Natacha" in prompt and "RECUSADA NA CONFERÊNCIA POR: tem e-mail" in prompt
    assert "VALOR DA HORA DELE: R$ 55" in prompt


def test_o_claude_que_diz_que_nao_entrega_volta_sem_texto():
    claude = _claude_gravado({"entrega": False, "motivo": "é edição de vídeo", "proposta": "Olá!", "prazo_dias": 0})

    escrita = claude.escrever(_freela(), "", CONTEXTO)

    assert (escrita.entrega, escrita.texto, escrita.motivo) == (False, "", "é edição de vídeo")


def test_o_claude_roda_mesmo_com_o_loop_do_playwright_aberto_na_thread():
    import asyncio

    claude = _claude_gravado({"entrega": True, "motivo": "dá", "proposta": TEXTO, "prazo_dias": 4})

    async def com_loop_rodando():
        return claude.escrever(_freela(), "", CONTEXTO)

    assert asyncio.run(com_loop_rodando()).texto == TEXTO


def test_logado_a_bandeira_de_exclusivo_de_outro_projeto_no_cabecalho_nao_barra(tmp_path: Path):
    cabecalho = '<li class="novo-projeto-item" data-id="1"><i class="flat_project_exclusive"></i>Outro projeto</li>'
    sessao = _logada(projeto=_projeto().replace("<body", f"<body><ul>{cabecalho}</ul", 1) if "<body" in _projeto() else cabecalho + _projeto())

    rodada, _, _ = _rodar(tmp_path, [_freela()], sessao=sessao)

    assert [r.situacao for r in rodada.resultados] == [propostas_auto.NO_ENSAIO]


def test_logado_quem_diz_exclusivo_e_o_formulario(tmp_path: Path):
    rodada, _, escritor = _rodar(tmp_path, [_freela()], sessao=_logada(formulario=_fixture("bid_exclusivo")))

    assert rodada.resultados == () and escritor.pedidos == []


def test_sem_login_a_bandeira_da_pagina_barra_o_exclusivo(tmp_path: Path):
    rodada, _, escritor = _rodar(
        tmp_path, [_freela()], sessao=None, publica=lambda _url: '<i class="flat_project_exclusive"></i>' + _projeto()
    )

    assert rodada.resultados == () and escritor.pedidos == []


# -- o botão Enviar no celular ---------------------------------------------------------------------

OUTRO = "https://www.99freelas.com.br/project/landing-page-de-advocacia-790999"
BOTAO = ((propostas_auto.ROTULO_DO_BOTAO, propostas_auto.chave_do_toque(LINK)),)


def _com_outro(sessao: SessaoFake, *, propostas: int = 7) -> SessaoFake:
    sessao.paginas[OUTRO] = (
        _projeto(propostas)
        .replace("sistema-web-para-gerar-mapas-numerologicos-790517", "landing-page-de-advocacia-790999")
        .replace("09/10/2026 às 19:32", "08/10/2026 às 23:30")
    )
    sessao.paginas[propostas_auto.formulario_da_proposta(OUTRO)] = _formulario()
    return sessao


def _tocar(tmp_path: Path, sessao: SessaoLogada, *, dados: str | None = None, agora: datetime = AGORA + timedelta(hours=1), **opcoes):
    return propostas_auto.tocou_enviar(
        dados if dados is not None else propostas_auto.chave_do_toque(LINK),
        abrir_sessao=lambda: sessao,
        vault=tmp_path / "vault",
        estado=tmp_path / "propostas-auto.json",
        travas=opcoes.pop("travas", Travas()),
        modo=opcoes.pop("modo", ENSAIO),
        trava=tmp_path / propostas_auto.NOME_DA_TRAVA,
        agora=agora,
        dormir=lambda _segundos: None,
        **opcoes,
    )


def _estado(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "propostas-auto.json").read_text(encoding="utf-8"))["projetos"]


def test_a_chave_do_botao_cabe_no_limite_do_telegram():
    chave = propostas_auto.chave_do_toque(LINK)

    assert chave.startswith(propostas_auto.PREFIXO_DO_TOQUE) and len(chave.encode()) <= 64
    assert chave == propostas_auto.chave_do_toque(LINK) != propostas_auto.chave_do_toque(OUTRO)


def test_o_ensaio_chega_no_celular_com_o_botao_enviar(tmp_path: Path):
    _, celular, _ = _rodar(tmp_path, [_freela()], sessao=_logada())

    assert celular.botoes == [BOTAO]


def test_a_enviada_sozinha_chega_sem_botao(tmp_path: Path):
    _, celular, _ = _rodar(tmp_path, [_freela()], modo=LIGADO, sessao=_logada(depois_de_enviar={LINK: _ja_proposto()}))

    assert celular.botoes == [()]


def test_com_a_cota_cheia_a_proxima_chega_escrita_para_aprovar_sem_clique(tmp_path: Path):
    sessao = _com_outro(_logada(depois_de_enviar={LINK: _ja_proposto()}))

    rodada, celular, _ = _rodar(
        tmp_path, [_freela(), _freela(OUTRO, propostas=9)], modo=LIGADO, sessao=sessao, travas=Travas(por_dia=1, para_aprovar=2)
    )

    assert [r.situacao for r in rodada.resultados] == [propostas_auto.ENVIADA, propostas_auto.PARA_APROVAR]
    assert [p[0] for p in sessao.preenchidos] == [FORMULARIO]
    assert celular[1].startswith("Para você aprovar: a cota automática de hoje (1) acabou.")
    assert TEXTO in celular[1] and "R$ 50 em 3 dias" in celular[1] and OUTRO in celular[1]
    assert celular.botoes[1] == ((propostas_auto.ROTULO_DO_BOTAO, propostas_auto.chave_do_toque(OUTRO)),)
    nota = (tmp_path / "vault" / "cacada" / "propostas-auto" / "landing-page-de-advocacia-790999.md").read_text(encoding="utf-8")
    assert "status: para aprovar em 2026-10-10 (R$ 50, 3 dias)" in nota
    assert [m.link for m in funil.ler_mandadas(tmp_path / "vault")] == [LINK]


def test_projeto_com_propostas_demais_nunca_sai_sozinho_mas_chega_para_aprovar(tmp_path: Path):
    sessao = _logada(projeto=_projeto(45))

    rodada, celular, _ = _rodar(tmp_path, [_freela(propostas=45)], modo=LIGADO, sessao=sessao, travas=Travas(para_aprovar=1))

    assert [r.situacao for r in rodada.resultados] == [propostas_auto.PARA_APROVAR]
    assert sessao.preenchidos == []
    assert celular[0].startswith("Para você aprovar: tem 45 propostas, e o automático só manda abaixo de 40.")


def test_conexoes_na_reserva_mandam_para_aprovar_em_vez_de_parar(tmp_path: Path):
    sessao = _logada(formulario=_formulario(restantes=2))

    rodada, celular, _ = _rodar(tmp_path, [_freela()], modo=LIGADO, sessao=sessao, travas=Travas(para_aprovar=1))

    assert [r.situacao for r in rodada.resultados] == [propostas_auto.PARA_APROVAR]
    assert sessao.preenchidos == []
    assert len(celular) == 1 and celular[0].startswith("Para você aprovar: sobrariam 2 conexões, e a reserva é 3.")


def test_a_fila_para_aprovar_tem_teto_por_dia(tmp_path: Path):
    sessao = _com_outro(_logada())

    rodada, _, escritor = _rodar(
        tmp_path, [_freela(), _freela(OUTRO)], modo=LIGADO, sessao=sessao, travas=Travas(por_dia=0, para_aprovar=1)
    )
    depois, _, de_novo = _rodar(tmp_path, [_freela(OUTRO)], modo=LIGADO, sessao=sessao, travas=Travas(por_dia=0, para_aprovar=1))

    assert [r.situacao for r in rodada.resultados] == [propostas_auto.PARA_APROVAR]
    assert len(escritor.pedidos) == 1 and "cota" in rodada.parou
    assert depois.resultados == () and de_novo.pedidos == []


def test_o_toque_envia_a_proposta_guardada_e_a_nota_vira_enviada(tmp_path: Path):
    _rodar(tmp_path, [_freela()], sessao=_logada())
    sessao = _logada(depois_de_enviar={LINK: _ja_proposto()})

    resposta = _tocar(tmp_path, sessao)

    assert resposta.tirar_botao is True
    assert resposta.texto.startswith("Enviada na 99Freelas: Sistema web para gerar mapas numerológicos · R$ 50 em 3 dias")
    assert "sobram 14 conexões" in resposta.texto and LINK in resposta.texto
    assert sessao.preenchidos == [(FORMULARIO, 50, 3, TEXTO, True)]
    nota = _nota(tmp_path)
    assert "status: enviada em 2026-10-10 (R$ 50, 3 dias)" in nota and "aprovada no celular" in nota and TEXTO in nota
    [mandada] = funil.ler_mandadas(tmp_path / "vault")
    assert mandada.link == LINK
    assert _estado(tmp_path)[LINK]["situacao"] == propostas_auto.ENVIADA and _estado(tmp_path)[LINK]["aprovada"]
    assert "enviada" in (tmp_path / "vault" / "cacada" / "propostas-auto.md").read_text(encoding="utf-8")


def test_o_toque_manda_o_texto_da_nota_quando_ele_editou(tmp_path: Path):
    _rodar(tmp_path, [_freela()], sessao=_logada())
    arquivo = tmp_path / "vault" / "cacada" / "propostas-auto" / "sistema-web-para-gerar-mapas-numerologicos-790517.md"
    editado = TEXTO.replace("Olá, Natacha!", "Oi, Natacha, tudo bem?")
    arquivo.write_text(arquivo.read_text(encoding="utf-8").replace(TEXTO, editado), encoding="utf-8")
    sessao = _logada(depois_de_enviar={LINK: _ja_proposto()})

    _tocar(tmp_path, sessao)

    assert sessao.preenchidos[0][3] == editado


def test_tocar_duas_vezes_nao_envia_de_novo(tmp_path: Path):
    _rodar(tmp_path, [_freela()], sessao=_logada())
    sessao = _logada(depois_de_enviar={LINK: _ja_proposto()})

    _tocar(tmp_path, sessao)
    segunda = _tocar(tmp_path, sessao)

    assert len(sessao.preenchidos) == 1
    assert segunda.tirar_botao is True and "já foi enviada" in segunda.texto


def test_ja_proposto_pelo_site_ou_projeto_fechado_tira_o_botao_sem_enviar(tmp_path: Path):
    _rodar(tmp_path, [_freela()], sessao=_logada())
    sessao = _logada(projeto=_ja_proposto())

    resposta = _tocar(tmp_path, sessao)

    assert resposta.tirar_botao is True and "já tinha proposto" in resposta.texto
    assert sessao.preenchidos == [] and _estado(tmp_path)[LINK]["situacao"] == propostas_auto.PULADA


def test_deslogado_mantem_o_botao_para_tocar_de_novo(tmp_path: Path):
    _rodar(tmp_path, [_freela()], sessao=_logada())
    sessao = SessaoFake({PAGINAS_DE_CONFERENCIA[NOVENTA_E_NOVE]: _fixture("deslogado"), LINK: _projeto()})

    resposta = _tocar(tmp_path, sessao)

    assert resposta.tirar_botao is False and "deslogado" in resposta.texto and "whis navegador" in resposta.texto
    assert _estado(tmp_path)[LINK]["situacao"] == propostas_auto.NO_ENSAIO


def test_chrome_ocupado_pela_vigia_ou_pela_cacada_mantem_o_botao(tmp_path: Path):
    _rodar(tmp_path, [_freela()], sessao=_logada())
    sessao = _logada()
    da_vigia = Trava(tmp_path / propostas_auto.NOME_DA_TRAVA).adquirir()
    try:
        ocupado = _tocar(tmp_path, sessao, espera_s=0)
    finally:
        da_vigia.liberar()
    cacada = _tocar(tmp_path, sessao, ocupada=lambda: True)

    assert ocupado.tirar_botao is False and "ocupado" in ocupado.texto
    assert cacada.tirar_botao is False and "caçada" in cacada.texto
    assert sessao.visitadas == [] and sessao.preenchidos == []


def test_formulario_que_recusa_mantem_o_botao_e_nada_muda(tmp_path: Path):
    _rodar(tmp_path, [_freela()], sessao=_logada())

    class Recusa(SessaoFake):
        def preencher_proposta_da_99freelas(self, url, **_opcoes):
            raise SemNavegador("o botão Enviar proposta está coberto")

    resposta = _tocar(tmp_path, Recusa(_logada().paginas))

    assert resposta.tirar_botao is False and "coberto" in resposta.texto
    assert _estado(tmp_path)[LINK]["situacao"] == propostas_auto.NO_ENSAIO


def test_toque_que_o_whis_nao_conhece_tira_o_botao(tmp_path: Path):
    resposta = _tocar(tmp_path, _logada(), dados="enviar:000000000000")

    assert resposta.tirar_botao is True and "Não achei" in resposta.texto


def test_a_aprovada_no_celular_nao_gasta_a_cota_automatica(tmp_path: Path):
    _rodar(tmp_path, [_freela()], modo=LIGADO, sessao=_logada(), travas=Travas(por_dia=0, para_aprovar=1))
    _tocar(tmp_path, _logada(depois_de_enviar={LINK: _ja_proposto()}), modo=LIGADO)
    sessao = _com_outro(_logada())
    sessao.depois_de_enviar = {OUTRO: _ja_proposto()}

    rodada, _, _ = _rodar(tmp_path, [_freela(OUTRO)], modo=LIGADO, sessao=sessao, travas=Travas(por_dia=1), agora=AGORA + timedelta(hours=2))

    assert [r.situacao for r in rodada.resultados] == [propostas_auto.ENVIADA]


def test_as_que_esperam_o_toque_voltam_ao_celular_com_o_botao(tmp_path: Path):
    _rodar(tmp_path, [_freela()], sessao=_logada())
    celular = CelularFake()

    oferecidas = propostas_auto.oferecer_pendentes(
        estado=tmp_path / "propostas-auto.json", vault=tmp_path / "vault", celular=celular, agora=AGORA + timedelta(hours=3)
    )

    assert oferecidas == 1
    assert celular[0].startswith("Esperando o seu toque (escrita em 10/10 às 10:00)") and TEXTO in celular[0]
    assert celular.botoes == [BOTAO]


# -- o preço -----------------------------------------------------------------------------------------


def _com_preco(preco: int, motivo: str = "") -> EscritorFake:
    return EscritorFake(respostas=[Escrita(entrega=True, motivo="dá", texto=TEXTO, prazo_dias=3, preco=preco, motivo_do_preco=motivo)])


def test_o_preco_e_o_do_claude_e_o_celular_mostra_a_conta(tmp_path: Path):
    sessao = _logada(depois_de_enviar={LINK: _ja_proposto()})

    rodada, celular, escritor = _rodar(
        tmp_path, [_freela()], modo=LIGADO, sessao=sessao, escritor=_com_preco(1200, "uns R$ 1.400 no mercado para esse escopo")
    )

    assert rodada.resultados[0].preco == 1200 and sessao.preenchidos[0][1] == 1200
    assert "R$ 1.200 em 3 dias (uns R$ 1.400 no mercado para esse escopo)" in celular[0]
    assert 'preco: "R$ 1200"' in _nota(tmp_path) and "status: enviada em 2026-10-10 (R$ 1.200, 3 dias)" in _nota(tmp_path)
    assert "Oferta mínima do projeto: R$ 50" in escritor.pedidos[0][1]


def test_o_preco_nunca_fica_abaixo_da_oferta_minima_nem_do_piso(tmp_path: Path):
    abaixo, _, _ = _rodar(tmp_path / "a", [_freela()], sessao=_logada(), escritor=_com_preco(30))
    piso, _, _ = _rodar(tmp_path / "b", [_freela()], sessao=_logada(), escritor=_com_preco(120), travas=Travas(piso=200))

    assert abaixo.resultados[0].preco == 50 and piso.resultados[0].preco == 200


def test_sem_preco_o_claude_escreve_de_novo(tmp_path: Path):
    escritor = EscritorFake(
        respostas=[
            Escrita(entrega=True, motivo="dá", texto=TEXTO, prazo_dias=3),
            Escrita(entrega=True, motivo="dá", texto=TEXTO, prazo_dias=3, preco=400),
        ]
    )

    rodada, _, _ = _rodar(tmp_path, [_freela()], sessao=_logada(), escritor=escritor)

    assert "preço" in escritor.pedidos[1][2] and rodada.resultados[0].preco == 400


def test_o_toque_usa_o_preco_da_nota_que_ele_pode_editar(tmp_path: Path):
    _rodar(tmp_path, [_freela()], sessao=_logada(), escritor=_com_preco(300))
    arquivo = tmp_path / "vault" / "cacada" / "propostas-auto" / "sistema-web-para-gerar-mapas-numerologicos-790517.md"
    arquivo.write_text(arquivo.read_text(encoding="utf-8").replace('preco: "R$ 300"', 'preco: "R$ 450"'), encoding="utf-8")
    sessao = _logada(depois_de_enviar={LINK: _ja_proposto()})

    resposta = _tocar(tmp_path, sessao)

    assert sessao.preenchidos[0][1] == 450 and "R$ 450 em 3 dias" in resposta.texto


def test_erro_inesperado_do_claude_pula_o_projeto_e_o_estado_fica_gravado(tmp_path: Path):
    sessao = _com_outro(_logada())

    class Quebra(EscritorFake):
        def escrever(self, oportunidade, pagina, contexto, *, corrigir=""):
            if oportunidade.link == OUTRO:
                raise Exception("Control request timeout: initialize")
            return super().escrever(oportunidade, pagina, contexto, corrigir=corrigir)

    rodada, _, _ = _rodar(tmp_path, [_freela(), _freela(OUTRO, propostas=9)], sessao=sessao, escritor=Quebra())

    assert [r.link for r in rodada.resultados] == [LINK]
    assert list(_estado(tmp_path)) == [LINK]



class Demora(SessaoFake):
    """A 99Freelas mostra "Enviando…" e só depois de umas leituras aparece o "Melhorar proposta"."""

    def __init__(self, *args, leituras_ate_confirmar: int = 3, **opcoes) -> None:
        super().__init__(*args, **opcoes)
        self.leituras_ate_confirmar = leituras_ate_confirmar
        self.enviada = False
        self.depois = 0

    def html(self, url):
        if self.enviada and url == LINK:
            self.depois += 1
            self.visitadas.append(url)
            return _ja_proposto() if self.depois >= self.leituras_ate_confirmar else _projeto()
        return super().html(url)

    def preencher_proposta_da_99freelas(self, url, *, oferta, dias, texto, enviar, pasta_das_fotos=None):
        self.enviada = self.enviada or enviar
        return super().preencher_proposta_da_99freelas(url, oferta=oferta, dias=dias, texto=texto, enviar=enviar, pasta_das_fotos=pasta_das_fotos)


def test_a_confirmacao_espera_a_pagina_mostrar_o_melhorar_proposta(tmp_path: Path):
    sessao = Demora(_logada().paginas)

    rodada, celular, _ = _rodar(tmp_path, [_freela()], modo=LIGADO, sessao=sessao)

    assert [r.situacao for r in rodada.resultados] == [propostas_auto.ENVIADA]
    assert sessao.depois == 3 and celular[0].startswith("Proposta enviada")


def test_o_toque_tambem_espera_a_confirmacao(tmp_path: Path):
    _rodar(tmp_path, [_freela()], sessao=_logada())
    sessao = Demora(_logada().paginas, leituras_ate_confirmar=2)

    resposta = _tocar(tmp_path, sessao)

    assert resposta.texto.startswith("Enviada na 99Freelas") and _estado(tmp_path)[LINK]["situacao"] == propostas_auto.ENVIADA



def test_chrome_que_nao_abre_so_avisa_na_terceira_rodada_seguida(tmp_path: Path):
    from whis.navegador_logado import PERFIL_EM_USO

    def sem_chrome() -> SessaoFake:
        sessao = SessaoFake({})
        sessao.motivo = PERFIL_EM_USO
        return sessao

    celulares = [
        _rodar(tmp_path, [_freela()], modo=LIGADO, sessao=sem_chrome(), agora=AGORA + timedelta(hours=hora))[1] for hora in range(4)
    ]

    assert celulares[0] == [] and celulares[1] == [] and celulares[3] == []
    [aviso] = celulares[2]
    assert "há 3 rodadas" in aviso and "feche" in aviso and "whis navegador" not in aviso


def test_o_chrome_que_abre_zera_a_contagem_de_falhas(tmp_path: Path):
    from whis.navegador_logado import PERFIL_EM_USO

    sessao = SessaoFake({})
    sessao.motivo = PERFIL_EM_USO
    _rodar(tmp_path, [_freela()], modo=LIGADO, sessao=sessao)
    _rodar(tmp_path, [_freela()], modo=LIGADO, sessao=_logada(depois_de_enviar={LINK: _ja_proposto()}), agora=AGORA + timedelta(hours=1))

    avisos = json.loads((tmp_path / "propostas-auto.json").read_text(encoding="utf-8"))["avisos"]
    assert "chrome_falhou" not in avisos



def test_a_vitrine_nunca_vai_na_proposta_nem_quando_esta_no_portfolio():
    from whis.criterios_da_cacada import PecaDoPortfolio

    portfolio = (*contexto_do_portfolio(), PecaDoPortfolio("Site do portfólio", "https://velozo.dev", "o portfólio inteiro"))
    peca = TEXTO.replace("todo dia", "todo dia (https://github.com/bielvelozo/inkly-shopify-theme)")
    com_a_vitrine = TEXTO.replace("todo dia", "todo dia (https://velozo.dev)")
    sem_esquema = TEXTO.replace("todo dia", "todo dia, veja em velozo.dev/br")
    dois = peca.replace("Gabriel", "https://github.com/bielvelozo/inkly-shopify-theme#cart\n\nGabriel")

    assert problemas_do_texto(peca, _freela(), "", portfolio) == []
    assert any("vitrine" in problema and "contato fora da plataforma" in problema for problema in problemas_do_texto(com_a_vitrine, _freela(), "", portfolio))
    assert any("vitrine" in problema for problema in problemas_do_texto(sem_esquema, _freela(), "", portfolio))
    assert "mais de um link" in problemas_do_texto(dois, _freela(), "", portfolio)


def test_o_claude_da_proposta_nao_recebe_a_vitrine(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "cacada").mkdir(parents=True)
    (vault / "cacada" / "criterios.md").write_text(
        "## O que eu procuro\n\n- Freela.\n\n## Portfólio\n\n"
        "- Tema Shopify Inkly: https://github.com/bielvelozo/inkly-shopify-theme — tema\n"
        "- Site do portfólio: https://velozo.dev — o portfólio inteiro\n",
        encoding="utf-8",
    )

    contexto = contexto_do_vault(vault, "shopify")

    from whis.propostas_auto_claude import SISTEMA_DA_PROPOSTA

    assert [peca.nome for peca in contexto.portfolio] == ["Tema Shopify Inkly"]
    assert "Site do portfólio" not in SISTEMA_DA_PROPOSTA

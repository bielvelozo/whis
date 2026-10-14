r"""O Chrome da caçada lido em Python: as páginas dos sites em que ele entrou à mão.

Ele entra uma vez em cada site pelo `whis navegador`, no perfil
`%LOCALAPPDATA%\whis\navegador-cacada`. A caçada abre esse mesmo perfil com o
Playwright (Chrome instalado, persistente, sem agente do Claude), lê as páginas
que só mostram a verdade logado e fecha. A janela fica fora da tela: sem janela
o site barra (o X mostrou isso), e com janela à vista a caçada da madrugada
roubaria a tela dele.

Nada aqui derruba a caçada. Chrome ausente, perfil aberto à mão ou página que
não carrega viram `motivo` na sessão, e quem chama segue pelo caminho sem
login. Os leitores das páginas são funções puras sobre o HTML (casam por texto
e classe estável, nunca por caminho de DOM: research/marcadores.md).
"""

from __future__ import annotations

import html as _html
import logging
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .oportunidades import FREELA, Oportunidade, texto_limpo

_log = logging.getLogger("whis.navegador_logado")

FREELANCER = "freelancer"
NOVENTA_E_NOVE = "99freelas"
VINTEPILA = "vintepila"
FREELANCER_BR = "freelancer.com.br"

NOMES = {
    FREELANCER: "Freelancer.com",
    NOVENTA_E_NOVE: "99Freelas",
    VINTEPILA: "VintePila",
    FREELANCER_BR: "freelancer.com.br",
}

#: A página que diz se ele está logado em cada site (o cabeçalho muda).
PAGINAS_DE_CONFERENCIA = {
    FREELANCER: "https://www.freelancer.com/dashboard",
    NOVENTA_E_NOVE: "https://www.99freelas.com.br/projects?categoria=web-mobile-e-software",
    VINTEPILA: "https://www.vintepila.com.br/trabalhos-freelance/",
    FREELANCER_BR: "https://freelancer.com.br/projetos",
}

#: As abas que `whis navegador` abre para ele entrar.
PAGINAS_DE_LOGIN = (
    "https://www.freelancer.com/login",
    "https://www.99freelas.com.br/login",
    "https://www.vintepila.com.br/trabalhos-freelance/",
    "https://freelancer.com.br/projetos",
)

LISTAGEM_DA_VINTEPILA = "https://www.vintepila.com.br/trabalhos-freelance/?page={pagina}"
ESPERA_DA_PAGINA_MS = 30_000
JANELA_FORA_DA_TELA = ("--window-position=-32000,-32000", "--window-size=1280,900")

SEM_CHROME = "o Chrome não foi encontrado"
PERFIL_EM_USO = "o Chrome da caçada está aberto"

LOGADO = "logado"
DESLOGADO = "deslogado"


class SemNavegador(RuntimeError):
    """O Chrome da caçada não abriu ou a página não carregou."""


# -- o estado de cada site, para o relatório ---------------------------------------------------


def estado_do_site(sessao: SessaoLogada | None, site: str) -> str:
    """`logado`, `deslogado` ou o motivo de não ter navegador; vazio sem porta de navegador."""
    if sessao is None:
        return ""
    if sessao.motivo:
        return sessao.motivo
    return LOGADO if sessao.logado(site) else DESLOGADO


def frase_do_estado(site: str, estado: str) -> str:
    nome = NOMES.get(site, site)
    if estado == LOGADO:
        return f"{nome}: logado no Chrome da caçada"
    if estado == DESLOGADO:
        return f"{nome}: deslogado — entre de novo pelo `whis navegador`"
    if estado == PERFIL_EM_USO:
        return f"{nome}: o Chrome da caçada estava aberto — feche-o para a caçada usar o login"
    if estado == SEM_CHROME:
        return f"{nome}: sem Chrome nesta máquina, a caçada seguiu sem login"
    return f"{nome}: sem o Chrome da caçada ({estado}), a caçada seguiu sem login"


# -- a sessão ---------------------------------------------------------------------------------


class SessaoLogada:
    """Uma abertura do Chrome da caçada: `html(url)`, `logado(site)` e `fechar()`.

    `motivo` vazio é navegador disponível. A conferência de login de cada site
    é feita uma vez por sessão, quando alguém pergunta.
    """

    def __init__(self) -> None:
        self.motivo = ""
        self._logado: dict[str, bool] = {}

    def html(self, url: str) -> str:
        raise NotImplementedError

    def logado(self, site: str) -> bool:
        if self.motivo:
            return False
        if site not in self._logado:
            try:
                self._logado[site] = logado_no_html(site, self.html(PAGINAS_DE_CONFERENCIA[site]))
            except SemNavegador as erro:
                _log.info("Caçada: não deu para conferir o login em %s: %s", NOMES.get(site, site), erro)
                self._logado[site] = False
        return self._logado[site]

    def fechar(self) -> None:
        return None

    def __enter__(self) -> SessaoLogada:
        return self

    def __exit__(self, *_: object) -> None:
        self.fechar()


def _playwright():
    from playwright.sync_api import sync_playwright

    return sync_playwright()


class NavegadorLogado:
    """A porta de verdade: cada `abrir()` é uma sessão que liga o Chrome só na primeira página."""

    def __init__(self, *, perfil: Path | None = None) -> None:
        if perfil is None:
            from .navegador_agente import pasta_do_perfil

            perfil = pasta_do_perfil()
        self.perfil = Path(perfil)

    def abrir(self) -> SessaoLogada:
        return _SessaoDoChrome(self.perfil)


class _SessaoDoChrome(SessaoLogada):
    def __init__(self, perfil: Path) -> None:
        super().__init__()
        self._perfil = perfil
        self._gerente = None
        self._contexto = None
        self._pagina = None

    def html(self, url: str) -> str:
        if self.motivo:
            raise SemNavegador(self.motivo)
        if self._pagina is None:
            self._ligar()
        try:
            self._pagina.goto(url, wait_until="domcontentloaded", timeout=ESPERA_DA_PAGINA_MS)
            try:
                self._pagina.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:  # noqa: BLE001 — página que nunca silencia já tem o que interessa
                pass
            return self._pagina.content()
        except Exception as erro:  # noqa: BLE001 — uma página não derruba a sessão
            raise SemNavegador(_motivo(erro)) from erro

    def _ligar(self) -> None:
        try:
            self._gerente = _playwright().start()
        except Exception as erro:  # noqa: BLE001 — sem Playwright é sem login
            self.motivo = f"o Playwright não abriu: {_motivo(erro)}"
            raise SemNavegador(self.motivo) from erro
        self._perfil.mkdir(parents=True, exist_ok=True)
        try:
            self._contexto = self._gerente.chromium.launch_persistent_context(
                str(self._perfil), channel="chrome", headless=False, args=list(JANELA_FORA_DA_TELA), locale="pt-BR"
            )
        except Exception as erro:  # noqa: BLE001 — o Playwright só diz o porquê no texto
            self.motivo = motivo_do_chrome(str(erro))
            self._parar()
            raise SemNavegador(self.motivo) from erro
        self._pagina = self._contexto.pages[0] if self._contexto.pages else self._contexto.new_page()
        _log.info("Caçada: o Chrome da caçada abriu (fora da tela).")

    def fechar(self) -> None:
        if self._contexto is not None:
            try:
                self._contexto.close()
            except Exception as erro:  # noqa: BLE001 — fechar mal não desfaz o que já foi lido
                _log.debug("O Chrome da caçada não fechou limpo: %s", erro)
        self._contexto = self._pagina = None
        self._parar()

    def _parar(self) -> None:
        if self._gerente is not None:
            try:
                self._gerente.stop()
            except Exception:  # noqa: BLE001 — o processo do Playwright sai de todo jeito
                pass
        self._gerente = None


def motivo_do_chrome(texto: str) -> str:
    if "is not found" in texto or "Executable doesn't exist" in texto:
        return SEM_CHROME
    if "ProcessSingleton" in texto or "already in use" in texto:
        return PERFIL_EM_USO
    return f"o Chrome não abriu: {_primeira_linha(texto)}"


def _motivo(erro: BaseException) -> str:
    if type(erro).__name__ == "TimeoutError":
        return "tempo esgotado"
    return _primeira_linha(str(erro)) or type(erro).__name__


def _primeira_linha(texto: str) -> str:
    return texto.strip().splitlines()[0][:160] if texto.strip() else ""


# -- os leitores das páginas ----------------------------------------------------------------------


def logado_no_html(site: str, pagina: str) -> bool:
    if site == FREELANCER:
        return "<app-logged-in-shell" in pagina
    if site == NOVENTA_E_NOVE:
        return "header-menu-logged" in pagina or re.search(r'<header\b[^>]*class="[^"]*\bfreelancer\b', pagina) is not None
    if site == VINTEPILA:
        return "vp-mc-g-nome" in pagina and 'id="__entrar"' not in pagina
    if site == FREELANCER_BR:
        return bool(pagina.strip()) and "header-login-btn" not in pagina
    return False


def texto_da_pagina(pagina: str) -> str:
    sem_codigo = re.sub(r"<(script|style)\b.*?</\1>", " ", pagina, flags=re.S | re.I)
    return " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", sem_codigo)).split())


@dataclass(frozen=True)
class PaginaDoFreelancer:
    logado: bool
    selecionados: bool = False
    ofertas: int | None = None
    lances: tuple[int, int] | None = None


def ler_freelancer(pagina: str) -> PaginaDoFreelancer:
    """O projeto do Freelancer.com: só para selecionados (saldo de US$ 20), ofertas e lances restantes."""
    texto = texto_da_pagina(pagina)
    dobrado = texto.casefold()
    selecionados = "aberto apenas a freelancers selecionados" in dobrado or "mantenha um saldo mínimo" in dobrado
    ofertas = re.search(r"\bOfertas (\d+) Oferta média", texto) or re.search(r"\b(\d+) proposals\b", texto)
    lances = re.search(r"\b(\d+) ofertas restantes de (\d+)", texto) or re.search(r"\b(\d+)/(\d+) restantes\b", texto)
    return PaginaDoFreelancer(
        logado=logado_no_html(FREELANCER, pagina),
        selecionados=selecionados,
        ofertas=int(ofertas.group(1)) if ofertas else None,
        lances=(int(lances.group(1)), int(lances.group(2))) if lances else None,
    )


ABERTO = "aberto"
CANCELADO = "cancelado"
EM_ANDAMENTO = "em_andamento"
JA_PROPOS = "ja_propos"
FECHADO = "fechado"


@dataclass(frozen=True)
class PaginaDa99Freelas:
    logado: bool
    situacao: str
    propostas: int | None = None


def ler_99freelas(pagina: str) -> PaginaDa99Freelas:
    """O projeto da 99Freelas: aberto, cancelado, em andamento (freelancer escolhido), já proposto ou fechado."""
    botao = re.search(r'<a\b[^>]*href="/project/bid/[^"]*"[^>]*>\s*([^<]*)', pagina, re.I)
    if re.search(r'class="[^"]*\bbtn\b[^"]*\bstatus-5\b', pagina):
        situacao = CANCELADO
    elif re.search(r'class="[^"]*\bbtn\b[^"]*\bstatus-3\b', pagina):
        situacao = EM_ANDAMENTO
    elif botao and "melhorar" in botao.group(1).casefold():
        situacao = JA_PROPOS
    elif botao:
        situacao = ABERTO
    else:
        situacao = FECHADO
    propostas = re.search(r"Propostas:\s*(\d+)", texto_da_pagina(pagina))
    return PaginaDa99Freelas(logado_no_html(NOVENTA_E_NOVE, pagina), situacao, int(propostas.group(1)) if propostas else None)


@dataclass(frozen=True)
class PropostaDa99Freelas:
    custo: int | None = None
    restantes: int | None = None
    exclusivo: bool = False

    @property
    def saldo(self) -> int | None:
        return self.custo + self.restantes if self.custo is not None and self.restantes is not None else None


def ler_proposta_da_99freelas(pagina: str) -> PropostaDa99Freelas:
    """O formulário `/project/bid/<slug>`: quantas conexões a proposta custa e quantas sobram depois."""
    texto = texto_da_pagina(pagina)
    custo = re.search(r"requer (\d+) conex", texto)
    restantes = re.search(r"terá (\d+) conex\S* restantes", texto)
    return PropostaDa99Freelas(
        custo=int(custo.group(1)) if custo else None,
        restantes=int(restantes.group(1)) if restantes else None,
        exclusivo="projetos exclusivos, assine" in texto,
    )


CANDIDATOS_DA_VINTEPILA = 5
SEM_SERVICO_ATIVO = "pelo menos um serviço ativo"


@dataclass(frozen=True)
class PaginaDaVintePila:
    logado: bool
    sem_servico_ativo: bool = False
    candidatos: tuple[int, int] | None = None


def ler_projeto_da_vintepila(pagina: str) -> PaginaDaVintePila:
    """O projeto da VintePila; o aviso de conta sem serviço ativo só existe num script da página."""
    candidatos = re.search(r"Candidatos \((\d+)/(\d+)\)", texto_da_pagina(pagina))
    return PaginaDaVintePila(
        logado=logado_no_html(VINTEPILA, pagina),
        sem_servico_ativo=SEM_SERVICO_ATIVO in _html.unescape(pagina),
        candidatos=(int(candidatos.group(1)), int(candidatos.group(2))) if candidatos else None,
    )


_CARTAO_DA_VINTEPILA = re.compile(r'<div\b[^>]*class="item h_p_(\d+)"', re.I)


def ler_listagem_da_vintepila(pagina: str, nome: str = "VintePila") -> tuple[Oportunidade, ...]:
    """Os cartões de `/trabalhos-freelance/`; o número de candidatos vai nos detalhes."""
    inicios = list(_CARTAO_DA_VINTEPILA.finditer(pagina))
    saida = []
    for indice, casou in enumerate(inicios):
        fim = inicios[indice + 1].start() if indice + 1 < len(inicios) else len(pagina)
        bloco = pagina[casou.start() : fim]
        titulo = re.search(r'<a\b[^>]*class="header"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', bloco, re.S | re.I)
        if not titulo:
            continue
        preco = re.search(r'id="project-price"[^>]*>(.*?)</span>', bloco, re.S)
        descricao = re.search(r'class="description"[^>]*>(.*?)</div>', bloco, re.S)
        candidatos = re.search(r'data-content="N\S*mero de candidatos[^"]*"[^>]*>(?:<i[^>]*></i>)?\s*(\d+)', bloco)
        prazo = re.search(r'data-content="Prazo m\S*ximo[^"]*"[^>]*>(?:<i[^>]*></i>)?\s*([^<]+)', bloco)
        pro = ">PRO<" in bloco
        detalhes = [
            f"Candidatos: {candidatos.group(1)}/{'sem limite' if pro else CANDIDATOS_DA_VINTEPILA}" if candidatos else "",
            f"prazo: {texto_limpo(prazo.group(1)).lower()}" if prazo else "",
        ]
        saida.append(
            Oportunidade.nova(
                tipo=FREELA,
                fonte=nome,
                titulo=texto_limpo(titulo.group(2)),
                link=_html.unescape(titulo.group(1)),
                faixa=" ".join(texto_limpo(preco.group(1)).split()) if preco else "",
                descricao=texto_limpo(descricao.group(1)) if descricao else "",
                detalhes=" | ".join(d for d in detalhes if d),
            )
        )
    return tuple(saida)


def candidatos_cheios(oportunidade: Oportunidade) -> bool:
    casou = re.search(r"Candidatos: (\d+)/(\d+)", oportunidade.detalhes)
    return bool(casou) and int(casou.group(1)) >= int(casou.group(2))


def casa_com_palavras(oportunidade: Oportunidade, palavras: Sequence[str]) -> bool:
    texto = f" {_sem_acento(oportunidade.titulo)} {_sem_acento(oportunidade.descricao)} "
    return any(re.search(rf"(?<![a-z0-9]){re.escape(_sem_acento(p))}(?![a-z0-9])", texto) for p in palavras if p.strip())


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto.casefold()) if not unicodedata.combining(c))

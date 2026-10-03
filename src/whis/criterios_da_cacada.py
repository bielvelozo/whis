"""`cacada/criterios.md`: o que ele procura, quem ele é e onde caçar, numa nota dele.

Como `noticias/fontes.md`: o Whis cria uma vez, a partir do modelo, e nunca
mais escreve. Ele edita no Obsidian — muda o piso, responde o que o Whis
perguntou em *Sobre mim*, tira ou põe uma fonte. A leitura é tolerante: linha
de fonte que não casa o formato é ignorada com aviso, e a caçada corre com o
que deu para ler.

Três seções contam. *O que eu procuro* e *Sobre mim* vão como texto, inteiras,
para o Claude — são as regras e os fatos dele. *Fontes* é uma fonte por linha,
`- Nome: tipo argumento`, e os tipos são os de `TIPOS_DE_FONTE`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import vault as _vault

_log = logging.getLogger("whis.criterios")

PASTA_CACADA = "cacada"
CAMINHO_DOS_CRITERIOS = f"{PASTA_CACADA}/criterios.md"

SECAO_PROCURO = "O que eu procuro"
SECAO_SOBRE_MIM = "Sobre mim"
SECAO_FONTES = "Fontes"
SECAO_CONTAS = "Contas"

#: O que cada tipo de fonte lê, e o argumento que aceita.
TIPOS_DE_FONTE = {
    "himalayas": "API do Himalayas (remoto internacional); argumento: termo de busca",
    "remotive": "API do Remotive (remoto internacional, 4 leituras por dia); argumento: termo de busca",
    "remoteok": "API do RemoteOK (remoto internacional); argumento: tag",
    "jobicy": "API do Jobicy (remoto); argumento: região (latam, brazil, anywhere)",
    "rss": "um feed RSS de vagas; argumento: a URL",
    "github": "issues de um repositório de vagas; argumento: dono/repositório",
    "hn": "o Ask HN: Who is hiring? do mês; argumento: termos que a vaga precisa citar, separados por vírgula",
    "gupy": "o portal público da Gupy (Brasil); argumento: termo de busca",
    "workana": "a listagem pública da Workana; argumento: a categoria",
    "99freelas": "a listagem pública da 99Freelas; argumento: a categoria",
    "linkedin": "a busca pública do LinkedIn, sem login; argumento: termos | local | remoto ou presencial",
    "getonbrd": "a API pública do Get on Board (tech na América Latina); argumento: termo de busca",
    "freelancer": "a API pública de projetos do Freelancer.com (só preço fechado); argumento: termo de busca",
    "web": "o Claude busca na web aberta; argumento: o que procurar",
}

MODELO_DOS_CRITERIOS = """\
# Critérios da caçada

O Whis lê esta nota a cada caçada e nunca escreve nela: ela é sua. Mude o que quiser.

## O que eu procuro

- Quero mais dinheiro: vaga de emprego ou freela, os dois servem.
- Emprego: qualquer regime (CLT, PJ, contrato internacional em dólar ou euro). Só remoto, ou presencial/híbrido perto de casa se pagar bem.
- Moro em Matão-SP (região de Araraquara). Remoto ou região de Araraquara: acima de R$ 5.000 por mês. Presencial/híbrido em Ribeirão Preto: a partir de uns R$ 7.000. Em São Paulo: a partir de uns R$ 8.000 a 9.000. Outras cidades presenciais, não.
- Vaga sem faixa salarial não é descartada por isso: entra dizendo que a faixa é desconhecida.
- Stack: web developer (full-stack web). Vagas de games e de software de áudio entram como tentar a sorte: é onde eu tenho vontade.
- Freela: por projeto (preço fechado) sim; contínuo pequeno (valor mensal) se pagar bem e couber nas minhas horas; por hora, não.
- Preço do freela: se eu faço com IA em algumas horas ou num fim de semana, pode sair abaixo do mercado; freela maior, ligeiramente abaixo do mercado.
- Descartar: freela grande com prazo curto (concilio trabalho, faculdade e freela).
- Considere que eu sou desenrolado e uso IA pesado: quase nada de web está fora do meu alcance. O que eu já fiz é fato e não se inventa; o que eu consigo fazer pode ir além.
- Golpe: sair fora (conversa fora da plataforma, pagamento fora do escrow, pedir dinheiro, "baixe e rode este repositório", teste que é o projeto inteiro).
- LinkedIn: nada automático, nunca. Meus colegas me seguem.

## Sobre mim

Responda o que puder, uma linha por item. O Whis usa isto para julgar e escrever as propostas, e pergunta no relatório o que faltar.

- Anos de experiência com desenvolvimento:
- Cargo atual (e se posso citar o nome da empresa numa candidatura: sim/não):
- Experiências anteriores:
- Formação (curso, faculdade, semestre):
- Inglês (básico, intermediário, avançado, fluente):
- Horas livres por semana para freela:
- GitHub público:
- Portfólio ou projetos que posso mostrar (links):
- LinkedIn (link):
- Currículo (caminho do PDF no PC):
- O que eu não quero mais fazer:

## Fontes

Uma fonte por linha: `- Nome: tipo argumento`. Apague a linha para desligar a fonte.

- Himalayas · full stack: himalayas full stack developer
- Himalayas · front-end: himalayas frontend developer
- Remotive · desenvolvimento: remotive developer
- RemoteOK · dev: remoteok dev
- Jobicy · América Latina: jobicy latam
- We Work Remotely · Full-Stack: rss https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss
- We Work Remotely · Front-End: rss https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss
- We Work Remotely · Back-End: rss https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss
- Vagas front-end (frontendbr): github frontendbr/vagas
- Vagas back-end (backend-br): github backend-br/vagas
- HN · Who is hiring: hn remote, react, typescript, full stack, frontend, node
- Gupy · desenvolvedor: gupy desenvolvedor
- Gupy · full stack: gupy full stack
- Gupy · front-end: gupy front-end
- Workana · TI e programação: workana it-programming
- 99Freelas · web, mobile e software: 99freelas web-mobile-e-software
- LinkedIn · web remoto: linkedin desenvolvedor web | Brasil | remoto
- LinkedIn · full stack remoto: linkedin full stack developer | Brasil | remoto
- LinkedIn · Ribeirão Preto: linkedin desenvolvedor | Ribeirão Preto, São Paulo | presencial
- LinkedIn · games: linkedin game developer | Brasil | remoto
- Get on Board · full stack: getonbrd full stack
- Get on Board · front-end: getonbrd frontend
- Freelancer.com · sites: freelancer website
- Freelancer.com · React: freelancer react
- Web · Programathor e Contra: web vagas no programathor.com.br e freelas por projeto no contra.com de desenvolvimento web que aceitem brasileiro, publicados nos últimos 14 dias
- Web · freelas e vagas fora das listas: web vagas remotas de desenvolvedor web que aceitem brasileiros, e freelas de sites e sistemas web por projeto, publicados nos últimos 7 dias, fora dos sites já listados acima
- Web · games e áudio: web vagas ou freelas de desenvolvimento de games ou de software de áudio (plugins, DAW, web audio) que aceitem brasileiro remoto, publicados nos últimos 14 dias

## Contas

Os sites onde o Whis cria conta para você com o Gmail dedicado (`whis contas`, com você no PC), uma linha por site: `- Nome: endereço`. CAPTCHA, telefone e documento ficam com você.

- Workana: https://www.workana.com
- 99Freelas: https://www.99freelas.com.br
- Gupy (candidato): https://portal.gupy.io
- Freelancer.com: https://www.freelancer.com
- Contra: https://contra.com
- Get on Board: https://www.getonbrd.com
- GeekHunter: https://www.geekhunter.com.br
- Programathor: https://programathor.com.br
- Upwork: https://www.upwork.com
"""


@dataclass(frozen=True)
class FonteDaCacada:
    """Uma linha de *Fontes*: o nome que aparece no relatório, o tipo e o argumento."""

    nome: str
    tipo: str
    argumento: str = ""


@dataclass(frozen=True)
class Conta:
    """Uma linha de *Contas*: o site e o endereço onde começar."""

    nome: str
    endereco: str


@dataclass(frozen=True)
class Criterios:
    """A nota lida: o texto das regras, o de *Sobre mim*, as fontes e os avisos de leitura."""

    procuro: str
    sobre_mim: str
    fontes: tuple[FonteDaCacada, ...]
    avisos: tuple[str, ...] = field(default_factory=tuple)
    contas: tuple[Conta, ...] = field(default_factory=tuple)

    def em_sobre_mim(self, comeco: str) -> str:
        """A resposta de um item de *Sobre mim* que começa com `comeco` (sem diferenciar maiúsculas)."""
        for linha in self.sobre_mim.splitlines():
            casou = re.match(r"^\s*-\s*(?P<pergunta>[^:]+):\s*(?P<resposta>.*)$", linha)
            if casou and casou["pergunta"].strip().casefold().startswith(comeco.casefold()):
                return casou["resposta"].strip()
        return ""

    def respostas_em_branco(self) -> tuple[str, ...]:
        """Os itens de *Sobre mim* que ele ainda não respondeu (`- Pergunta:` sem nada depois)."""
        vazios = []
        for linha in self.sobre_mim.splitlines():
            casou = re.match(r"^\s*-\s*(?P<pergunta>[^:]+):\s*$", linha)
            if casou:
                vazios.append(casou["pergunta"].strip())
        return tuple(vazios)


_LINHA_DE_FONTE = re.compile(r"^-\s*(?P<nome>[^:]+?):\s*(?P<tipo>[\w-]+)\b\s*(?P<argumento>.*)$")


def interpretar_criterios(texto: str) -> Criterios:
    """Lê a nota em seções `##`; o que estiver fora delas é ignorado."""
    secoes: dict[str, list[str]] = {}
    atual: str | None = None
    for linha in texto.splitlines():
        cabecalho = re.match(r"^##\s+(?P<titulo>.+?)\s*$", linha)
        if cabecalho:
            atual = cabecalho["titulo"].strip().casefold()
            secoes.setdefault(atual, [])
            continue
        if atual is not None:
            secoes[atual].append(linha)

    avisos: list[str] = []
    fontes: list[FonteDaCacada] = []
    vistos: set[str] = set()
    for linha in secoes.get(SECAO_FONTES.casefold(), []):
        texto_da_linha = linha.strip()
        if not texto_da_linha.startswith("-"):
            continue
        casou = _LINHA_DE_FONTE.match(texto_da_linha)
        if casou is None or casou["tipo"].casefold() not in TIPOS_DE_FONTE:
            _avisar(avisos, f"Fonte ignorada (formato ou tipo desconhecido): {texto_da_linha}")
            continue
        nome = casou["nome"].strip()
        if nome.casefold() in vistos:
            _avisar(avisos, f"Fonte repetida ignorada: {nome}")
            continue
        vistos.add(nome.casefold())
        fontes.append(FonteDaCacada(nome, casou["tipo"].casefold(), casou["argumento"].strip().strip("`")))

    contas: list[Conta] = []
    for linha in secoes.get(SECAO_CONTAS.casefold(), []):
        casou = re.match(r"^-\s*(?P<nome>[^:]+?):\s*(?P<endereco>https?://\S+)\s*$", linha.strip())
        if casou:
            contas.append(Conta(casou["nome"].strip(), casou["endereco"].strip()))

    return Criterios(
        contas=tuple(contas),
        procuro=_texto(secoes.get(SECAO_PROCURO.casefold(), [])),
        sobre_mim=_texto(secoes.get(SECAO_SOBRE_MIM.casefold(), [])),
        fontes=tuple(fontes),
        avisos=tuple(avisos),
    )


def garantir_criterios(vault: Path) -> Path:
    """Cria `cacada/criterios.md` a partir do modelo, se ainda não existe. Nunca reescreve."""
    arquivo = Path(vault) / CAMINHO_DOS_CRITERIOS
    if arquivo.is_file():
        return arquivo
    _log.info("Criando %s a partir do modelo.", CAMINHO_DOS_CRITERIOS)
    return _vault.escrever(vault, CAMINHO_DOS_CRITERIOS, MODELO_DOS_CRITERIOS, zonas=(PASTA_CACADA,))


def ler_criterios(vault: Path) -> Criterios:
    arquivo = garantir_criterios(vault)
    return interpretar_criterios(arquivo.read_text(encoding="utf-8"))


def _texto(linhas: list[str]) -> str:
    return "\n".join(linhas).strip()


def _avisar(avisos: list[str], mensagem: str) -> None:
    _log.warning("%s", mensagem)
    avisos.append(mensagem)

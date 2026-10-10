"""O modo freelas rápidos da caçada (`whis hunt --freelas`): dinheiro rápido, só freela.

A corrida é a mesma da caçada; muda o que ela lê e como julga. Das fontes de
*Fontes*, ficam só as de freela (Workana, 99Freelas, Freelancer.com), e
entram as de `FONTES_DE_FREELA_RAPIDO`: mais buscas no Freelancer.com e a web
vasculhada por vários lados (plataformas, Shopify, bounties pagos, posts de
quem está contratando). O pedido do modo vai na frente de *O que eu procuro*,
então a triagem e o resumo leem as regras do modo antes das dele.
"""

from __future__ import annotations

from dataclasses import replace

from .criterios_da_cacada import Criterios, FonteDaCacada

MODO_FREELAS = "freelas"

TIPOS_DE_FREELA = frozenset({"workana", "99freelas", "freelancer"})

PEDIDO_DE_FREELAS_RAPIDOS = """\
NESTA CAÇADA (modo freelas rápidos), estas regras valem antes das outras:
- Só freela. Vaga de emprego, CLT, PJ fixo ou contrato contínuo é "descartada", por melhor que seja.
- O que ele quer é dinheiro rápido: freela pequeno de preço fechado (ou por marco) que ele entrega com \
IA em algumas horas ou num fim de semana, até umas 20 horas de trabalho, e que paga na entrega pela \
plataforma (escrow, marco) ou por bounty.
- "chance_boa" é o freela rápido que casa forte com o que ele já fez: ajuste ou seção de tema Shopify, \
app ou checkout Shopify, landing page, site pequeno, correção de bug em React/Next.js/Node, integração \
de API ou webhook, automação ou script em Python ou Node, scraping, painel simples, integração com LLM. \
Quanto mais novo o anúncio (até 3 dias) e menos propostas, maior o encaixe.
- "tentar_a_sorte" é o freela rápido de encaixe médio, ou o bom que já tem muita proposta.
- Freela grande (semanas de trabalho), sem orçamento nenhum e sem escopo, ou com prazo curto demais \
para quem trabalha de dia é "descartada". Freela por hora avulso continua "descartada".
- No resumo do freela, diga quantas horas ele leva com IA e o preço que faz sentido pedir."""

_A_FUNDO = (
    "Vasculhe a fundo: abra várias listagens e páginas, confira se cada projeto ainda está aberto e "
    "recebendo propostas, e traga o máximo de freelas reais que achar."
)

FONTES_DE_FREELA_RAPIDO = (
    FonteDaCacada("Freelancer.com · Shopify", "freelancer", "shopify"),
    FonteDaCacada("Freelancer.com · Next.js", "freelancer", "nextjs"),
    FonteDaCacada("Freelancer.com · Node.js", "freelancer", "nodejs"),
    FonteDaCacada("Freelancer.com · Python", "freelancer", "python"),
    FonteDaCacada("Freelancer.com · landing page", "freelancer", "landing page"),
    FonteDaCacada("Freelancer.com · bug fix", "freelancer", "bug fix"),
    FonteDaCacada("Freelancer.com · API", "freelancer", "api integration"),
    FonteDaCacada("Freelancer.com · automação", "freelancer", "automation"),
    FonteDaCacada(
        "Web · Workana e 99Freelas recentes",
        "web",
        "projetos de preço fechado na Workana e na 99Freelas publicados nas últimas 72 horas, com poucas "
        "propostas, de landing page, site pequeno, Shopify, WordPress, React/Next.js, correção de bug, "
        "integração de API ou automação, que dê para entregar em até um fim de semana. " + _A_FUNDO,
    ),
    FonteDaCacada(
        "Web · Upwork, Contra e afins",
        "web",
        "fixed-price freelance web development gigs posted in the last 3 days on Upwork, Contra, Freelancer.com, "
        "Guru, PeoplePerHour or Toptal-like boards that accept workers from Brazil or worldwide: small Shopify "
        "fixes, landing pages, React/Next.js or Node bug fixes, API integrations, scripts and automations, "
        "doable in under 20 hours. " + _A_FUNDO,
    ),
    FonteDaCacada(
        "Web · Shopify",
        "web",
        "lojistas e agências contratando freela rápido de Shopify nos últimos 5 dias: ajuste de tema Liquid, "
        "seção nova, bug no tema ou no carrinho, app ou checkout extension, migração pequena, velocidade da "
        "loja; em fóruns, Reddit (r/shopify, r/ShopifyeCommerce), Upwork, Shopify Community e grupos. " + _A_FUNDO,
    ),
    FonteDaCacada(
        "Web · bounties pagos",
        "web",
        "bounties pagos e abertos em projetos open-source de TypeScript, JavaScript, React, Node ou Python, "
        "publicados nos últimos 14 dias, de US$ 50 para cima, no Algora, Opire, IssueHunt, BountySource ou "
        "issues do GitHub com label de bounty, que dê para resolver em poucas horas. " + _A_FUNDO,
    ),
    FonteDaCacada(
        "Web · posts de quem está contratando",
        "web",
        "posts [Hiring] dos últimos 3 dias no Reddit (r/forhire, r/jobbit, r/slavelabour, r/webdev, "
        "r/reactjs), no X/Twitter e no Hacker News de gente procurando freela de desenvolvimento web, script "
        "ou automação com pagamento por tarefa, aceitando remoto do Brasil. " + _A_FUNDO,
    ),
    FonteDaCacada(
        "Web · freelas no Brasil fora das plataformas grandes",
        "web",
        "pedidos de freela de desenvolvimento web, sistema pequeno, automação ou loja virtual publicados nos "
        "últimos 3 dias no Brasil fora da Workana e da 99Freelas (GetNinjas, Freelas.com.br, Trampos, "
        "comunidades e posts públicos), com orçamento ou preço fechado. " + _A_FUNDO,
    ),
)


def criterios_de_freelas(criterios: Criterios) -> Criterios:
    """Os critérios dele com as fontes de freela, as do modo e o pedido do modo na frente."""
    dele = [fonte for fonte in criterios.fontes if fonte.tipo in TIPOS_DE_FREELA]
    nomes = {fonte.nome.casefold() for fonte in dele}
    fontes = dele + [fonte for fonte in FONTES_DE_FREELA_RAPIDO if fonte.nome.casefold() not in nomes]
    procuro = f"{PEDIDO_DE_FREELAS_RAPIDOS}\n\n{criterios.procuro}".rstrip()
    return replace(criterios, fontes=tuple(fontes), procuro=procuro)

"""O modo freelas rápidos da caçada (`whis hunt --freelas`): dinheiro rápido, só freela.

A corrida é a mesma da caçada; muda o que ela lê e como julga. Das fontes de
*Fontes*, ficam só as de freela (Workana, 99Freelas, Freelancer.com), e
entram as de `FONTES_DE_FREELA_RAPIDO`: mais buscas no Freelancer.com e a web
vasculhada por vários lados (plataformas, Shopify, bounties pagos, posts de
quem está contratando). O pedido do modo vai na frente de *O que eu procuro*,
então a triagem e o resumo leem as regras do modo antes das dele.
"""

from __future__ import annotations

from collections.abc import Sequence
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
- Bounty de issue (GitHub, Algora, Opire) é disputado em minutos: ganha quem posta a proposta logo que \
a issue abre. Bounty com proposta já postada, PR aberto ou mais de uns 5 comentários nunca é \
"chance_boa": no máximo "tentar_a_sorte". Bounty com responsável designado, PR já aceito ou issue \
fechada é "descartada". Sem "detalhes" que mostrem a concorrência, bounty também fica em \
"tentar_a_sorte", e o motivo diz que não deu para ver quantos já propuseram.
- Projeto da 99Freelas com "Projeto exclusivo para assinantes" nos detalhes só aceita proposta dele na hora que os detalhes dizem: julgue igual aos outros, e o resumo começa dizendo quando abre para ele.
- Projeto do Freelancer.com com "escolha a skill" nos detalhes: o resumo diz qual skill ele marca na proposta e avisa que, se a página disser "aberto apenas a freelancers selecionados", ele pula (pede saldo de US$ 20, que ele não deposita). A conta grátis dele tem só 6 propostas por mês no Freelancer.com: lá, "chance_boa" só com encaixe muito forte.
- Freela grande (semanas de trabalho), sem orçamento nenhum e sem escopo, ou com prazo curto demais \
para quem trabalha de dia é "descartada". Freela por hora avulso continua "descartada".
- No resumo do freela, diga quantas horas ele leva com IA e o preço que faz sentido pedir."""

_A_FUNDO = (
    "Vasculhe a fundo: abra várias listagens e páginas, confira se cada projeto ainda está aberto e "
    "recebendo propostas, e traga o máximo de freelas reais que achar."
)

PEDIDO_DA_RODADA_EXTRA = (
    "RODADA EXTRA: a primeira passada já trouxe o que está em JÁ VISTAS. Agora traga freelas DIFERENTES: "
    "abra páginas, filtros, categorias e sites que você ainda não abriu, e não repita nenhum link."
)

PEOPLEPERHOUR = "peopleperhour"
WORKANA = "workana"
NOVENTA_E_NOVE = "99freelas"
VINTEPILA = "vintepila"
FREELANCER_BR = "freelancer.com.br"


def _web_recentes(com_workana: bool, com_99freelas: bool = True) -> FonteDaCacada | None:
    if com_workana and com_99freelas:
        nome, onde = "Web · Workana e 99Freelas recentes", "na Workana e na 99Freelas"
    elif com_99freelas:
        nome, onde = "Web · 99Freelas recentes", "na 99Freelas (nada da Workana: a conta dele lá não está ativa)"
    elif com_workana:
        nome, onde = "Web · Workana recentes", "na Workana (nada da 99Freelas: ela é lida logada à parte)"
    else:
        return None
    return FonteDaCacada(
        nome,
        "web",
        f"projetos de preço fechado {onde} publicados nas últimas 72 horas, com poucas "
        "propostas, de landing page, site pequeno, Shopify, WordPress, React/Next.js, correção de bug, "
        "integração de API ou automação, que dê para entregar em até um fim de semana. " + _A_FUNDO,
    )


def _web_fora_das_grandes(com_workana: bool, sem_vintepila: bool = False, sem_freelancer_br: bool = False) -> FonteDaCacada:
    fora = "fora da Workana e da 99Freelas" if com_workana else (
        "fora da 99Freelas e sem nada da Workana (a conta dele lá não está ativa)"
    )
    nada = [
        "da VintePila (ela é lida logada à parte)" if sem_vintepila else "",
        "do freelancer.com.br (responder lá pede plano pago)" if sem_freelancer_br else "",
    ]
    nada_de = f"Não traga nada {' nem '.join(n for n in nada if n)}. " if any(nada) else ""
    return FonteDaCacada(
        "Web · freelas no Brasil fora das plataformas grandes",
        "web",
        "pedidos de freela de desenvolvimento web, sistema pequeno, automação ou loja virtual publicados nos "
        f"últimos 3 dias no Brasil {fora} (GetNinjas, Freelas.com.br, Trampos, "
        f"comunidades e posts públicos), com orçamento ou preço fechado. {nada_de}" + _A_FUNDO,
    )


def _web_internacional(com_peopleperhour: bool) -> FonteDaCacada:
    depois = "Guru and PeoplePerHour" if com_peopleperhour else "Guru"
    pular = "Freelancer.com and Upwork (paid bids)"
    if not com_peopleperhour:
        pular += ", PeoplePerHour (his account there is still under review)"
    return FonteDaCacada(
        "Web · Contra e clientes dos EUA e da Europa",
        "web",
        "fixed-price freelance web development gigs posted in the last 3 days by clients in the US, Canada, "
        f"Europe or Latin America that accept workers from Brazil: Contra projects first (no fees), then {depois}; "
        f"skip {pular} and any project budgeted in Indian rupees. Small Shopify fixes, landing pages, "
        "React/Next.js or Node bug fixes, API integrations, scripts and automations, doable in under 20 hours. "
        + _A_FUNDO,
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
    _web_recentes(com_workana=True),
    _web_internacional(com_peopleperhour=True),
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
        "issues do GitHub com label de bounty, que dê para resolver em poucas horas. Abra a issue de cada "
        "bounty e diga em detalhes quantas propostas e comentários ela já tem, se alguém foi designado e se "
        "já há PR; prefira as que ainda não têm proposta nenhuma. Nunca traga bounty de repositório da "
        "organização SUSU-LABS no GitHub: os repositórios dela escondem malware no eslint.config.js. " + _A_FUNDO,
    ),
    FonteDaCacada(
        "Web · posts de quem contrata no Brasil",
        "web",
        "posts públicos dos últimos 3 dias de brasileiros procurando freelancer ou dev para um trabalho pago: "
        "LinkedIn (\"procuro freelancer\", \"preciso de um dev\", \"freela de site\", \"freela Shopify\"), X/Twitter "
        "(\"freela dev\", \"procuro programador\"), grupos e comunidades públicas (Discord, Telegram, Facebook, "
        "Reddit r/brdev e r/programacao), de site, loja, automação, integração ou correção de bug. Traga o "
        "post com o link dele e como falar com quem postou. " + _A_FUNDO,
    ),
    FonteDaCacada(
        "Web · Shopify no Brasil",
        "web",
        "lojistas e agências brasileiras de Shopify procurando dev freela nos últimos 7 dias: posts no "
        "LinkedIn e no Instagram, comunidades de Shopify no Brasil, agências parceiras da Shopify que "
        "terceirizam tema, seção, app ou migração, e lojas que anunciam vaga freela. " + _A_FUNDO,
    ),
    _web_fora_das_grandes(com_workana=True),
)


def criterios_de_freelas(
    criterios: Criterios,
    plataformas_sem_conta: Sequence[str] = (),
    *,
    cobertos: Sequence[str] = (),
    plataformas_pagas: Sequence[str] = (),
) -> Criterios:
    """Os critérios dele com as fontes de freela, as do modo e o pedido do modo na frente.

    Plataforma em `plataformas_sem_conta` some do texto das buscas web; hoje
    só o PeoplePerHour e a Workana são citados nelas. `cobertos` são os sites
    que o Chrome da caçada leu logado nesta corrida (99Freelas, VintePila): o
    explorador deixa de procurar neles, e volta quando o login cai. Site em
    `plataformas_pagas` (freelancer.com.br) também sai das buscas.
    """
    dele = [fonte for fonte in criterios.fontes if fonte.tipo in TIPOS_DE_FREELA]
    nomes = {fonte.nome.casefold() for fonte in dele}
    sem_conta = {p.casefold() for p in plataformas_sem_conta}
    logados = {c.casefold() for c in cobertos}
    pagas = {p.casefold() for p in plataformas_pagas}
    trocas = {
        FONTES_DE_FREELA_RAPIDO.index(original): nova
        for original, nova in (
            (_web_recentes(True), _web_recentes(WORKANA not in sem_conta, NOVENTA_E_NOVE not in logados)),
            (_web_internacional(True), _web_internacional(PEOPLEPERHOUR not in sem_conta)),
            (
                _web_fora_das_grandes(True),
                _web_fora_das_grandes(WORKANA not in sem_conta, VINTEPILA in logados, FREELANCER_BR in pagas),
            ),
        )
    }
    do_modo = [trocas.get(i, fonte) for i, fonte in enumerate(FONTES_DE_FREELA_RAPIDO)]
    fontes = dele + [fonte for fonte in do_modo if fonte is not None and fonte.nome.casefold() not in nomes]
    procuro = f"{PEDIDO_DE_FREELAS_RAPIDOS}\n\n{criterios.procuro}".rstrip()
    return replace(criterios, fontes=tuple(fontes), procuro=procuro)

# 03 — O perfil: o que o Whis já sabe dele

Type: research
Status: resolved

## Question

O mapa original adiou a busca "até o perfil existir", e a interface (Q29) disse que ele existe.
**Confira**: com o que está no vault hoje (diário, reuniões, cópias da daily, notas) e nas fontes
passivas (git, Linear), o Whis consegue dizer a stack, o tipo de problema que ele resolve, a
senioridade e o idioma de trabalho dele — o bastante para julgar uma vaga?

E o que **não** dá para tirar dali e só ele sabe: preferência, faixa, o que ele quer deixar de
fazer, o currículo. Disso sai a pergunta para o ticket 04: o perfil é **escrito por ele** (um
arquivo dele no vault, como `noticias/fontes.md`), **derivado pelo agente**, ou os dois.

**Candidata levantada por ele em 2026-10-02: o contexto do Claude Code** — *como* ele trabalha
(fluxo com agentes, skills, specs, em que repos e linguagens), que o git não mostra. Conferir antes
de pensar em hook: o Claude Code já guarda as sessões em `~/.claude/projects/` (JSONL), o que faria
disso uma fonte passiva lida depois, sem nada rodando enquanto ele trabalha. Medir o que dá para
tirar dali, por quanto tempo fica guardado (`cleanupPeriodDays`, 30 dias por padrão) e o que é do
empregador e não pode sair do PC nem aparecer numa candidatura.

Lembrete da interface: o `%APPDATA%` e o vault desta sessão de agente não são os dele — quem
confere o vault real é ele.

**Decidido por ele (ticket 01)**: o que está no vault basta, e o que faltar o Whis pede. Esta
pesquisa vira: o que o Whis tira do vault, e **a lista do que vai pedir** na primeira corrida —
candidatar-se pede o que o vault não tem (currículo, formação, contato, pretensão, portfólio).

## Answer

[Research 03](../research/03-o-perfil.md). **O vault guarda o trabalho do dia, não o
profissional**: dá o tipo de problema e o domínio, mal a stack, e nada de senioridade ou inglês.
O "vault basta" dele vira **o vault mais as fontes passivas relidas**: os repositórios de
`[git].raiz` dão linguagens (extensões), frameworks (manifestos) e anos de commit, de graça.
O Claude Code é a melhor fonte de "como ele trabalha" e a mais perigosa (o código do empregador
está nos transcripts): fica para depois. O que só ele sabe vai para *Sobre mim* em
`cacada/criterios.md`, com os itens já listados; o que faltar vira pergunta no topo do relatório.
O resumo do perfil abstrai o empregador, e é só ele que as propostas leem.

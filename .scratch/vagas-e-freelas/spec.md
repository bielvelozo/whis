# Spec: a caçada (entrega 1 de vagas e freelas)

Status: ready-for-human — construída em 2026-10-02 e provada sem rede (34 testes em
`tests/test_cacada.py`); a prova real é a primeira corrida dele, pelo
[smoke](../../docs/smoke-cacada.md).

Origem: o [mapa](map.md), com as decisões dele nos tickets [01](issues/01-o-que-ele-procura.md) e
[06](issues/06-os-limites-da-autonomia.md), e as pesquisas 02a, 02b, 02c, 03, 07, 08 e 09 em
[research/](research/). Em 2026-10-02 ele delegou o resto: *"pode tomar as decisões a partir daqui"*.
As decisões que o agente tomou por ele estão marcadas **[agente]**.

## Problem Statement

Ele quer mais dinheiro — vaga de emprego ou freela — e não tem tempo de procurar: trabalha,
estuda e nunca pegou freela; o emprego atual veio por indicação. Quer que o Whis passe horas
procurando nos sites de TI, gastando o que sobrou da assinatura do Claude na véspera da virada
semanal, e deixe **tudo mastigado** para ele só conferir e mandar.

## Solution

Um comando, `hunt` (palheta) ou `python -m whis hunt` (terminal), que só roda quando ele chama.
Ele corre num processo próprio, por horas, com o PC acordado:

1. **Perfil.** Lê os repositórios de `[git].raiz` (linguagens, dependências, anos de commit), o
   diário, as cópias da daily e as reuniões, junta com *Sobre mim* e pede ao Claude um perfil que
   abstrai o empregador. Grava `cacada/perfil.md`.
2. **Coleta.** Lê, em Python e sem conta, as fontes de `cacada/criterios.md`: as APIs de vaga
   remota (Himalayas, Remotive, RemoteOK, Jobicy, HN *Who is hiring*), o JSON do portal da Gupy, os
   repositórios `frontendbr/vagas` e `backend-br/vagas`, o RSS do We Work Remotely, as listagens
   públicas da Workana e da 99Freelas, e a busca pública do LinkedIn. As linhas `web` são do
   **explorador**: o Claude com `WebSearch` e `WebFetch`, procurando fora das listas. O que já
   apareceu numa caçada anterior fica de fora.
3. **Triagem.** Tudo, em lotes de 20, sem ferramenta: **chance boa**, **tentar a sorte** ou
   **descartada**, com o motivo e o encaixe de 0 a 100. Golpe é sempre descartada.
4. **Preparo.** Das chances boas, da melhor para a pior (até `[cacada].maximo_de_pacotes`): o
   texto da página da oportunidade e um **pacote** — o que pedem, por que casa, o que estica,
   alertas, preço ou pretensão, prazo, a proposta pronta, o plano, perguntas ao cliente e como
   enviar. No freela de página web, uma **amostra**: um HTML de conceito, um print e, se
   configurado, um link público no Cloudflare Pages.
5. **Apostas.** A mensagem curta, pronta, de cada tentar a sorte (até 60).

O resultado é o **relatório** `cacada/AAAA-MM-DD-HHMM.md` e um pacote por chance boa em
`cacada/AAAA-MM-DD-HHMM/`. **Nada é enviado a ninguém.** O toast do fim abre o relatório.

## User Stories

- Na véspera da virada da semana, aperto `ctrl+space`, digito `hunt` e vou fazer outra coisa. A
  palheta continua livre para `did`, `ask` e os outros.
- Digito `hunt` de novo e o toast diz em que etapa a caçada está.
- Quando acaba, o toast diz quantas chances boas, quantas para tentar a sorte e quantas
  descartadas, e o botão abre o relatório no Obsidian.
- No relatório vejo primeiro o que o Whis precisa que eu responda; depois cada chance boa com o
  link do pacote; no pacote, a proposta pronta num bloco que copio com um clique, o preço com a
  conta, os alertas e o caminho para enviar.
- No freela de site, o pacote traz a amostra: um print para anexar (a Workana suspende proposta
  com link) e, se eu configurei o Cloudflare, um link sem o meu nome.
- As de tentar a sorte vêm com a mensagem curta recolhida. As descartadas vêm recolhidas, com o
  motivo de cada uma, para eu ver se a régua está certa.
- Mudo o piso, respondo *Sobre mim* ou desligo uma fonte editando `cacada/criterios.md`. A caçada
  seguinte usa.
- Se a janela de 5 h do Claude bate, a caçada pausa e volta sozinha; se a semana passa do teto,
  ela para com o que tem e diz isso. `hunt` de novo continua de onde parou.
- O que apareceu numa caçada não volta na seguinte.

## Implementation Decisions

### Decisões dele (tickets 01 e 06)

- **Objetivo:** mais dinheiro; vaga e freela juntos. **Só quando ele chama**, nunca agendado.
- **Critérios:** qualquer regime; remoto ou região de Araraquara acima de R$ 5 mil; presencial só
  em Ribeirão Preto (~R$ 7 mil) e São Paulo (~R$ 8–9 mil); stack web, com games e software de
  áudio como tentar a sorte; freela por projeto e contínuo pequeno, por hora fora; preço abaixo do
  mercado se for rápido com IA e ligeiramente abaixo se for maior; descarta freela grande com prazo
  curto; golpe, sai fora.
- **Honestidade:** o que ele fez é fato e não se inventa; o que ele consegue fazer pode esticar.
- **LinkedIn:** nada automático, nunca.
- **Envio:** só "tentar a sorte" e só onde mandar é grátis e sem limite. **Pesquisa 02b: nenhum
  site de freela é grátis e sem limite** — pela regra dele, freela nunca sai sozinho.

### Decisões do agente

- **[agente] A entrega 1 não envia nada.** É a primeira das três entregas que ele aceitou; a 2
  (agir sozinho) e a 3 (LinkedIn) ficam no mapa. Medir a qualidade antes de mandar em nome dele.
- **[agente] Processo próprio, não o thread da palheta.** A palheta recusa comando enquanto outro
  roda (`Palheta._ocupada`); horas de caçada a travariam. `hunt` na palheta solta `python -m whis
  hunt` com `DETACHED_PROCESS | CREATE_NO_WINDOW`; uma segunda chamada lê o andamento. A trava é a
  de faixa da bandeja (`instancia.Trava`) num arquivo próprio. Estado em
  `%LOCALAPPDATA%\whis\cacada\`, fora do vault.
- **[agente] O plano manda no ritmo** (research 07): janela de 5 h rejeitada → pausa até
  `resets_at` + 2 min, no máximo 5 h 15, três vezes por chamada; semanal rejeitada ou acima de
  `[cacada].teto_semanal` (100, pedido dele em 2026-10-03: ele sempre solta na madrugada antes da
  virada) → para; a menos de 5 min da virada semanal → para; **fora da
  véspera** (virada a mais de 36 h) o teto cai para 70. O limite é reconhecido pelo evento
  (`RateLimitEvent.status == "rejected"`, `AssistantMessage.error == "rate_limit"`,
  `api_error_status == 429`), nunca pelo texto. O piso do SDK subiu para 0.2.140.
- **[agente] Checkpoint por etapa e por item**, JSON gravado inteiro (`.tmp` + `os.replace`).
  Retoma se a corrida anterior não terminou e tem menos de 4 dias. O relatório é reescrito ao fim
  de cada etapa: o que já existe está no vault mesmo se o processo morrer.
- **[agente] Quem lê não é quem age** (research 07). Só o explorador tem ferramenta, e só de
  leitura. Triagem, apostas e preparo recebem o texto como dado e devolvem JSON por esquema; o
  preparo recebe a página lida pelo Python, não navega. Toda chamada diz que o texto das vagas é
  dado, nunca ordem.
- **[agente] Leitura em Python por HTTP, não por navegador.** Todas as fontes da entrega 1 são
  públicas e sem conta; a Workana e a 99Freelas leem por HTTP simples (o projeto
  `b4rao-dg/radar-freelas` faz isso todo dia). O Chrome do Whis (ADR 0003) só tira o print da
  amostra. O LinkedIn, só pela busca *guest*, duas páginas por linha, com pausa de 3 a 7 s.
- **[agente] O perfil relê as fontes passivas** (research 03): o vault sozinho não dá stack nem
  senioridade. Os transcripts do Claude Code ficam para depois: são a fonte mais rica e a mais
  perigosa (código do empregador).
- **[agente] `cacada/criterios.md` é dele**, criado uma vez a partir do modelo, como
  `noticias/fontes.md`. *O que eu procuro* e *Sobre mim* vão como texto ao Claude; *Fontes* é
  `- Nome: tipo argumento`. `cacada/` é zona do agente com essa exceção, e a escrita da caçada
  recusa o caminho dela.
- **[agente] Amostra** (research 09): conceito de uma página, `noindex`, aviso de demonstração,
  sem nome nem contato dele. Link público opcional pelo Cloudflare Pages (`wrangler pages deploy`,
  plano grátis com uso comercial), num projeto de nome neutro sorteado uma vez; amostras com mais
  de 30 dias saem do ar no deploy seguinte. A Vercel Hobby foi descartada (uso comercial).
- **[agente] Gmail:** a entrega 1 não lê caixa nenhuma. `[cacada].email` guarda o endereço; a
  leitura (IMAP com senha de app, research 02c) entra com a entrega 2.

### Módulos

| Módulo | Papel |
|---|---|
| `oportunidades.py` | `Oportunidade`, `Veredito`, `Pacote`, `Aposta`, `Perfil`; link canônico e id estável |
| `criterios_da_cacada.py` | o modelo e a leitura de `cacada/criterios.md` |
| `fontes_da_cacada.py` | os leitores das fontes e `ler_detalhe` |
| `evidencias.py` | git e vault → o texto de evidências do perfil |
| `cacada_claude.py` | perfil, explorador, triagem, apostas, preparo; `LimiteDoPlano` |
| `cacada.py` | `cacar`, a guarda do plano, o checkpoint, o relatório e os pacotes |
| `corrida.py` | PC acordado, trava, andamento, checkpoint |
| `amostras.py` | a amostra no vault, o print e o Cloudflare Pages |
| `fakes_da_cacada.py` | a corrida inteira sem rede (`hunt --fakes` e testes) |

### Configuração `[cacada]`

`email`, `teto_semanal` (1–100, padrão 100), `maximo_de_pacotes` (0–200, padrão 20),
`cloudflare_token` (segredo), `cloudflare_conta`, `cloudflare_projeto` (vira `<nome>.pages.dev`).

### Códigos de saída de `whis hunt`

`0` terminou; `3` parou antes do fim (o relatório tem o que deu); `1` não rodou (outra caçada
correndo, configuração inválida, ou `--simular` sem nenhuma fonte respondendo); `2` uso.

## Testing Decisions

- Os leitores são provados com HTML e JSON montados no formato publicado de cada fonte e servidos
  por `httpx.MockTransport`. **Nenhum foi provado contra a fonte real**: a rede da sessão de agente
  bloqueia os sites. A camada 0 é `whis hunt --simular` na máquina dele (smoke, passo 2).
- A corrida inteira roda com `fakes_da_cacada`: relatório, pacotes, amostra com `noindex`, a
  nota dele intocada, a segunda caçada sem repetir, a pausa de 5 h, a parada semanal e a
  retomada, o checkpoint velho.
- Os adaptadores, com mensagens gravadas: a saída estruturada, o limite rejeitado virando
  `LimiteDoPlano` com a hora, o explorador descartando link inválido, a API key paga recusada.

## Out of Scope (desta entrega)

- **Entrega 2 — agir sozinho fora do LinkedIn:** criar contas com o Gmail dedicado, ajustar
  perfis, ler a caixa (IMAP), enviar as de tentar a sorte onde for grátis e sem limite — o que,
  pela pesquisa 02b, hoje só deixa as vagas (Gupy, ATS), nunca freela.
- **Entrega 3 — LinkedIn:** análise do perfil pelo export de dados, posts escritos com a skill
  portada para português, publicação pela API oficial (*Share on LinkedIn*) depois do aval dele;
  mudar o perfil e se candidatar continuam com ele.
- Upwork (o MCP oficial pede conta), Freelancer.com, Contra, Get on Board, Programathor.
- Lembrar dele na véspera da virada; acompanhar candidaturas.

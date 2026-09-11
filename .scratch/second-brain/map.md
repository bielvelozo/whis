# Mapa: Second Brain

Labels: wayfinder:map

## Destination

Todas as decisões arquiteturais centrais fechadas — estender-Whis-vs-separado, captura de atividade, transcrição, escrita no vault, recuperação — culminando numa **spec construível do tracer bullet**: "aperto um botão durante a reunião → nota transcrita/resumida aparece no vault". Este mapa planeja; a construção começa depois do handoff da spec.

## Notes

- Idioma: todos os artefatos deste esforço em português.
- Transcrição é **sob demanda**: liga/desliga manual, nunca escuta contínua. **Não há observação de atividade do PC** — contexto de trabalho vem de reuniões + fontes passivas (git, Linear, Slack, navegador se relevante).
- Áudio de reuniões pode ir para APIs em nuvem. Teto de custo: **R$ 100/mês** em APIs — mas o pipeline decidido roda a **R$ 0 real** (crédito Deepgram de US$ 200). Claude via conta própria do usuário (sem custo novo).
- Pragmatismo > purismo local: escolher o que for mais rápido de funcionar.
- Hardware: o second brain vai viver no **PC desktop** do usuário (Windows 11, Ryzen 5 5600G, sem GPU dedicada); o desenvolvimento começa neste notebook (Ryzen 5 5500U). Nenhuma das máquinas tem GPU dedicada — Whisper local grande é inviável; nuvem é o caminho provável.
- Reuniões: Google Meet, com fone (a voz dos outros não passa pelo microfone — captura precisa de loopback do áudio do sistema), idioma misto pt-BR/inglês.
- O usuário ainda não usa Obsidian — o vault nasce do zero, sem notas manuais preexistentes.
- O Whis (`~/development/project-whis`) já existe: agente pessoal self-hosted com WhatsApp (Evolution API) + Claude + vault Obsidian + arquitetura de skills. Ver [Examinar a arquitetura do Whis](issues/01-examinar-arquitetura-whis.md).
- Skills a consultar por sessão: `/grilling` e `/domain-modeling` nos tickets de decisão; `/research` nos de pesquisa; `/to-spec` no ticket final.
- Achados de research vivem em `.scratch/second-brain/research/`, linkados do ticket.

## Decisions so far

<!-- uma linha por ticket fechado: gist + link -->

- [Examinar a arquitetura do Whis](issues/01-examinar-arquitetura-whis.md) — Whis é agente de chat Docker-only em produção na EC2 (Claude Agent SDK, vault prompt-driven na EC2, WhatsApp dormente); um coletor no Windows local seria externo por construção (integração só via MCP remoto, endpoint novo ou sync do vault) e o projeto está sem commits há ~3 meses.
- [Pesquisar captura de áudio no Windows + STT em nuvem](issues/03-pesquisa-captura-audio-stt.md) — captura é problema resolvido (PyAudioWPatch: mic + loopback WASAPI; OBS como opção zero-código); todos os STT cabem no teto de R$ 100 para 20h/mês — Deepgram Nova-3 (~R$ 60–73, único com code-switching pt/en formal), AssemblyAI (~R$ 25), OpenAI gpt-4o-transcribe (~R$ 39, limite 25 MB/arquivo).
- [Avaliar agentes prontos como base (OpenClaw e afins)](issues/10-pesquisa-agentes-prontos.md) — OpenClaw dá loop/memória-markdown/cron/OAuth de graça, mas Windows nativo é segunda classe (WSL2 é o caminho oficial), vault Obsidian externo foi recusado como "not planned", e o histórico de segurança é pesado (gateways expostos, 3 CVEs altas, prompt injection aberta); os coletores WASAPI/atividade e o pipeline STT seriam custom em qualquer cenário. Hermes (Nous Research) é a mesma categoria, menos maduro e Linux-first.
- [Pesquisar opções de captura de atividade do PC](issues/05-pesquisa-captura-atividade.md) — ActivityWatch (janela+AFK+URLs, API local, liga/desliga fácil) + fontes retroativas (git log, histórico do navegador) cobrem o resumo diário por centavos e exposição mínima; screenshots+visão custam US$ 4–10+/mês com o pior perfil de privacidade (precedente Windows Recall), mitigável só com OCR local (screenpipe).

- [Pesquisar Granola como motor de transcrição + STT grátis](issues/11-pesquisa-granola-stt-gratis.md) — Granola free é sustentável mas só como fonte manual (cache Windows encriptado, transcript automatizado é feature paga, histórico 30 dias); STT de graça existe de verdade: Groq free (Whisper large-v3, 8h/dia, R$ 0) e crédito Deepgram de US$ 200 sem cartão (~3 anos a 20h/mês, com diarização nativa).
- [Estender o Whis ou projeto separado?](issues/02-estender-whis-ou-separar.md) — **Projeto separado, fino e 100% local**: coletores Windows custom + Claude Agent SDK (OAuth da conta) + vault Obsidian novo no PC; Whis aposentado vira doador de ideias, OpenClaw avaliado e descartado. ADR: [0001](../../docs/adr/0001-projeto-separado-100-local.md).

- [Pesquisar acesso às fontes passivas](issues/12-pesquisa-fontes-passivas.md) — as quatro fontes saem a R$ 0 com leitura retroativa sob demanda: git é trivial (`git log --author --since` por repo), Linear tem API key read-only sem expiração + MCP oficial readonly, navegador é copiar o SQLite antes de ler, e Slack funciona via app interna com user token xoxp (rate limits punitivos de 2025/26 não atingem apps internas) — o único risco real é aprovação de admin no workspace.
- [Decidir a abordagem de captura de atividade](issues/06-decidir-captura-atividade.md) — **não haverá monitoramento de atividade do PC**; o contexto de trabalho vem de fontes passivas — git local, Linear e Slack (usuário consegue criar tokens), navegador se relevante — cujo detalhe fica em [Decidir as integrações de fontes passivas](issues/13-decidir-fontes-passivas.md).
- [Decidir o pipeline de transcrição](issues/04-decidir-pipeline-transcricao.md) — PyAudioWPatch (mic + loopback em canais separados) com liga/desliga na bandeja → Deepgram Nova-3 batch no crédito de US$ 200 (R$ 0 real por ~3 anos) → resumo do Claude na nota + transcrição bruta linkada; Granola vira fonte manual interina e se aposenta quando o coletor provar.

- [Estrutura do vault Obsidian](issues/07-estrutura-vault-obsidian.md) — vault em pasta dedicada fora do repo, estrutura por fonte (`reunioes/`, `transcricoes/`, `diario/`, `notas/`), frontmatter mínimo com wikilink para a transcrição, zonas de propriedade (agente nunca edita `notas/`), áudio bruto retido 7 dias fora do vault.

- [Como o agente recupera contexto](issues/08-recuperacao-de-contexto.md) — busca agêntica pura (agente com `cwd` no vault, grep/leitura pela estrutura), sem índice; RAG só se o vault passar de ~2.000 notas ou a busca falhar na prática; entrada via chat no terminal + comando one-shot; escrita em `notas/` só sob pedido explícito.

- [Decidir as integrações de fontes passivas](issues/13-decidir-fontes-passivas.md) — v1 lê git (varredura automática de repos) + Linear (tudo do time, API key read-only) + Slack (tudo que o usuário participa, com blocklist, via app interna xoxp); navegador fora da v1; diário gerado por tarefa agendada no fim do dia; filtro de exclusão configurável antes de qualquer coisa ir ao Claude.

- **Entrega 2 — fontes passivas + daily** (2026-09-03/04): fechada e em uso real. Diário, daily com janela da última fala, coletores de git/Linear/Slack, e a daily lida numa reunião de verdade em 2026-09-04. Spec em [.scratch/fontes-passivas/spec.md](../fontes-passivas/spec.md); onze camadas, dez resolvidas e uma revertida.
- **Entrega 3 — recuperação de contexto** (aberta em 2026-09-04, **provada na máquina do usuário em 2026-09-10**): a DM do Slack no ar, o Claude lendo o vault com 17 chamadas de ferramenta a US$ 0,56 equivalentes por pergunta, o fio de 24 h e a fonte ao vivo confirmados. Falta só a pasta privada, que depende da escolha dele. Spec em [.scratch/recuperacao-contexto/spec.md](../recuperacao-contexto/spec.md), com contrato fixado e cinco camadas. O ticket 08 foi **refinado**: o agente não recebe `cwd` cru no vault, e sim ferramentas nossas — foi o que a pasta privada escolhida pelo usuário exigiu.
- **Entrega 4 — a interface** (levantamento aberto em 2026-09-09): o usuário percebeu que acionar o Whis por comando "vai ser muito ruim". A frente 1 do handoff (fechar o Slack) foi cumprida em 10/09 e deixou seis achados de uso real, todos decisões de interface. Resta o levantamento das superfícies (agendador + toast, bandeja, DM do Slack como painel, Obsidian, janela local), em [.scratch/interface/handoff.md](../interface/handoff.md). **É levantamento antes de spec**, pela lição da entrega 3.
- **O projeto virou `Whis`** em 2026-09-09, herdando o nome do agente aposentado do usuário. O glossário em `CONTEXT.md` distingue os dois; documentos de entregas fechadas guardam o nome antigo de propósito.
- [Escrever a spec do tracer bullet](issues/09-spec-tracer-bullet.md) — **destino alcançado**: spec publicada em [.scratch/tracer-bullet/spec.md](../tracer-bullet/spec.md) (`ready-for-agent`), consolidando todas as decisões; nenhum ticket aberto resta no mapa.

## Not yet specified

- Busca de vagas e freelance usando o perfil acumulado — em escopo, mas só especificável depois que o observador rodar e o perfil existir.
- Lembretes e comportamento proativo do agente (avisar sem ser perguntado) — a interface reativa já foi decidida (chat + one-shot); a proativa depende de uso real. **O uso real chegou** (2026-09-09): a daily cinco minutos antes da reunião, pedida na demo de 04/09, é o primeiro caso — vai pela entrega 4.
- Backup/versionamento do vault (git próprio? sync na nuvem?) — relevante quando o vault tiver dados que doeria perder.
- Conforto do liga/desliga além da bandeja (atalho global de teclado).
## Out of scope

<!-- trabalho conscientemente excluído deste esforço -->

- Monitoramento full de atividade do PC (ActivityWatch, screenshots + visão, hooks de janela, modo sempre-ligado, detecção automática de reunião) — cortado pelo usuário ao resolver [Decidir a abordagem de captura de atividade](issues/06-decidir-captura-atividade.md): reuniões + fontes passivas bastam. Os fatos levantados ficam em [Pesquisar opções de captura de atividade do PC](issues/05-pesquisa-captura-atividade.md) se um esforço futuro reabrir o tema.

# Pesquisa: agentes prontos como base (OpenClaw e afins)

Ticket: [10-pesquisa-agentes-prontos](../issues/10-pesquisa-agentes-prontos.md) · Data: 2026-08-14

Contexto avaliado: second brain 100% local em Windows 11 nativo (Ryzen 5600G, sem GPU), vault Obsidian novo como memória, transcrição de reuniões sob demanda (WASAPI → STT em nuvem → nota), consumo via Obsidian + CLI, Claude via conta Pro/Max, teto R$ 100/mês.

---

## 1. OpenClaw (ex-Clawdbot, ex-Moltbot)

Projeto de Peter Steinberger (fundador do PSPDFKit). Assistente pessoal open-source (MIT, "OpenClaw Foundation") que roda um **Gateway** local e conversa via mensageiros (WhatsApp, Telegram, Slack, Discord, Google Chat, Signal, iMessage), com skills, cron, browser control, voz e "nodes" em dispositivos. Repo: [github.com/openclaw/openclaw](https://github.com/openclaw/openclaw) (~386k stars, ~79k commits). Histórico de nomes: Clawdbot (nov/2025) → Moltbot (27/jan/2026, por pressão jurídica da Anthropic — "Clawdbot" soava como "Claude") → OpenClaw (30/jan/2026). Cada rename veio com quebra de formato de config (JSON → TOML → YAML) ([histórico](https://eastondev.com/blog/en/posts/ai/20260204-openclaw-rename-history/), [DEV](https://dev.to/jordanolsen/openclaw-rebrand-clawdbot-to-moltbot-to-openclaw-explained-522m)).

### 1.1 Windows nativo (sem WSL/Docker)

**Estado real: funciona, mas é caminho de segunda classe.**

- O README oficial lista plataformas como "macOS, Linux, Windows (**via WSL2**)" ([repo](https://github.com/openclaw/openclaw)).
- A [página oficial de Windows](https://docs.openclaw.ai/platforms/windows) oferece três caminhos: **Windows Hub** (app WinUI nativo, Win10 20H2+/11, sem admin — mas o fluxo recomendado "Set up locally" **provisiona um distro WSL gerenciado** por baixo), **CLI nativa via PowerShell** (Node.js direto no Windows) e **WSL2** (runtime "mais compatível" para o Gateway).
- Requisito: Node.js 22.22.3+ / 24.15+ / 25.9+.
- A issue [#23178](https://github.com/openclaw/openclaw/issues/23178) ("Windows native (non-WSL2) setup is undocumented and actively discouraged", fev/2026) confirma: o core roda bem nativo via Node + PowerShell (inclusive auth por token `sk-ant-oat01-*`), mas a documentação implica que nativo não é suportado. Problemas práticos relatados: `&&` inválido em PowerShell causando **falhas silenciosas em cadeias de exec de skills**, e tradeoffs Task Scheduler vs NSSM para auto-start. A issue foi **fechada como stale**, sem correção da doc — sinal de que Windows nativo não é prioridade dos mantenedores.
- Consequência para os coletores: skills que assumem shell POSIX (a maioria das skills da comunidade) quebram ou exigem adaptação em PowerShell. Coletores WASAPI (mic + loopback) não existem no ecossistema — seriam binários/scripts custom chamados via exec, exatamente como num agente próprio.

### 1.2 Modelo de memória — compatível com vault Obsidian?

Memória é **markdown puro em disco** — modelo conceitualmente idêntico ao desejado ([docs de memória](https://docs.openclaw.ai/concepts/memory)):

- Workspace padrão `~/.openclaw/workspace` com: `MEMORY.md` (fatos duráveis, carregado a cada sessão), `memory/YYYY-MM-DD.md` (diários; hoje e ontem carregam automaticamente), `USER.md` (preferências, opcional), `DREAMS.md` (consolidações, opcional). Lema oficial: "o modelo só lembra do que é salvo em disco; não há estado oculto". Quem escreve é o próprio agente, quando instruído ("remember that...") e numa rodada silenciosa de consolidação antes de compactar contexto.
- Busca padrão em SQLite embutido; com provedor de embeddings configurado (OpenAI, Gemini, Ollama, GGUF local etc.), `memory_search` combina vetor + keyword.
- **Apontar para um vault Obsidian arbitrário não é suportado nativamente.** A feature request [#22958](https://github.com/openclaw/openclaw/issues/22958) (Obsidian vault como memória externa, com caminho configurável e indexação de pastas) foi **fechada como "not planned"**. O caminho da comunidade é o inverso: abrir o *workspace do OpenClaw* como vault no Obsidian (symlink/pasta) — funciona porque é tudo markdown ([VelvetShark](https://velvetshark.com/openclaw-memory-masterclass), [betterclaw](https://www.betterclaw.io/blog/openclaw-obsidian)). Há ainda o plugin `memory-wiki` (compila memória durável num wiki navegável, "Obsidian-friendly") e o backend experimental **QMD** para indexar diretórios externos, incluindo vaults ([pminsights](https://pminsights.substack.com/p/configuring-openclaw-for-persistent)).
- Convenções: as do OpenClaw (MEMORY.md + diários datados), não as suas. Um vault com estrutura própria (notas de reunião, atividade) teria que ser escrito por skills custom via exec/ferramenta de arquivos — possível, mas fora do modelo de memória "de graça".

### 1.3 Autenticação Claude (Pro/Max via OAuth)

**Suportado localmente, com asterisco.** Segundo os [docs de OAuth](https://docs.openclaw.ai/concepts/oauth) e [autenticação](https://docs.openclaw.ai/gateway/authentication):

- Dois caminhos: **reuso do login do Claude Code CLI** (`claude -p`) e **`claude setup-token`** → `openclaw models auth setup-token --provider anthropic` (ou colar token gerado em outra máquina). Refresh automático com timestamp de expiração, credenciais em SQLite local.
- Os docs afirmam que ambos os caminhos são "sancionados por orientação da equipe da Anthropic, salvo mudança de política" — mas registram que **API key "continua sendo o caminho mais seguro e recomendado"**, e relatos de terceiros indicam que a Anthropic **fechou o uso de subscription em instâncias hospedadas** (só uso pessoal local) ([openclawlaunch](https://openclawlaunch.com/guides/openclaw-claude-subscription), [havstock](https://havstock.com/post/openclaw-claude-max-setup-guide)). Há fricção recorrente com expiração/mudanças de token ([answeroverflow](https://www.answeroverflow.com/m/1469511158040891402)).
- Conclusão factual: o requisito "Claude via conta Pro/Max, sem API key" é atendível hoje em uso pessoal local, mas depende de uma política da Anthropic que já mudou durante 2026 e pode mudar de novo — mesmo risco que um agente próprio usando OAuth teria, nem melhor nem pior.

### 1.4 Skills: plugar "gravar áudio → transcrever → nota"

Arquitetura de skills ([docs](https://docs.openclaw.ai/tools/skills)): cada skill é um diretório com `SKILL.md` (frontmatter YAML + instruções em prosa) — sem API de plugin nem compilação. Skills viram slash commands; descoberta automática (até 6 níveis), com watch de arquivos. Escopos: `<workspace>/skills` (por agente) e `~/.openclaw/skills` (compartilhado). Skills **rodam comandos locais no host** via ferramenta de exec do agente (com aprovações/política de ferramentas), e são filtradas em load por presença de binários/ambiente.

Para o pipeline de reunião: a skill em si é barata (um SKILL.md dizendo "rode `gravar.ps1`, depois mande para STT, depois escreva a nota em X") — **mas os três programas de verdade (captura WASAPI mic+loopback, chamada de STT, formatação da nota) são código custom seu de qualquer jeito**. O OpenClaw contribui com o loop de agente, o disparo por chat/CLI e o cron; não contribui com nada específico de áudio no Windows. E o exec em PowerShell nativo tem as arestas da issue #23178.

### 1.5 Segurança: episódios públicos e estado atual

Histórico ruim e recente, hoje parcialmente mitigado:

- **Instâncias expostas em massa**: varreduras acharam **900+ gateways OpenClaw sem autenticação** vazando API keys, tokens OAuth e históricos em markdown/JSON plano ([Bitsight](https://www.bitsight.com/blog/openclaw-ai-security-risks-exposed-instances)); um estudo independente (Maor Dayan) reportou **42.665 instâncias expostas, 5.194 verificadas vulneráveis, 93,4% com bypass de autenticação** ([Infosecurity](https://www.infosecurity-magazine.com/news/researchers-40000-exposed-openclaw/)).
- **CVEs**: SecurityScorecard divulgou três CVEs de alta severidade com exploit público; a mais grave, **CVE-2026-25253** (CVSS 8.8, one-click via UI de Control), foi corrigida na v2026.1.29 em 30/jan/2026 ([Infosecurity](https://www.infosecurity-magazine.com/news/researchers-six-new-openclaw/), [Kaspersky](https://www.kaspersky.com/blog/openclaw-vulnerabilities-exposed/55263/)).
- **Prompt injection indireta** (mensagens/sites com instruções ocultas) é reconhecida como não resolvida — os docs dizem explicitamente que guardrails de prompt não bastam; a defesa real é política de ferramentas, aprovação de exec, sandbox e allowlists ([Giskard](https://www.giskard.ai/knowledge/openclaw-security-vulnerabilities-include-data-leakage-and-prompt-injection-risks), [docs de segurança](https://docs.openclaw.ai/gateway/security)).
- **Skills maliciosas** no marketplace comunitário (ClawHub): centenas de skills disfarçadas instalando stealers ([DigitalOcean](https://www.digitalocean.com/resources/articles/openclaw-security-challenges)).
- **Mitigação atual do projeto**: bind padrão `loopback` + token; `dmPolicy="pairing"` (contatos novos ignorados até aprovação) e allowlists em dois níveis nos mensageiros; comando `openclaw security audit [--deep]`; recomendação de Tailscale Serve em vez de expor na LAN, sandbox Docker/Podman por agente, e "nunca exponha o gateway sem auth em 0.0.0.0" ([docs](https://docs.openclaw.ai/gateway/security)).
- Leitura para o nosso caso: um deploy 100% localhost, sem mensageiros e sem exposição de rede evita a classe principal de incidente — mas essa configuração "podada" é justamente abrir mão do que o OpenClaw oferece.

### 1.6 Maturidade, cadência e o que vem "de graça"

- **Cadência**: versionamento `YYYY.MAJOR.MINOR` com múltiplas releases por semana (ex.: betas quase diárias no fim de jul/2026, hotfixes em ago/2026) ([releases](https://github.com/openclaw/openclaw/releases)). Três renomes e três formatos de config em ~3 meses (nov/2025–jan/2026). Ou seja: projeto vivo e veloz, com custo real de acompanhamento (breaking changes frequentes).
- **Instalação**: Node 22.22.3+/24.15+/25.9+, Gateway como serviço; no Windows, Hub (que prefere WSL gerenciado) ou CLI PowerShell.
- **De graça, mas não pedido na v1**: sete mensageiros, browser control, voz/talk, canvas, nodes de dispositivos, marketplace de skills. **De graça e útil**: loop de agente com sessões, memória markdown + busca SQLite/embeddings, cron/automations persistentes (`openclaw automations`, jobs em `~/.openclaw/cron/`, tipos at/every/cron, execução em sessão principal ou isolada — [docs](https://docs.openclaw.ai/automation/cron-jobs)), auth Anthropic com refresh, CLI local.
- **Não vem**: captura de áudio Windows (WASAPI), observação de atividade, integração STT, escrita de nota com as suas convenções, e suporte Windows nativo de primeira classe.

---

## 2. "Hermes" — identificação do candidato

O candidato claro é o **Hermes Agent, da Nous Research** ([get-hermes.ai](https://get-hermes.ai/), MIT): agente autônomo self-hosted, "self-improving", com memória em três camadas (sessão, persistente e "skill memory") gravada como **markdown pesquisável em `~/.hermes/`**, skills no padrão aberto agentskills.io (o agente escreve as próprias skills quando resolve um problema), e gateway multi-plataforma (Telegram, Discord, terminal) ([hermes-agent.io](https://hermes-agent.io/), [guia](https://tosea.ai/blog/hermes-agent-self-improving-ai-guide)). É da mesma categoria do OpenClaw (assistente pessoal com memória em markdown) e mais novo/menos maduro; a orientação da Nous é rodar em servidor Linux como processo persistente — Windows nativo tampouco é alvo primário. Ressalva: "Hermes" também é o nome da família de LLMs abertos da própria Nous, então a menção do usuário pode se referir ao modelo, não ao agente; se for o agente, é este. Nenhum dos dois resolve coletores de áudio/atividade Windows.

Outras alternativas óbvias na mesma categoria, só para registro: **Claude Code/Agent SDK com um diretório de memória em markdown** (a base "construir fino" já considerada no mapa) e forks/derivados menores do próprio OpenClaw — nenhum outro projeto com tração comparável apareceu com memória markdown + Windows como foco.

---

## 3. Custo de adotar vs. construir fino (factual)

| Capacidade necessária (mapa) | OpenClaw dá de graça? | Teria que construir mesmo assim? |
|---|---|---|
| Loop de agente + sessões + CLI local | Sim | Não (mas o Agent SDK também dá isso) |
| Memória em markdown + busca | Sim, nas convenções dele (workspace próprio) | Adaptação: vault Obsidian arbitrário foi recusado (#22958); ou aceita o workspace como vault, ou escreve skills custom de escrita de nota |
| Claude via conta Pro/Max | Sim (setup-token/reuso do CLI), com risco de política Anthropic | Mesmo risco em qualquer abordagem |
| Cron/agendamento persistente | Sim | Não |
| Captura de áudio WASAPI (mic + loopback) | Não | **Sim — custom em qualquer cenário** |
| Pipeline STT em nuvem → nota formatada | Não (só o "cérebro" que orquestra) | **Sim — custom em qualquer cenário** |
| Observação de atividade Windows | Não | **Sim — custom em qualquer cenário** |
| Windows 11 nativo de primeira classe | Não (WSL2 é o caminho abençoado; nativo é undocumented/stale) | Construir fino roda nativo por definição |
| Chat via mensageiro | Sim (7 canais) | Não é requisito da v1 — peso morto + superfície de ataque |
| Browser control, voz, canvas, nodes | Sim | Não pedidos |

**Síntese factual**: os coletores Windows (áudio, atividade) e o pipeline de transcrição — o coração da v1 — são código custom nos dois cenários. O que o OpenClaw economiza (loop, memória, cron, CLI, auth) é a parte que o Claude Agent SDK também cobre em grande medida; o que ele acrescenta por cima (mensageiros, browser, marketplace) não é requisito da v1 e é exatamente onde moram os episódios de segurança. O custo recorrente específico de adotar é acompanhar um projeto com releases múltiplas por semana, breaking changes de config e Windows nativo tratado como caso marginal.

## Fontes principais

- Docs oficiais: [Windows](https://docs.openclaw.ai/platforms/windows) · [Memória](https://docs.openclaw.ai/concepts/memory) · [OAuth](https://docs.openclaw.ai/concepts/oauth) · [Autenticação](https://docs.openclaw.ai/gateway/authentication) · [Skills](https://docs.openclaw.ai/tools/skills) · [Segurança](https://docs.openclaw.ai/gateway/security) · [Automations/cron](https://docs.openclaw.ai/automation/cron-jobs)
- Repo/issues: [openclaw/openclaw](https://github.com/openclaw/openclaw) · [#23178 Windows nativo](https://github.com/openclaw/openclaw/issues/23178) · [#22958 vault Obsidian (not planned)](https://github.com/openclaw/openclaw/issues/22958) · [Releases](https://github.com/openclaw/openclaw/releases)
- Segurança: [Bitsight](https://www.bitsight.com/blog/openclaw-ai-security-risks-exposed-instances) · [Infosecurity 40k+](https://www.infosecurity-magazine.com/news/researchers-40000-exposed-openclaw/) · [Infosecurity CVEs](https://www.infosecurity-magazine.com/news/researchers-six-new-openclaw/) · [Kaspersky](https://www.kaspersky.com/blog/openclaw-vulnerabilities-exposed/55263/) · [Giskard](https://www.giskard.ai/knowledge/openclaw-security-vulnerabilities-include-data-leakage-and-prompt-injection-risks)
- Hermes: [get-hermes.ai](https://get-hermes.ai/) · [hermes-agent.io](https://hermes-agent.io/)

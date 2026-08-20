# Avaliar agentes prontos como base (OpenClaw e afins)

Type: research
Status: resolved

## Question

Em vez de construir um agente próprio (mesmo fino, sobre o Claude Agent SDK), vale adotar um agente pessoal open-source pronto — OpenClaw (ex-Clawdbot/Moltbot) ou similar — como base do second brain?

Levantar fatos, não decidir, contra os requisitos do mapa:

- Roda **nativo no Windows 11** (sem WSL/Docker obrigatórios)? Coletores locais (áudio WASAPI, atividade) conseguem viver dentro dele como skill/extensão?
- Modelo de memória: arquivos markdown compatíveis com um vault Obsidian local? Quem escreve, com que convenções?
- Usa Claude via conta própria (OAuth Pro/Max) ou exige API key paga à parte?
- Arquitetura de skills/extensões: quanto custa plugar um pipeline "gravar reunião → transcrever → nota no vault"?
- Postura de segurança e maturidade (o OpenClaw teve episódios públicos de instâncias expostas/prompt injection — estado atual?).
- Custo de manutenção: o que se ganha de graça (interfaces de chat, cron, memória) vs. o peso do que não será usado.

O resultado alimenta [Estender o Whis ou projeto separado?](02-estender-whis-ou-separar.md), que passa a incluir a terceira opção: adotar um agente pronto.

## Answer

Achados completos em [../research/10-agentes-prontos.md](../research/10-agentes-prontos.md). Resumo:

- **Windows nativo**: funciona via Node + PowerShell, mas é caminho de segunda classe — o README lista Windows "via WSL2", o Windows Hub provisiona um distro WSL por baixo, e a issue #23178 pedindo doc de setup nativo foi fechada como stale. Skills baseadas em shell POSIX quebram/precisam adaptação em PowerShell.
- **Memória**: markdown puro (`MEMORY.md`, diários `memory/YYYY-MM-DD.md`, `USER.md`) escrito pelo agente no workspace dele, busca SQLite/embeddings. Apontar para um vault Obsidian arbitrário foi **recusado como "not planned"** (#22958); o padrão da comunidade é o inverso: abrir o workspace do OpenClaw como vault.
- **Auth Claude**: OAuth de conta Pro/Max funciona localmente (`claude setup-token` ou reuso do login do Claude Code CLI, refresh automático); os próprios docs recomendam API key como caminho "mais seguro", e a política da Anthropic já mudou em 2026 (fechou uso hospedado) — risco igual ao de um agente próprio.
- **Skills**: `SKILL.md` em markdown, rodam comandos locais no host — plugar o pipeline de reunião é barato na casca, mas captura WASAPI, chamada STT e escrita da nota são código custom seu de qualquer forma.
- **Segurança**: histórico pesado e recente — 900+ gateways sem auth vazando tokens (Bitsight), estudo com 42k instâncias expostas, 3 CVEs altas (CVE-2026-25253 CVSS 8.8, corrigida em 2026.1.29), skills maliciosas no ClawHub; prompt injection admitida como não resolvida. Mitigação atual: loopback por default, pairing, allowlists, `openclaw security audit`, sandbox opcional.
- **Custo adotar vs. construir**: o que o OpenClaw dá de graça e útil (loop, memória md, cron, CLI, auth) o Agent SDK cobre em grande medida; o extra (7 mensageiros, browser, voz, canvas) não é requisito da v1 e é onde moram os incidentes. Coletores Windows são custom em qualquer cenário. Custo recorrente: releases múltiplas por semana e breaking changes (3 renomes, 3 formatos de config em ~3 meses).
- **"Hermes"**: candidato claro é o Hermes Agent da Nous Research (self-hosted, memória/skills em markdown em `~/.hermes/`, gateway Telegram/Discord) — mesma categoria, menos maduro, Linux-first; "Hermes" também nomeia os LLMs da Nous, ambiguidade registrada.

# Projeto separado, fino e 100% local

O Second Brain é um projeto novo, não uma extensão do Whis nem uma instalação de agente pronto: coletores Windows custom + Claude via Agent SDK (OAuth da conta Pro/Max do usuário) + vault Obsidian novo criado localmente no PC (Windows 11, Ryzen 5600G). Tudo roda na máquina do usuário; nenhum componente em servidor.

## Considered Options

- **Estender o Whis** — rejeitado: o Whis está aposentado pelo usuário e seu runtime é Docker-only numa EC2 com vault remoto, sem caminho para coletores nativos no Windows (áudio WASAPI, janelas). Fica como doador de ideias: convenções de vault prompt-driven, arquitetura de skills, uso do Agent SDK.
- **Adotar agente pronto (OpenClaw; Hermes/Nous)** — rejeitado: no Windows nativo é suporte de segunda classe (caminho oficial é WSL2), apontar a memória para um vault Obsidian externo foi recusado pelo projeto ("not planned"), e o histórico de segurança é pesado (gateways expostos, CVEs altas, prompt injection em aberto). O núcleo da v1 — captura de áudio, STT, escrita de notas — seria código custom em qualquer cenário, então a plataforma só adicionaria peso onde o projeto luta contra os dois requisitos centrais (Windows nativo, vault local). Evidências: `.scratch/second-brain/research/10-agentes-prontos.md`.

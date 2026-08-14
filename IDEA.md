# Second Brain — agente de IA observador

## A ideia

Um "segundo cérebro": agente de IA rodando no PC (Windows 11) que:

1. **Observa** o que eu faço no trabalho (atividade no PC) e salva o contexto no **Obsidian**.
2. **Transcreve minhas reuniões** e salva as transcrições/resumos no vault.
3. **Me auxilia no trabalho** — lembrar de coisas, recuperar contexto do que fiz.
4. **Busca vagas de emprego e freelance** usando o perfil que ele constrói a partir de tudo que observa.

## Fato relevante: o Whis já existe

`~/development/project-whis` — agente pessoal self-hosted já em andamento:

- WhatsApp como interface (Evolution API), motor de raciocínio Claude.
- **Vault Obsidian como memória durável** (`context/`).
- Arquitetura de skills: capacidades vivem fora do core.
- Baseado em [zeno-agent](https://github.com/ribeirogab/zeno-agent). Monorepo pnpm + turbo, Docker Compose.

Sobreposição óbvia: o Whis já tem o núcleo (motor + memória Obsidian + skills) que o second brain precisaria.

## Primeiro ticket de decisão do wayfinder

**Estender o Whis ou projeto separado?** (decisão deliberadamente adiada para o wayfinder examinar o Whis antes)

- Estender: observador de PC e transcrição viram novos coletores alimentando o mesmo vault.
- Separar: observador desacoplado do bot de WhatsApp; podem compartilhar o mesmo vault mesmo assim.

## Outras frentes de decisão previstas

- **Captura de atividade**: screenshots periódicos? ActivityWatch? hooks de janela ativa? Custo de privacidade/armazenamento.
- **Transcrição**: áudio do sistema + microfone no Windows, Whisper local vs. API, detectar quando há reunião.
- **Escrita no Obsidian**: formato das notas, estrutura do vault, agente escrever sem conflitar com notas manuais.
- **Recuperação**: como o agente "lembra" — busca semântica, índice, RAG sobre o vault.
- **Busca de vagas**: fase 2 — depende do perfil acumulado pelas frentes acima.

## Tracer bullet provável

*"Uma reunião acontece → nota transcrita aparece no vault."*

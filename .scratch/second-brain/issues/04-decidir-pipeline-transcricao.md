# Decidir o pipeline de transcrição

Type: grilling
Status: resolved
Blocked by: 03, 11

## Question

Qual é o pipeline de transcrição do tracer bullet — da captura sob demanda até a nota no vault?

Decidir, com os fatos da [pesquisa de captura + STT](03-pesquisa-captura-audio-stt.md) em mãos:

- Stack de captura (biblioteca/ferramenta, mic + loopback) e como o liga/desliga funciona na prática (atalho? bandeja? CLI?).
- Provedor de STT e modo (batch pós-reunião vs. streaming ao vivo).
- Diarização: precisamos saber quem falou?
- O que vai para a nota: transcrição bruta, resumo gerado pelo Claude, ou ambos?

## Answer

Pipeline decidido pelo usuário em 2026-08-14, com os fatos de [Pesquisar captura de áudio + STT](03-pesquisa-captura-audio-stt.md) e [Pesquisar Granola + STT grátis](11-pesquisa-granola-stt-gratis.md):

- **Captura**: script Python com **PyAudioWPatch** — microfone + loopback WASAPI em **canais separados** (a distinção "eu vs. os outros" sai de graça dos canais). OBS é plano B.
- **Liga/desliga**: **ícone na bandeja** do Windows.
- **STT**: **Deepgram Nova-3 multilingual, batch pós-reunião**, rodando no **crédito de US$ 200** (custo real R$ 0 por ~3 anos a 20h/mês; diarização nativa disponível sem custo extra; sem limite de 25 MB). Quando o crédito acabar, a decisão reabre — fallbacks documentados: Groq free (Whisper large-v3, 8h/dia, exige fatiar >25 MB, sem diarização) e Whisper local em CPU (plano C offline).
- **Diarização**: requisito mínimo é "eu vs. os outros", garantido pelos canais separados; a diarização nativa do Deepgram fica como bônus disponível.
- **Nota**: **resumo gerado pelo Claude na nota + transcrição bruta em arquivo separado, linkado** — o formato exato fica para [Estrutura do vault Obsidian](07-estrutura-vault-obsidian.md).
- **Granola**: descartado como motor (cache encriptado no Windows, transcript automatizado é feature paga, histórico de 30 dias); segue como fonte manual interina e **se aposenta quando o coletor próprio provar que funciona**.

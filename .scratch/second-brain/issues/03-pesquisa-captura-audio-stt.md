# Pesquisar captura de áudio no Windows + STT em nuvem

Type: research
Status: resolved

## Question

Quais são as opções concretas para (a) capturar o áudio de uma reunião do Google Meet no Windows 11 quando o usuário usa fone, e (b) transcrever esse áudio em nuvem com boa qualidade para pt-BR misturado com termos em inglês?

Levantar fatos, não decidir:

- **Captura**: loopback WASAPI (voz dos outros) + microfone (voz do usuário) — bibliotecas e abordagens (Python, Node, ferramentas prontas), como misturar ou gravar em canais separados, liga/desliga sob demanda.
- **STT**: OpenAI (Whisper API / gpt-4o-transcribe), Deepgram, AssemblyAI, Google — preço por minuto, qualidade em pt-BR com code-switching para inglês, diarização (quem falou), limites de tamanho/duração, batch vs. streaming.
- Estimativa de custo mensal para ~20h de reunião, contra o teto de R$ 100/mês.

O resultado alimenta [Decidir o pipeline de transcrição](04-decidir-pipeline-transcricao.md).

## Answer

Captura é problema resolvido no Windows: **PyAudioWPatch** (fork do PyAudio) expõe loopback WASAPI como input normal — um script Python grava mic + saída do sistema em dois streams, mixados ou em arquivos separados, com liga/desliga trivial. Alternativa zero-código: **OBS ≥ 28** (Desktop/Application Audio Capture + mic em trilhas separadas). python-soundcard funciona mas tem issues conhecidas no WASAPI; naudiodon (Node) não tem loopback; ffmpeg exige driver virtual de terceiros (caminho mais frágil).

STT em nuvem: todos cabem com folga no teto de R$ 100 para 20h/mês (câmbio R$ 5,40/US$, batch, com diarização):

- **Deepgram Nova-3 multilingual** — ~R$ 60–73/mês; único com code-switching pt/en formal (`language=multi`, idioma por palavra).
- **AssemblyAI Universal-3.5 Pro** — ~R$ 25/mês; mais barato, arquivos até 10h/5 GB, pt-BR bom, mas sem code-switching explícito.
- **OpenAI gpt-4o-transcribe / whisper-1** — ~R$ 39/mês; `prompt` de glossário mitiga termos em inglês; limite de 25 MB por arquivo obriga a fatiar/comprimir.

Combinações mais promissoras: (1) PyAudioWPatch com canais separados → Deepgram Nova-3 multilingual (diarização "eu vs. outros" de graça pelos canais); (2) PyAudioWPatch → AssemblyAI U3.5 Pro (melhor custo); (3) OBS → OpenAI gpt-4o-transcribe com glossário (menor esforço inicial). Só o Google em modo real-time padrão (US$ 0,016/min ≈ R$ 104) estoura o teto.

Detalhes e fontes: [../research/03-captura-audio-stt.md](../research/03-captura-audio-stt.md)

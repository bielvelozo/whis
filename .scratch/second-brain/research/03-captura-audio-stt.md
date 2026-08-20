# Research: Captura de áudio no Windows + STT em nuvem

Data: 2026-08-13. Contexto: Windows 11, Ryzen 5 5500U sem GPU dedicada, reuniões no Google Meet com fone (voz dos outros só existe no áudio de saída do sistema → precisa de loopback WASAPI), pt-BR com termos em inglês, captura sob demanda, ~20h/mês, teto R$ 100/mês.

Alimenta: [04 — Decidir o pipeline de transcrição](../issues/04-decidir-pipeline-transcricao.md).

---

## 1. Captura de áudio no Windows (loopback WASAPI + microfone)

O problema tem duas fontes: **microfone** (sua voz) e **loopback WASAPI do dispositivo de saída** (voz dos outros no Meet, já que com fone nada passa por alto-falante/mic). Windows expõe loopback nativamente via WASAPI ([Microsoft Learn — Loopback Recording](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording)); a questão é qual biblioteca expõe isso de forma prática.

### 1.1 PyAudioWPatch (Python) — recomendação natural para script próprio

- Fork do PyAudio que expõe **dispositivos de loopback WASAPI como se fossem inputs** — [github.com/s0d3s/PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch).
- API de conveniência: `p.get_default_wasapi_loopback()` retorna o loopback do dispositivo de saída padrão; daí é um `stream.read()` normal de PyAudio.
- Wheels pré-compiladas para Windows, Python 3.7–3.13; ~240 stars, mantido. Maturidade: boa para o caso de uso (é exatamente o nicho dele); base de código do PyAudio é antiga mas estável.
- **Duas fontes**: abrir dois streams (um no mic, um no loopback) no mesmo processo e gravar em **arquivos/canais separados** (recomendado — facilita diarização "eu vs. outros" de graça) ou mixar por soma de amostras com resample para taxa comum (loopback costuma vir a 48 kHz estéreo; mic a 16/44.1 kHz mono). Liga/desliga sob demanda é trivial (abrir/fechar streams).
- Pegadinha conhecida do loopback WASAPI: quando **nenhum áudio está tocando**, o dispositivo pode não entregar frames (silêncio não gera callback) — tratar preenchendo silêncio pelo relógio, ou tocar um stream de silêncio.

### 1.2 python-soundcard

- Biblioteca cross-platform com suporte a loopback no Windows desde 2018 — [github.com/bastibe/SoundCard](https://github.com/bastibe/SoundCard) (`get_microphone(id, include_loopback=True)`).
- Ativa (fix de compatibilidade com NumPy em jan/2026), porém o próprio README lista **issues conhecidas no WASAPI**: "records garbage if you record only a single channel", ignora blocksize em alguns casos, underruns. Autor declara projeto de hobby.
- Veredito: funciona, mas PyAudioWPatch é mais previsível para loopback.

### 1.3 Node.js (naudiodon etc.)

- [naudiodon](https://github.com/Streampunk/naudiodon) (bindings PortAudio para Node): os próprios autores dizem "not yet complete", recomendado para protótipos; 48 issues abertas; **sem suporte documentado a loopback WASAPI** (PortAudio upstream só ganhou loopback em forks/patches).
- Não há opção Node madura para loopback WASAPI sem código nativo próprio. Se a stack do projeto for Node, o caminho realista é chamar um helper externo (ffmpeg+driver virtual, OBS, ou um exe/py auxiliar).

### 1.4 ffmpeg

- **ffmpeg no Windows não tem input WASAPI**; só `-f dshow`, que enumera fontes DirectShow — o mix do sistema não aparece lá por padrão ([thread ffmpeg-user](https://ffmpeg.org/pipermail/ffmpeg-user/2017-May/036214.html)).
- Workarounds: habilitar "Stereo Mix" (depende do driver da placa; frequentemente ausente em notebooks) ou instalar um driver virtual como [virtual-audio-capture-grabber-device](https://github.com/rdp/virtual-audio-capture-grabber-device) (projeto antigo) / VB-Cable. Com isso dá para gravar mic + "loopback" em um comando `ffmpeg -f dshow -i audio=... -f dshow -i audio=...` com filtros `amix` ou `amerge` (mixado ou canais separados).
- Veredito: possível, mas exige driver de terceiros e é o caminho mais frágil.

### 1.5 OBS Studio — opção pronta, zero código

- OBS ≥ 28 tem **Application Audio Capture** (Windows 10 2004+/11): captura o áudio só do app (ex.: navegador com o Meet), além das fontes clássicas "Desktop Audio" (loopback) e "Mic/Aux" — [guia oficial](https://obsproject.com/kb/application-audio-capture-guide).
- Gravação com **múltiplas trilhas de áudio** (mic na trilha 1, desktop/app na trilha 2) via Advanced Audio Properties + checkboxes de trilha no Output → Recording ([fórum OBS](https://obsproject.com/forum/threads/record-mic-and-game-audio-separately.145229/)). Dá para gravar só áudio (container mkv/mka) e ligar/desligar manualmente.
- Custo de CPU baixo se não houver vídeo. Desvantagem: passo manual de exportar/demuxar trilhas antes do STT (automatizável com ffmpeg local, que aí só remuxa arquivos, sem precisar de driver).

### 1.6 Resumo captura

| Opção | Loopback WASAPI | Mic + loopback juntos | Maturidade | Esforço |
|---|---|---|---|---|
| PyAudioWPatch | Nativo | 2 streams no mesmo script (mix ou separado) | Boa (nicho exato) | Baixo (script ~100 linhas) |
| python-soundcard | Sim, com issues conhecidas | Sim | Média (hobby) | Baixo |
| naudiodon (Node) | Não documentado | — | Protótipo | Alto |
| ffmpeg + driver virtual | Via dshow (indireto) | Sim (amix/amerge) | Frágil (driver 3º) | Médio |
| OBS Studio | Sim (Desktop/App Audio) | Sim, trilhas separadas | Alta (produto maduro) | Zero código, passo manual |

---

## 2. STT em nuvem — preços oficiais (2026-08), pt-BR, code-switching

Câmbio usado nas conversões: **US$ 1 ≈ R$ 5,40** (aproximação, ago/2026). 20h/mês = 1.200 min.

### 2.1 OpenAI — [pricing oficial](https://platform.openai.com/docs/pricing) · [guia STT](https://platform.openai.com/docs/guides/speech-to-text)

- **whisper-1**: US$ 0,006/min. 98 idiomas incl. pt; único com `timestamp_granularities`.
- **gpt-4o-transcribe**: US$ 0,006/min. Suporta `prompt` (bom para glossário de termos em inglês) e streaming.
- **gpt-4o-mini-transcribe**: US$ 0,003/min — o mais barato da linha.
- **gpt-4o-transcribe-diarize**: US$ 0,006/min, **com diarização** (segmentos com speaker/start/end); não aceita `prompt`.
- Limites: **arquivo ≤ 25 MB** por request (é preciso fatiar reuniões longas; 25 MB ≈ ~3h20 de mp3 64 kbps ou ~20 min de WAV 16 kHz — comprimir antes). Batch (upload) e streaming (`stream=true` nos gpt-4o-*).
- pt-BR: suportado; code-switching pt/en: Whisper/gpt-4o lidam razoavelmente por serem multilíngues por natureza, mas não há modo explícito de code-switching — o `prompt`/`keywords` com os termos técnicos em inglês é o mitigador oficial.

### 2.2 Deepgram — [pricing oficial](https://deepgram.com/pricing) · [idiomas](https://developers.deepgram.com/docs/models-languages-overview) · [code-switching](https://developers.deepgram.com/docs/multilingual-code-switching)

- **Nova-3 monolingual**: batch US$ 0,0077/min · streaming US$ 0,0048/min.
- **Nova-3 multilingual (`language=multi`)**: batch US$ 0,0092/min · streaming US$ 0,0058/min.
- **Diarização**: add-on **US$ 0,0020/min**.
- pt (`pt`, `pt-BR`, `pt-PT`) suportado no nova-3 e nova-2. **Code-switching é feature explícita e documentada**: `language=multi` marca idioma por palavra com confiança — nova-3 multilingual cobre inglês+português no mesmo áudio (nova-2 `multi` era só es+en). É o único dos quatro com suporte formal a pt/en misturado.
- Batch e streaming; crédito grátis de US$ 200 para novas contas. Preço do nova-2 não é mais listado na página (modelo legado).

### 2.3 AssemblyAI — [pricing oficial](https://www.assemblyai.com/pricing) · [idiomas](https://www.assemblyai.com/docs/speech-to-text/pre-recorded-audio/supported-languages) · [limites (FAQ)](https://www.assemblyai.com/docs/faq/are-there-any-limits-on-file-size-or-file-duration-for-files-submitted-to-the-api)

- **Universal-3.5 Pro** (async): **US$ 0,21/h** (= US$ 0,0035/min). **Universal-2**: US$ 0,15/h.
- Streaming: U3.5 Pro Realtime US$ 0,45/h; Universal-Streaming multilingual US$ 0,15/h.
- **Diarização**: add-on **+US$ 0,02/h** (async) · +US$ 0,12/h (streaming).
- pt suportado (incl. variantes BR/PT detectadas automaticamente). **Sem suporte explícito a code-switching pt/en** (só "Spanglish" documentado); detecção automática escolhe um idioma dominante.
- Limites generosos: até **10h / 5 GB** por arquivo (2,2 GB via endpoint de upload). US$ 50 de crédito grátis.

### 2.4 Google Cloud Speech-to-Text — [pricing oficial](https://cloud.google.com/speech-to-text/pricing)

- V2: **US$ 0,016/min** (reconhecimento padrão/real-time, primeira faixa; cai com volume) · **Dynamic Batch ~US$ 0,003/min** (turnaround até 24h). Chirp incluso sem sobrepreço. 60 min/mês grátis + US$ 300 de crédito inicial. (Página oficial exige JS; faixas confirmadas por fontes secundárias — validar no console antes de decidir.)
- pt-BR suportado (Chirp/latest_long). Diarização disponível em modelos selecionados. Sem modo explícito de code-switching por palavra; aceita idiomas alternativos como dica.
- É a integração mais burocrática (projeto GCP, GCS bucket para batch longo).

---

## 3. Custo mensal estimado — 20h/mês (1.200 min), câmbio R$ 5,40/US$

| Provedor / modelo (batch, com diarização quando add-on) | US$/mês | R$/mês | % do teto R$ 100 |
|---|---|---|---|
| AssemblyAI Universal-2 (+diar.) | 20h × $0,17/h = **$3,40** | **R$ 18** | 18% |
| OpenAI gpt-4o-mini-transcribe (sem diar.) | 1200 × $0,003 = **$3,60** | **R$ 19** | 19% |
| Google V2 Dynamic Batch (~$0,003/min) | **$3,60** | **R$ 19** | 19% |
| AssemblyAI Universal-3.5 Pro (+diar.) | 20h × $0,23/h = **$4,60** | **R$ 25** | 25% |
| OpenAI whisper-1 / gpt-4o-transcribe(-diarize) | 1200 × $0,006 = **$7,20** | **R$ 39** | 39% |
| Deepgram Nova-3 mono batch (+diar.) | 1200 × $0,0097 = **$11,64** | **R$ 63** | 63% |
| Deepgram Nova-3 **multilingual** batch (+diar.) | 1200 × $0,0112 = **$13,44** | **R$ 73** | 73% |
| Google V2 padrão real-time ($0,016/min) | **$19,20** | **R$ 104** | **104% — estoura** |

Todos os provedores em modo batch cabem com folga no teto; só o Google em modo real-time padrão estoura. STT local (Whisper no CPU) foi descartado do escopo de custo, mas vale registrar: num 5500U sem GPU, whisper medium/large roda bem abaixo de tempo real — nuvem é a escolha certa para 20h/mês.

## 4. Combinações mais promissoras (fatos para a decisão em 04)

1. **PyAudioWPatch (mic + loopback em canais/arquivos separados) → Deepgram Nova-3 multilingual batch**: único STT com code-switching pt/en formal; gravando as fontes separadas, a diarização "eu vs. outros" sai de graça (pode até dispensar o add-on de diarização, caindo para ~R$ 60). ~R$ 60–73/mês.
2. **PyAudioWPatch → AssemblyAI Universal-3.5 Pro**: o melhor custo (~R$ 25/mês com diarização), limites de arquivo enormes (10h/5 GB, sem fatiar), pt-BR bom — mas sem garantia formal para trechos em inglês no meio do pt.
3. **OBS (trilhas separadas, zero código) → OpenAI gpt-4o-transcribe com `prompt` de glossário**: ~R$ 39/mês, setup de captura imediato; limite de 25 MB obriga a comprimir/fatiar o áudio antes do upload.

## Fontes

- https://github.com/s0d3s/PyAudioWPatch
- https://github.com/bastibe/SoundCard
- https://github.com/Streampunk/naudiodon
- https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording
- https://ffmpeg.org/pipermail/ffmpeg-user/2017-May/036214.html
- https://github.com/rdp/virtual-audio-capture-grabber-device
- https://obsproject.com/kb/application-audio-capture-guide
- https://obsproject.com/forum/threads/record-mic-and-game-audio-separately.145229/
- https://platform.openai.com/docs/pricing (→ developers.openai.com/api/docs/pricing)
- https://platform.openai.com/docs/guides/speech-to-text
- https://deepgram.com/pricing
- https://developers.deepgram.com/docs/models-languages-overview
- https://developers.deepgram.com/docs/multilingual-code-switching
- https://www.assemblyai.com/pricing
- https://www.assemblyai.com/docs/speech-to-text/pre-recorded-audio/supported-languages
- https://www.assemblyai.com/docs/faq/are-there-any-limits-on-file-size-or-file-duration-for-files-submitted-to-the-api
- https://cloud.google.com/speech-to-text/pricing

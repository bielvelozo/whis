# Research: Granola como motor de transcrição + STT grátis/quase grátis

Data: 2026-08-14 · Ticket: [11-pesquisa-granola-stt-gratis](../issues/11-pesquisa-granola-stt-gratis.md) · Câmbio usado: ~R$ 5,40/US$ (estimativa)

Contexto: ~20 h de reunião/mês (Google Meet, pt-BR com termos em inglês), transcrição sob demanda, destino = nota no vault Obsidian local, teto R$ 100/mês, PC Windows 11 com Ryzen 5600G (sem GPU dedicada).

---

## Frente 1 — Granola como fonte

### 1.1 Pricing e o que o "grátis" cobre hoje

O pricing foi reestruturado em 2026. Planos atuais ([granola.ai/pricing](https://www.granola.ai/pricing)):

| Plano | Preço | Relevante |
|---|---|---|
| **Basic (free)** | US$ 0 | Notas de IA, reuniões **ilimitadas**, mas **histórico limitado** (blog oficial: acesso só às notas dos **últimos 30 dias**; notas antigas não são apagadas, ficam inacessíveis até upgrade). Sem integrações. Multi-idioma incluso. |
| **Business** | US$ 14/usuário/mês (~R$ 76) | Histórico ilimitado, integrações (Notion, Slack, Zapier...), modelos de IA avançados. |
| **Enterprise** | US$ 35/usuário/mês | **Acesso à API oficial** ("API access requires Enterprise plan upgrade"). |

- Fontes oficiais: [pricing](https://www.granola.ai/pricing), [blog de pricing](https://www.granola.ai/blog/granola-pricing-plans-features-roi), [free vs paid](https://www.granola.ai/blog/granola-free-vs-paid-features-each-plan).
- Fontes terciárias divergem (algumas citam "25 reuniões lifetime" e "14 dias de histórico" — ex. [get-alfred](https://get-alfred.ai/blog/granola-pricing), [usecarly](https://www.usecarly.com/blog/granola-pricing/)); o material **oficial** de 2026 diz reuniões ilimitadas + janela de 30 dias. É plausível que o limite exato varie por coorte/experimento.
- **Veredito sobre sustentabilidade do "grátis"**: usar de graça é sustentável *enquanto* o fluxo for "transcreve → copia pro vault em até 30 dias". O risco real não é perder acesso ao app, e sim (a) o Granola endurecer o free (histórico já vem encolhendo) e (b) o vault ficar dependente de um SaaS que muda regras sem aviso.

### 1.2 Onde ficam as transcrições no Windows (cache local)

- Caminho no Windows: **`%APPDATA%\Granola`** (`C:\Users\<user>\AppData\Roaming\Granola`) — equivalente ao `~/Library/Application Support/Granola/` do macOS. Fonte: [extensão Raycast oficial-comunitária](https://www.raycast.com/Rob/granola) (lê `%APPDATA%\Granola` no Windows) e ferramentas de export ([granary](https://github.com/wassimk/granary), [theantichris/granola](https://github.com/theantichris/granola)).
- Formato histórico: `cache-v3.json` (JSON gigante com documentos/transcrições) + `supabase.json` (tokens de autenticação WorkOS/Supabase).
- **Mudança importante (2025-2026): o cache passou a ser encriptado.** Versões modernas gravam `cache-v6.json.enc`, `supabase.json.enc` e uma chave `storage.dek` protegida pelo `safeStorage` do Electron (DPAPI no Windows). Ferramentas que esperavam o JSON em texto puro quebraram — ver [openclaw/graincrawl issue #15](https://github.com/openclaw/graincrawl/issues/15).
- **O cache não contém tudo**: transcrições são buscadas dos servidores do Granola sob demanda quando você abre a reunião, e as antigas são purgadas do cache periodicamente ([análise da Kai](https://hirekai.ai/blog/export-granola-notes)). Ou seja: o cache local NÃO é um arquivo confiável de longo prazo.

### 1.3 APIs, export e ferramentas da comunidade

- **API oficial REST**: só no Enterprise (US$ 35/mês).
- **MCP oficial** (`mcp.granola.ai`): existe e é o caminho "sancionado" ([listagem](https://mcpservers.org/servers/granola-mcp), [PulseMCP](https://www.pulsemcp.com/servers/granola)). Ferramentas: buscar reuniões, notas, resumos — **mas `get_meeting_transcript` (transcrição completa) é restrito a planos pagos**; no Basic o MCP responde só com resumos/notas.
- **Export oficial manual**: Settings → Profile → "Generate CSV"; chega por e-mail em horas, link válido por 24 h, 1 export a cada 24 h ([Kai](https://hirekai.ai/blog/export-granola-notes)). Inviável como pipeline automático.
- **Ferramentas da comunidade** (todas não-oficiais):
  - [moona3k/granola-export](https://github.com/moona3k/granola-export) — usa a **API REST não documentada** (`api.granola.ai`) com o token lido do `supabase.json`; exporta **transcrição completa com diarização** (microfone vs. áudio do sistema), notas, metadados. **Só macOS hoje** (PRs de cross-platform em aberto). No Windows, o token está em `supabase.json.enc` (DPAPI) — dá para decriptar via Electron/DPAPI, mas ninguém empacotou isso ainda.
  - MCPs da comunidade ([pedramamini/GranolaMCP](https://mcpservers.org/servers/pedramamini/GranolaMCP), [Bencockin/granola-mcp](https://github.com/Bencockin/granola-mcp), [jeffmm/granola-fast-mcp](https://github.com/jeffmm/granola-fast-mcp) etc.) — leem o cache local em caminhos macOS hard-coded; **nenhum dos populares suporta Windows out-of-the-box**, e os que leem cache quebraram com a encriptação.
  - [Raycast Granola](https://www.raycast.com/Rob/granola) — lê `%APPDATA%\Granola` no Windows, mas Raycast Windows + dependência do formato do cache = mesma fragilidade.
  - [obsidian-granola-sync](https://github.com/tomelliot/obsidian-granola-sync) — plugin Obsidian que usa as credenciais do `supabase.json` para puxar notas via API não documentada; mesma classe de risco/fragilidade.

### 1.4 Diarização, pt-BR e o que se perde

- A transcrição bruta do Granola **existe e tem separação de falantes** (no mínimo "eu" vs. "os outros", via canal microfone vs. áudio do sistema — é assim que o export da comunidade a recebe). No app free, dá para **ver e copiar a transcrição completa** dentro da janela de 30 dias.
- pt-BR com code-switching: multi-language é suportado no free (confirmado pela experiência do usuário). Limite conhecido: diarização por canal não distingue **entre** os vários participantes remotos (todos chegam pelo mesmo canal de sistema); a distinção fina que o usuário vê vem dos rótulos de participante do Meet/notas do Granola.
- **O que se perde vs. pipeline próprio**: controle do dado (transcrição mora no servidor deles), acesso programático estável (só Enterprise/MCP pago), e qualquer garantia de continuidade do free.

### 1.5 ToS e fragilidade

- Os [termos publicados](https://docs.granola.ai/help-center/policies/terms-of-service/application-terms-of-service) (parte visível) não trazem cláusula explícita anti-scraping/engenharia reversa, mas os User/Platform Terms completos não foram auditáveis; o próprio [moona3k/granola-export](https://github.com/moona3k/granola-export) se resguarda ("é sua responsabilidade garantir conformidade com os ToS"). Uso pessoal de dados próprios é zona cinzenta de baixo risco prático, mas **sem garantia**.
- Fragilidade demonstrada na prática: formato de cache já mudou de v3 → v6 **e** ganhou encriptação, quebrando o ecossistema de ferramentas em ~1 ano. Qualquer coletor baseado em cache/API não documentada exige manutenção contínua.

**Conclusão Frente 1**: Granola serve como motor *hoje* com fluxo semi-manual (abrir reunião → copiar transcrição → colar/salvar no vault, dentro de 30 dias). Como fonte **automatizada** no Windows é frágil: cache encriptado, ferramentas da comunidade macOS-first, transcript via MCP oficial atrás de paywall, API oficial só Enterprise.

---

## Frente 2 — STT grátis / quase grátis

### 2.1 Groq (Whisper large na API) — o melhor "grátis" de API

Free tier atual ([docs de rate limits](https://console.groq.com/docs/rate-limits), [speech-to-text](https://console.groq.com/docs/speech-to-text)):

- `whisper-large-v3` e `whisper-large-v3-turbo`: **20 req/min, 2.000 req/dia, 7.200 audio-seconds/hora (2 h de áudio por hora), 28.800 audio-seconds/dia (8 h de áudio por dia)**.
- Limite de arquivo: **25 MB no free** (100 MB no dev tier). 1 h de áudio em Opus/M4A 16 kbps mono ≈ 7 MB → cabe; MP3 64 kbps não cabe (precisa comprimir ou fatiar).
- Preço se virar pago: large-v3 US$ 0,111/h, **turbo US$ 0,04/h** → 20 h/mês = **US$ 0,80 (~R$ 4,50/mês)**. Irrisório.
- Timestamps por segmento/palavra via `verbose_json`; **sem diarização** nativa.
- pt-BR: Whisper large-v3 é forte em português (WER de single digits em benchmarks); code-switching pt/en é um dos pontos fortes do Whisper.
- 20 h/mês cabem folgadas no free tier (limite real: 8 h de áudio/dia).

### 2.2 Google Gemini API (free tier)

- Após o corte de quotas de dez/2025, free tier típico ([guia consolidado](https://www.aifreeapi.com/en/posts/gemini-api-free-tier-rate-limits); os números oficiais só aparecem logado no [AI Studio](https://aistudio.google.com/rate-limit)): **2.5 Flash ~10 RPM / 250 RPD / 250k TPM; Flash-Lite ~15 RPM / 1.000 RPD**. Quotas já foram reduzidas sem aviso (50-80%) — free tier volátil.
- Áudio: aceita arquivos longos (até ~9,5 h/request); 1 h de áudio ≈ ~115k tokens (32 tokens/s), cabe no TPM. Consegue transcrever **e** rotular falantes razoavelmente num prompt só, pt-BR ok, mas transcrição verbatim é menos fiel que Whisper (tende a "limpar"/resumir) e timestamps são pouco confiáveis.
- Viável de graça para 20 h/mês; risco = volatilidade da quota e qualidade verbatim inferior.

### 2.3 Google Cloud STT

- Free tier: **60 min/mês grátis (API V1)**; a V2 não tem a mesma franquia recorrente ([pricing](https://cloud.google.com/speech-to-text/pricing), [análise 2026](https://diyai.io/ai-tools/speech-to-text/google-cloud-speech-to-text-pricing/)). Depois, ~US$ 0,016/min (V2 standard).
- 60 min ≪ 20 h/mês → **insuficiente**; pago sairia ~US$ 19/mês (~R$ 103) — estoura o teto e perde para todas as alternativas.
- Novos clientes GCP ganham US$ 300 por 90 dias (one-off).

### 2.4 Créditos iniciais

- **Deepgram**: **US$ 200 de crédito no signup, sem cartão** ([pricing](https://deepgram.com/pricing) via análises: [diyai](https://diyai.io/ai-tools/speech-to-text/deepgram-pricing-2026/), [gladia](https://www.gladia.io/blog/deepgram-pricing)). Nova-3 batch ~US$ 0,0043/min → 20 h/mês = **US$ 5,16/mês**; o crédito cobre **~3 anos** de uso nesse ritmo (há relatos divergentes sobre expiração em 1 ano — conferir no cadastro). Tem **diarização nativa** e pt-BR (Nova-2/Nova-3 multilingual).
- **AssemblyAI**: ~US$ 50 de crédito inicial; depois ~US$ 0,12-0,27/h conforme já levantado no ticket 03 (~R$ 25/mês).

### 2.5 Whisper local em CPU (Ryzen 5600G, faster-whisper int8)

Benchmarks de referência ([faster-whisper](https://github.com/SYSTRAN/faster-whisper), [issue #526](https://github.com/SYSTRAN/faster-whisper/issues/526), [issue #1030](https://github.com/SYSTRAN/faster-whisper/issues/1030), [benchmark 2026](https://snailtext.app/blog/do-you-need-a-gpu-for-voice-to-text/)):

- `small` int8: ~13 min de áudio em ~1m42s num i7-12700K (RTF ~0,13). Num 5600G (6C/12T Zen 3, ~60-70% do MT do 12700K), estimativa realista: **RTF ~0,2 → 1 h de reunião em ~12-18 min**.
- `medium` int8: ~real-time em desktops rápidos → no 5600G, **1 h de áudio em ~45-70 min**. Usável "sob demanda", mas ocupa o PC.
- `large-v3` int8: RTF ~2+ em CPU → 2-3 h por hora de áudio. Impraticável.
- Qualidade pt-BR: `medium` é bom; `small` erra mais em termos técnicos em inglês no meio do pt-BR (justamente o caso de uso). `large` (via Groq) resolve isso melhor que qualquer modelo que roda bem nesse CPU.
- **Diarização local** exige pyannote/WhisperX por cima — em CPU pura adiciona ~tempo real de novo e complexidade de setup; na prática, sem GPU, diarização local é o elo fraco.
- Custo: R$ 0 e 100% local/privado (único caminho totalmente alinhado ao "second brain 100% local").

---

## Tabela comparativa (20 h de reunião/mês, teto R$ 100)

| Caminho | Custo real/mês | Esforço de integração | Fragilidade / risco | Diarização | Observações |
|---|---|---|---|---|---|
| **Granola como fonte (free)** | R$ 0 | Baixo se manual (copiar/colar no vault); **alto** se automatizado no Windows (cache encriptado, ferramentas macOS-first) | **Alta**: free pode encolher; formato mudou v3→v6+encriptação; transcript via MCP oficial é pago; API oficial só Enterprise (~R$ 190/mês); janela de 30 dias | Sim (por canal + rótulos do Meet) | O que o usuário já tem; bom como fonte *interina* manual |
| **Groq free (Whisper large-v3)** | **R$ 0** (pago: ~R$ 4,50 com turbo) | Baixo-médio: capturar áudio, comprimir <25 MB, chamar API | Baixa-média: free tier pode mudar, mas o pago é irrisório como fallback | Não (precisa pós-processo) | Melhor custo/qualidade pt-BR+en; 8 h de áudio/dia de folga |
| **Gemini API free** | R$ 0 | Baixo: um prompt com o arquivo de áudio | Média-alta: quotas já cortadas 50-80% sem aviso | "Rótulos" via LLM (não verbatim confiável) | Bom plano B; transcrição menos fiel que Whisper |
| **Google STT free** | R$ 0 até 60 min; depois ~R$ 103/mês | Médio (GCP) | Baixa | Sim (paga) | 60 min/mês ≪ 20 h → descartar |
| **Deepgram (crédito US$ 200)** | R$ 0 por ~3 anos; depois ~R$ 28/mês (Nova-3 batch) | Baixo: API simples | Baixa (crédito pode expirar em 1 ano — verificar) | **Sim, nativa** | Único "grátis" com diarização de verdade |
| **STT pago (referência ticket 03)** | Deepgram ~R$ 60-73 · AssemblyAI ~R$ 25 · OpenAI ~R$ 39 | Baixo | Baixa | Deepgram/AssemblyAI sim | Todos sob o teto; ver ticket 03 |
| **Whisper local (faster-whisper int8)** | R$ 0 | Alto: setup Python, captura, fila; diarização local penosa em CPU | Baixa (nada expira); custo = tempo de CPU | Só com pyannote/WhisperX (lento em CPU) | `small`: 1 h em ~15 min; `medium`: ~1 h; 100% local/privado |

## Leitura dos fatos

1. **O "grátis" do usuário no Granola é real e continua** (Basic = reuniões ilimitadas), mas com janela de 30 dias e sem caminho automatizado estável no Windows: o cache agora é `cache-v6.json.enc` + `storage.dek` (DPAPI), o transcript via MCP oficial é feature paga, e a API oficial é Enterprise.
2. Como **fonte automatizada**, Granola é o caminho mais frágil da tabela; como **fonte manual interina** (copiar a transcrição para o vault logo após a reunião), é gratuito e funciona hoje.
3. Para pipeline próprio dentro do teto: **Groq free (Whisper large-v3)** é o melhor custo/qualidade para pt-BR com code-switching (R$ 0, fallback pago de ~R$ 4,50/mês); **Deepgram com US$ 200 de crédito** é a opção "grátis por anos" que já traz diarização nativa; **Whisper local `small`/`medium` int8** é o único 100% local e viável no 5600G para uso sob demanda (15-60 min por hora de áudio), pagando com tempo de máquina e sem diarização prática.

# Pesquisa: opções de captura de atividade do PC (Windows 11, sob demanda)

Data: 2026-08-13
Contexto: observação **sob demanda** (liga/desliga manual), Windows 11, dados sensíveis de empregador/clientes na tela, destino final = resumos diários em notas markdown no vault Obsidian, teto global de R$ 100/mês de APIs (já parcialmente consumido por transcrição).

---

## 1. ActivityWatch

**O que é:** time tracker automático open-source (MPL-2.0), local-first, ~18,6k estrelas no GitHub, projeto maduro e ativo (existe desde ~2016, múltiplos watchers oficiais). Fontes: [repo](https://github.com/ActivityWatch/activitywatch), [docs](https://docs.activitywatch.net/en/latest/introduction.html).

### O que os watchers capturam (Windows)

| Watcher | Captura | Notas |
|---|---|---|
| `aw-watcher-window` | app ativo + **título da janela** | padrão, funciona em Windows |
| `aw-watcher-afk` | ativo/AFK via atividade de mouse/teclado (AFK após ~3 min inativo) | padrão |
| `aw-watcher-web` | aba ativa do navegador: título, **URL**, estado audível/anônimo | extensão oficial para Chrome, Edge e Firefox |
| `aw-watcher-input` | contagem de teclas e distância do mouse (não o conteúdo digitado) | opcional |

Fonte: [docs de watchers](https://docs.activitywatch.net/en/latest/watchers.html).

### Arquitetura e consulta de dados

- **Servidor local** (`aw-server`, com reescrita em Rust em andamento) + watchers que enviam "heartbeats". Nada sai da máquina — "our current security consists only of not allowing non-localhost connections".
- **REST API em `http://localhost:5600/api/0/`**: buckets (`GET /api/0/buckets/`), eventos (`GET /api/0/buckets/<id>/events`), heartbeats e uma **Query API** para agregações (tempo por app, por título, filtrado por não-AFK). Há browser interativo da API em `http://localhost:5600/api/`. Fonte: [REST API](https://docs.activitywatch.net/en/latest/api/rest.html).
- Dados brutos guardados em banco local (eventos timestamped com duração), filosofia de guardar dado bruto na maior resolução possível.

### Ligar/desligar

- Gerenciado pelo `aw-qt` (ícone de bandeja) que sobe servidor + watchers; dá para iniciar/parar módulos pela bandeja ou simplesmente abrir/fechar o processo. Não é "push-to-record" nativo, mas iniciar/matar `aw-qt` por script/atalho é trivial — atende bem o requisito de observação sob demanda.

### Volume de dados/dia e caminho até o resumo

- Eventos são JSON pequenos (app, título, timestamps). Um dia intenso de trabalho gera **na ordem de centenas de KB a poucos MB** — irrelevante em disco.
- **Pipeline de resumo:** script diário consulta a Query API (tempo por app / título / domínio, só períodos ativos), gera um texto compacto (1–3 KB) e pede a um modelo barato (ex.: Claude Haiku 4.5, US$ 1/M tokens de entrada) um resumo em prosa → nota markdown no vault. Custo por dia: **< US$ 0,01** (centavos por mês). Cabe folgado no orçamento.
- **Privacidade:** títulos de janela podem conter nomes de clientes/projetos, mas é ordens de magnitude menos exposto do que pixels da tela; o dado bruto nunca sai da máquina — só o agregado vai para a API (e mesmo isso pode ser filtrado antes).

---

## 2. Screenshots periódicos + resumo por modelo de visão

### Volume de armazenamento

- Screenshot PNG 1080p: ~200–500 KB. Em sessão observada de 4 h com 1 captura/min → 240 imagens ≈ **50–120 MB/dia**. Com captura a cada 10–30 s, sobe para 0,5–1+ GB/dia.
- Referência de sistema contínuo: **screenpipe** reporta ~5–10 GB/mês (com captura orientada a eventos e compressão em vídeo) — ordem de 0,2–0,7 GB/dia. Fontes: [screenpipe](https://github.com/screenpipe/screenpipe), [docs](https://docs.screenpipe.com/home).

### Custo de API para resumir (Claude)

- Uma imagem consome até **~1.600 tokens** na resolução padrão (modelos atuais aceitam alta resolução até ~4.784 tokens/imagem, desnecessário aqui — melhor reduzir para ~1.568 px no lado maior).
- Com **Claude Haiku 4.5** (US$ 1/M entrada, US$ 5/M saída):
  - 240 imagens/dia × 1.600 tokens ≈ 384 K tokens ≈ **US$ 0,40/dia** só de entrada.
  - 20 dias úteis/mês ≈ **US$ 8–10/mês** (~R$ 45–55) — com Batch API (−50%) ≈ US$ 4–5/mês.
  - Intervalo de 30 s dobra tudo; com Sonnet em vez de Haiku, triplica.
- Conclusão de custo: **tecnicamente cabe no teto de R$ 100/mês, mas consome a maior parte do orçamento restante** (que já está parcialmente comprometido com transcrição). Alternativa: OCR/resumo local (screenpipe usa OCR local + LLM opcional) e mandar para a API só o texto extraído, reduzindo o custo em ~10×.

### Riscos de privacidade

- Screenshots capturam **tudo**: e-mails, chats, senhas visíveis, dados de clientes/empregador. Enviar pixels brutos a uma API de nuvem é o cenário de maior exposição possível — provavelmente violaria políticas de confidencialidade do empregador.
- **Precedente Windows Recall:** o recurso da Microsoft (screenshots contínuos + OCR local) sofreu recuo público em 2024: pesquisadores mostraram que os snapshots e o texto extraído ficavam em SQLite **sem criptografia**, incluindo senhas e números de cartão. A Microsoft tornou o recurso opt-in, com dupla criptografia e Windows Hello obrigatório — e mesmo assim pesquisadores seguem apontando risco. Fontes: [The Record](https://therecord.media/microsoft-reverses-course-recall-opt-in), [VentureBeat](https://venturebeat.com/ai/microsofts-recall-feature-will-now-be-opt-in-and-double-encrypted-after-privacy-outcry). Lição: mesmo armazenamento **local** de tela vira alvo; o mínimo seria criptografia em repouso + retenção curta (apagar screenshots após resumir).
- **Alternativas open-source:**
  - [screenpipe](https://github.com/screenpipe/screenpipe) — Rust, 24/7, captura texto de tela via APIs de acessibilidade com fallback de OCR, áudio, nomes de app e URLs; **roda em Windows**; API local em `localhost:3030` (`/search?q=...`); dados em `~/.screenpipe/`; ~5–10 % de CPU. É o mais próximo de um "Recall open-source" utilizável no Windows.
  - [rem](https://github.com/jasonjmcghee/rem) — screenshot a cada 2 s + OCR local, SQLite + vídeo; **só macOS (Apple Silicon)**; existe um port experimental [xrem](https://github.com/jasonjmcghee/xrem) multiplataforma, pouco maduro. Relevante só como referência de design.

### Como viraria resumo diário

Duas rotas: (a) enviar lotes de screenshots ao modelo de visão pedindo linha do tempo do dia (caro, exposto); (b) OCR local (screenpipe/tesseract) → texto → resumo por LLM barato (custo ~US$ 0,05–0,20/dia, exposição menor mas o texto de tela ainda contém dados sensíveis). Em ambos os casos, apagar o bruto após o resumo.

---

## 3. Hooks de janela ativa / título puro

- **Como se faz:** Win32 `GetForegroundWindow()` + `GetWindowText()`.
  - Python: [pywin32](https://pypi.org/project/pywin32/) (`win32gui`) ou [PyGetWindow](https://pypi.org/project/PyGetWindow/) (`getActiveWindow().title`).
  - Node: [get-windows](https://github.com/sindresorhus/get-windows) (ex-`active-win`) — retorna `title`, `owner.name/path`, `bounds`, e no macOS até URL; no Windows dá título + processo.
- **O que se aprende só com isso:** qual app está em foco e o título da janela — que na prática carrega muito contexto: nome do arquivo/projeto no VS Code, assunto do e-mail, título da página/aba no navegador, nome do documento. Combinado com um timer/AFK simples, reconstrói-se a linha do tempo do dia ("2h em `foo.py — projeto X`, 40min em reuniões do Meet").
- **Limites:** não vê conteúdo (o que foi escrito/lido), não vê URL exata fora do título, títulos genéricos ("Nova aba", "Slack") viram buracos.
- **Custo/volume:** desprezível — um evento por troca de janela, poucos KB–MB/dia; resumo diário via LLM custa centavos.
- **Observação importante:** isso é exatamente o que o `aw-watcher-window` do ActivityWatch já faz, com armazenamento, dedupe (heartbeats), AFK e query prontos. Só vale escrever hook próprio se quiser algo minimalista (um script de ~30 linhas) sem instalar o ActivityWatch.

---

## 4. Outras fontes passivas baratas

| Fonte | Onde/como | O que dá | Volume/dia |
|---|---|---|---|
| **Histórico do navegador** | SQLite em `%LOCALAPPDATA%\Google\Chrome\User Data\Default\History` e `%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\History`; tabela `urls` (`SELECT datetime(last_visit_time/1000000-11644473600,'unixepoch'), url, title FROM urls`). Copiar o arquivo antes de ler (fica lockado com o navegador aberto). Fontes: [Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/2371810/where-is-the-file-for-edge-history-stored), [Foxton Forensics](https://www.foxtonforensics.com/browser-history-examiner/chrome-history-location) | páginas visitadas com timestamp — o que foi pesquisado/lido | dezenas–centenas de linhas; KB |
| **Arquivos recentes do Windows** | `%APPDATA%\Microsoft\Windows\Recent` (atalhos .lnk / jump lists) | quais documentos foram abertos e quando | dezenas de entradas; KB |
| **Git local** | `git log --since=... --author=...` (e `git reflog`) varrendo os repositórios da pasta de desenvolvimento | commits, branches, mensagens = registro semântico do trabalho de código, escrito pelo próprio usuário | KB; qualidade altíssima por byte |

Todas são **retroativas** (não precisam de nada "ligado" durante o trabalho), custam zero de captura e o resumo diário conjunto (histórico + recentes + commits) cabe em poucos KB de prompt → **centavos/mês** de API. Privacidade: URLs e nomes de arquivo ainda podem citar clientes, mas o usuário controla o filtro antes do envio.

---

## 5. Comparativo — volume, custo e caminho até a nota no vault

| Abordagem | Dado bruto/dia | Custo API/mês (estim.) | Exposição de dados sensíveis | Esforço p/ virar resumo diário |
|---|---|---|---|---|
| ActivityWatch (janela+AFK+web) | ~1 MB (JSON local) | < US$ 0,30 | baixa (títulos/URLs; agregado sai, bruto fica) | baixo — Query API pronta → prompt → nota md |
| Screenshots + visão (Claude Haiku) | 50 MB–1 GB (imagens) | US$ 4–10 (batch/1 min) até US$ 20+ | **alta** (pixels da tela vão à nuvem) | médio — pipeline de captura, envio, retenção/limpeza |
| Screenshots + OCR local (screenpipe) e LLM só no texto | 0,2–0,7 GB (vídeo/DB local) | ~US$ 1–4 | média (texto de tela sai; pixels ficam) | médio — screenpipe + query `localhost:3030` → resumo |
| Hook de título de janela (pywin32/get-windows) | KB–MB | < US$ 0,30 | baixa | baixo, mas reimplementa o que o ActivityWatch já dá |
| Fontes passivas (navegador, recentes, git) | KB | < US$ 0,10 | baixa–média (URLs/nomes) | baixo — leitura retroativa, sem nada "ligado" |

Padrão que emerge dos fatos: título de janela + AFK + URL (ActivityWatch) mais fontes retroativas (git, histórico) cobrem ~90 % do sinal necessário para um resumo diário por custo desprezível e exposição mínima; screenshots + visão adicionam o conteúdo da tela, mas com o pior perfil de privacidade e consumindo quase todo o orçamento de API restante.

## Fontes principais

- ActivityWatch: https://github.com/ActivityWatch/activitywatch · https://docs.activitywatch.net/en/latest/watchers.html · https://docs.activitywatch.net/en/latest/api/rest.html
- screenpipe: https://github.com/screenpipe/screenpipe · https://docs.screenpipe.com/home
- rem / xrem: https://github.com/jasonjmcghee/rem · https://github.com/jasonjmcghee/xrem
- Windows Recall (precedente): https://therecord.media/microsoft-reverses-course-recall-opt-in · https://venturebeat.com/ai/microsofts-recall-feature-will-now-be-opt-in-and-double-encrypted-after-privacy-outcry
- Janela ativa: https://github.com/sindresorhus/get-windows · https://pypi.org/project/PyGetWindow/
- Histórico de navegador: https://learn.microsoft.com/en-us/answers/questions/2371810/where-is-the-file-for-edge-history-stored · https://www.foxtonforensics.com/browser-history-examiner/chrome-history-location
- Preços Claude (Haiku 4.5 US$ 1/US$ 5 por M tokens; imagem ≤ ~1.600 tokens padrão): https://platform.claude.com/docs/en/pricing

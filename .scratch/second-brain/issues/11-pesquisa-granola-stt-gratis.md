# Pesquisar Granola como motor de transcrição + opções de STT grátis

Type: research
Status: resolved

## Question

O usuário já usa o Granola no Windows, sem pagar, e ele transcreve bem as reuniões (inclusive distinguindo falantes). Duas frentes de fato para fechar o pipeline de transcrição:

**Granola como motor:**

- O plano grátis do Granola cobre o quê, hoje? (trial de N reuniões? plano free permanente? limites) — risco de o "grátis" acabar.
- Onde as transcrições ficam no disco no Windows (cache local, formato)? Existe API, export automático ou ferramenta da comunidade (MCP server, scripts) para extraí-las de forma estável?
- Extrair do cache local viola ToS? O formato muda com frequência (fragilidade)?
- O que se perde vs. um pipeline próprio: transcrição bruta completa disponível? diarização acessível no export? idioma pt-BR com termos em inglês funciona bem (o usuário diz que sim — confirmar limites conhecidos)?

**STT grátis (alternativa se o Granola não servir de fonte):**

- Groq (Whisper large na API grátis): limites de rate/duração hoje.
- Google Gemini API tier grátis para transcrição de áudio: limites e qualidade pt-BR.
- Tiers/créditos: Deepgram (crédito inicial), Google STT (60 min/mês), outros.
- Whisper local em CPU (faster-whisper int8, modelos small/medium) num Ryzen 5600G: velocidade realista para 1h de reunião, qualidade pt-BR com code-switching.

Comparar contra o teto de R$ 100/mês e os fatos já levantados em [Pesquisar captura de áudio + STT](03-pesquisa-captura-audio-stt.md).

O resultado alimenta [Decidir o pipeline de transcrição](04-decidir-pipeline-transcricao.md), que agora inclui a opção "Granola como motor + coletor só copia a transcrição para o vault".

## Answer

Achados completos: [../research/11-granola-stt-gratis.md](../research/11-granola-stt-gratis.md)

- **Granola free (Basic) é sustentável, com asterisco**: pricing 2026 oficial dá reuniões ilimitadas de graça, mas o histórico fica acessível só por **30 dias** (fontes terciárias citam limites menores em algumas coortes). Multi-idioma incluso.
- **Extração automática no Windows é frágil**: o cache local fica em `%APPDATA%\Granola`, mas desde 2025/26 é **encriptado** (`cache-v6.json.enc` + `storage.dek` via DPAPI/safeStorage), o que quebrou os scrapers; além disso, transcrições são buscadas do servidor sob demanda e purgadas do cache. As ferramentas da comunidade (granola-export, MCPs, granary) são macOS-first; o export oficial é um CSV manual 1x/dia por e-mail; a transcrição completa via **MCP oficial é feature paga** e a API REST oficial é só Enterprise (US$ 35/mês). ToS: zona cinzenta, sem proibição explícita visível, risco prático baixo para dados próprios.
- **Conclusão Granola**: serve como fonte *interina manual* (abrir reunião e copiar a transcrição — com falantes — para o vault dentro de 30 dias); não serve como fonte automatizada robusta no Windows hoje.
- **STT grátis**: **Groq free** roda Whisper large-v3 com 8 h de áudio/dia e arquivos até 25 MB — cobre as 20 h/mês por **R$ 0** (e o pago é ~R$ 4,50/mês com o turbo); **Deepgram** dá US$ 200 de crédito sem cartão (~3 anos de uso a 20 h/mês) **com diarização nativa**; Gemini free funciona mas as quotas são voláteis e a transcrição é menos verbatim; Google STT (60 min/mês) é insuficiente.
- **Whisper local no 5600G (CPU)**: `small` int8 ≈ 1 h de áudio em ~15 min, `medium` int8 ≈ ~1 h — viável sob demanda e 100% local, mas diarização em CPU (pyannote) é lenta e trabalhosa.
- **Leitura para o ticket 04**: Groq free (qualidade pt-BR/en do large-v3, custo zero) ou Deepgram-no-crédito (diarização nativa) batem qualquer opção paga já pesquisada; Granola fica como fonte manual de transição.

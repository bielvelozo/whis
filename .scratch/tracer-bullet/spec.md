# Spec: Tracer bullet — reunião vira nota no vault

Status: ready-for-agent

Origem: [mapa second-brain](../second-brain/map.md) — consolidação de todas as decisões do esforço de wayfinding. Decisões detalhadas vivem nos tickets linkados; glossário em `CONTEXT.md`; ADR 0001 (projeto separado, 100% local) governa a arquitetura.

## Problem Statement

Reuniões no Google Meet se perdem: o que foi decidido, quem pediu o quê, e o contexto acumulado só existem na memória do usuário. Hoje ele depende do Granola — que funciona, mas é manual, guarda o histórico por apenas 30 dias, e não alimenta nenhuma memória durável que um agente possa consultar depois. O usuário quer que cada reunião vire, sem esforço, uma nota permanente e pesquisável num vault Obsidian local.

## Solution

Um **coletor de reunião sob demanda**: um ícone na bandeja do Windows liga e desliga a gravação. Ao parar, o pipeline transcreve o áudio na nuvem, gera um resumo com o Claude e grava no **vault** duas coisas: a **nota de reunião** (resumo que o usuário relê) e a **transcrição** bruta diarizada, linkadas entre si. O usuário abre o Obsidian e a reunião está lá — esse é o tracer bullet inteiro: *aperto um botão durante a reunião → nota transcrita/resumida aparece no vault*.

## User Stories

1. Como usuário em reunião, quero iniciar a gravação por um clique no ícone da bandeja, para capturar a reunião sem sair do Meet.
2. Como usuário, quero que o ícone da bandeja mostre visualmente se está gravando ou parado, para nunca ficar em dúvida se a reunião está sendo capturada.
3. Como usuário de fone, quero que a gravação capture tanto minha voz (microfone) quanto a dos outros (áudio do sistema), para a transcrição não perder metade da conversa.
4. Como usuário, quero parar a gravação por um clique e que o processamento dispare sozinho, para não ter passos manuais depois da reunião.
5. Como usuário, quero que uma nota de reunião com resumo em português apareça em `reunioes/`, para reler decisões e pendências sem ouvir áudio.
6. Como usuário, quero a transcrição completa em `transcricoes/`, linkada da nota, para conferir literalmente o que foi dito quando o resumo não bastar.
7. Como usuário, quero que a transcrição distinga minha fala da dos outros participantes, para saber quem disse o quê.
8. Como usuário que fala português com termos em inglês, quero que o code-switching seja transcrito corretamente, para nomes de tecnologia e jargão não virarem ruído.
9. Como usuário, quero frontmatter consistente (data, tipo, participantes, link da transcrição) em cada nota, para a recuperação futura filtrar por metadados.
10. Como usuário do Obsidian, quero abrir o vault e navegar as reuniões por data pelo nome do arquivo, para achar uma reunião sem buscar.
11. Como usuário, quero que o vault e suas pastas sejam criados automaticamente na primeira execução, para não ter setup manual de estrutura.
12. Como dono das minhas notas, quero que o coletor escreva apenas nas zonas dele (`reunioes/`, `transcricoes/`), para minhas notas manuais em `notas/` nunca serem tocadas.
13. Como usuário preocupado com privacidade, quero o áudio bruto retido por 7 dias fora do vault e então apagado, para poder re-transcrever falhas sem acumular áudio sensível.
14. Como usuário, quero que uma falha de rede ou do STT preserve a gravação e sinalize o erro, para nenhuma reunião ser perdida por instabilidade.
15. Como usuário, quero um comando para reprocessar uma gravação retida, para recuperar manualmente uma reunião cujo processamento falhou.
16. Como usuário com teto de R$ 100/mês, quero a transcrição rodando no crédito gratuito do Deepgram, para o custo real ser zero no horizonte de anos.
17. Como usuário de Windows 11 sem Docker, quero instalar e rodar o coletor nativamente, para não depender de WSL ou containers.
18. Como usuário diagnosticando problemas, quero logs legíveis do pipeline (gravação, transcrição, resumo, escrita), para entender o que falhou e onde.

## Implementation Decisions

- **Arquitetura geral** (ADR 0001): projeto novo, fino, 100% local no PC do usuário (Windows 11, Ryzen 5600G, sem GPU dedicada). Nenhum componente em servidor. O Whis é referência de ideias, nunca dependência.
- **Captura** ([pipeline de transcrição](../second-brain/issues/04-decidir-pipeline-transcricao.md)): Python com **PyAudioWPatch** — microfone e loopback WASAPI gravados em **canais/arquivos separados**; a separação de canais é o que garante a distinção "eu vs. os outros" independentemente de diarização. OBS é plano B documentado.
- **Gesto**: ícone na bandeja do Windows com liga/desliga da gravação e indicação de estado. É uma casca fina sobre o coletor — sem lógica própria.
- **STT**: **Deepgram Nova-3 multilingual, batch pós-reunião**, autenticado com a API key do crédito de US$ 200 (custo real R$ 0 por ~3 anos a 20h/mês). Diarização nativa disponível sem custo extra. Fallbacks documentados no ticket: Groq free (fatiar >25 MB, sem diarização) e Whisper local em CPU.
- **Resumo**: gerado pelo **Claude via conta Pro/Max do usuário** (Claude Agent SDK, OAuth — padrão validado no Whis), em português, cobrindo decisões, ações/pendências e tópicos.
- **Vault** ([estrutura do vault](../second-brain/issues/07-estrutura-vault-obsidian.md)): pasta dedicada no perfil do usuário, fora do repo de código, caminho configurável. Estrutura por fonte: `reunioes/`, `transcricoes/`, `diario/`, `notas/`. Nota em `reunioes/YYYY-MM-DD-nome-da-reuniao.md` com frontmatter mínimo (`data`, `tipo`, `participantes`, `transcricao` como wikilink); transcrição em `transcricoes/` com o mesmo prefixo de nome.
- **Zonas de propriedade**: o coletor cria/regenera apenas `reunioes/` e `transcricoes/`; jamais escreve em `notas/`.
- **Retenção de áudio**: gravações brutas vivem fora do vault, retidas 7 dias após transcrição bem-sucedida, depois apagadas. Falha de processamento preserva a gravação indefinidamente até reprocesso manual.
- **Porta e adaptador**: STT e resumo são portas injetáveis no pipeline (adaptadores Deepgram e Claude), permitindo fakes em teste e troca de provedor sem tocar o pipeline.
- **Configuração**: arquivo local simples (caminho do vault, chave Deepgram, pasta de gravações, dias de retenção). Sem segredos no repo.
- **Idioma**: todo texto voltado ao usuário (notas, resumos, logs) em português.

## Testing Decisions

- **Costura única** (confirmada com o usuário): `processar(pasta-da-gravacao) → arquivos no vault`. Os testes exercitam o pipeline completo do pós-gravação com **fakes de STT e de resumo** e áudio de fixture, verificando apenas comportamento externo: os arquivos certos aparecem nos lugares certos, com frontmatter, nome datado, wikilink correto e conteúdo vindo dos fakes.
- Casos de falha testados pela mesma costura: STT indisponível → nenhuma nota parcial é escrita, a gravação permanece retida e o erro é sinalizado; reprocesso da mesma pasta é idempotente (não duplica notas).
- Retenção testada como comportamento: gravações com transcrição bem-sucedida e mais de 7 dias somem após a rotina de limpeza; gravações com falha permanecem.
- **Fora da costura**: captura WASAPI e ícone de bandeja — validados por smoke manual (roteiro curto no repo: gravar 1 min de Meet real, conferir a nota no Obsidian).
- Prior art: nenhum — projeto greenfield; estes testes estabelecem o padrão do repo (testes de comportamento contra a costura, fakes nas portas, zero mock de detalhe interno).

## Out of Scope

- **Diário e fontes passivas** (git, Linear, Slack) — decididos em [integrações de fontes passivas](../second-brain/issues/13-decidir-fontes-passivas.md), são a entrega seguinte, não o tracer bullet.
- **Recuperação de contexto** (chat no terminal + one-shot) — decidida em [recuperação de contexto](../second-brain/issues/08-recuperacao-de-contexto.md), entrega separada.
- Histórico de navegador; busca de vagas/freelance; lembretes e proatividade; backup/versionamento do vault; atalho global de teclado; detecção automática de reunião; transcrição em streaming; qualquer monitoramento de atividade do PC (fora de escopo do esforço inteiro).

## Further Notes

- **Tarefas de setup antes da primeira execução** (humanas, fora do código): criar conta Deepgram sem cartão para ativar o crédito de US$ 200 e guardar a API key na configuração local.
- **Transição**: o Granola continua como muleta manual até o coletor provar que funciona numa reunião real; depois se aposenta.
- Evidências e alternativas avaliadas: [captura de áudio + STT](../second-brain/research/03-captura-audio-stt.md), [Granola + STT grátis](../second-brain/research/11-granola-stt-gratis.md), [agentes prontos](../second-brain/research/10-agentes-prontos.md).
- O vocabulário deste spec segue o glossário (`CONTEXT.md`): **Coletor**, **Vault**, **Sob demanda**, **Zona de propriedade**, **Tracer bullet**.

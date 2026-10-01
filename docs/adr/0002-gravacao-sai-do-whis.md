# A gravação de reunião sai do Whis; as reuniões ficam no Granola

> Registro de 2026-09-30.

O Whis deixou de gravar reunião. Saíram o gravador WASAPI, a transcrição pela Deepgram, o resumo de reunião pelo Claude, os comandos `processar`, `reprocessar` e `limpar`, a tarefa `Whis-Limpeza`, o `record` da palheta e o clique de gravar da bandeja. A bandeja ficou só como a casa da palheta. O usuário voltou a gravar as reuniões no Granola, no plano gratuito (Basic).

O motivo é o uso real: entre 16/09 e 30/09 foram 5 gravações (6,8 GB de WAV), e nenhuma virou nota. Quatro falharam na Deepgram — rede, HTTP 400 com áudio "corrupt or unsupported", nenhuma fala reconhecida e HTTP 504 com um arquivo de 1,6 GB — e a quinta nunca foi processada.

`reunioes/` e `transcricoes/` continuam no vault, mas nenhum coletor escreve mais nelas. O diário e a daily leem `reunioes/AAAA-MM-DD-HHMM-titulo.md` só pelo nome do arquivo; o `ask` lê o conteúdo. Uma nota de reunião posta ali, de qualquer origem, já é usada pelos três.

## O que o Granola permite hoje (conferido em 2026-09-30 nas páginas oficiais)

- O Granola não grava áudio: ele manda o som direto ao provedor de transcrição e não guarda arquivo nenhum. Também não importa áudio já gravado ([transcription](https://docs.granola.ai/help-center/taking-notes/transcription)).
- A API oficial (`public-api.granola.ai`, chave pessoal) entrega nota, resumo, participantes e transcrição, mas só nos planos Business e Enterprise ([granola-api](https://docs.granola.ai/help-center/sharing/integrations/granola-api)).
- O MCP oficial funciona no Basic, mas só com as notas e os resumos dos últimos 30 dias. A transcrição (`get_meeting_transcript`) é só para os planos pagos, e o acesso exige login OAuth pelo navegador ([mcp](https://docs.granola.ai/help-center/sharing/integrations/mcp)).
- O export em CSV traz o histórico inteiro, com transcrição, mas é manual: chega por e-mail, o link vale 24 h e dá para pedir um por dia ([exporting-notes](https://docs.granola.ai/help-center/sharing/exporting-notes)).
- Os termos de uso proíbem *crawl/scrape* e engenharia reversa. Por isso ficam de fora as ferramentas da comunidade que leem a credencial local e chamam a API interna ([user terms](https://docs.granola.ai/help-center/policies/terms-of-service/user-terms-of-service)).

## Considered Options

- **Consertar a gravação própria** (cortar o áudio antes da Deepgram, trocar de provedor): não seguido — o usuário escolheu voltar ao Granola.
- **Só tirar os botões e deixar o código**: oferecido e não escolhido; o usuário pediu a remoção de toda a gravação própria.
- **Puxar as reuniões do Granola automaticamente**: não construído. No Basic, o único caminho oficial automático é o MCP: traz o resumo, não traz a transcrição e exige login pelo navegador.

## O MCP testado no plano Basic (2026-09-30)

A sonda usou o SDK `mcp` 2.0.0 que já vem na venv, contra `https://mcp.granola.ai/mcp`:

- O login OAuth pelo navegador funcionou, com registro dinâmico do cliente e retorno em `http://127.0.0.1`. O usuário fez o login e autorizou; a sonda não viu senha nenhuma.
- O token dura 6 h e vem acompanhado de `refresh_token` (escopo `mcp offline_access`). A renovação sem navegador respondeu HTTP 200 e trouxe um token e um `refresh_token` novos, ou seja, o refresh roda a cada uso. Quanto tempo um `refresh_token` parado continua valendo não foi testado.
- `list_meetings` funciona: por padrão cobre os últimos 30 dias e traz id, título, data, participantes e o link da nota. Achou 3 reuniões, de 31/08 e 01/09; depois disso, nenhuma.
- `get_meetings` funciona: traz título, data, participantes e o resumo em markdown (o dessa reunião veio em inglês). O log da sonda cortou os últimos 1.273 caracteres da resposta, então não ficou confirmado se as notas privadas vêm junto.
- `get_meeting_transcript` recusou: "Transcripts are only available to paid Granola tiers".
- `query_granola_meetings` respondeu, mas pediu o título ou a data mesmo recebendo o id da reunião.

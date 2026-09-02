# 06 — Retenção e reprocesso

**What to build:** O ciclo de vida do áudio bruto e a rede de segurança: gravações com transcrição bem-sucedida são retidas por 7 dias (configurável) fora do vault e apagadas pela rotina de limpeza; gravações cujo processamento falhou permanecem indefinidamente até um **comando de reprocesso** — idempotente — completá-las. Nenhuma reunião se perde por instabilidade, e áudio sensível não acumula para sempre.

**Blocked by:** 01 — Esqueleto do pipeline com portas fake; 03 — STT real: adapter Deepgram.

**Status:** resolved

- [x] Rotina de limpeza apaga apenas gravações com processamento bem-sucedido e mais de 7 dias (período configurável)
- [x] Gravações com falha nunca são apagadas pela limpeza
- [x] Comando de reprocesso completa uma gravação retida e é idempotente (não duplica notas)
- [x] Comportamentos cobertos por testes na costura única (com fakes), incluindo os casos de falha

## Comments

**Camada 06 entregue** — `src/second_brain/retencao.py`, os subcomandos `reprocessar` e `limpar` em `src/second_brain/__main__.py`, o `transcricao.json` em `src/second_brain/gravacao.py` + `src/second_brain/pipeline.py`, e os testes em `tests/test_retencao.py`, `tests/test_comando.py` e `tests/test_pipeline.py`. Suíte: **161 passaram, 3 desselecionados** (`rede`).

**Como ficou.** A retenção trabalha em duas etapas explícitas, porque apagar áudio de reunião não se desfaz: `avaliar()` julga cada pasta e devolve o motivo em português, `limpar(simular=True)` mostra isso sem tocar em nada, e só `limpar(simular=False)` apaga — registrando nome, idade, tamanho e motivo. Candidata é só `status: transcrito` com mais de `retencao_dias` contados do `processado_em` (caindo para o mtime do `estado.json` quando a data falta); `falhou` e `pendente` ficam indefinidamente. Pasta com nome fora do contrato `YYYY-MM-DD-HHMM-<slug>` nunca é candidata — é a cerca que impede a limpeza de opinar sobre o que não nasceu do gravador. O `reprocessar` sem argumento varre as retidas; com pasta explícita, aceita o caminho.

**A CLI ficou unificada**, como o contrato previa: `processar`, `reprocessar` e `limpar` sobre a mesma configuração, agora com os **adaptadores reais por padrão** e `--fakes` como a forma explícita de exercitar tudo sem rede nem crédito.

**Fecha o critério 3 da camada 04.** O `transcricao.json` é gravado assim que o STT devolve, antes de qualquer tentativa de resumo: uma falha do Claude não custa mais uma segunda chamada à Deepgram.

**Provas que o orquestrador executou, não apenas recebeu** (cenário montado no temp, CLI de verdade):

- `limpar --simular` sobre quatro gravações (transcrita há 30 dias, transcrita há 2 dias, `falhou` há 60 dias, `pendente` antiga) + uma pasta fora do contrato: apagaria só a de 30 dias, e o disco ficou intacto depois.
- `limpar` de verdade: apagou exatamente aquela pasta (13,3 KB), preservou as três outras com o motivo de cada uma, não tocou `backup-do-usuario/importante.txt` e deixou o vault byte a byte idêntico (hash antes/depois), incluindo `notas/minha-nota.md` plantada de propósito.
- `reprocessar --fakes`: completou a que falhou e a que nunca foi processada; a segunda rodada disse "Nenhuma gravação retida" e o hash do vault não mudou; reprocessar uma pasta já concluída responde "Já processada" sem reescrever nada.
- Ciclo falha-do-resumo → reprocesso com um STT que conta chamadas: **1 chamada no total**, `transcricao.json` presente após a falha, áudio preservado, nenhuma nota parcial no vault, `transcricao_reaproveitada=True` na segunda passada e status final `transcrito`.

**Dois consertos do orquestrador, na mesma camada:**

1. **O relatório da limpeza mentia num caso.** Quando a única vencida falhava ao ser apagada, `limpar` imprimia "Nenhuma gravação venceu o prazo de retenção" e logo abaixo listava a falha. Agora essa frase só sai quando nada venceu mesmo. Teste novo segura isso com um modo de falha real do Windows — um handle aberto num WAV da pasta, sem mock nenhum — e foi confirmado que ele falha se o conserto for revertido.
2. **Prazo de retenção negativo apagava tudo que já virara nota.** `--dias=-1` e `retencao_dias = -3` eram aceitos e tornavam toda gravação transcrita "vencida", incluindo a reunião da manhã. Agora o parser recusa `--dias` negativo com mensagem que ensina o `0`, e `retencao_dias` negativo ou não inteiro é `ConfiguracaoInvalida` na leitura da configuração. Zero continua válido — é a escolha legítima de apagar o áudio assim que ele vira nota.

**Sondagens que passaram sem conserto:** uma junção do Windows apontando para uma pasta do usuário, plantada dentro de `gravacoes` com nome de contrato e `estado.json` vencido, **não** foi seguida — `rmtree` recusa symlink, o alvo ficou intacto e a falha apareceu no relatório com código de saída 1.

Achados registrados em `.scratch/tracer-bullet/DEFERRED.md`: limpeza que falha no meio deixa a pasta sem `estado.json` (e o reprocesso paga um STT novo); junção dentro de `gravacoes` repete o erro a cada limpeza sem dizer o que fazer; nada agenda a limpeza (candidato: a bandeja da camada 05); nada impede `vault` e `gravacoes` de apontarem para o mesmo lugar.

**Fechada pelo orquestrador.** Resta desta camada nenhuma pendência com o usuário — retenção e reprocesso são inteiramente locais e provados pela costura.

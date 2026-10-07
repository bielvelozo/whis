# O que ele marca na página do jornal mora no banco do artifact, e o vault copia toda manhã

> Registro de 2026-10-06.

A formação do jornal (*Aprender hoje*, de negócios, e *Para aprender*, de carros) só avança numa
área depois de ele marcar a aula anterior como lida, e no sábado vem o *Quiz da semana*. O check
"Li esta aula" e as respostas do quiz ficam na própria página publicada, no banco do artifact (a
capacidade `db`, coleções `leituras` e `respostas`). Toda manhã, antes de escrever as aulas, o
Whis lê esse banco por uma sessão do CLI com a ferramenta `ArtifactData` e copia o que mudou para
o vault: a aula vira `status: lida` em `noticias/aulas/<id>.md` e a pergunta ganha o `Resultado:`
em `noticias/quiz/AAAA-MM-DD.md`. Spec em `.scratch/jornal-formacao/spec.md`, achados da sonda em
`.scratch/jornal-formacao/research/00-banco-e-fotos.md`.

## Por quê

Ele lê o jornal no celular, na página publicada. O vault não é alcançável de lá, e o check tem de
estar onde ele lê; marcar no Obsidian continua valendo, mas como segundo caminho.

## Considered Options

- **Só o Obsidian** (`status: lida` na nota da aula): nada fora do vault, mas obriga a abrir outro
  app para cada aula. Ficou como alternativa, não como o caminho principal.
- **A página se republica sozinha com o estado embutido** (a capacidade `artifact`): o estado
  ficaria no HTML, que o republish das 08:20 substitui; o Whis teria de garimpar o HTML vivo e
  competir com a própria publicação.
- **Banco do artifact** (escolhida): as linhas sobrevivem ao republish, a página grava e lê com
  `claude.use("db")`, e o CLI lê sem permissão extra.

## Consequências

- **A regra "nenhum estado fora do vault" ganha uma exceção de entrada.** O banco é por onde a marca
  chega; depois da cópia, a verdade é o vault. Aula já `lida` no vault não volta a pendente.
- **O Whis só lê o banco.** Em `dontAsk`, a `ArtifactData` lê, mas qualquer escrita e o `out_dir`
  são negados. Por isso o Python lê o texto do resultado da ferramenta (uma linha JSON por
  documento entre marcadores), nunca o texto do modelo; só com `ArtifactData` a sessão nasce sem
  ferramenta e o modelo diz "OK" sem ter lido nada, então o adaptador pede `Artifact` junto.
- **A leitura pede só o que interessa** (`query` com `where`: leituras desde a aula pendente mais
  antiga, respostas dos quizzes ainda sem resultado) e segue o cursor. Sem nada pendente, nem roda.
  Custo: uns US$ 0,01 a 0,04 por manhã.
- **Falha na leitura não avança nada**: a edição avisa no topo e as aulas pendentes continuam
  pendentes. Errar desse lado é melhor que andar sem ele ter lido, mas a trilha para até consertar.
- **Depende de duas coisas não documentadas**: `CLAUDE_CODE_ARTIFACT=1` e a `ArtifactData` em
  headless, que só vem no CLI do npm (2.1.274 ou mais novo), não no empacotado do SDK.
- **A página ganhou o primeiro script.** Fora do claude.ai (a página local do `--simular`) ou sem
  permissão, o botão aparece apagado com uma linha dizendo por quê, e tudo continua legível.

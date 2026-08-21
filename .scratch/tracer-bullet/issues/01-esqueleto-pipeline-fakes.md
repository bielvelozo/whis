# 01 — Esqueleto do pipeline com portas fake

**What to build:** O coração demoável do coletor de reunião: um comando que recebe uma pasta de gravação (áudio de fixture) e produz os artefatos no vault usando STT e resumo **fake** injetados pelas portas. Na primeira execução, cria o vault e as pastas (`reunioes/`, `transcricoes/`, `diario/`, `notas/`) no caminho configurado. O resultado é uma nota de reunião com frontmatter (`data`, `tipo`, `participantes`, `transcricao` como wikilink) em `reunioes/YYYY-MM-DD-nome-da-reuniao.md` e a transcrição em `transcricoes/` com o mesmo prefixo. Este ticket estabelece a costura de teste do repo: testes de comportamento contra `processar(pasta) → arquivos no vault`, com fakes nas portas, sem mock de detalhe interno.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] Comando processa uma pasta de gravação fixture e cria nota + transcrição nos lugares e formatos decididos na spec
- [x] Vault e estrutura de pastas criados automaticamente se não existirem; caminho vem de configuração local
- [x] Nota linka a transcrição por wikilink e o frontmatter contém todos os campos mínimos
- [x] O pipeline nunca escreve fora de `reunioes/` e `transcricoes/` (zona de propriedade respeitada)
- [x] Testes de comportamento cobrem o caminho feliz e rodam verdes com fakes de STT e resumo
- [x] Reprocessar a mesma pasta não duplica notas (idempotência básica)

## Comments

**Camada 01 entregue** — pipeline, portas, fakes, configuração, vault e o subcomando `processar`, com 34 testes de comportamento verdes contra a costura única. Registrado em `.scratch/tracer-bullet/DEFERRED.md`:

- Caminho Windows com barra invertida no `config.toml` quebra o parse do TOML com mensagem pouco didática (`src/second_brain/configuracao.py`) — ergonomia de setup, não coberta por nenhum critério do 01; sugerido para a camada 05.
- Não existe comando que crie o `config.toml` inicial — o usuário escreve à mão em `%APPDATA%\second-brain\`; um `second-brain init` cabe na camada 05.
- O frontmatter é montado à mão, sem biblioteca de YAML (ADR 0001 pede projeto fino) — suficiente para os campos do contrato, revisitar só se algum campo precisar de bloco multilinha.

Notas de entrega para as camadas seguintes: as duas portas estão em `src/second_brain/portas.py` (`PortaSTT.transcrever(canais) -> Transcricao`, `PortaResumo.resumir(transcricao, titulo) -> Resumo`); `Resumo.participantes` e `Resumo.titulo` são opcionais — vazios fazem o pipeline cair para os falantes da transcrição e para o título da gravação. O wikilink usa o caminho (`[[transcricoes/<basename>]]`) e não o nome curto, porque nota e transcrição compartilham o basename fixado pelo contrato.

**Fechada pelo orquestrador.** Revisão encontrou um furo na zona de propriedade — `vault.escrever` validava só o primeiro componente do caminho, então `reunioes/../notas/invadida.md` escapava e escrevia na zona do usuário. Corrigido na mesma camada: a checagem passa a comparar o caminho **resolvido** com `is_relative_to` da pasta da zona, e a escrita usa o caminho resolvido. Teste parametrizado cobre 8 fugas nas duas zonas mais os casos de caminho vazio e de escrita sobre a própria pasta; confirmado que falham se o conserto for revertido.

Provas conferidas pelo orquestrador, não só reportadas: `pytest` 46 verdes; execução real do comando com as seis fugas recusadas e `reunioes/2026/nota.md` ainda permitido; nota e transcrição lidas no disco com frontmatter completo e wikilink correto; idempotência provada por hash do vault antes/depois de reprocessar; `notas/` intacta com uma nota manual plantada de propósito.

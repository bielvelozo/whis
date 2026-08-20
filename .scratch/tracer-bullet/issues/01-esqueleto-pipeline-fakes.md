# 01 — Esqueleto do pipeline com portas fake

**What to build:** O coração demoável do coletor de reunião: um comando que recebe uma pasta de gravação (áudio de fixture) e produz os artefatos no vault usando STT e resumo **fake** injetados pelas portas. Na primeira execução, cria o vault e as pastas (`reunioes/`, `transcricoes/`, `diario/`, `notas/`) no caminho configurado. O resultado é uma nota de reunião com frontmatter (`data`, `tipo`, `participantes`, `transcricao` como wikilink) em `reunioes/YYYY-MM-DD-nome-da-reuniao.md` e a transcrição em `transcricoes/` com o mesmo prefixo. Este ticket estabelece a costura de teste do repo: testes de comportamento contra `processar(pasta) → arquivos no vault`, com fakes nas portas, sem mock de detalhe interno.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Comando processa uma pasta de gravação fixture e cria nota + transcrição nos lugares e formatos decididos na spec
- [ ] Vault e estrutura de pastas criados automaticamente se não existirem; caminho vem de configuração local
- [ ] Nota linka a transcrição por wikilink e o frontmatter contém todos os campos mínimos
- [ ] O pipeline nunca escreve fora de `reunioes/` e `transcricoes/` (zona de propriedade respeitada)
- [ ] Testes de comportamento cobrem o caminho feliz e rodam verdes com fakes de STT e resumo
- [ ] Reprocessar a mesma pasta não duplica notas (idempotência básica)

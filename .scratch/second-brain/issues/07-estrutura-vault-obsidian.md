# Estrutura do vault Obsidian

Type: grilling
Status: resolved
Blocked by: 02

## Question

Como o vault é estruturado e como o agente escreve nele? O usuário ainda não usa Obsidian — o vault nasce do zero.

Decidir (sessão com `/domain-modeling` — aqui nasce o vocabulário do domínio):

- Já decidido em [Estender o Whis ou projeto separado?](02-estender-whis-ou-separar.md): **vault novo, local, sem legado** — resta decidir onde no disco e como nasce. As convenções prompt-driven do SOUL.md do Whis são referência opcional.
- Estrutura de pastas: reuniões, atividade diária, perfil profissional, notas manuais futuras.
- Formato das notas: frontmatter, tags, convenções de nome, links.
- Regras de escrita do agente: append-only? nunca editar nota manual? como evitar conflito quando o usuário começar a usar o Obsidian.

## Answer

Decidido pelo usuário em 2026-08-14:

- **Localização**: pasta dedicada no perfil do usuário (ex.: `C:\Users\<usuário>\vault`), **fora do repo de código** — vault é dado, repo é código. O nome/caminho exato fica para a spec.
- **Estrutura por fonte**, mínima na v1:
  - `reunioes/` — notas de reunião (resumo, o que o usuário relê)
  - `transcricoes/` — transcrições brutas diarizadas, linkadas das notas
  - `diario/` — resumos de trabalho vindos das fontes passivas (`diario/YYYY-MM-DD.md`)
  - `notas/` — notas manuais do usuário, zona livre
  - Agrupamento por projeto/cliente emerge via links e tags, não via pastas.
- **Nomes e frontmatter**: `reunioes/YYYY-MM-DD-nome-da-reuniao.md`; frontmatter mínimo `data`, `tipo`, `participantes`, `transcricao` (wikilink). Campos extras e tags evoluem com o uso.
- **Zonas de propriedade**: coletores/agente são donos de `reunioes/`, `transcricoes/` e `diario/` (criam e podem regenerar); `notas/` é do usuário — o agente **nunca edita**, só lê e linka.
- **Áudio bruto**: retido **7 dias** após a transcrição (janela de re-transcrição) e apagado; vive fora do vault.
- Névoa nova registrada no mapa: backup/versionamento do vault.

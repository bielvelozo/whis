# 01 — Inventário dos pontos de contato

Type: research
Status: resolved

## Question

Qual é, hoje, o conjunto exato de gestos que o Whis oferece — como cada um é acionado, onde o
usuário está naquela hora, e como ele descobre que algo falhou? A tabela do
[handoff](../handoff.md) é o ponto de partida; **confira cada linha no código e na máquina**
antes de confiar.

Em especial, resolver as dúvidas que o handoff deixou marcadas:

- O diário está agendado? (`windows --limpeza` agenda só a limpeza.)
- O que exatamente o menu da bandeja oferece hoje?
- Por onde uma falha da daily, do diário ou do atendente chega ao usuário?
- Que superfície candidata cobre cada gesto?

O resultado alimenta os tickets 02–04 (o que cada superfície precisa cobrir) e o 05 (as
perguntas do *grilling* nascem das dores reais, não das imaginadas).

## Answer

A tabela do handoff está certa no essencial, e **errada por otimismo em três pontos**. Detalhes,
comandos e saídas em [../research/01-pontos-de-contato.md](../research/01-pontos-de-contato.md).

1. **O Whis está parado na máquina dele agora.** Nenhum processo Python no ar: nem a bandeja nem
   o atendente. O atalho de logon (`Second Brain.lnk`) aponta para `-m second_brain bandeja`, e
   esse módulo deixou de existir no rename de 09/09 — sobe com `pythonw.exe`, que não tem
   console, então o erro não aparece em lugar nenhum. O atendente **nunca teve atalho**
   (`whis windows --atendente` não foi rodado). A tarefa agendada `SecondBrain-Limpeza` roda
   `-m second_brain limpar` todo dia ao meio-dia e falha calada pelo mesmo motivo. A pendência 3
   do handoff não é cosmética: **são três automações mortas**.
2. **O diário nunca foi agendado por código nenhum.** `automacao.py` só sabe criar dois atalhos
   de logon e agendar a limpeza — não há caminho para agendar `diario` nem `daily`. E
   `[diario].hora_da_tarefa = "19:00"` é lida e validada em `configuracao.py`, tem teste, aparece
   no `MODELO_DE_CONFIGURACAO` com o comentário *"quando a tarefa agendada gera o diário"* — e
   **nenhum código a usa**. É uma intenção documentada que nunca virou comportamento: agendar o
   diário é trabalho novo, não configuração.
3. **Falha de automação não tem para onde gritar.** O balão do Windows é da bandeja, e só sobre
   reunião; todo o resto (daily, diário, atendente, limpeza) deixa rastro só em
   `%APPDATA%\whis\bandeja.log`, que ninguém abre. Pior: **quem falha antes de subir não escreve
   log nenhum** — é exatamente o caso das três automações mortas acima, e o mesmo caso do OAuth
   vencido de 10/09. A linha "saber que algo falhou" do inventário não é hipótese: está
   acontecendo, sem ninguém saber.

**Acrescentado depois, pelo ticket 04:** há uma **quarta** coisa quebrada. `.md` não tem programa
associado nesta máquina (`assoc .md` → *"Associação de arquivo não encontrada"*), e
`bandeja.abrir_no_windows` usa `os.startfile` — então o item de menu *"Abrir a última nota"*, o
único que liga a bandeja ao vault, **não abre o Obsidian**. Trocar por uma URI `obsidian://` é uma
linha, e é a menor entrega útil que este levantamento produziu.

Três confirmações que valem registro:

- **A bandeja já sabe dar balão do Windows**, por `pystray.Icon.notify` — sem dependência nova.
  Serve para avisar; **não tem botão**, e é isso que o ticket 02 precisa resolver.
- **O menu da bandeja hoje** tem cinco itens e nenhum deles fala de daily, diário ou pergunta:
  *Gravar reunião* (padrão, também no clique esquerdo), o estado por extenso (desabilitado),
  *Abrir a última nota*, *Abrir a pasta de gravações*, *Sair*.
- **Os envelopes `interactive` e `slash_commands` já são confirmados** em `dm_slack._receber`,
  mas **descartados em seguida** — o `return` acontece quando o tipo não é `events_api`. Ligar
  botão do Block Kit significa tratar esse envelope, não trocar o transporte.

**Correção operacional importante, provada aqui:** o `%APPDATA%` desta sessão de agente **não é
o do usuário**. `conversas.json` (que nenhum agente escreveu) mostra os turnos reais da demo de
10/09 às 19:51 e 19:58; `bandeja.log` e `config.toml`, escritos por agente em 09/09, estão
congelados naquele dia — o log não tem uma linha sequer da demo, e o `config.toml` legível pelo
agente mostra `[slack].bot_token` e `app_token` **vazios**, o que contradiz a DM ter funcionado.
São cópias velhas. **Nenhuma afirmação sobre o conteúdo de `config.toml` neste esforço pode vir
de leitura do agente** — quem confere é o usuário.

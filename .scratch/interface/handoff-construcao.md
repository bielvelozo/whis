# Handoff: construir a entrega 4 (a palheta e a daily viva)

Documento de continuação, escrito em 2026-09-11, no fim da sessão que **fechou o levantamento e a
spec**. Assume **zero contexto**: leia inteiro antes de tocar em qualquer coisa.

A spec está pronta e aprovada pelo usuário: **[spec.md](spec.md)**, `ready-for-agent`. Esta sessão
é de **construção**, conduzida com `/rb-orchestrate`.

> **A lição que este projeto já aprendeu duas vezes, e que a spec existe para não repetir:** a
> entrega certa não é a que cabe na arquitetura existente, é a que cabe no dia do usuário. A
> primeira spec da entrega 3 foi escrita para o terminal e recusada inteira. A entrega 4 nasceu
> porque ele **parou de usar** o que estava pronto. Se algo na spec parecer caro de construir, o
> caminho é falar com ele, não simplificar por conta própria.

---

## 0. FAÇA ISTO ANTES DE ABRIR A SESSÃO DE CONSTRUÇÃO

**A camada zero começa com um passo que nenhum agente consegue fazer**, porque o Windows não
renomeia o *cwd* de um processo vivo. Com **nenhuma sessão de agente aberta na pasta**, no
PowerShell do usuário:

```
Rename-Item C:\Users\gabri\development\second-brain C:\Users\gabri\development\whis
```

E, **imediatamente depois**, de dentro da pasta nova:

```
.venv\Scripts\python.exe -m pip install -e .
```

Sem isso o `import whis` quebra: o editable install gravou o caminho absoluto antigo em
`.venv/Lib/site-packages/__editable__.whis-0.1.0.pth`.

Só então abra a sessão de construção, já com o *cwd* em `C:\Users\gabri\development\whis`.

---

## 1. Onde as coisas estão

| | |
|---|---|
| suíte | **862 verdes**, 8 desselecionados (7 antigos + o teste de rede da busca) |
| spec | [spec.md](spec.md), `ready-for-agent`, escopo confirmado por ele em 11/09 |
| levantamento | [map.md](map.md) + seis tickets em [issues/](issues/) + cinco achados em [research/](research/) |
| em uso real | **nada**. O usuário parou de usar o Whis; foi isso que gerou esta entrega |
| na máquina | a bandeja **não sobe** no logon, o atendente **nunca teve** atalho, a tarefa de limpeza **falha calada** todo dia — tudo apontando para o módulo `second_brain`, que não existe mais |

### Verifique antes de começar

```
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m whis perguntar --fakes --sem-fio "teste"
git log --oneline -10
```

862 passam. O `perguntar --fakes` imprime a resposta de exemplo e sai `0`.

### O que ler, nesta ordem

1. **[spec.md](spec.md)** — é o contrato. Tudo o mais é contexto para entendê-la.
2. `CONTEXT.md` — o glossário. **Daily** e **Diário** são termos distintos, e **Whis** (este
   projeto) não é o **Whis da EC2** (o agente aposentado dele). A entrega 4 **acrescenta um termo**:
   a terceira zona de propriedade.
3. [issues/05-o-dia-do-usuario.md](issues/05-o-dia-do-usuario.md) — as sete rodadas do *grilling*,
   com as palavras dele. **Quando a spec for ambígua, a resposta está aqui.**
4. [research/01-pontos-de-contato.md](research/01-pontos-de-contato.md) — o que está quebrado na
   máquina e por quê.
5. Os outros achados, conforme a camada: [02](research/02-windows-agendador-e-aviso.md) (agendar e
   avisar), [05](research/05-janela-local-e-launcher.md) (palheta e atalho global),
   [04](research/04-obsidian-como-interface.md) (URI do Obsidian).
6. `.scratch/second-brain/map.md` — o mapa do esforço original, onde esta é a **entrega 4**. A
   pasta mantém o nome antigo de propósito: uma dúzia de documentos históricos linka para dentro
   dela. **Não renomeie.**

---

## 2. A entrega, em um parágrafo

O Whis passa a ter **uma palheta de comandos** aberta por atalho global no PC (dispara, a janela
some, o resultado cai no vault, um toast avisa) e **uma daily viva** em `daily/atual.md` que ele
*mantém* em vez de reescrever. A DM do Slack **dorme**. O diário fica **suspenso**. E um vigia
bobo, fora do Whis, avisa quando alguma peça não subiu.

**O coração da entrega é uma regra, não uma tela:** ao mover um item de *O que estou fazendo* para
*O que eu fiz*, o agente **carrega o texto do usuário literalmente, sem reescrever uma palavra**.
Foi o Whis re-descrever todo dia, com palavras novas, um trabalho que ele já tinha nomeado do seu
jeito, que o fez parar de usar — nas palavras dele: *"da maneira que ele descrevia o que eu fiz eu
não lembrava exatamente o que era e não sabia explicar"*. Se essa regra não for cumprida, o resto
da entrega não vale nada.

---

## 3. As camadas, na ordem em que se resolvem

| nº | o que fecha |
|---|---|
| **0** | Arrumar a casa: remover `Second Brain.lnk` e a tarefa `SecondBrain-Limpeza`, recriar atalhos e tarefas com os nomes novos **e com AUMID**, tirar `"second-brain"` de `[daily].referencias_pessoais` |
| **1** | A nota viva `daily/atual.md`: quatro seções, a terceira zona no `CONTEXT.md`, e a regra de carregar sem reescrever — **com o teste que a sonda nos dois sentidos** |
| **2** | Agendamento confiável (módulo PowerShell `ScheduledTasks`, com `-StartWhenAvailable`), horário por dia da semana, e o vigia que avisa por toast |
| **3** | A palheta: atalho global, janela, registro de comandos, contrato de *dispara e some* |
| **4** | O painel de configuração das 24 chaves e o escritor de TOML próprio, com backup |
| **5** | O toast com botão que abre a nota, e a troca do `os.startfile` por URI `obsidian://` |

A camada 1 é a que entrega valor sozinha: se a sessão morrer depois dela, o usuário já tem a daily
que ele queria. Considere isso ao dividir o trabalho.

---

## 4. Armadilhas — não redescubra

**Do ambiente:**

- **O `%APPDATA%` do agente pode não ser o do usuário.** Provado nesta sessão
  ([research/01](research/01-pontos-de-contato.md), §5): arquivo que um agente escreveu fica
  congelado na versão dele; arquivo que só o usuário tocou passa direto. O `config.toml` que o
  agente lê mostra `bot_token` vazio, o que é falso. **Nunca conclua nada sobre `config.toml`, nem
  sobre a pasta de Inicialização, por leitura sua** — quem confere é ele. Para entregar bytes que
  ele precise ver, escreva fora do `AppData` (`C:\Users\gabri\` atravessa nos dois sentidos).
- **O terminal dele é PowerShell 5.1**, não bash. `&&` não existe, caminho é `C:\assim`, e `;`
  separa comandos. Sessões anteriores erraram isso três vezes.
- **Credencial não se grava por insistência.** Ele vai pedir para você colar o token; a saída que
  funciona é um comando com `Read-Host` que ele roda. Use `[IO.File]::WriteAllText`, porque
  `Set-Content` no PowerShell 5.1 escreve UTF-8 **com BOM** e o `tomllib` engasga com BOM.

**Da implementação, todas verificadas:**

- **`schtasks` não consegue ligar `-StartWhenAvailable`** — percorrida a sintaxe inteira do
  `/create`. Sem essa opção, uma daily agendada **não acontece** se o PC estiver desligado na hora,
  e não avisa. Use o módulo PowerShell `ScheduledTasks`, que já vem no Windows.
- **Toast exige atalho no Menu Iniciar com AUMID** para app não empacotado. O atalho de hoje não
  tem — é por isso que a camada 0 recria os atalhos, e não só conserta o caminho.
- **O `_mainloop` do `pystray` consome todas as mensagens do thread**, então a `WM_HOTKEY` precisa
  de janela ou thread próprio. O conflito de main loop tem saída: `pystray._win32._run_detached` é
  literalmente uma thread — Tk no principal, bandeja na secundária.
- **`.md` não tem programa associado nesta máquina.** `os.startfile` num `.md` não abre o Obsidian
  — abre o diálogo "como você quer abrir", ou falha. Use a URI.
- **`tomllib` só lê.** Não há escritor de TOML instalado, e a spec decidiu escrever o nosso a
  partir do `MODELO_DE_CONFIGURACAO`. Não instale dependência para isso sem falar com ele.
- **Dois testes de uma tarde faltam** antes de fechar o desenho da palheta: `RegisterHotKey` sob
  `pythonw.exe`, e `pystray.run_detached` convivendo com o `mainloop` do Tk. Faça-os cedo — eles
  podem mudar a forma da camada 3.

**Do produto:**

- **Não decida a interface pela arquitetura.** Está escrito três vezes na linhagem destes
  documentos, de propósito.
- **Não "conserte" a spec de volta.** Ela reverte cinco decisões anteriores, e os documentos das
  entregas fechadas ainda dizem o contrário — são registro do que aconteceu, não instrução. As
  cinco estão nomeadas no topo da spec.

---

## 5. O que está fora, e não deve entrar sozinho

- **Os seis comandos futuros** — vagas e freelas, notícias de IA, weekly/planning, slides,
  reminders. O usuário recusou **explicitamente** incluir até mesmo um deles como prova.
- **Pesquisa noturna**, áudio e imagem na DM, Google Calendar, plugin do Obsidian, nota-painel
  adicional, backup do vault.
- **Reescrever a daily, o diário ou o agente.** Eles funcionam. Isto decide por onde ele os aciona
  e por onde eles falam com ele.

---

## 6. Pendências com o usuário

1. **A pasta privada nunca foi exercitada.** `[privacidade].pastas_privadas` está vazia desde
   04/09 — o agente enxerga o vault inteiro. É a única garantia de privacidade da entrega 3 e a
   única não testada. Passo 9 do `docs/smoke-atendente.md`, dois minutos, mas **a escolha da pasta
   é dele**. Com o painel de configuração da camada 4, isso fica fácil — talvez seja a hora.
2. **O aviso ao admin do Slack.** O pedido anterior afirmava que a app não teria scope de escrita,
   e hoje tem quatro de bot mais o `files:read` que ele adicionou. Com o Slack dormindo, nada é
   usado — mas os scopes estão concedidos. **Decisão dele** se avisa ou revoga.
3. **Armadilha viva no vault**: a Daily notes do núcleo do Obsidian está ligada e transforma o
   campo `data:` de toda nota do Whis em link para uma daily note inexistente na raiz; clicar cria
   lixo. Barato de resolver, e a camada 1 já mexe no frontmatter.

---

## 7. Como conduzir

`/rb-orchestrate` a partir de **[spec.md](spec.md)**. Confirme o plano com ele antes de executar,
como a skill manda. Sugestões:

- **Uma camada por vez, com a suíte verde entre elas.** É como as três entregas anteriores foram
  construídas, e é o que permitiu 862 testes sem nenhum editado.
- **Camada 1 primeiro se precisar cortar escopo** — ela entrega valor sozinha.
- **A prova final não é a suíte**, é ele lendo `daily/atual.md` em voz alta numa daily de verdade e
  sabendo explicar cada linha. Nenhuma das entregas anteriores foi considerada fechada antes da
  prova na máquina dele.

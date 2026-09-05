# Handoff: recuperação de contexto — o agente no Slack

Documento de continuação. Escrito em 2026-09-04, no fim da sessão que fechou a entrega de fontes
passivas e **abriu** esta. Assume **zero contexto**: leia isto inteiro antes de tocar em qualquer
coisa.

Seu trabalho: **construir esta entrega**, camada por camada. Nada dela existe ainda — só a spec,
o contrato e os cinco tickets.

---

## 1. Onde as coisas estão

**A entrega anterior está fechada e em uso real.** Fontes passivas + daily: onze camadas, dez
resolvidas e uma revertida. A daily foi lida numa reunião de verdade em 2026-09-04 e funcionou.

**Esta entrega está planejada e não construída.** Spec, contrato e cinco tickets escritos e
commitados; zero linha de código.

| | |
|---|---|
| suíte | **610 verdes**, 7 desselecionados (todos `@pytest.mark.rede`) |
| pacote | ~9.500 linhas em `src/second_brain/` |
| último commit | `dbc808e` — a reescrita desta entrega |

### Verifique antes de começar

```bash
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m second_brain --help
git log --oneline -12
```

610 passam, 7 desselecionados. **Se a suíte não estiver verde, pare e descubra por quê.**

---

## 2. O que ler, nesta ordem

1. `CONTEXT.md` — o glossário. **Daily** e **Diário** são termos distintos, com significado fixo.
2. `.scratch/recuperacao-contexto/spec.md` — a spec desta entrega, com 12 user stories. Leia
   também o aviso no topo: ela foi **reescrita** depois de o usuário recusar a primeira versão.
3. `.scratch/recuperacao-contexto/contrato-busca.md` — o contrato entre camadas. É ele que fixa
   os tipos, a fronteira e o fio de 24 horas.
4. `.scratch/recuperacao-contexto/issues/01-*.md` — o seu primeiro ticket.
5. `AGENTS.md` e `docs/agents/` — como issues, labels e docs de domínio funcionam neste repo.
6. `.scratch/fontes-passivas/DEFERRED.md` — **45 itens**. Vale ler antes de começar; vários
   tocam o que você vai construir.

---

## 3. As decisões do usuário, e o porquê

Herde, não reabra. Tudo abaixo foi decidido por ele, e a razão importa mais que a regra.

- **A interface é uma DM do Slack, não o terminal.** Ele recusou a primeira spec com todas as
  letras: *"muito complexo e nada prático — eu abrir um terminal, digitar o comando e mandar
  minha pergunta"*. Um comando por pergunta é formulário, não conversa. **Não reintroduza o
  terminal como caminho principal**; `second-brain perguntar` existe só para teste e diagnóstico.
- **Fio de conversa de 24 horas, por silêncio.** Ele perguntou de manhã, volta à tarde, o fio
  continua. 24h desde o último turno, não meia-noite.
- **Pasta privada no vault.** Ele escolheu "tudo, menos uma pasta privada" quando perguntei o que
  a busca podia ler. Ele **ainda não disse qual pasta** — a lista nasce vazia, que significa vault
  inteiro visível, e ele configura quando quiser.
- **O agente não recebe o vault cru.** Isto **refina o ticket 08** do mapa, que dizia "agente com
  `cwd` no vault, grep/leitura". Com acesso livre ao disco a pasta privada dependeria de o modelo
  obedecer — a garantia fraca que já foi recusada nas DMs do Slack. Todo acesso passa por
  `Ferramentas`, e a fronteira é verificada em um ponto só.
- **A recusa diz "não existe", nunca "é privado".** Dizer que há algo escondido já vaza metade do
  que a pasta promete.
- **Fontes ao vivo incluindo o Slack**, escolhidas por ele sabendo que reabre a questão das DMs. A
  resposta de projeto: passar pelos coletores existentes, para blocklist, `so_com_mencao` e filtro
  de exclusão continuarem valendo sem ninguém lembrar deles.
- **Bot, e não o user token postando como ele.** A alternativa exigia `chat:write` no token de
  usuário, que permite postar como ele em qualquer conversa do workspace — pior de usar e mais
  difícil de o admin aprovar que um bot que só fala na própria DM.
- **Processo separado da bandeja.** Ela tem trava de instância e máquina de estados de gravação,
  e o pipeline de reunião está em uso real.
- **Toda resposta cita a fonte**, e "não achei" é resposta válida.

---

## 4. O passo humano que bloqueia a camada 04

**Só a camada 04 depende disso. As três primeiras não.**

Socket Mode exige um **app-level token** (`xapp-`) e um **bot token** (`xoxb-`) — conferido na
documentação do Slack em 2026-09-04. O user token `xoxp` que ele já tem **não recebe mensagem**.

Então a app interna existente precisa ganhar um bot, com `im:history`, `im:read`, `chat:write` e
`reactions:write`, mais Socket Mode ligado e o evento `message.im` assinado.

**O incômodo**: `docs/smoke-slack.md` promete ao admin que a app **não** pediria bot token. Esse
roteiro precisa ser atualizado antes de o usuário voltar a falar com o admin, senão ele se
contradiz. Está no ticket da camada 05.

---

## 5. O mapa do código que já existe

`src/second_brain/`, e o que desta entrega vai encostar em cada um:

| módulo | papel | você vai... |
|---|---|---|
| `vault.py` | escrita no vault, zonas de propriedade, notas de reunião/diário/daily | **ler muito**: `escrever` tem o padrão de checagem de caminho resolvido que a fronteira deve copiar |
| `fonte_git.py` `fonte_linear.py` `fonte_slack.py` | os três coletores | **chamar pelas fábricas `de_configuracao`**, nunca reimplementar |
| `resumo_dia_claude.py` | o Claude por OAuth: resumo do dia e roteiro da daily | **copiar o padrão**: recusa de API key paga, registro de custo, parse tolerante |
| `configuracao.py` | o `config.toml` e sua validação | acrescentar 2 chaves na camada 01, e **mais ninguém toca** |
| `portas.py` `fakes.py` | protocolos e fakes | acrescentar `BuscaFake` |
| `registro.py` | log em arquivo, para o que roda sem console | usar no atendente, que roda o dia todo sem ninguém olhando |
| `automacao.py` | atalho de logon e tarefa agendada | camada 05, para o atendente subir no logon |
| `bandeja.py` `coletor.py` `instancia.py` | a bandeja e a máquina de estados | **não toque** |

---

## 6. Estado da máquina do usuário

`config.toml` em `%APPDATA%\second-brain\`, com backups de cada mudança desta sessão
(`.antes-da-camada-08`, `.antes-do-slack`, `.antes-da-blocklist`, `.antes-do-so-com-mencao`).

| chave | valor |
|---|---|
| `vault` | `C:\Users\gabri\second-brain-vault` |
| `[git].raiz` | `C:\Users\gabri\development`, profundidade 3 |
| `[deepgram]`, `[linear]`, `[slack].user_token` | preenchidos e funcionando |
| `[slack].conversas_excluidas` | `slackbot, uslack, notifier, sentry, zeno-agent` |
| `[slack].so_com_mencao` | `dev-codereview` |
| `[daily].referencias_pessoais` | `second-brain, renovo-hub` |
| `[daily].contexto_do_time` | preenchido (Zeno aprova, o merge é dele) |
| `[privacidade].excluir` | **vazio — nunca exercitado com padrão real** |

**Vault real**: `daily/2026-09-04.md`, `diario/2026-09-03.md`, duas reuniões em `reunioes/`, e
`notas/daily.md` com as quatro seções e um ponto do usuário. O Obsidian já está configurado
apontando para o vault, com "Local padrão para novas notas" em `notas/`.

**Há material de verdade para a busca achar.** A daily de 2026-09-04 tem 677 eventos nas listas
cruas, incluindo Slack.

---

## 7. O que foi provado, e o que não foi

**Provado com dado real**: os três coletores contra as APIs de verdade; a daily inteira de ponta a
ponta, lida numa reunião real; o corte trabalho/pessoal (32 eventos calados, zero falso positivo);
o filtro de menção do code review (121 → 37 eventos, todos citando o usuário); a blocklist do
Slack (8 conversas nunca consultadas).

**Não provado**: nada desta entrega — ela não existe. E o filtro `[privacidade].excluir` continua
sem nunca ter rodado com um padrão real, o que passa a importar mais com a consulta ao vivo.

---

## 8. Armadilhas já pagas — não redescubra

As dos handoffs anteriores continuam valendo (barra invertida no TOML, cp1252 no console, limites
da bandeja, `pythonw.exe` sem console, `git log --since` escondendo commit do dia, header do
Linear sem `Bearer`, fim de janela exclusivo). Acrescente estas, todas pagas nesta sessão:

- **Use `.venv/Scripts/python.exe`, nunca `python`.** O `python` do PATH não enxerga o pacote.
- **Não passe script Python por heredoc** (`python - <<'EOF'`) **com acento ou travessão.** O
  interpretador decodifica o stdin com a codepage errada e o arquivo chega mastigado — houve um
  commit inteiro só para consertar isso (`ee49ea5`). Escreva o script num arquivo `.py` em UTF-8 e
  rode-o.
- **O logger do Slack é `second_brain.fonte_slack`**, não `second_brain.fonte.slack`. Um
  `caplog.at_level` com o nome errado passa vazio e o teste falha sem dizer por quê.
- **`total_cost_usd` não é cobrança.** A conta é por assinatura via OAuth; o número é o
  equivalente da tabela da API e serve como medida relativa de cota. Os tokens de entrada que o
  log mostra vêm subnotificados (o volume real cai em `cache_creation_input_tokens`).
- **Socket Mode não funciona com user token.** Conferido na documentação; exige app-level + bot.
- **Uma daily real custa o equivalente a US$ 0,66–0,84** e leva ~40s. Teste de rede gasta a
  assinatura: rode de propósito, nunca por hábito, e **peça antes**.
- **`pytest` com `addopts` do projeto engole o resumo** em algumas invocações; use
  `-o addopts="-m \"not rede\""` quando quiser ver a contagem.

---

## 9. O padrão de trabalho desta casa

Foi ele que pegou todos os achados das duas entregas anteriores:

1. O **orquestrador** escreve a spec, quebra em camadas e **fixa os contratos por escrito antes**
   de abrir qualquer uma. Isto já está feito para esta entrega.
2. Cada camada é entregue por um **executor** e depois **revisada pelo orquestrador, que executa
   as provas ele mesmo** em vez de aceitar o relato. Isso pegou, nesta sessão: um furo de
   cobertura na janela, um relatório que afirmava faltar um teste que existia, o bug do
   `git log --since`, e uma linha que dizia "as últimas 24 horas" cobrindo 34.
3. **Mutação é a prova de que o teste morde.** Quebre a linha de propósito e conte quantos testes
   caem; se nenhum cair, o teste não vale nada. Está nos comentários de entrega de várias camadas.
4. Achado fora do escopo vai para `.scratch/fontes-passivas/DEFERRED.md` — uma linha: o quê, onde,
   por que ficou de fora, de qual camada veio.
5. Camada fechada recebe comentário de entrega no ticket, **com as provas executadas**, não com
   adjetivos. E o `Status:` muda para `resolved`.
6. **Comentários no código só quando explicam o PORQUÊ não óbvio.** Nunca o quê.
7. **Não edite teste existente.** Quando for inevitável — porque o formato mudou a pedido do
   usuário — diga isso no comentário de entrega e explique.

---

## 10. Uma coisa que esta sessão errou, e vale como aviso

A primeira spec desta entrega foi escrita para o terminal, e o usuário a recusou inteira. O sinal
já estava na mesa: a bandeja fica ligada o dia todo, ele vive no Slack, e o agente anterior dele
(o Whis) morava no WhatsApp. **A entrega certa não é a que cabe na arquitetura existente, é a que
cabe no dia do usuário.** Quando a próxima decisão de interface aparecer, pergunte antes de
escrever.

O mesmo se aplica à página HTML da daily, construída e revertida no mesmo dia: veja o ticket
`.scratch/fontes-passivas/issues/09-a-daily-como-pagina.md`, que registra por que ela deixou de
fazer sentido assim que o Obsidian entrou.

---

## 11. Por onde começar

**Camada 01** (`.scratch/recuperacao-contexto/issues/01-a-costura-a-fronteira-e-o-fio.md`) — não
depende de nada externo, nem de rede, nem do admin do Slack. Entrega a costura, as ferramentas
com a fronteira da pasta privada, o fio de 24 horas e o fake.

O teste que mais importa dela: **um arquivo sob a pasta privada não aparece na busca, não é lido,
não é listado, e não chega ao fake** — sondado nos dois sentidos, como a zona de propriedade já é
em `tests/test_zona_de_propriedade.py`.

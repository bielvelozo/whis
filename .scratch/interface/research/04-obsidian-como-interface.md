# O Obsidian como interface

Levantado em 2026-09-10, contra a documentação oficial do Obsidian, os repositórios dos plugins
citados e a máquina do usuário. Ticket: [04](../issues/04-obsidian-como-interface.md). Herda os
fatos de [01 — Inventário dos pontos de contato](01-pontos-de-contato.md).

**Aviso de confiabilidade.** Três níveis de evidência, e eles estão marcados no texto:

| nível | o que é | como aparece |
|---|---|---|
| **documentado** | página oficial do Obsidian / Microsoft / repositório do plugin | citação + URL |
| **verificado na máquina** | registro do Windows, `obsidian.json`, o vault, o código do Whis | comando ou caminho |
| **observação** | o que a máquina mostra mas eu não posso garantir que é a vista do usuário | dito com todas as letras |

O `%APPDATA%` desta sessão **pode não ser o do usuário** (research 01, §5). O corte lá descrito —
arquivo que agente escreveu fica congelado, arquivo que só o usuário tocou passa — sugere que
`obsidian.json` e o vault que li são os reais (ambos com mtime de hoje, 10/09, e escritos só pelo
Obsidian dele). **Ainda assim, tudo que vem de leitura de disco aqui está marcado como observação.**

**Eu não executei nenhuma URI e não abri o Obsidian.** Abrir o app reescreve
`.obsidian/workspace.json` — seria escrita dentro do vault do usuário, que o ticket proíbe. Os
testes de 10 segundos que faltam estão listados na §6, prontos para colar.

---

## 1. A URI `obsidian://` — o ponto mais importante do ticket

### 1.1 A sintaxe, verbatim

Formato: `obsidian://action?param1=value&param2=value`. As ações **de fábrica**, todas na mesma
página oficial ([Obsidian URI](https://obsidian.md/help/uri)):

| ação | o que faz | exige plugin? |
|---|---|---|
| `open` | abre um vault, ou um arquivo dentro dele | não |
| `new` | cria (ou acrescenta a) uma nota | não |
| `daily` | cria ou abre a *daily note do Obsidian* | **Daily notes** (núcleo) |
| `unique` | cria uma nota de nome único | **Unique note creator** (núcleo) |
| `search` | abre a busca, opcionalmente já com o termo | não |
| `choose-vault` | abre o gerenciador de vaults | não |
| `hook-get-address` | integração com o app Hook | não |

Os parâmetros de `open`, citados da página:

- **`vault`** — "can be either the vault name or the vault ID".
- **`file`** — "can be either a file name, or a path from the vault root to the specified file.
  If the file extension is `md`, the extension can be omitted."
- **`path`** — "an absolute file system path to a file. Using this parameter will override both
  `vault` and `file`. This will cause the app to search for the most specific vault which contains
  the specified file path. Then the rest of the path replaces the `file` parameter."
- **`paneType`** (opcional) — ausente, "the last active tab is replaced"; `tab` abre em aba nova;
  `split` em novo grupo de abas; `window` em **janela destacada** ("Desktop only").
- **`prepend`** / **`append`** — "will add to the top / to the end of the file and attempt to merge
  properties".

**Então: `vault=` é o *nome* do vault (ou o ID), não o caminho.** Quem aceita caminho absoluto é
`path=`, e ele não é um atalho para "abrir uma pasta qualquer": a página diz que o app **procura o
vault mais específico que contém aquele caminho** — ou seja, `path=` também depende de o vault já
ser conhecido do Obsidian.

O ID é explicado numa nota de rodapé da mesma página: *"Vault ID is the random 16-character code
assigned to the vault, for example `ef6ca3e3b524d22f`. This ID is unique per folder on your
computer. The ID can be found by opening the vault switcher and clicking 'Copy vault ID' in the
context menu for the desired vault."*

Há ainda duas formas curtas: `obsidian://vault/my vault/my note` equivale a
`obsidian://open?vault=my%20vault&file=my%20note`, e `obsidian:///caminho/absoluto/nota` equivale a
`open?path=...`.

### 1.2 Os valores para **este** vault

Verificado em `C:\Users\gabri\AppData\Roaming\obsidian\obsidian.json` (mtime 2026-09-10 19:21,
escrito pelo Obsidian do usuário — **observação**, pela ressalva do `%APPDATA%`):

```json
{"vaults":{
  "48d0aa91d0876fa3":{"path":"C:\\Users\\gabri\\Downloads","ts":1788532512167},
  "783d9ba94357b075":{"path":"C:\\Users\\gabri\\Documents\\Financeiro","ts":1789041591387},
  "245833c11ad43e6e":{"path":"C:\\Users\\gabri\\whis-vault","ts":1789049325303,"open":true}}}
```

- **nome do vault: `whis-vault`** (o nome da pasta) — sem espaço, sem acento.
- **ID do vault: `245833c11ad43e6e`**.
- O vault está registrado e marcado `"open": true`.
- **Há outros dois vaults na máquina** (`Downloads` e `Documents\Financeiro`). Isso importa para
  `path=`: "the most specific vault which contains the specified file path" — e importa mais ainda
  para a ideia de "pasta privada", §3.4.

As URIs concretas, então, são:

```
obsidian://open?vault=whis-vault&file=daily%2F2026-09-08
obsidian://open?vault=whis-vault&file=notas%2Fdaily
obsidian://open?vault=245833c11ad43e6e&file=diario%2F2026-09-03
obsidian://search?vault=whis-vault&query=retencao
```

Usar **o ID** em vez do nome é mais robusto: o nome muda se ele renomear a pasta; o ID é "unique
per folder on your computer" e só muda se ele mover o vault.

### 1.3 Com o Obsidian **fechado**

**A documentação não responde.** A única frase sobre o assunto é a do exemplo de `open`: *"This
opens the vault `my vault`. If the vault is already open, focus on the window."* Nada sobre o app
não estar rodando.

O que dá para provar sem executar nada, **verificado no registro desta máquina**:

```
HKCU:\SOFTWARE\Classes\obsidian
  (default)     = URL:obsidian
  URL Protocol  = (vazio, como manda o contrato de protocolo do Windows)
HKCU:\SOFTWARE\Classes\obsidian\shell\open\command
  (default)     = "C:\Users\gabri\AppData\Local\Programs\Obsidian\Obsidian.exe" "%1"
```

Ou seja: **o protocolo está registrado e o handler é o executável do Obsidian, recebendo a URI
inteira como argumento**. Com o app fechado, quem dispara a URI faz o Windows *iniciar o
Obsidian.exe* — isso é o Shell do Windows, não o Obsidian. O que o Obsidian faz com o argumento
ao subir do zero (abre o vault certo? cai na nota? cai no seletor de vaults?) **eu não testei**,
porque testar abre o app e reescreve `workspace.json` dentro do vault dele. Teste na §6.1.

A página oficial confirma o mecanismo do registro: *"On Windows and macOS, running the app once
should be sufficient to register the Obsidian URI protocol on your computer."* (No Linux é um
processo manual de `.desktop` — irrelevante aqui.)

**O que a URI não faz, em nenhum caso**: alcançar um vault que o Obsidian não conhece. Um
moderador do fórum oficial põe isso na frase mais curta que achei: *"The `obsidian://` URI scheme
looks up information that your vault has indexed (as you found in appdata)"*
([forum.obsidian.md](https://forum.obsidian.md/t/starting-obsidian-from-command-line-with-uri-open-path-is-not-working-under-windows/107025)).
É relato de fórum, não documentação — mas bate com o `obsidian.json` acima e com o texto de `path=`.

### 1.4 Acento e espaço — e a armadilha do `+`

O aviso da página é um callout de `warning`, e é literal:

> *"Ensure that your values are properly URI encoded. For example, forward slash characters `/`
> must be encoded as `%2F` and space characters must be encoded as `%20`. This is especially
> important because an improperly encoded 'reserved' character may break the interpretation of
> the URI."*

Ou seja: **a barra do caminho também é codificada** (`daily/2026-09-08` → `daily%2F2026-09-08`).
Acento é UTF-8 percent-encoded. Calculado aqui com o Python do projeto:

| valor | codificado |
|---|---|
| `daily/2026-09-08` | `daily%2F2026-09-08` |
| `notas/daily` | `notas%2Fdaily` |
| `notas/Minha Daily` | `notas%2FMinha%20Daily` |
| `reunioes/reunião de time` | `reunioes%2Freuni%C3%A3o%20de%20time` |

**A armadilha, e ela é de Python, não do Obsidian**: `urllib.parse.urlencode` codifica espaço como
`+`, não como `%20` — é `quote_plus` por padrão.

```
urlencode({'vault':'whis vault','file':'reunioes/reunião de time'})
  -> vault=whis+vault&file=reunioes%2Freuni%C3%A3o+de+time     # <- o '+'
quote('reunioes/reunião de time', safe='')
  -> reunioes%2Freuni%C3%A3o%20de%20time                       # <- o que a doc pede
```

A doc pede `%20` explicitamente e **não diz** que `+` é aceito. A rota segura é
`urllib.parse.quote(valor, safe='')` por parâmetro (ou `urlencode(..., quote_via=quote)`).

Dois fatos que aliviam metade do problema, verificados no código e no vault:

- **Nome de nota gerada pelo agente nunca tem acento nem espaço.** `gravador.criar_slug` faz
  `NFKD → ascii ignore → [^A-Za-z0-9]+ → '-'`, e as pastas datadas são `YYYY-MM-DD[-HHMM]`. Os
  arquivos reais são `reunioes/2026-09-03-1403-reuniao.md`, `daily/2026-09-08.md`,
  `diario/2026-09-03.md` (**observação**, listagem do vault).
- **A zona do usuário tem os dois.** `notas/` hoje contém `daily.md`, `Cycle 19.md` e
  `Minha Daily.md` (**observação**). Qualquer link para a zona dele precisa de codificação de
  verdade.

Também documentado: `Note%23Heading` navega para um cabeçalho e `Note%23%5EBlock` para um bloco —
`#` codificado. Serve para apontar direto para `## Preciso de` dentro da daily.

### 1.5 Acionar um **comando** do Obsidian pela URI

**De fábrica: não.** As sete ações da §1.1 são a lista inteira. Nenhuma executa comando da paleta.
`daily` e `unique` são as únicas que dependem de plugin, e são plugins de núcleo.

**Com plugin de terceiro: sim, e o plugin é o *Advanced URI*.** Deixando claro, porque o ticket
pede: **não é oficial nem da equipe do Obsidian**. É comunitário, de um autor individual —
`manifest.json` diz `"author": "Vinzent"`, `"authorUrl": "https://github.com/Vinzent03"`,
`"id": "obsidian-advanced-uri"`, versão 2.0.0, `minAppVersion` 1.5.7, `isDesktopOnly: false`;
repositório [Vinzent03/obsidian-advanced-uri](https://github.com/Vinzent03/obsidian-advanced-uri),
MIT, ~1,2k estrelas, último push 2026-08-17.

Ele usa um esquema próprio, `obsidian://adv-uri`, e o README dá o exemplo do comando por ID:

```
obsidian://adv-uri?vault=<your-vault>&filepath=<your-file>&commandid=workspace%3Aexport-pdf
```

A [documentação dele](https://publish.obsidian.md/advanced-uri-doc/Actions/Commands) distingue
`commandname` ("the one you see when searching in Obsidian's command palette") de `commandid`
("invisible to the user, but can be read from the plugin's source code"), e recomenda o ID:
*"using the command's ID is strongly recommended, because it's not likely to change"*. Aceita
combinar comando + arquivo + `line=`/`mode=`, e tem um parâmetro `confirm` que *"finds the first
main button and clicks it"*.

O resto do que ele abre, pelo README: escrever/append/prepend em arquivo, append **abaixo de um
cabeçalho específico**, busca-e-substitui com regex, abrir por alias ou por UID de frontmatter,
`openmode=silent`, abrir tela de configuração (`settingid`), checar se arquivo existe.

**O que isso custa**: sair do Restricted mode e instalar um plugin de terceiro — que, pela
documentação oficial de segurança, ganha acesso total (§4.4).

### 1.6 Quem chama a URI

- **Toast do Windows**: documentado pela Microsoft. O elemento `<action>` do toast aceita
  `activationType="protocol"`, descrito como *"Launch a different app using protocol activation"*,
  e o atributo `arguments` carrega a URI
  ([element-action](https://learn.microsoft.com/en-us/uwp/schemas/tiles/toastschema/element-action)).
  É o caminho documentado para o botão "abrir a daily" no toast. (O resto é ticket 02.)
- **Python**: `os.startfile` é descrito como *"Start a file with its associated application"* e
  embrulha o `ShellExecute` do Win32 — **a documentação do Python não diz que aceita URI**, e a
  página do `ShellExecuteW` descreve `lpFile` como "the file or object on which to execute the
  specified verb", também sem falar de URL. Funciona na prática; **não achei a frase oficial**.
  Está na §6 como teste.
- **Slack**: o campo `url` do botão do Block Kit é documentado como *"A URL to load in the user's
  browser when the button is clicked. Maximum length is 3000 characters."*
  ([Block Kit — button](https://docs.slack.dev/reference/block-kit/block-elements/button-element)).
  **A documentação não diz quais esquemas são aceitos** — não afirma `http`/`https` só, nem
  autoriza `obsidian://`. Isso é pergunta aberta do ticket 03, e tem um segundo problema que não
  depende de validação nenhuma: **a URI só abre o Obsidian na máquina onde o Obsidian está**. Do
  Slack do celular, um botão `obsidian://` não alcança o PC dele.

---

## 2. Nota-painel gerada pelo agente

### 2.1 Custa uma linha — confirmado no `vault.py`

Escrever qualquer arquivo numa pasta da zona do agente é **uma chamada**, sem código novo de
interface:

```python
vault.escrever(configuracao.vault, "daily/painel.md", conteudo, zonas=vault.ZONAS_DA_DAILY)
```

`escrever` (`src/whis/vault.py`) cria as pastas que faltarem, escreve UTF-8 e devolve o caminho. A
única regra é a zona: `relativo.parts[0]` tem que estar em `zonas`, e a checagem é refeita no
caminho **resolvido** (`..` não escapa). As zonas existentes são constantes do módulo:
`ZONAS_DE_ESCRITA = ("reunioes", "transcricoes")`, `ZONAS_DO_DIARIO = ("diario",)`,
`ZONAS_DA_DAILY = ("daily",)`, e `notas/` é recusada para todas.

`vault.wikilink(caminho)` já existe e devolve `[[daily/2026-09-08]]` a partir de
`daily/2026-09-08.md` — inclusive com o caminho, não só o nome, "porque nota e transcrição
compartilham o basename".

**A decisão que um painel força, e é a única**: em que zona ele mora. Um painel que aponta para
`daily/` + `diario/` + `reunioes/` não pertence a coletor nenhum. Ou ele entra numa zona existente
(`daily/painel.md`), ou nasce uma zona nova — o que é uma constante a mais em `vault.py` e um
`zonas=` a mais na chamada, não um módulo.

### 2.2 Um `daily/hoje.md` **não** quebra a âncora da janela — provado

Era o risco óbvio: a daily ancora a janela no campo `ate` da nota anterior, e um arquivo a mais na
pasta poderia confundir. Não confunde. `ate_da_daily_anterior` varre `pasta.glob("*.md")` e passa
cada nome por `_data_do_nome`, que faz `datetime.strptime(nome, "%Y-%m-%d")`. Executado aqui:

```
_data_do_nome('hoje')       -> None
_data_do_nome('painel')     -> None
_data_do_nome('2026-09-08') -> 2026-09-08
_momento_da_reuniao('painel') -> None
```

Nome fora do padrão vira `None` e é **pulado em silêncio** — o docstring diz que isso é de
propósito ("a daily não pode deixar de nascer por causa de um arquivo editado à mão"). O mesmo vale
para `reunioes_na_janela`, que exige o prefixo `YYYY-MM-DD-HHMM`. E um arquivo `.base` seria
invisível para os dois, que só olham `*.md`.

É exatamente a mesma prova que o ticket 09 já tinha feito para o `.html` ("A âncora sobrevive").

### 2.3 O que a nota-painel **não** resolve

- **Não aciona nada.** Um wikilink navega dentro do vault; um link `obsidian://` dentro da nota
  também só navega. Nada ali roda `whis daily`. Para o painel ter botão que *faz*, é plugin de
  terceiro (§4) ou plugin próprio (§4.4).
- **É um segundo artefato do mesmo dado** — a divergência que matou a página HTML (§5).
- **Ele precisa abrir o painel.** Se a nota-painel é o alvo do toast/atalho, a URI da §1 resolve;
  se depende de ele lembrar de abrir uma nota, é o mesmo problema de `notas/daily.md` ("depende de
  lembrar do arquivo", inventário 01).

### 2.4 Uma armadilha viva no vault dele, achada de passagem

A Daily notes do núcleo está **ligada** (`.obsidian/core-plugins.json`: `"daily-notes": true`) e
sem arquivo de configuração próprio — ou seja, no padrão. A página oficial diz: *"By default,
Obsidian creates a new empty note named after today's date in the YYYY-MM-DD format"*, na raiz do
vault. E diz mais:

> *"When the Daily notes plugin is activated and a date property is present within any note,
> Obsidian will automatically attempt to generate a link to the daily note for that specific day.
> For instance, if a note titled `example.md` includes a date property like `2023-01-01`, this date
> will transform into a clickable link in the live preview."*

**Toda nota que o Whis escreve tem `data:` no frontmatter** (`vault._frontmatter`, campo `data` em
reunião, transcrição, diário e daily) — e `_texto_yaml` deixa data sem aspas de propósito. Logo,
no Live Preview, esse campo vira **link clicável para uma daily note do Obsidian que não existe**,
e clicar cria `C:\Users\gabri\whis-vault\2026-09-08.md` vazio na raiz. Três nomes diferentes para a
mesma data: `daily/2026-09-08.md` (Daily do Whis), `diario/2026-09-03.md` (Diário) e um
`2026-09-08.md` solto na raiz (daily note do Obsidian). **Observação** — não cliquei em nada; a
regra é documentada e o plugin está ligado.

---

## 3. Entrada de dados pelo Obsidian

### 3.1 O que já existe

`notas/daily.md` (`vault.ARQUIVO_DE_PONTOS`) é o modelo funcionando: quatro seções de título
conhecido, itens `- [ ]`, e a regra de que **só o desmarcado entra na daily**. O parser é uma
regex de três linhas (`_ITEM_DESMARCADO`) e um dicionário de títulos aceitos (`_SECOES_DOS_PONTOS`,
que já aceita "dúvidas" e "duvidas", "off-topic" e "off topic"). A escrita é append-only
(`anotar_ponto`), e o arquivo nasce de `MODELO_DOS_PONTOS` com um callout `> [!tip]` explicando as
regras **dentro da nota**.

Duas propriedades desse desenho valem para qualquer outra "entrada por nota":

- **É tolerante.** Seção ausente, arquivo ausente, lista vazia: nada disso é erro.
- **O formato se explica sozinho, no lugar onde ele o edita.** Quem ensina o formato é o callout
  na própria nota, não a documentação.

E é o que ele de fato usa: os dois arquivos abertos no Obsidian agora são `notas/daily.md` e
`notas/Minha Daily.md` (**observação**, `.obsidian/workspace.json`).

### 3.2 O que mais poderia ser escrito numa nota

Cruzando o `MODELO_DE_CONFIGURACAO` (`src/whis/__main__.py:659`) com o que é texto e o que é
segredo:

| chave | cabe numa nota? | por quê |
|---|---|---|
| `[privacidade].pastas_privadas` | texto | lista de pastas do vault — §3.4 tem o porém |
| `[privacidade].excluir` | texto | substrings que nunca saem da máquina |
| `[daily].referencias_pessoais` | texto | repos e canais dele |
| `[daily].contexto_do_time` | **texto livre, o caso mais forte** | vai cru no prompt do roteiro (`resumo_dia_claude._prompt`); é prosa, e prosa em TOML de uma linha é ruim |
| `[slack].conversas_excluidas`, `so_com_mencao` | texto | listas de canais |
| `[busca].maximo_de_notas`, `[diario].inicio_do_dia`, `retencao_dias` | número/hora | validados hoje com mensagem de erro decente |
| `vault`, `gravacoes`, `[git].raiz` | caminhos | ovo e galinha: para ler a nota é preciso saber onde é o vault |
| `[deepgram].api_key`, `[linear].api_key`, `[slack].*_token` | **não** | §3.5 |

O `contexto_do_time` é o que mais quer uma nota: é o único campo que é redação, é o que ele mais
vai reescrever, e é o que muda o roteiro da daily diretamente.

### 3.3 Que formato os dois lados leem

Três candidatos, com o que a documentação oficial diz de cada um.

**(a) Frontmatter YAML (Properties).** É o formato nativo. A
[página de Properties](https://obsidian.md/help/properties) dá a UI (linha de nome/valor no topo,
`Cmd/Ctrl+;` para adicionar) e seis tipos: Text, List, Number, Checkbox, Date, Date & time, Tags.
Quatro armadilhas, todas documentadas na mesma página:

1. *"Once a property type is assigned to a property name, all properties with that name across your
   vault will use the same type."* O tipo é **do vault inteiro**. Se a nota de configuração usar um
   nome que o Whis já escreve — `fontes`, `temas`, `data`, `janela` —, o tipo colide com as notas
   geradas.
2. *"**Nested properties**: To view nested properties, we recommend using the source mode"* — não
   suportado na UI. Ou seja, a estrutura de seções do TOML (`[slack].conversas_excluidas`) **não
   tem equivalente editável**: vira `slack_conversas_excluidas` chato, ou vira YAML aninhado que a
   UI não mostra.
3. *"**Markdown in properties**: This is an intentional limitation"* — nada de link, nada de
   ênfase, e nada de texto longo confortável. Isso desqualifica frontmatter para
   `contexto_do_time`, que é justamente prosa.
4. **Settings → Editor → "Properties in document"** tem três modos: *Visible* (padrão), *Hidden* e
   *Source*. Em **Hidden**, o frontmatter some da nota — a configuração ficaria invisível
   exatamente para quem "não achou o arquivo".

**(b) Lista de checkbox, como `notas/daily.md` já faz.** Prova de que funciona: está em produção.
Serve bem para listas de ligar/desligar (canais excluídos, pastas privadas, referências pessoais),
e o checkbox dá um estado a mais de graça. Não serve para valor com nome (`inicio_do_dia = "04:00"`)
sem inventar convenção de `chave: valor` dentro do item.

**(c) Code block dentro do corpo da nota** (```` ```toml ````). É o único que não tem editor
próprio no Obsidian: a UI de Properties só mexe no frontmatter, e o corpo é texto. Ele **vê** o
bloco com syntax highlight e o Whis lê o mesmo TOML que já sabe ler — `tomllib.loads` no trecho
entre as cercas, com as mesmas mensagens de erro de hoje (inclusive `_dica_de_barra_invertida`).
Custo: um extrator de cerca, umas dez linhas. O que ele perde é a edição guiada — é texto solto, e
errar a sintaxe é tão fácil quanto no arquivo original.

### 3.4 A pergunta que o ticket faz e que tem resposta ruim: "uma pasta privada **dentro** do vault é lida por quem?"

`[privacidade].pastas_privadas` é validada para apontar **para dentro do vault**
(`configuracao._pastas_privadas` recusa caminho absoluto e `..`, com a justificativa escrita ali:
"uma pasta privada que não protege nada é pior do que nenhuma"). E `ferramentas.Ferramentas` cumpre
isso à risca: recusa igual para "fora do vault", "sob pasta privada" e "não existe", de propósito,
porque "dizer 'isso é privado' já contaria que há algo escondido".

**Mas o escudo é do Whis, e só do Whis.** A pasta continua sendo uma pasta comum dentro do vault:

- **O Obsidian a indexa e a busca dele acha.** O ajuste que chega mais perto de esconder,
  *Settings → Files and links → Excluded files*, faz só isso, e a doc é explícita: os arquivos
  *"will be hidden in Search, Graph View, and Unlinked Mentions (Backlinks and Outgoing links), and
  less noticeable in Quick Switcher and link suggestions"*. **Continuam no explorador de arquivos e
  continuam abrindo.** Não existe pasta privada de verdade no Obsidian.
- **Qualquer plugin comunitário lê.** A página oficial de
  [Plugin security](https://obsidian.md/help/plugin-security) não deixa margem: *"Due to technical
  limitations, Obsidian cannot reliably restrict plugins to specific permissions or access levels.
  This means that plugins will inherit Obsidian's access levels."* E lista: *"Community plugins can
  access files on your computer. Community plugins can connect to internet. Community plugins can
  install additional programs."*
- **E, se a configuração morar numa nota do vault, a nota vira o índice do que está escondido.**
  `ferramentas.buscar_no_vault` varre **todas** as notas fora das pastas privadas. Uma nota que diz
  "a pasta privada é `notas/pessoal`" está fora da pasta privada — logo é pesquisável, logo o
  agente pode lê-la e citá-la numa resposta na DM. O conteúdo continua protegido; **a existência e
  o nome, não.** Hoje, com a configuração em `%APPDATA%`, esse índice está fora do alcance das
  ferramentas do agente por construção.

### 3.5 O que não pode ir para nota nenhuma

`config.toml` guarda `deepgram.api_key`, `linear.api_key`, `slack.user_token`, `slack.bot_token` e
`slack.app_token`. O docstring de `configuracao.py` diz o porquê de onde ele mora: *"Nenhum segredo
mora no repositório: as chaves da Deepgram, do Linear e do Slack vivem só neste arquivo, que está
no `.gitignore`."*

Um vault não tem `.gitignore`, tem três coisas piores: é uma pasta que ele abre no explorador, é
sincronizável (o `core-plugins.json` lista `"sync": true` — **mas não há arquivo de configuração de
Sync em `.obsidian/`, então se ele tem assinatura ativa é pergunta para ele**), e é lida por
qualquer plugin comunitário que um dia entre. **Uma configuração por nota, se acontecer, é
configuração partida em duas**: texto na nota, segredo no `config.toml`. Isso é um fato de custo,
não uma objeção — mas é o fato que decide se "acabar com o `config.toml`" está mesmo em cima da
mesa, ou se o que está em cima da mesa é "não precisar abrir o `config.toml` no dia a dia".

### 3.6 Um detalhe de formato que fecha a porta do "`config.toml` dentro do vault"

A saída preguiçosa — deixar o próprio `config.toml` dentro da pasta do vault, para ele achar pelo
explorador do Obsidian — não funciona como interface: a
[lista oficial de formatos aceitos](https://obsidian.md/help/file-formats) é `.md`, `.base`,
`.canvas`, imagens, áudio, vídeo e `.pdf`. **`.toml` não aparece no explorador do Obsidian e não
abre nele.** O arquivo ficaria lá, invisível, resolvendo nada.

---

## 4. Plugins

### 4.1 O que ele tem hoje — **observação**, e a pergunta continua sendo dele

Lido em `C:\Users\gabri\whis-vault\.obsidian\` (**observação**; o ticket 05 confirma com ele):

- **Não existe a pasta `.obsidian/plugins/`** e não existe `community-plugins.json`. Nos dois casos
  o Obsidian criaria o arquivo/pasta ao instalar ou ao sair do Restricted mode. A leitura mais
  provável é **nenhum plugin comunitário instalado neste vault, Restricted mode ligado** — mas
  isto é inferência sobre ausência de arquivo, não confirmação. **Ele pode ter plugins em outro
  vault**, e tem outros dois (§1.2): plugin é por vault, não por instalação.
- `core-plugins.json` mostra ligados, entre outros: `bases`, `daily-notes`, `templates`,
  `properties`, `global-search`, `bookmarks`, `canvas`, `sync`, `command-palette`. Desligados:
  `slides`, `audio-recorder`, `workspaces`, `webviewer`, `zk-prefixer`, `slash-command`,
  `markdown-importer`, `random-note`, `publish`, `footnotes`.
- `app.json`: `newFileLocation: "folder"`, `newFileFolderPath: "notas"`, `newLinkFormat:
  "absolute"` — as três opções de *Arquivos & Links* que o ticket 09 registra que ele configurou
  em 04/09. **Nota nova nasce em `notas/`**, a zona dele. Isso importa para `obsidian://new?name=`,
  que usa exatamente essa preferência.

### 4.2 O que já vem de fábrica e cobre parte do que se pediria a plugin

**Bases** é plugin **de núcleo** e está ligado. A doc oficial: *"Bases is a core plugin that lets
you create database-like views of your notes. Using a base you can view, edit, sort, and filter
files and their properties"*, e *"All the data in Obsidian Bases is stored in your local Markdown
files and their properties"*. As views são Table, List, Cards, Kanban e Map, e podem ser *"saved as
a `.base` file or embedded in code blocks within your Markdown files"*
([Bases](https://obsidian.md/help/bases)).

Isso muda o custo do painel: **a tabela "minhas dailies, com temas e fontes, ordenada por data" não
precisa de plugin nenhum**, porque o Whis já escreve o frontmatter de que ela precisa —
`tipo`, `data`, `desde`, `ate`, `fontes`, `fontes_com_falha`, `temas`, `reunioes` na daily;
`tipo`, `data`, `janela`, `fontes`, `temas`, `reunioes` no diário; `tipo`, `data`, `participantes`
na reunião. Um `.base` (ou um bloco embutido numa nota) é escrito por `vault.escrever` como
qualquer outro arquivo.

**Templates** (núcleo) também está ligado, mas é inserção de texto com `{{date}}` — não roda nada.

### 4.3 Dataview, Templater e Buttons — o que cada um daria de graça

Todos os três são **comunitários** (terceiros), e nenhum está instalado neste vault (§4.1).

**Dataview** — [blacksmithgu/obsidian-dataview](https://github.com/blacksmithgu/obsidian-dataview),
`manifest.json`: id `dataview`, autor "Michael Brenan", `isDesktopOnly: false`. README: *"Treat your
Obsidian Vault as a database which you can query from. Provides a JavaScript API and pipeline-based
query language."* Um bloco ```` ```dataview ```` no painel faria tabela/lista/`task` sobre o
frontmatter e sobre as tarefas `- [ ]` — inclusive listar os itens desmarcados de `notas/daily.md`
em qualquer nota. **Só mostra; não aciona.** Observação de manutenção, da API do GitHub: último
push em **2025-11-17** (~10 meses atrás), enquanto o Bases entrou no núcleo — quem escolher
Dataview hoje escolhe um plugin parado para fazer o que um plugin de núcleo faz.

**Templater** — [SilentVoid13/Templater](https://github.com/SilentVoid13/Templater), id
`templater-obsidian`, v2.25.0, `isDesktopOnly: false`. É **o único dos três que consegue executar
alguma coisa fora do Obsidian**, e isso é documentado:

> *"System Command User Functions — This type of user functions allows you to execute system
> commands and retrieve their output. System command user functions need to be enabled in
> Templater's settings."*
> ([docs/src/user-functions/system-user-functions.md](https://github.com/SilentVoid13/Templater/blob/master/docs/src/user-functions/system-user-functions.md))

Define-se um nome associado a um comando, chama-se `<% tp.user.nome() %>` na nota, e a **saída do
comando entra na nota**. Argumentos viram variáveis de ambiente. Isto é, literalmente, "rodar
`whis daily` a partir de uma nota". Três limites, todos da doc oficial do plugin:

- **`Timeout`: "Maximum timeout in seconds for a system command. Defaults to 5."**
  ([settings](https://github.com/SilentVoid13/Templater/blob/master/docs/src/settings.md)) — `whis
  daily` chama o Claude e as fontes; cinco segundos não chegam perto. É configurável, mas é o
  padrão com que ele começaria.
- *"Currently user functions are unavailable on Obsidian for mobile."* — some no celular.
- O próprio README abre um `## Warning`: *"Templater allows you to execute arbitrary JavaScript
  code and system commands. It can be dangerous to execute arbitrary JavaScript code or system
  commands from untrusted sources."*

E **Template Hotkeys** fecha o laço com um botão: *"Template Hotkeys allows you to bind a template
to a command, and then bind that command to a hotkey"* — o template vira comando da paleta.

**Buttons** — [shabegom/buttons](https://github.com/shabegom/buttons), id `buttons`, autor
"shabegom", v0.9.13, `isDesktopOnly: false`. O README lista os tipos: **Command** ("Click the Button
to run a Command from the Command Palette"), **Link** ("Click the Button to open a URL or URI"),
Calculate, Template, Text, Swap, Chain. Tem botão inline e `Button Maker` na paleta.

Combinando os três, **sem uma linha de TypeScript**, o painel com botão existe:

```
Buttons (Command) -> comando registrado pelo Template Hotkeys do Templater
                  -> template com <% tp.user.whis_daily() %>
                  -> System Command User Function roda `whis daily`
Buttons (Link)    -> obsidian://open?vault=whis-vault&file=daily%2F2026-09-10
```

O preço: **dois plugins de terceiro, Restricted mode desligado, e o acesso total da §4.4** — mais
o timeout de 5 s para acertar e o fato de que nada disso existe no celular.

### 4.4 Plugin próprio: o custo real

**Linguagem e build**, do repositório oficial
[obsidianmd/obsidian-sample-plugin](https://github.com/obsidianmd/obsidian-sample-plugin):
README — *"This project uses TypeScript to provide type checking and documentation. The repo
depends on the latest plugin API (obsidian.d.ts) in TypeScript Definition format"*; e
*"Make sure your NodeJS is at least v18"*, `npm i`, `npm run dev`. O `package.json` do sample traz
**esbuild, eslint, typescript-eslint, obsidian, @types/node, globals, jiti** — a stack inteira que
o ADR 0001 ("projeto fino, 100% local") não tem hoje. A doc de desenvolvimento repete os
pré-requisitos: *"Git installed on your local machine"*, *"A local development environment for
Node.js"*, *"A code editor, such as Visual Studio Code"*
([Build a plugin](https://docs.obsidian.md/Plugins/Getting+started/Build+a+plugin)).

**Como se instala num vault** — e aqui a notícia é boa, não precisa publicar nada: o README oficial
diz *"Copy over `main.js`, `styles.css`, `manifest.json` to your vault
`VaultFolder/.obsidian/plugins/your-plugin-id/`"*. Ou seja, três arquivos numa pasta. Depois,
Settings → Community plugins → **Turn on community plugins** (sair do Restricted mode) → habilitar
na lista. O `manifest.json` mínimo é `id`, `name`, `version`, `minAppVersion`, `author`,
`description`, `isDesktopOnly` ([Manifest](https://docs.obsidian.md/Reference/Manifest)). Depois de
cada build: comando *"Reload app without saving"*, ou desabilita-e-habilita.

**Ele consegue falar com um processo Python local? Sim, e a própria documentação oficial admite o
mecanismo** — o campo `isDesktopOnly` é descrito como *"Whether the plugin can only be used on the
desktop app, for example because it uses NodeJS or Electron APIs"*. Plugin de desktop é código
Node dentro do Electron: `child_process` para chamar `whis daily`, ou HTTP para um servidor local.
Para HTTP a API oficial tem `requestUrl`, documentado como *"request a URL using HTTP/HTTPS,
without any CORS restrictions"*
([requestUrl](https://docs.obsidian.md/Reference/TypeScript+API/requestUrl)) — o que resolveria o
CORS de falar com um `localhost` do Whis.

**O que o plugin próprio compra que o resto não compra**: botão nativo na interface, sem depender
de dois plugins de terceiro; um painel que atualiza sozinho; e um caminho de volta (o plugin
mostra o erro dentro do Obsidian — o único lugar que ele tem aberto o dia inteiro e que, ao
contrário da bandeja e do atendente, não morre calado, research 01 §4).

**O que ele custa além do build**: um segundo projeto, em outra linguagem, com outro ciclo de
release (`versions.json`, tag do GitHub, `minAppVersion`), e mais um lugar onde a regra de negócio
pode divergir do Python. E, se o objetivo é só rodar comando, ele **não dá nada que o par
Templater+Buttons já não dê** — o que ele dá é não ter dois plugins de terceiro lendo o vault.

**O preço comum a todos os caminhos com plugin**, oficial e sem meio-termo
([Plugin security](https://obsidian.md/help/plugin-security)): sair do Restricted mode —
*"By default, Obsidian runs in Restricted Mode to prevent third-party code execution. Only disable
Restricted mode if you trust the authors of the plugins that you install"* — e aceitar que
*"plugins will inherit Obsidian's access levels"*. Vale igual para o plugin próprio: o Restricted
mode é global do vault, não por plugin. Habilitar um plugin próprio **abre a porta para instalar
qualquer outro**. Para um vault que guarda transcrição de reunião de trabalho e tem uma pasta
"privada" (§3.4), isso é a decisão, não um detalhe.

---

## 5. O precedente contra: a página HTML da daily

Ticket [`09-a-daily-como-pagina.md`](../../fontes-passivas/issues/09-a-daily-como-pagina.md),
status `wontfix` — **construída, usada por um dia e revertida no mesmo dia** (2026-09-04), commit
`9a53218`.

**O que foi construído e funcionava**: `daily/YYYY-MM-DD.html` ao lado da nota, mesma zona, mesma
execução; roteiro em corpo grande no topo; listas cruas em `<details>` recolhidos com contagem;
autossuficiente (CSS embutido, nada da rede); escape de tudo que vem de fora; claro e escuro. 28
testes, suíte em 614 verdes, página real de 243 KB gerada e conferida no navegador.

**A lição exata, na frase do ticket**:

> *"A página existia para resolver 'o markdown é feio de ler', e essa premissa caiu. O Obsidian
> renderiza a mesma nota com tipografia boa, links clicáveis e cabeçalho recolhível — que era
> exatamente o que os `<details>` da página davam."*

E a fala do usuário que a derrubou, no mesmo dia em que ele abriu o vault no Obsidian pela primeira
vez e configurou as três opções de Arquivos & Links: *"acho que o html se torna desnecessário agora
como a opção de ver pelo obsidian o que é bem mais bonito"*.

**Por que ela perdeu a razão de existir**, decomposto como o ticket decompõe:

1. **A premissa era sobre a leitura, e outra superfície já resolvia a leitura.** O que sobrava de
   vantagem era marginal — corpo maior (o Obsidian tem zoom) e abrir sem o Obsidian (ele está
   sempre aberto).
2. **O custo era real e recorrente**: "240 KB por dia de arquivo que ninguém abriria, um módulo e
   28 testes para manter, e um segundo artefato podendo divergir da nota".
3. **O markdown não era o problema, era o ativo.** A nota é "o registro durável do vault", é o que
   a entrega seguinte lê e é o que o Obsidian indexa — "trocar markdown por HTML mataria as três
   coisas para resolver um problema de leitura".

**O que sobreviveu, e é o formato da lição**: `vault.agrupar_por_referencia`, extraída para a
página não duplicar a regra do contrato, **devolve dados em vez de markdown** e continua sendo usada
pelo construtor da nota. A parte da página que era desenho morreu; a parte que era separação de
regra e formato ficou.

**Como isso cai neste ticket, sem decidir nada:**

- O precedente **favorece** o Obsidian como superfície: foi exatamente ele que tornou a página
  desnecessária, e é a origem da lição do mapa ("não invente superfície nova onde uma que ele já
  usa serve").
- O precedente **acusa** a nota-painel da §2 pelo mesmo crime da página: é um segundo artefato do
  mesmo dado, escrito na mesma zona, que pode divergir do primeiro. A diferença é de grau — uma
  nota de wikilinks custa pouco mais que zero, a página custava um módulo e 28 testes —, mas a
  pergunta de teste é a mesma que derrubou a página: **qual premissa a nota-painel resolve, e essa
  premissa está de pé?**
- E dá um critério pronto: **o que valeu a pena da página não foi o artefato, foi a refatoração
  que ela forçou.**

---

## 6. O que eu **não** consegui confirmar

Em ordem de quanto atrapalha a decisão.

**6.1 O que acontece com o Obsidian fechado.** Provei que o Windows lança o `Obsidian.exe` com a
URI (§1.3); **não provei** que ele cai na nota certa ao subir do zero. Não testei porque abrir o
app escreve em `.obsidian/workspace.json`, dentro do vault dele. Teste, por ele, com o Obsidian
fechado:

```powershell
Start-Process "obsidian://open?vault=whis-vault&file=daily%2F2026-09-08"
```

E o mesmo com o app aberto, para comparar. Se abrir só o vault e não a nota, a URI ainda serve para
o botão — mas o botão passa a ser "abre o Obsidian", não "abre a daily".

**6.2 Se `os.startfile` aceita uma URI.** Nem a doc do Python nem a do `ShellExecuteW` mencionam
URL. Teste: `python -c "import os; os.startfile('obsidian://open?vault=whis-vault')"`. Se não
funcionar, a alternativa é `subprocess.run(["cmd","/c","start","",uri])`.

**6.3 Se o Slack aceita `obsidian://` no `url` de um botão do Block Kit.** A doc só diz "A URL to
load in the user's browser". Não achei declaração de esquemas permitidos nem de recusa. Só um teste
com um bloco real responde (ticket 03) — e mesmo que aceite, o botão não faz nada no celular.

**6.4 Quais plugins o usuário já tem.** Isto é **pergunta para ele** (ticket 05), não adivinhação.
O que observei: este vault não tem `.obsidian/plugins/` nem `community-plugins.json`, o que
*sugere* nenhum plugin comunitário e Restricted mode ligado. É observação de ausência de arquivo,
não confirmação — e ele tem outros dois vaults na máquina, onde a resposta pode ser outra.

**6.5 Se o Obsidian reescreve o frontmatter ao editá-lo pela UI de Properties.** A doc documenta
tipos, colisão de tipo por nome e ausência de propriedades aninhadas, mas **não** descreve o que o
editor faz com aspas, ordem de chaves e formatação ao salvar. Importa se a configuração for
frontmatter: o Whis escreveria um formato e a UI poderia devolver outro.

**6.6 Se ele tem Obsidian Sync ativo.** `core-plugins.json` lista `"sync": true`, mas não há
arquivo de configuração de Sync em `.obsidian/`. Se tiver, tudo que for escrito no vault —
configuração, pasta "privada", segredo — sai da máquina. Pergunta para ele.

**6.7 O comportamento de `prepend`/`append` na ação `open`.** A doc lista os dois parâmetros mas
não documenta de onde vem o conteúdo (não há `content`/`data` listado em `open`, só em `new`).
Não testei.

**6.8 Obsidian no celular.** Não verifiquei se ele tem, nem se `obsidian://` funciona lá. Se
tivesse e o vault estivesse sincronizado, mudaria a conta da DM do Slack versus Obsidian.

---

## 7. Fatos soltos, verificados, que os próximos tickets herdam

- **`.md` não tem programa associado nesta máquina.** `assoc .md` responde "Associação de arquivo
  não encontrada"; `HKCU\...\FileExts\.md` não tem `UserChoice`; `HKCU\SOFTWARE\Classes\.md` só tem
  `OpenWithProgids` (`VSCode.md` e um AppX) e nenhum valor padrão; a `OpenWithList` do Explorer é
  `chrome.exe`, `claude.exe`, `Code.exe`. **O Obsidian não está na lista.**
  Consequência direta: `bandeja.abrir_no_windows` usa `os.startfile(caminho)`, e o item de menu
  ***"Abrir a última nota" não abre o Obsidian hoje*** — no melhor caso mostra o diálogo "Como você
  quer abrir este arquivo?", no pior devolve `SE_ERR_NOASSOC` e o código só loga um erro. Trocar
  esse `os.startfile(caminho)` por uma URI `obsidian://` conserta um gesto que já existe no
  inventário. (**Verificado no registro; observação quanto a ser a vista do usuário.**)
- **`obsidian://` está registrado em `HKCU`, não em `HKLM`** — é instalação por usuário
  (`%LOCALAPPDATA%\Programs\Obsidian\Obsidian.exe`). Uma tarefa agendada rodando como outro usuário
  não teria o protocolo.
- **`vault.escrever` não olha extensão** — `daily/painel.base` e `daily/painel.canvas` passam pela
  mesma checagem de zona que `.md`. E `ate_da_daily_anterior`/`reunioes_na_janela` só varrem
  `*.md`, então arquivo de outra extensão é invisível para eles.
- **`app.json` diz `newFileFolderPath: "notas"`** — toda nota nova nasce na zona do usuário. Vale
  para `obsidian://new?name=...` e para qualquer botão de "criar nota".
- **A Daily notes do núcleo está ligada e transforma o campo `data:` de toda nota do Whis em link
  para uma daily note inexistente na raiz** (§2.4). Clicar cria lixo na raiz do vault.
- **Os dois arquivos abertos no Obsidian dele agora são `notas/daily.md` e `notas/Minha Daily.md`**,
  e o `lastOpenFiles` passa por `notas/`, `daily/`, `diario/`, `reunioes/`, `transcricoes/` — ele lê
  o vault inteiro, e mora na zona dele. (**Observação**, `.obsidian/workspace.json`.)
- **Existe um `Pasted image 20260908143924.png` na raiz do vault** — ele colou imagem numa nota. É
  uso real do Obsidian como ferramenta, não só como visualizador.

---

## Fontes

**Obsidian, documentação oficial** (help): [Obsidian URI](https://obsidian.md/help/uri) ·
[Plugin security](https://obsidian.md/help/plugin-security) ·
[Community plugins](https://obsidian.md/help/community-plugins) ·
[Properties](https://obsidian.md/help/properties) ·
[Accepted file formats](https://obsidian.md/help/file-formats) ·
[Introduction to Bases](https://obsidian.md/help/bases) ·
[Daily notes](https://obsidian.md/help/plugins/daily-notes) ·
[Search](https://obsidian.md/help/plugins/search) ·
[Settings — Excluded files](https://obsidian.md/help/settings)

**Obsidian, documentação de desenvolvedor**: [docs.obsidian.md](https://docs.obsidian.md/Home) ·
[Build a plugin](https://docs.obsidian.md/Plugins/Getting+started/Build+a+plugin) ·
[Manifest](https://docs.obsidian.md/Reference/Manifest) ·
[requestUrl](https://docs.obsidian.md/Reference/TypeScript+API/requestUrl) ·
[obsidianmd/obsidian-sample-plugin](https://github.com/obsidianmd/obsidian-sample-plugin)

**Fórum oficial** (relato, não documentação):
[Starting obsidian from command line with URI "...open?path=..." is not working under Windows](https://forum.obsidian.md/t/starting-obsidian-from-command-line-with-uri-open-path-is-not-working-under-windows/107025)

**Plugins de terceiro**:
[Vinzent03/obsidian-advanced-uri](https://github.com/Vinzent03/obsidian-advanced-uri) +
[documentação](https://publish.obsidian.md/advanced-uri-doc) ·
[blacksmithgu/obsidian-dataview](https://github.com/blacksmithgu/obsidian-dataview) ·
[SilentVoid13/Templater](https://github.com/SilentVoid13/Templater)
([system user functions](https://github.com/SilentVoid13/Templater/blob/master/docs/src/user-functions/system-user-functions.md),
[settings](https://github.com/SilentVoid13/Templater/blob/master/docs/src/settings.md)) ·
[shabegom/buttons](https://github.com/shabegom/buttons)

**Microsoft / Python**:
[toast `<action>` element](https://learn.microsoft.com/en-us/uwp/schemas/tiles/toastschema/element-action) ·
[ShellExecuteW](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecutew) ·
[os.startfile](https://docs.python.org/3/library/os.html#os.startfile) ·
[Block Kit — button element](https://docs.slack.dev/reference/block-kit/block-elements/button-element)

**Repositório e máquina**: `src/whis/vault.py` · `src/whis/configuracao.py` ·
`src/whis/ferramentas.py` · `src/whis/__main__.py` (`MODELO_DE_CONFIGURACAO`, l. 659) ·
`src/whis/gravador.py` (`criar_slug`) · `src/whis/bandeja.py` (`abrir_no_windows`) ·
`.scratch/fontes-passivas/issues/09-a-daily-como-pagina.md` ·
`C:\Users\gabri\AppData\Roaming\obsidian\obsidian.json` ·
`C:\Users\gabri\whis-vault\.obsidian\{app,appearance,core-plugins,workspace}.json` ·
`HKCU:\SOFTWARE\Classes\obsidian` · `HKCU:\SOFTWARE\Classes\.md`

# Uma janela local com atalho global: plugin de launcher ou janela nossa

Levantado em 2026-09-12 contra fontes primárias — documentação e código-fonte oficial de cada
projeto, docs da Microsoft para as APIs do Windows, e a máquina do usuário (venv do projeto,
`pywin32` e `pystray` instalados).

A pergunta que originou isto, dele: *"seria mt mais complexo fazer um app mesmo que abre por
comando tipo um raycast?"* — um launcher com atalho global de teclado, campo de texto e comandos.

Os gestos que essa superfície precisaria cobrir: gerar a daily agora, abrir a daily, anotar um
ponto, perguntar ao vault (**~60 s de espera**, US$ 0,56) e **configurar as 24 chaves do
`config.toml`, cinco delas segredos** — e o valor de um segredo tem que ir do teclado dele para o
arquivo sem passar por modelo nenhum.

**Isto é levantamento, não decisão.** Onde há trade-off, os dois lados estão com o custo.

---

## Resumo dos achados que mudam a decisão

1. **O atalho global custa zero dependência nova.** `RegisterHotKey` do `user32` está exposto no
   `pywin32` **que já está instalado** nesta venv (verificado: `win32gui.RegisterHotKey` existe),
   e a documentação da Microsoft não menciona privilégio de administrador em requisito nenhum. O
   que ele exige é um *message loop* — não um console —, então `pythonw.exe` não é obstáculo em
   tese.
2. **O plugin de launcher nunca é o Whis rodando: é sempre um cliente fino.** Todos os launchers
   com suporte a Python embutem **o interpretador deles**, não o nosso — o Flow Launcher baixa um
   *embeddable* **3.11.4**, o Keypirinha embute um **3.5.0**. Nossa venv é 3.12 com
   `claude-agent-sdk`, `PyAudioWPatch` e `slack_sdk`. Qualquer plugin acaba fazendo `subprocess`
   para `.venv\Scripts\python.exe -m whis ...`. Isso muda a conta: o launcher entrega a *caixa de
   texto*, não a execução.
3. **E entrega mal a espera de 60 s.** O Flow Launcher **abre um processo novo por consulta** e o
   mata pelo *cancellation token* (`JsonRPCPlugin.cs`). Uma resposta que leva um minuto não tem
   onde aparecer dentro do launcher: teria que ser despachada para o nosso processo e voltar por
   outro caminho (balão, DM, Obsidian).
4. **A exceção que surpreende: o Flow Launcher tem, sim, formulário de configuração — com campo de
   senha.** `SettingsTemplate.yaml` suporta oito controles, entre eles `passwordBox`, `textarea`,
   `dropdown` e `checkbox`. Mas o valor é gravado **no armazenamento de settings do Flow**, não no
   nosso `config.toml` — os segredos passariam a existir em dois lugares.
5. **PowerToys Run está fora: plugin é só C#** (`"Language": "csharp"`, alvo
   `net10.0-windows10.0.22621.0`) — e a própria Microsoft já anuncia o sucessor, o **Command
   Palette**, cujas extensões também são **C# + WinUI + MSIX + modo desenvolvedor**.
6. **Janela sem borda no centro da tela é barato em Tkinter e não custa dependência**:
   `wm overrideredirect` + `wm geometry` + `wm attributes -topmost` são do Tk 8.6, e o `tkinter`
   **já importa nesta venv** (`TkVersion 8.6`). Campo de segredo também é nativo: `entry -show`.
7. **O conflito de main loop tem saída documentada, e ela é do lado do `pystray`.** O `pystray`
   diz que `run()` "must be called from the main thread", mas o backend Windows implementa
   `_run_detached` como `threading.Thread(target=lambda: self._run()).start()` — no código
   instalado, 0.19.5. Ou seja: **Tk no thread principal, bandeja num thread secundário** é o
   arranjo que a própria biblioteca prevê. Não foi testado nesta máquina.
8. **O que é caro não é o Raycast — é gravar o `config.toml` de volta.** O projeto lê TOML com
   `tomllib`, que é **somente leitura** por definição da stdlib, e não tem nenhum escritor de TOML
   entre as dependências. Salvar o formulário significa ou regenerar o arquivo a partir do
   `MODELO_DE_CONFIGURACAO` (perdendo o que o usuário escreveu à mão) ou uma dependência nova
   (`tomlkit`/`tomli-w`).

---

## 1. Plugin de um launcher que já existe

### 1.0 O fato que vale para os quatro, e vem antes de qualquer comparação

Um plugin de launcher roda **dentro do processo (ou do interpretador) do launcher**, não dentro da
nossa venv. Consequência prática, e ela não depende de qual launcher se escolhe:

- o plugin **não consegue** `import whis` — teria que empurrar nosso `src/` no `sys.path` e ainda
  assim faltariam `claude-agent-sdk`, `slack_sdk`, `httpx`, `PyAudioWPatch`;
- o caminho real é o plugin virar **três linhas de `subprocess`** chamando
  `.venv\Scripts\python.exe -m whis <subcomando>` — que é exatamente o que o projeto já faz para
  criar `.lnk` por PowerShell;
- logo, **o launcher entrega o gesto de invocar e o campo de texto**; não entrega execução, nem
  espera longa, nem escrita no nosso arquivo de configuração.

### 1.1 Flow Launcher — o único com Python de verdade

**Linguagem.** O `plugin.json` declara o campo `Language`, e a documentação lista, textualmente:
*"Available fields are csharp, fsharp, python, javascript, typescript and executable"*
([plugin.json][fl-pluginjson]). Para Python, `ExecuteFileName` é `main.py`.

**Qual Python.** Não o nosso. A documentação diz que os usuários *"will most likely be using Flow
Launcher's download of Embedded Python"* ([py-develop-plugins][fl-pydev]), e o código-fonte fixa a
versão: o caminho de instalação é `PythonEmbeddable-v3.11.4` e o executável resolvido é
`Path.Combine(InstallPath, "pythonw.exe")` ([PythonEnvironment.cs][fl-pyenv]). Dependências do
plugin vão numa pasta `lib/` empacotada no zip, prependada ao `sys.path` pelo próprio `main.py`
([py-setup-project][fl-pysetup]).

**Texto longo? Sim — como *entrada*.** O `query()` recebe o texto livre inteiro que o usuário
digitou e devolve uma lista de resultados (`title`, `subTitle`, `icoPath`, `jsonRPCAction`,
`score`) ([py-write-code][fl-pywrite]). Então *"pergunte ao vault: por que a migration quebrou"*
chega ao plugin sem problema.

**Mas a resposta de 60 s não cabe.** `JsonRPCPlugin` executa cada consulta com `Process.Start`,
espera com `WaitForExitAsync(token)` e faz `process.Kill()` quando o token cancela
([JsonRPCPlugin.cs][fl-jsonrpc]) — **um processo novo por consulta, sem processo persistente**.
Não há onde renderizar "estou pensando há 40 segundos" dentro do launcher. O padrão viável é:
o plugin dispara o nosso processo e devolve na hora *"perguntando…"*; a resposta chega por outra
superfície.

**Formulário de configuração: existe, e é melhor do que eu esperava.** O `SettingsTemplate.yaml`
define a página de settings do plugin, com oito tipos de controle — `textBlock`, `input`,
`inputWithFileBtn`, `inputWithFolderBtn`, `textarea`, `passwordBox`, `dropdown`, `checkbox`
([json-rpc-settings][fl-settings]). Isso cobre, no papel, quase tudo o que as 24 chaves pedem:
`passwordBox` para os cinco segredos, `inputWithFolderBtn` para vault/gravações/`git.raiz`,
`textarea` para as sete listas, `checkbox`/`dropdown` para o resto.

**O preço disso, que é o que decide:** o valor vai para a configuração **do Flow**, não para o
nosso `config.toml`. O plugin teria que ler dali e reescrever o nosso arquivo — ou seja, o
problema de escrever TOML (§4) continua inteiro, e agora os segredos existem duplicados, num
arquivo de terceiro que não está sob o `[privacidade]` do projeto.

**Distribuição.** O caminho documentado é GitHub Releases + o repositório de manifesto da loja
([py-release-project][fl-pyrelease]). A pasta de plugins na máquina é
`%APPDATA%\FlowLauncher\Plugins` (de `DataLocation.cs`: `RoamingDataPath` = `ApplicationData` +
`"FlowLauncher"`, e `PluginsDirectory` = `DataDirectory()` + `Plugins`) ([DataLocation.cs][fl-data]).
**Não confirmado:** se existe um comando documentado para instalar um zip local/privado sem passar
pela loja — a rota óbvia é copiar a pasta, mas não achei isso escrito na documentação oficial.

### 1.2 PowerToys Run — só C#, e com sucessor anunciado

A documentação de produto da Microsoft descreve o Run como *"modular and supports additional
plugins"* e traz o gerenciador de plugins, mas **não documenta desenvolvimento de plugin**
([PowerToys Run][pt-run]). Quem documenta é o repositório: o checklist de plugin novo fixa
`"Language": "csharp"` como a única opção, alvo `net10.0-windows10.0.22621.0`, classe `Main` com
`PluginID` estático, testes MSTest e entrada no instalador (`Product.wxs`)
([new-plugin-checklist][pt-checklist]). **Não há suporte a outra linguagem.**

E há um sinal de direção que importa para não construir sobre areia: a própria página do Run avisa
que *"PowerToys Run is getting an upgrade to v2"*, apontando para o **Command Palette**. As
extensões do Command Palette são **C#**, com Visual Studio + WinUI/Windows App SDK, empacotamento
MSIX e **modo desenvolvedor ligado** ([creating-an-extension][pt-cmdpal]). Para este projeto isso
é um segundo runtime, um segundo build e um segundo instalador — fora da faixa do ADR 0001.

### 1.3 Wox e Keypirinha

**Wox** está vivo (v2.4.3, setembro de 2026), reescrito como app nativo, e o README oferece
extensão *"with Node.js, Python, or script plugins from the store"*, com os diretórios
`wox.plugin.python` e `wox.plugin.nodejs` no repositório ([Wox][wox]). **Levantei só a superfície:**
não confirmei qual Python ele usa, nem se há página de settings por plugin. Se o Flow for
descartado por algum motivo, o Wox é o próximo a investigar — não antes.

**Keypirinha** é o caso mais Python de todos e o mais datado. A documentação diz que ele *"embeds a
vanilla version of CPython"* — **3.5.0** — e que a stdlib embutida **exclui `tkinter`**, entre
outros ([Embedded Python Interpreter][kp-python]). Entrada de texto livre existe e é limpa:
`on_suggest()` recebe `user_input` ([Plugin class][kp-plugin]). Configuração é **arquivo de texto**
lido por `load_settings()`, sem formulário gráfico. Ou seja: serve para digitar, não para
configurar, e o interpretador é velho demais para hospedar qualquer coisa nossa (o projeto exige
`>=3.12` e usa `tomllib`, que é 3.11+).

### 1.4 O quadro

| launcher | linguagem do plugin | texto longo como entrada | mostra resposta de ~60 s | formulário das 24 chaves |
|---|---|---|---|---|
| **Flow Launcher** | Python (embedded 3.11.4), C#, JS/TS, executável | **sim** (`query()` recebe o texto todo) | **não** (processo novo por consulta, morto pelo token) | **sim, mas grava nos settings do Flow**, não no nosso TOML |
| **PowerToys Run** | **só C#** | sim | não levantado — irrelevante sem Python | opções declaradas pelo plugin C#; nada genérico |
| **Command Palette** (sucessor) | **só C#** + WinUI + MSIX | sim | idem | idem |
| **Wox** | Python, Node.js, script | provável, **não confirmado** | não confirmado | não confirmado |
| **Keypirinha** | Python **3.5.0 embutido**, sem `tkinter` | **sim** (`on_suggest(user_input)`) | não confirmado | **não** — settings são arquivo de texto |

Uma observação que o quadro não mostra: **qualquer um destes é um aplicativo de terceiro que o
usuário precisa instalar e manter instalado**. O ADR 0001 fala de "sem componente em servidor", e
nenhum deles é servidor — mas todos são um pré-requisito novo na máquina dele, do mesmo tipo que o
projeto evitou ao recusar plataforma de agente pronta.

---

## 2. Janela própria em Python

### 2.1 Tkinter — a que já está aqui

**Dependência nova: nenhuma.** É stdlib (a documentação a chama de *optional module*, e a build
oficial do Windows traz Tcl/Tk 8.6 embutida — [tkinter][py-tk]). **Verificado nesta venv:**
`import tkinter` funciona e `tkinter.TkVersion` é `8.6`.

**Janela sem borda, centrada, por cima de tudo.** Tudo do manual do `wm` do Tk 8.6
([wm][tk-wm]):

| o que se quer | comando | o que o manual diz |
|---|---|---|
| sem borda nem barra de título | `wm overrideredirect 1` | a janela passa a ser *"disregarded by the window manager"*, sem reparenting em moldura decorativa |
| no centro da tela | `wm geometry =WxH±x±y` | posição em pixels relativa às bordas da tela (com `winfo_screenwidth/height` para calcular o centro) |
| sempre por cima | `wm attributes -topmost` | *"Specifies whether this is a topmost window (displays above all other windows)"* — documentado para Windows |
| ainda disponíveis | `-alpha`, `-toolwindow`, `-transparentcolor` | transparência e estilo *tool window* do Windows |

**Formulário de 24 campos: dá, e o campo de segredo é nativo.** A opção `-show` do widget `entry`
existe exatamente para isso: *"each character in the entry's value will be displayed as the first
character in the value of this option, such as '\*'. This is useful, for example, if the entry is
to be used to enter a password"* ([entry][tk-entry]). O que as 24 chaves pedem, contadas do
`MODELO_DE_CONFIGURACAO`:

| tipo | quantas | widget |
|---|---|---|
| segredo (`deepgram.api_key`, `linear.api_key`, `slack.user_token`, `bot_token`, `app_token`) | **5** | `Entry(show="•")` |
| lista de strings | 7 | `Text` multilinha, uma por linha |
| caminho (`vault`, `gravacoes`, `git.raiz`) | 3 | `Entry` + botão de pasta |
| número inteiro | 3 | `Spinbox` |
| hora | 2 | `Entry` com a validação que `configuracao._hora` já faz |
| texto livre | 4 | `Entry` / `Text` |

Feio por padrão, e essa é a crítica honesta ao Tk: sem trabalho de estilo, a janela parece Windows
95. `ttk` melhora bastante e continua stdlib.

**Não tem ícone de bandeja.** O Tk não oferece tray icon — o `pystray` continua sendo necessário
(§2.4).

**O risco de verdade é o de thread**, e a documentação da stdlib é explícita: o `mainloop` roda no
thread que criou o objeto `Tk`; chamadas vindas de outro thread são enfileiradas no interpretador
Tcl, mas *"If the Tcl interpreter is not running the event loop and processing events, any tkinter
calls made from threads other than the one running the Tcl interpreter will fail"*; e
*"any long-running computations should not run in an event handler"* ([tkinter][py-tk]). Traduzindo
para o nosso caso: **a pergunta de 60 s tem que rodar num worker e voltar via `after()`** — se
rodar no handler do botão, a janela congela um minuto inteiro.

### 2.2 pywebview — HTML dentro de uma janela

**Dependência nova.** O wheel é pequeno (`pywebview-6.2.1-py3-none-any.whl`, 525,5 kB — [PyPI][pw-pypi]),
mas as dependências declaradas no `pyproject.toml` do projeto incluem, para Windows,
**`pythonnet`** (que puxa `clr-loader`), além de `proxy_tools`, `bottle` e `typing_extensions`
([pyproject][pw-toml]). Não é uma dependência, é um pequeno conjunto — e uma delas é uma ponte CLR.

**O runtime já está na máquina.** O renderer no Windows é o WebView2, e a Microsoft diz:
*"The Evergreen WebView2 Runtime will be included as part of the Windows 11 operating system"*
([distribution][ms-webview2]). Máquina do usuário é Windows 11 — então não há instalador extra.
(Vale checar o registro antes de prometer isso, como a própria MS recomenda.)

**Janela sem borda e centrada: suportado.** `create_window` aceita `frameless` (*"Create a frameless
window. Default is False"*), `on_top`, `x`/`y` (*"Default is centered"*), `hidden`, e a janela tem
`show()`/`hide()` — o que é exatamente o ciclo de vida de um launcher ([API][pw-api]).

**Main loop:** *"This function must be called from a main thread"*, diz a documentação de
`webview.start()`, que aceita um `func` para o seu código rodar em outro thread. É o mesmo conflito
do Tk com o `pystray`, e a mesma saída (§2.4).

**Formulário de 24 campos:** é HTML — o mais confortável dos três para fazer bonito, e o único que
exige escrever front-end (HTML/CSS/JS) e uma ponte JS↔Python para os valores. **Há precedente
contra no próprio projeto:** a página HTML da daily nasceu e foi revertida no mesmo dia
(`.scratch/fontes-passivas/issues/09-a-daily-como-pagina.md`, commit `9a53218`), e o mapa desta
entrega registra isso como regra.

### 2.3 PySide6/Qt — a mais capaz e a mais pesada

**Tamanho.** `PySide6` no PyPI é um meta-pacote — *"an alias to other two wheels PySide6_Essentials
and PySide6_Addons"* ([PySide6][qt-pypi]). O wheel real do Essentials para Windows x64 é
**76,9 MB** (`pyside6_essentials-6.11.2-cp310-abi3-win_amd64.whl` — [PySide6-Essentials][qt-ess]),
antes de `shiboken6` e do Addons. A venv inteira do projeto hoje tem 48 pacotes; isto é a maior
dependência que o projeto já teria.

**Licença:** *"LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"*, ou comercial. Python suportado:
`>=3.10, <3.15` — cobre o 3.12 do projeto.

**O que ele entrega em troca, e é real:** janela sem borda (`Qt.FramelessWindowHint`), formulário
decente sem esforço, **e `QSystemTrayIcon` no próprio `QtWidgets`** — ou seja, Qt poderia
**substituir o `pystray`** e acabar com o problema de dois loops: um só event loop para bandeja e
janela. O preço é reescrever `bandeja.py`.

**Não confirmado:** se o Qt oferece atalho *global* (fora do app). As páginas de `QShortcut` e
`QSystemTrayIcon` do Qt for Python não me devolveram o texto descritivo nas tentativas de leitura —
só confirmei que as classes existem no módulo. A hipótese de trabalho é que **o atalho global
continuaria sendo `RegisterHotKey`** mesmo com Qt, mas isso precisa ser verificado antes de virar
argumento.

### 2.4 Conviver com o `pystray` — o risco real, e o que o código diz

O `pystray` já roda um loop na máquina do usuário. Os fatos, da documentação e do **código
instalado (0.19.5, nesta venv)**:

- `Icon.run()`: *"This method is blocking until stop() is called. It **must** be called from the
  main thread."* (docstring em `_base.py`).
- A razão declarada é o macOS: *"the system tray icon implementation for OSX will fail unless
  called from the main thread"* ([usage][ps-usage]). Para integrar com outro framework, a
  biblioteca oferece `run_detached()` — *"Call this method before entering the mainloop of the
  other library"*.
- **No Windows, `run_detached` é trivial e está implementado:**
  `def _run_detached(self): threading.Thread(target=lambda: self._run()).start()` (`_win32.py`).
  O `_run` cria as duas janelas escondidas e roda `_mainloop` **nesse thread**.

Conclusão de engenharia, com o custo: **Tk (ou pywebview) no thread principal + `pystray.run_detached()`
num thread secundário** é um arranjo previsto pela biblioteca e barato de escrever. As chamadas do
menu da bandeja para a janela atravessam threads — e a documentação do tkinter diz que isso é
enfileirado com segurança **enquanto o loop do Tk estiver rodando**.

**Uma armadilha achada lendo o código, que ainda não é fato de execução:** o `_mainloop` do
`pystray` faz `GetMessage(lpmsg, None, 0, 0)` seguido de `TranslateMessage`/`DispatchMessage` —
isto é, **consome todas as mensagens daquele thread**. Uma `WM_HOTKEY` registrada com `hWnd = NULL`
nesse mesmo thread seria retirada da fila e descartada, porque `DispatchMessage` sem janela não
entrega a ninguém. O desenho seguro é **registrar o hotkey contra uma janela oculta nossa**, ou dar
ao hotkey **o seu próprio thread e o seu próprio loop**. *Isto é leitura de código, não teste.*

### 2.5 O quadro

| | dependência nova | tamanho | sem borda + centrada | formulário de 24 campos | convive com o `pystray` |
|---|---|---|---|---|---|
| **Tkinter** | **nenhuma** (stdlib, já importa aqui) | 0 | sim (`overrideredirect` + `geometry` + `-topmost`) | sim, com `-show` para os segredos; **feio sem trabalho** | sim, com `run_detached` no thread da bandeja |
| **pywebview** | `pythonnet`+`clr-loader`, `proxy_tools`, `bottle` | wheel 525 kB + CLR; WebView2 **já vem no Windows 11** | sim (`frameless`, `on_top`, `x`/`y`) | sim — mas é HTML/CSS/JS + ponte; **precedente contra no projeto** | mesmo arranjo; `start()` exige main thread |
| **PySide6** | a maior do projeto | Essentials **76,9 MB** + shiboken + Addons | sim | sim, e é o melhor acabamento | **substitui** o `pystray` (`QSystemTrayIcon`) — um loop só, ao custo de reescrever a bandeja |

---

## 3. O atalho global de teclado

### 3.1 `ctypes`/`pywin32` + `RegisterHotKey` — e ele já está instalado

A API é `RegisterHotKey`, descrita pela Microsoft como *"Defines a system-wide hot key"*
([RegisterHotKey][ms-hotkey]). O que a página oficial diz, e o que ela **não** diz:

- **Privilégio:** a seção *Requirements* lista apenas `winuser.h`, `User32.lib`, `User32.dll`,
  Windows Vista ou superior. **Nenhuma menção a administrador, em lugar nenhum da página.**
- **Loop de mensagens:** *"If this parameter is NULL, WM_HOTKEY messages are posted to the message
  queue of the calling thread and must be processed in the message loop."* É disso que a §2.4
  trata. Console não é requisito — logo, `pythonw.exe` serve em tese.
- **Conflito:** *"Typically, RegisterHotKey also fails if the keystrokes specified for the hot key
  have already been registered for another hot key"* — falha silenciosa se ninguém checar o
  retorno. E *"some pre-existing, default hotkeys registered by the OS (such as PrintScreen…) may
  be overridden by another hot key registration when one of the app's windows is in the foreground"*.
- **Tecla Windows:** `MOD_WIN` é aceito, mas *"Keyboard shortcuts that involve the WINDOWS key are
  reserved for use by the operating system"*. **F12 é reservada para o depurador, sempre.**
- **`MOD_NOREPEAT`** evita disparo repetido pelo auto-repeat do teclado — o exemplo oficial usa
  `MOD_ALT | MOD_NOREPEAT`.

**Custo zero de dependência, verificado na máquina dele.** O `pywin32` 312 está na venv e expõe
tudo: `win32gui.RegisterHotKey`, `win32gui.UnregisterHotKey`, `win32con.MOD_ALT/MOD_CONTROL/MOD_WIN`,
`win32con.WM_HOTKEY` (= 786). E o `ctypes.windll.user32.RegisterHotKey` também está lá, se a
preferência for não depender nem do `pywin32`.

**Um alerta que não está na página do `RegisterHotKey`, mas está na documentação da Microsoft:** a
própria página do PowerToys Run traz a opção *"Use centralized keyboard hook — Try this setting if
there are issues with the shortcut (PowerToys Run might not get focus when triggered from an
elevated window)"* ([PowerToys Run][pt-run]). Isto é a Microsoft admitindo, na documentação do
próprio launcher, que **atalho de processo não elevado tem problema quando a janela em foco é
elevada**. Se ele estiver com um terminal como administrador em foco, o atalho pode não funcionar.
**Não confirmei** a mecânica exata (UIPI) em fonte primária.

### 3.2 A biblioteca `keyboard`

Do README oficial ([keyboard][kb]):

- *"Pure Python, no C modules to be compiled"* e *"Zero dependencies"*.
- Funciona em Windows e Linux, e o `sudo` que ela pede é **só no Linux** (*"reads raw device files
  (/dev/input/input\*) but this requires root"*). Nada de administrador no Windows, pelo README.
- É um **hook global em todas as teclas**: *"Global event hook on all keyboards (captures keys
  regardless of focus)"*, com os eventos capturados num thread separado.
- **E o aviso que pesa mais:** *"This project is currently unmaintained."*

Para um projeto com uma seção `[privacidade]` no `config.toml`, vale dizer em voz alta o que um
hook global é: **um processo residente que vê tudo o que o usuário digita**, em qualquer app.
`RegisterHotKey` não faz isso — o sistema só avisa quando aquela combinação específica é
pressionada.

### 3.3 `pynput`

A documentação oferece `pynput.keyboard.GlobalHotKeys`, que recebe um dicionário de combinação →
callback ([pynput][pyn]). *"A keyboard listener is a `threading.Thread`, and all callbacks will be
invoked from the thread"*. O aviso relevante para nós: *"The listener callbacks are invoked directly
from an operating thread on some platforms, notably Windows"*, e por isso procedimentos longos não
devem rodar no callback — **congelam o sistema de entrada inteiro**. Com uma ação de 60 s, isso
deixa de ser detalhe. **A documentação não fala de privilégio**; não confirmado.

### 3.4 O quadro

| | dependência | administrador? | com `pythonw.exe`? | conflito com hotkey do Windows |
|---|---|---|---|---|
| **`RegisterHotKey`** (ctypes ou `pywin32`) | **nenhuma — `pywin32` já está instalado** | **não documentado como necessário** | sim em tese (precisa de loop, não de console) | **falha e avisa** pelo retorno; `MOD_WIN` é reservado pelo SO; F12 é do depurador |
| **`keyboard`** | pacote novo, zero deps | root **só no Linux** | não confirmado | hook global — não "falha", convive; pode conflitar com hooks de outros apps |
| **`pynput`** | pacote novo | não documentado | não confirmado | listener próprio; callback longo **congela a entrada do sistema** |

---

## 4. O veredito de esforço

Do mais barato ao mais caro. "Entrega" e "não entrega" são o que cada caminho resolve dos seis
gestos.

**1. Hotkey + janela Tkinter mínima (um campo de texto, Enter).** Dependência nova: **zero**.
Entrega: invocar por atalho de qualquer lugar, gerar a daily, abrir a daily, anotar um ponto,
disparar a pergunta. **Não entrega**: a resposta de 60 s renderizada com elegância (mostra
"perguntando…" e precisa decidir onde a resposta aparece), nem o formulário de configuração, nem
qualquer beleza.

**2. O mesmo, mais o formulário das 24 chaves.** Dependência nova: **zero para a interface** — o
custo está em outro lugar: **escrever o `config.toml` de volta**. O projeto lê com `tomllib`, que
é somente leitura; não existe escritor de TOML nas dependências. Ou se regenera o arquivo a partir
do `MODELO_DE_CONFIGURACAO` (perdendo comentários e qualquer edição manual dele) ou entra uma
dependência (`tomlkit` preserva comentários; `tomli-w` não). Entrega: a única superfície do
inventário que resolve "configurar" de verdade, com os segredos indo do teclado direto ao arquivo,
sem modelo no meio. **Não entrega**: nada no celular; nada quando o Whis está morto.

**3. Plugin do Flow Launcher.** Dependência nova: **um aplicativo inteiro que o usuário instala e
mantém**. Entrega: a caixa de texto pronta, bonita, com atalho já resolvido por ele, e uma página
de settings com `passwordBox` de graça. **Não entrega**: execução (é sempre `subprocess` para a
nossa venv), a espera de 60 s (processo novo por consulta, morto pelo token), e a configuração
**no nosso arquivo** — grava na do Flow, duplicando os segredos.

**4. pywebview.** Dependência nova: `pythonnet` + três pacotes; o WebView2 já vem no Windows 11.
Entrega: a interface mais bonita por menos CSS, e o mesmo conjunto de gestos do caminho 2.
**Não entrega**: nada a mais que o Tkinter não entregue — e reabre a discussão que a página HTML da
daily já perdeu uma vez neste projeto.

**5. PySide6.** Dependência nova: ~77 MB só de Essentials. Entrega: tudo dos caminhos anteriores,
com acabamento profissional, **e a unificação do loop** (o `QSystemTrayIcon` aposenta o `pystray`).
**Não entrega**: nada de novo em função — só em forma; e cobra a reescrita de `bandeja.py`.

**6. PowerToys Run / Command Palette.** Fora: C#, .NET SDK, MSIX, modo desenvolvedor. Um segundo
projeto, em outra linguagem, para entregar menos que o caminho 1.

### E a pergunta dele, direto

*"Seria muito mais complexo fazer um app que abre por comando tipo um Raycast?"*

**Não. A parte "Raycast" é a barata.** O atalho global são poucas dezenas de linhas com uma API do
Windows que já está instalada na máquina (`pywin32`), e a janela sem borda, centrada e por cima de
tudo são três chamadas do Tk que já está na venv. Comparado a uma janela de configuração comum, o
*extra* do Raycast é: registrar o hotkey, esconder a borda, centralizar, e mostrar/esconder em vez
de abrir/fechar.

**O que é mais caro do que uma janela de configuração comum são três coisas, e nenhuma delas é o
atalho:**

1. **A espera de 60 s.** Uma janela de configuração salva em milissegundos. Esta tem uma ação que
   demora um minuto e custa US$ 0,56 — precisa de worker thread, de estado visível ("perguntando
   há 40 s"), de cancelamento, e de uma decisão de produto sobre onde a resposta aparece se ele
   fechar a janela.
2. **Conviver com o `pystray`**, que já tem loop e quer o thread principal. Tem saída documentada
   (`run_detached`), mas é o tipo de coisa que funciona no teste e falha no logon.
3. **Gravar o `config.toml` de volta** sem destruir o que ele escreveu à mão — o único ponto deste
   levantamento inteiro que provavelmente custa uma dependência nova.

---

## O que não consegui confirmar

- Se o Flow Launcher tem caminho **documentado** para instalar um plugin local/privado sem a loja
  (a pasta é `%APPDATA%\FlowLauncher\Plugins`, mas copiar a pasta é inferência).
- **Onde** o Flow Launcher grava os valores do `SettingsTemplate.yaml`, e se os `passwordBox`
  ficam em texto puro no disco. Isso decide se o formulário dele é aceitável para os cinco segredos.
- Se o Qt/PySide6 oferece **atalho global** (fora do app) — as páginas de `QShortcut` e
  `QSystemTrayIcon` do Qt for Python não devolveram o texto descritivo nas leituras.
- A mecânica exata do problema de foco com janela elevada (a documentação do PowerToys confirma que
  o problema existe; não achei a explicação em fonte primária da API).
- Se `keyboard` e `pynput` exigem privilégio no **Windows** — a documentação de nenhum dos dois
  afirma que sim, mas também não afirma que não.
- **Nada disto foi executado nesta máquina**, além dos imports: que `RegisterHotKey` dispara a
  partir de `pythonw.exe`, e que `pystray.run_detached()` convive com um `mainloop` do Tk, são
  hipóteses de leitura de documentação e de código-fonte. **São os dois testes que valem uma tarde
  antes de qualquer spec.**
- O Wox foi levantado só na superfície (README).

---

## Fontes

**Máquina do usuário / repositório** (leitura direta, 2026-09-12)

- `.venv`: Python 3.12.10; `import tkinter` OK, `TkVersion 8.6`; `pywin32` 312 com
  `win32gui.RegisterHotKey` e `win32gui.UnregisterHotKey`; `pystray` 0.19.5.
- `.venv/Lib/site-packages/pystray/_base.py` (docstrings de `run` e `run_detached`) e
  `_win32.py` (`_run`, `_run_detached`, `_mainloop`).
- `src/whis/__main__.py` (`MODELO_DE_CONFIGURACAO`, as 24 chaves), `src/whis/configuracao.py`
  (`tomllib`, somente leitura), `src/whis/bandeja.py`, `pyproject.toml`.

**Launchers**

- [Flow Launcher — plugin.json (campo `Language`)][fl-pluginjson]
- [Flow Launcher — Python: desenvolver plugins (Embedded Python)][fl-pydev]
- [Flow Launcher — Python: preparar o projeto (`lib/`, `sys.path`)][fl-pysetup]
- [Flow Launcher — Python: escrever o código (`query()`, resultados)][fl-pywrite]
- [Flow Launcher — Python: publicar][fl-pyrelease]
- [Flow Launcher — `SettingsTemplate.yaml` (os oito controles, `passwordBox`)][fl-settings]
- [Flow Launcher — `PythonEnvironment.cs` (embeddable 3.11.4, `pythonw.exe`)][fl-pyenv]
- [Flow Launcher — `JsonRPCPlugin.cs` (processo por consulta, `Kill()` no cancelamento)][fl-jsonrpc]
- [Flow Launcher — `DataLocation.cs` (pasta de plugins)][fl-data]
- [PowerToys Run — documentação de produto (plugin manager, hook centralizado)][pt-run]
- [PowerToys — checklist de plugin novo (`"Language": "csharp"`)][pt-checklist]
- [PowerToys Command Palette — criar uma extensão (C#, WinUI, MSIX)][pt-cmdpal]
- [Wox — README][wox]
- [Keypirinha — interpretador Python embutido (3.5.0, sem `tkinter`)][kp-python]
- [Keypirinha — classe `Plugin` (`on_suggest`, `load_settings`)][kp-plugin]

**Interface**

- [Python — `tkinter` (stdlib, Tcl/Tk 8.6, modelo de threads)][py-tk]
- [Tk 8.6 — `wm` (`overrideredirect`, `geometry`, `attributes`)][tk-wm]
- [Tk 8.6 — `entry` (opção `-show`)][tk-entry]
- [pywebview — API (`frameless`, `on_top`, `start()` no main thread)][pw-api]
- [pywebview — `pyproject.toml` (dependências no Windows)][pw-toml]
- [pywebview — PyPI][pw-pypi]
- [Microsoft — distribuir o WebView2 Runtime (incluído no Windows 11)][ms-webview2]
- [PySide6 — PyPI (licenças, meta-pacote)][qt-pypi]
- [PySide6-Essentials — PyPI (76,9 MB win_amd64)][qt-ess]
- [pystray — uso (`run` no main thread, `run_detached`)][ps-usage]

**Atalho global**

- [Microsoft — `RegisterHotKey`][ms-hotkey]
- [`keyboard` — README (zero deps, sudo só no Linux, sem manutenção)][kb]
- [`pynput` — teclado (`GlobalHotKeys`, callbacks no thread do SO)][pyn]

[fl-pluginjson]: https://github.com/Flow-Launcher/docs/blob/main/plugin.json.md
[fl-pydev]: https://github.com/Flow-Launcher/docs/blob/main/py-develop-plugins.md
[fl-pysetup]: https://github.com/Flow-Launcher/docs/blob/main/py-setup-project.md
[fl-pywrite]: https://github.com/Flow-Launcher/docs/blob/main/py-write-code.md
[fl-pyrelease]: https://github.com/Flow-Launcher/docs/blob/main/py-release-project.md
[fl-settings]: https://github.com/Flow-Launcher/docs/blob/main/json-rpc-settings.md
[fl-pyenv]: https://github.com/Flow-Launcher/Flow.Launcher/blob/dev/Flow.Launcher.Core/ExternalPlugins/Environments/PythonEnvironment.cs
[fl-jsonrpc]: https://github.com/Flow-Launcher/Flow.Launcher/blob/dev/Flow.Launcher.Core/Plugin/JsonRPCPlugin.cs
[fl-data]: https://github.com/Flow-Launcher/Flow.Launcher/blob/dev/Flow.Launcher.Infrastructure/UserSettings/DataLocation.cs
[pt-run]: https://learn.microsoft.com/en-us/windows/powertoys/run
[pt-checklist]: https://github.com/microsoft/PowerToys/blob/main/doc/devdocs/modules/launcher/new-plugin-checklist.md
[pt-cmdpal]: https://learn.microsoft.com/en-us/windows/powertoys/command-palette/creating-an-extension
[wox]: https://github.com/Wox-launcher/Wox
[kp-python]: https://keypirinha.com/api/python.html
[kp-plugin]: https://keypirinha.com/api/plugin.html
[py-tk]: https://docs.python.org/3/library/tkinter.html
[tk-wm]: https://www.tcl-lang.org/man/tcl8.6/TkCmd/wm.htm
[tk-entry]: https://www.tcl-lang.org/man/tcl8.6/TkCmd/entry.htm
[pw-api]: https://pywebview.flowrl.com/api/
[pw-toml]: https://github.com/r0x0r/pywebview/blob/master/pyproject.toml
[pw-pypi]: https://pypi.org/project/pywebview/
[ms-webview2]: https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution
[qt-pypi]: https://pypi.org/project/PySide6/
[qt-ess]: https://pypi.org/project/PySide6-Essentials/
[ps-usage]: https://pystray.readthedocs.io/en/latest/usage.html
[ms-hotkey]: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey
[kb]: https://github.com/boppreh/keyboard
[pyn]: https://pynput.readthedocs.io/en/latest/keyboard.html

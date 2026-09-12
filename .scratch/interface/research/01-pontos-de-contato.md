# Inventário dos pontos de contato do Whis

Levantado em 2026-09-10, no repositório e na máquina do usuário, a partir da tabela do
[handoff da entrega 4](../handoff.md). Ticket:
[01](../issues/01-inventario-dos-pontos-de-contato.md).

**Aviso de confiabilidade, leia antes de citar qualquer coisa daqui.** O `%APPDATA%` desta
sessão de agente **não é o do usuário** (seção 5). Tudo o que vem de `config.toml` e de
`bandeja.log` é cópia velha e está marcado como *não confiável* abaixo. Tudo o que vem do
código-fonte, do Agendador de Tarefas e da lista de processos é de primeira mão.

---

## 1. A tabela, conferida

| gesto | como se faz hoje | onde ele está | dor | conferido |
|---|---|---|---|---|
| gravar a reunião | clique no ícone da bandeja | no Meet, no PC | nenhuma — é o gesto da spec original | `bandeja.py`; **mas o ícone não sobe mais**, §2 |
| ler a nota da reunião | Obsidian, `reunioes/` | no PC, depois | nenhuma | `vault.PASTA_REUNIOES` |
| abrir a nota pelo menu da bandeja | *Abrir a última nota* | no PC | **quebrado**, §2.1 | `bandeja.abrir_no_windows` |
| **gerar a daily** | `whis daily` no terminal | entrando na reunião, no PC | **a maior** | `__main__._comando_daily` |
| anotar um ponto | `notas/daily.md` no Obsidian, `daily --anotar "..."`, ou `anotar ...` na DM | qualquer lugar | depende de lembrar do arquivo | `vault.ARQUIVO_DE_PONTOS`, `atendente._PEDIDO_DE_ANOTACAO` |
| conferir o filtro | `daily --simular` / `diario --simular` | no PC | raro, aceitável no terminal | `__main__` |
| gerar o diário | `whis diario` — **e só à mão**, §3 | — | **esquecido**: nada o agenda | `automacao.py` |
| perguntar ao vault | a DM do Slack, do PC ou do celular | no Slack | resolvida, com os achados de uso | `atendente.py`, `dm_slack.py` |
| configurar | editar `config.toml` à mão em `%APPDATA%` | raro | ele não achou o arquivo sozinho quando precisou | `configuracao.py` |
| subir no logon, limpar, init | `windows`, `limpar`, `init` | uma vez | **quebrado**, §2 | `automacao.py` |
| saber que algo falhou | balão da bandeja (só reunião); código de saída e `bandeja.log` (o resto) | — | **§4** | `bandeja._balao`, `registro.py` |

O menu da bandeja, por extenso (`bandeja._construir_icone`) — cinco itens, nenhum sobre daily,
diário ou pergunta:

1. *Gravar reunião* / *Parar e processar* (item padrão; é também o clique esquerdo)
2. o estado por extenso, desabilitado (`situacao.descricao()`)
3. *Abrir a última nota* (habilitado só quando existe uma)
4. *Abrir a pasta de gravações*
5. *Sair*

---

## 2. Três automações mortas, agora, sem ninguém saber

**Nenhum processo Python no ar.** Em 303 processos visíveis, zero `python`/`pythonw`. Nem a
bandeja nem o atendente estão rodando.

```
Get-Process | Where-Object { $_.ProcessName -match 'python' }   # vazio
(Get-Process).Count                                            # 303
```

**O atalho de logon aponta para um módulo que não existe.** A pasta de Inicialização tem um
único atalho, `Second Brain.lnk`:

```
TargetPath       : C:\Users\gabri\development\second-brain\.venv\Scripts\pythonw.exe
Arguments        : -m second_brain bandeja
WorkingDirectory : C:\Users\gabri\development\second-brain
Description      : Second Brain — coletor de reunião na bandeja
```

E o módulo morreu no rename de 09/09:

```
$ .venv/Scripts/python.exe -m second_brain limpar
...\python.exe: No module named second_brain
```

Como o alvo é `pythonw.exe`, **não há console** para mostrar o erro, e o Whis não chega a subir
para abrir o log. O erro não existe em lugar nenhum: a bandeja simplesmente não aparece.

**O atendente nunca teve atalho.** Só o da bandeja está instalado —
`whis windows --atendente` (passo 11 do `docs/smoke-atendente.md`) nunca foi rodado. A DM, que é
a única superfície que o usuário aprovou no uso real, **não sobrevive a um reboot**.

**A tarefa agendada falha calada todo dia ao meio-dia.** Lida do Agendador (não de arquivo, e
portanto confiável):

```
TaskName  : SecondBrain-Limpeza
State     : Ready
Execute   : "C:\Users\gabri\development\second-brain\.venv\Scripts\pythonw.exe"
Arguments : -m second_brain limpar
Trigger   : 2026-09-03T12:00:00, diária
```

Mesmo `No module named second_brain`, mesmo `pythonw.exe`, mesmo silêncio. O áudio bruto vem se
acumulando desde 09/09 (uma reunião de 40 min ocupa ~420 MB nos dois canais).

A pendência 3 do handoff descreve isso como "os atalhos têm nomes antigos". **É mais que isso:
são três automações mortas há um dia e meio, e nada avisou.**

### 2.1 E uma quarta coisa quebrada, achada depois pelo ticket 04

`bandeja.abrir_ultima_nota` chama `abrir_no_windows`, que é `os.startfile(caminho)`. Só que **`.md`
não tem programa associado nesta máquina**:

```
$ cmd /c "assoc .md"
Associação de arquivo não encontrada para a extensão .md
```

Não há `UserChoice` em `HKCU\...\FileExts\.md`, e a `OpenWithList` do Explorer traz `chrome.exe`,
`claude.exe` e `Code.exe` — **o Obsidian não está nela**. Ou seja, o item de menu *"Abrir a última
nota"* — o único que liga a bandeja ao vault — **não abre o Obsidian hoje**: no melhor caso mostra
o diálogo *"Como você quer abrir este arquivo?"*, no pior devolve `SE_ERR_NOASSOC`, que
`abrir_no_windows` engole num `_log.error`. Silêncio, de novo.

O conserto é uma linha: `os.startfile` vira uma URI `obsidian://open?vault=...&file=...`. Os
valores deste vault estão levantados em
[04-obsidian-como-interface.md](04-obsidian-como-interface.md). É a menor entrega útil que esta
entrega inteira produziu até agora — e conserta um gesto que **já existe** no inventário, em vez
de inventar superfície.

---

## 3. O diário nunca foi agendado — por código nenhum

`automacao.py` sabe fazer exatamente três coisas: `instalar_inicializacao()` (atalho da bandeja),
`instalar_atendente()` (atalho do atendente) e `agendar_limpeza()` (`schtasks /Create`,
`NOME_DA_TAREFA = "Whis-Limpeza"`, `/SC DAILY`, `/ST 12:00`). **Não existe caminho para agendar
`diario` nem `daily`**, e `whis windows` só oferece `--atendente` e `--limpeza`.

Pior, há uma configuração que promete o contrário:

```toml
[diario]
hora_da_tarefa = "19:00"     # quando a tarefa agendada gera o diário
```

Ela é lida (`configuracao.py:153`), validada como hora (erro de configuração se for
`"meio-dia"`), tem teste (`tests/test_configuracao_diario.py`) e aparece no
`MODELO_DE_CONFIGURACAO` com aquele comentário. **Nenhum código a usa** — `grep` por
`diario_hora_da_tarefa` acha só a definição, a leitura e os testes. É uma intenção documentada
que nunca virou comportamento, e a documentação faz parecer que virou.

Consequência para a entrega 4: **agendar é trabalho novo, não configuração**. O ticket 02 herda
isso.

---

## 4. Falha não tem para onde gritar

O único aviso que chega ao usuário sem ele procurar é o **balão da bandeja**
(`pystray.Icon.notify`, em `bandeja._balao`), e ele só fala de reunião: *"A reunião não virou
nota"* e *"Reunião no vault"*. Tudo o mais — daily, diário, atendente, limpeza — tem como único
rastro o `bandeja.log` em `%APPDATA%\whis\`, que ninguém abre, e um código de saída que ninguém
lê porque não há terminal aberto.

E há um buraco pior que o log não olhado: **quem falha antes de subir não escreve log nenhum**.
O log é aberto por `registro.acrescentar_arquivo`, chamado *depois* de o comando começar. Os três
casos mortos da §2 morrem antes disso. O mesmo vale para `ConfiguracaoInvalida` (já registrado no
DEFERRED) e para o OAuth vencido de 10/09 quando quem chama o Claude é uma tarefa agendada.

A linha "saber que algo falhou" do inventário, portanto, **não é uma dor hipotética**: três
coisas estão quebradas agora, e a única razão de alguém ter descoberto é um agente ter ido olhar.

Fato útil para o ticket 02: **o balão do Windows já funciona hoje sem dependência nova** — mas
`pystray.Icon.notify` não tem botão, e depende de a bandeja estar no ar (que é justamente o que
falha).

---

## 5. O `%APPDATA%` do agente não é o do usuário — provado

A armadilha que o handoff descreve continua ativa nesta sessão, e agora tem prova limpa.

Na pasta `%APPDATA%\whis\`, o agente enxerga:

| arquivo | mtime que o agente vê | quem escreveu por último | confiável? |
|---|---|---|---|
| `conversas.json` | **2026-09-10 19:59** | o usuário, na demo | **sim** — contém os turnos reais de `19:51` e `19:58` |
| `atendente.lock` | 2026-09-10 19:50 | o usuário, na demo | sim |
| `bandeja.log` | 2026-09-09 20:06 (+ o que esta sessão acrescentou) | um agente, em 09/09 | **não** |
| `config.toml` | 2026-09-09 20:39 | um agente, no rename | **não** |

O corte é exato: **arquivo que algum agente escreveu ficou congelado na versão dele; arquivo que
só o usuário tocou passa direto.** As duas provas:

- `conversas.json` tem os turnos da demo de 10/09 (`2026-09-10T19:51`, `2026-09-10T19:58`), mas o
  `bandeja.log` que o agente lê **não tem uma única linha de 10/09 às 19h** — e o atendente
  escreve no log a cada mensagem. O log é uma cópia de 09/09.
- O `config.toml` que o agente lê tem `[slack].bot_token = ""` e `app_token = ""`. Se fosse o
  arquivo real, a demo de 10/09 **não teria como ter acontecido**: `dm_slack.de_configuracao`
  recusa subir sem os dois. É uma cópia de antes de o usuário colar os tokens.

Não há `WHIS_CONFIG` no ambiente, e uma varredura em `C:\Users\gabri` não achou nenhum outro
`config.toml` do Whis — ou seja, não é "o usuário usa outro arquivo": é a mesma rota, com vistas
diferentes.

**Regras que caem daqui, e valem para o resto desta entrega:**

1. **Nunca afirme o conteúdo de `config.toml` a partir de leitura do agente.** Quem confere é o
   usuário, no terminal dele. Isso inclui a pendência 1 (pasta privada vazia) e a 4
   (`referencias_pessoais` com os dois nomes): as duas estão coerentes com o handoff, mas nenhuma
   das duas foi *verificada* aqui.
2. **Nunca conclua nada sobre o histórico de uso a partir do `bandeja.log`.** Na cópia legível,
   a última daily é de 08/09 e a demo de 10/09 não existe — o que só prova que a cópia é velha.
3. Para gravar qualquer coisa que o usuário precise ver em `%APPDATA%`, escreva fora do
   `AppData` (`C:\Users\gabri\` atravessa nos dois sentidos) e peça a ele para mover.

---

## 6. O que cada superfície candidata cobre

Primeiro cruzamento, para o *grilling* não começar do zero. Não é decisão.

| gesto | agendador + toast | bandeja ampliada | DM do Slack | Obsidian | janela local |
|---|---|---|---|---|---|
| gravar a reunião | — | **já é** | — | — | — |
| ler a daily | abre a nota pelo botão | abre a nota | recebe o roteiro | **já é** | mostra |
| **gerar a daily** | **sozinha, no horário** | item de menu | *"gera a daily"* / botão | — | botão |
| anotar um ponto | — | janelinha de texto (o `pystray` não tem) | **já é** (`anotar X`) | **já é** (checkbox) | campo |
| perguntar ao vault | — | janelinha de texto | **já é** | — | campo |
| gerar o diário | **sozinho, às 19:00** | item de menu | — | — | — |
| configurar | — | — | perguntas na DM | nota de configuração | formulário |
| **saber que falhou** | **toast** | balão (se a bandeja estiver no ar) | mensagem na DM | — | — |

Duas observações que o cruzamento já entrega:

- **A DM cobre mais gestos do que qualquer outra superfície**, e é a única que funciona do
  celular. É também a única que o usuário já usou de verdade e já reclamou — o que vale mais que
  qualquer previsão.
- **"Saber que falhou" é a única linha que nenhuma superfície cobre sozinha**: o toast depende da
  bandeja estar no ar, a DM depende do atendente estar no ar, e os dois são exatamente o que
  morre. Quem avisa que o Whis caiu não pode ser o Whis. Isso é pergunta do ticket 02.

---

## 7. Fatos soltos, verificados, que os próximos tickets herdam

- **`dm_slack._receber` já confirma os envelopes `interactive` e `slash_commands`** — o
  `send_socket_mode_response` acontece antes do `if requisicao.type != "events_api": return`.
  Botão do Block Kit e slash command já **chegam**; falta tratá-los. (Ticket 03.)
- **`atendente.formatar_para_slack` monta o bloco de fontes** com uma linha por citação,
  `• \`origem\` — trecho`, com o trecho inteiro. A resposta longa vem do modelo; o bloco de
  fontes vem daqui. São dois consertos diferentes, como o DEFERRED já dizia. (Ticket 03.)
- **`atendente._e_para_mim` exige `subtipo is None`** — é por isso que imagem e áudio na DM não
  ganham nem o 👀: eles chegam com `subtype`. (Ticket 03.)
- **A trava de instância é bloqueio de faixa do SO** (`msvcrt.locking`), não arquivo-marcador:
  `atendente.lock` sobrando no disco **não** impede o atendente de subir. Não é a causa de nada.
- **`vault.ARQUIVO_DE_PONTOS` é `notas/daily.md`**, a única escrita na zona do usuário, e o
  caminho `anotar` não passa pelo modelo.
- **A suíte está em 862 verdes, 8 desselecionados**, e `whis perguntar --fakes --sem-fio "teste"`
  sai `0`. O repositório está limpo.

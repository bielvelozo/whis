# 04 — O Obsidian como interface

Type: research
Status: resolved
Blocked by: 01

## Question

O vault já é onde o usuário **lê**. Quanto de interface dá para fazer sem sair dele — e sem
stack nova?

Levantar fatos, não decidir:

- **`obsidian://`**: o que a URI abre (`open?vault=&file=`), se funciona com o Obsidian fechado,
  se dá para acionar comando/plugin, e o que ela faz com caminho com acento e espaço. É o que
  qualquer botão de "abrir a daily" vai usar, venha ele do toast (02) ou do Slack (03).
- **Nota-painel gerada pelo agente**: uma `daily/hoje.md` ou um *dashboard* com links, escrito
  pelo Whis na zona dele. Custo: zero código novo de interface (é `vault.escrever`). O que se
  perde: não aciona nada, só mostra.
- **Entrada de dados pelo Obsidian**: `notas/daily.md` já é isso (checkbox + `anotar`). O que
  mais o usuário poderia **escrever** numa nota para o Whis **ler** — configuração (pasta
  privada, blocklist, contexto do time) numa nota em vez de `config.toml`? Isso resolveria
  "ele não achou o arquivo sozinho quando precisou"?
- **Plugins que ele já tem instalados** — pergunta para ele no 05, mas levantar antes o que
  Dataview/Templater/Buttons dariam de graça, e o que exigiria um plugin próprio (TypeScript,
  stack nova, contra o ADR de projeto fino).
- **O precedente contra**: a página HTML da daily foi construída e revertida no mesmo dia
  (`.scratch/fontes-passivas/issues/09-a-daily-como-pagina.md`, commit `9a53218`) porque o
  Obsidian já lia a nota bem. Reler o ticket e trazer a lição exata para cá.

O resultado alimenta o 05 e o 06.

## Answer

**A URI é sólida e barata; a nota-painel custa quase nada mas repete o crime da página revertida;
e configuração em nota tem furo de privacidade.** Detalhes, com três níveis de evidência marcados
(documentado / verificado na máquina / observação), em
[../research/04-obsidian-como-interface.md](../research/04-obsidian-como-interface.md).

- **A URI resolve, e os valores deste vault estão levantados**: `obsidian://open?vault=<nome ou
  ID>&file=<caminho>`; `vault=` é o **nome** do vault (ou o ID), não o caminho. Deste vault: nome
  `whis-vault`, ID `245833c11ad43e6e` — **conferido em `obsidian.json`**, junto com outros dois
  vaults na máquina. Armadilha de Python anotada: `urlencode` gera `+` para espaço e a doc pede
  `%20`; usar `quote(v, safe='')`.
- **Achado que corrige o inventário**: `.md` **não tem programa associado nesta máquina** —
  `assoc .md` responde *"Associação de arquivo não encontrada"* e não há `UserChoice`
  (**conferido por mim, independentemente**). Como `bandeja.abrir_no_windows` usa
  `os.startfile`, o item de menu ***"Abrir a última nota" não abre o Obsidian hoje***: no melhor
  caso mostra o diálogo "Como você quer abrir este arquivo?", no pior devolve `SE_ERR_NOASSOC` e
  só loga. **Trocar por uma URI conserta um gesto que já existe** — é a menor entrega útil desta
  entrega inteira.
- **Com o Obsidian fechado**, o Windows *lança* o `Obsidian.exe` (o protocolo está registrado em
  `HKCU`, handler `Obsidian.exe "%1"`). O que ele faz com o argumento ao subir do zero **não foi
  testado** — testar abre o app e reescreve `workspace.json` dentro do vault. Teste de 10
  segundos está pronto no achado.
- **Comando do Obsidian por URI só com plugin de terceiro** (Advanced URI). De fábrica há `open`,
  `new`, `search`, `daily`, `unique`, `choose-vault`.
- **Nota-painel custa uma linha** (`vault.escrever`), e `daily/hoje.md` **não quebra a âncora da
  janela** (`_data_do_nome('hoje') → None`, provado). Mas ela é **um segundo artefato do mesmo
  dado, que pode divergir** — exatamente o que derrubou a página HTML no ticket 09, cuja lição é:
  a página *"existia para resolver 'o markdown é feio de ler', e essa premissa caiu"*.
- **Bases é plugin de núcleo e já está ligado** — dá tabela/dashboard sobre o frontmatter que o
  Whis já escreve, sem plugin comunitário. Dataview está parado desde 11/2025. Templater
  consegue rodar `whis daily` (System Command User Functions), **mas com timeout padrão de 5 s** —
  e a daily leva 40 —, e não existe no celular.
- **Configuração em nota tem três furos**: frontmatter não suporta aninhamento e o tipo é global
  do vault; *Excluded files* só esconde da busca, não é pasta privada; e **a nota que declara a
  pasta privada fica fora dela, logo é pesquisável pelo próprio agente**. Segredos (Deepgram,
  Linear, Slack) não podem ir para o vault, o que partiria a configuração em duas. E `.toml` não
  abre no Obsidian — pôr o `config.toml` dentro do vault não resolve nada.
- **Bug vivo no vault dele, achado de passagem**: a Daily notes do núcleo está ligada e o campo
  `data:` que **toda** nota do Whis escreve vira link clicável para uma daily note inexistente na
  raiz; clicar cria lixo. Três nomes para a mesma data.

**Pergunta que continua sendo dele** (o levantamento não pode responder): quais plugins ele usa
— este vault não tem `.obsidian/plugins/`, mas ele tem outros dois vaults —, e se tem Obsidian
Sync ativo.

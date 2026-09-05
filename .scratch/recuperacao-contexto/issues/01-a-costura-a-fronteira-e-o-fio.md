# 01 — A costura, a fronteira e o fio

**What to build:** `responder(pergunta, conversa) → Resposta` com as ferramentas de vault atrás
dela, a fronteira da pasta privada, o fio de conversa que expira em 24h, as chaves de
configuração e o fake da porta. É a camada que torna todas as outras testáveis sem rede e sem
Slack.

Contrato: **[contrato-busca.md](../contrato-busca.md)**, seções 1 a 4.

**Blocked by:** nada

**Status:** resolved

- [x] `busca.py` com `Citacao`, `Resposta`, `ErroDeBusca` e `PortaBusca`
- [x] `ferramentas.py` com `buscar_no_vault`, `ler_nota`, `listar` e `ForaDaFronteira`
- [x] `conversa.py` com `Turno` e `Conversa`, expirando por **24h de silêncio**, com relógio
      injetado e persistência em `conversas.json` ao lado do `config.toml`
- [x] `pergunta.py` com `responder`, na ordem fixa da seção 3
- [x] `[privacidade].pastas_privadas` e `[busca].maximo_de_notas`, achatadas, validadas e no
      `MODELO_DE_CONFIGURACAO`
- [x] `BuscaFake` guardando pergunta, ferramentas e histórico recebidos
- [x] **A fronteira sondada nos dois sentidos**: arquivo sob a pasta privada não aparece na busca,
      não é lido, não é listado, e `..` não escapa nem para fora do vault
- [x] A recusa diz "não existe", nunca "é privado" — dizer que há algo escondido já vaza
- [x] Arquivo de conversas corrompido não derruba nada: vale como conversa vazia
- [x] Suíte inteira verde (**713**, eram 610), sem editar teste existente

## Notas para o executor

- A checagem de fronteira é **uma função só**, usada pelas três ferramentas — mesma lição do
  filtro de exclusão do diário, que age num ponto só. Compare caminhos **resolvidos**, como
  `vault.escrever` já faz.
- A expiração é **por silêncio**: 24h desde o último turno, não meia-noite. Teste com relógio
  injetado; ninguém espera 24 horas para rodar a suíte.
- `conversas.json` não vai para o vault. Rascunho de conversa não é memória durável.

## Comments

**Camada 01 entregue e fechada** (2026-09-04). Quatro módulos novos (`busca.py`,
`ferramentas.py`, `conversa.py`, `pergunta.py`), `BuscaFake` em `fakes.py`, as duas chaves em
`configuracao.py` e no `MODELO_DE_CONFIGURACAO`, e 103 testes novos em quatro arquivos
(`test_ferramentas.py`, `test_conversa.py`, `test_pergunta.py`, `test_configuracao_busca.py`),
com o cenário em `tests/fixtures/busca.py`. Suíte em **713 verdes**, 7 desselecionados, nenhum
teste existente editado — o cenário vive num fixture novo em vez de no `conftest.py`.

**O que foi acrescentado ao contrato**, registrado na seção 8 dele para as camadas seguintes:
`LimiteDeNotas` (a chave `maximo_de_notas` precisava de alguém que a lesse, e `Ferramentas` é
o único lugar que sabe quantas notas a pergunta abriu), o arquivo `Conversas` com
`abrir`/`guardar`, `Conversa.expirar`, o `agora` de `responder`, `PerguntaVazia` e
`SEM_RESPOSTA`. Nenhum deles muda o que as seções 1 a 4 fixaram; preenchem o que elas deixaram
em aberto.

**Provas executadas:**

- **Mutação, 16 linhas quebradas de propósito**, contando os testes que caem em cada uma:
  fronteira ignora a pasta privada → 17; recusa diz "privado" → 17; busca não filtra a pasta
  privada → 4; listar mostra a pasta privada → 3; caminho absoluto passa → 1; teto de notas
  ignorado → 1; fio nunca expira → 6; janela de 24h vira 48h → 6; silêncio conta do primeiro
  turno → 1; arquivo corrompido derruba → 8; histórico não vai à busca → 2; `responder` não
  expira o fio → 1; pergunta vazia passa → 3; configuração aceita pasta fora do vault → 6;
  configuração aceita teto zero → 2. **Uma sobreviveu na primeira rodada**: tirar o
  `resolve()` de dentro da checagem única não derrubava nada, porque o teste de link simbólico
  era pulado nesta máquina (exige privilégio). Trocado por link de pasta com fallback para
  **junção do Windows**, que não exige nada: agora a mutação derruba 2 testes, e o teste roda
  aqui de verdade — junção para dentro da pasta privada e junção para fora do vault.
- **Contra o vault real do usuário, só leitura**: `listar()` devolve as cinco pastas;
  `"retenção 180"` acha 5 linhas do `diario/2026-09-03.md` (a etapa 2.1 da FN-1558 está lá);
  `"Zeno merge"` acha a decisão da reunião de 03/09 e as PRs do diário; `"daily"` acha a
  reunião de demo de 04/09. `../config.toml`, `..\..\.ssh\id_rsa`, `C:/Windows/win.ini`,
  `/etc/passwd` e `""` são recusados com a mesma frase `Não existe no vault: '...'`.
  `conversas.json` moraria em `%APPDATA%\second-brain\` — nada foi escrito.
- **A recusa é literalmente igual**: o teste compara a mensagem do privado com a do
  inexistente pela igualdade da string, não por "contém".
- **Os dois sentidos**: `notas/pessoal-trabalho.md` fica visível com `notas/pessoal` privada —
  o teste pegou uma comparação por prefixo de texto **no próprio teste** na primeira rodada, o
  que é o motivo de a vizinha existir no cenário.
- **Caixa no Windows**: conferido que `resolve()` devolve a caixa real do disco para pasta
  existente, então `Notas/Pessoal` na configuração protege `notas/pessoal`.

**Não provado**: nada com o Claude de verdade — é a camada 02. O comando de diagnóstico
`second-brain perguntar` **não** está nesta camada (o ticket não o pede e sem adaptador ele não
prova nada); entra com a 02.

**Achados fora do escopo** foram para `.scratch/fontes-passivas/DEFERRED.md`, marcados
"Recuperação de contexto, camada 01".

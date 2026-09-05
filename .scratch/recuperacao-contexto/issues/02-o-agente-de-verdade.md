# 02 — O agente de verdade

**What to build:** `busca_claude.py` — o adaptador que implementa `PortaBusca` com o Claude da
conta do usuário, expondo as ferramentas da camada 01 ao modelo e traduzindo a resposta em
`Resposta`, com citações e com o fio da conversa.

Contrato: **[contrato-busca.md](../contrato-busca.md)**, seções 1, 2 e 6.

**Blocked by:** 01

**Status:** resolved

- [x] Implementa `PortaBusca` pela conta do usuário (OAuth), recusando API key paga como
      `resumo_dia_claude` já faz
- [x] As ferramentas da camada 01 viram tool definitions; o modelo **não** recebe shell nem
      acesso a arquivo
- [x] O `historico` da conversa entra no turno, para a pergunta de acompanhamento funcionar
- [x] O prompt manda: procurar no vault antes de tudo, **citar o arquivo** de cada afirmação, e
      responder "não achei" em vez de deduzir
- [x] `ForaDaFronteira` é traduzido para o modelo como "esse arquivo não existe"
- [x] `LimiteDeNotas` é traduzido para o modelo como "responda com o que já leu" — é o freio
      de `[busca].maximo_de_notas`, não um erro (contrato, seção 8)
- [x] Resposta ilegível vira `ErroDeBusca`, com o texto cru no log
- [x] `custo_usd` a partir do `ResultMessage`, no formato da entrega anterior
- [x] Teste de tradução sem rede e um `@pytest.mark.rede` opcional, que **gasta a assinatura**
- [x] Suíte verde (**767**, eram 713), sem editar teste existente

## Notas para o executor

- O irmão mais próximo é `resumo_dia_claude.py`: mesma credencial, mesma recusa de API key paga,
  mesmo jeito de registrar custo.
- **Nunca dê `Bash` nem leitura de arquivo ao modelo.** A pasta privada só é privada porque todo
  acesso passa por `Ferramentas`.
- Uma resposta sem citação nenhuma é suspeita: registre no log, mas não invente citação.

## Comments

**Camada 02 entregue e fechada** (2026-09-04). `busca_claude.py` (adaptador, prompt, as três
ferramentas como tools de um servidor MCP em processo), `second-brain perguntar` em
`__main__.py` com a fábrica `montar_busca`, e 54 testes novos em `test_busca_claude.py` e
`test_comando_perguntar.py`. Suíte em **767 verdes**, 8 desselecionados (o oitavo é o teste
de rede desta camada), nenhum teste existente editado.

**O que foi acrescentado ao contrato**, na seção 9: `FerramentasDoVault` e
`ferramentas_permitidas()` como o ponto em que a camada 03 pendura as fontes ao vivo; o
formato da resposta com `origem` livre para os prefixos `linear:`/`slack:`/`git:`; o
comando `perguntar` com os códigos `0`/`3`/`1`. O comando entrou aqui, e não na 01, porque
sem adaptador ele não provava nada; a camada 05 documenta os códigos no `--help`.

**Provas executadas:**

- **Mutação, 15 linhas quebradas de propósito**: recusa da leitura vira exceção crua → 6;
  recusa não marcada como erro → 6; `achou` ausente vira sempre verdadeiro → 1; citação sem
  normalizar a barra → 1; fio não vai no prompt → 3; fio inteiro vai no prompt → 1; custo não
  entra na resposta → 1; API key paga passa → 3; busca não registra o que o modelo viu → 1;
  nome do servidor muda → 1; resposta sem campo nenhum passa → 1; resposta sem citação não é
  registrada → 1; não achou sai zero → 1; fio do terminal não é gravado → 3; `--sem-fio`
  ignorado → 1. Nenhuma sobreviveu.
- **O SDK sem rede**: `create_sdk_mcp_server` constrói o servidor `vault` com as três tools;
  `ClaudeAgentOptions` aceita `tools=[]` + `allowed_tools` com os nomes
  `mcp__vault__<ferramenta>` + `mcp_servers` + `strict_mcp_config`; os três esquemas JSON
  aceitam os argumentos válidos e recusam os inválidos pelo mesmo `jsonschema` que o SDK
  usa antes de chamar o handler (`listar` sem argumento é válido, de propósito).
- **A fronteira pelas tools, como o modelo a veria**: o double `ClaudeDeMentira` com
  `usar_ferramentas=True` busca, abre a nota pública e tenta a privada **pelos mesmos
  handlers que o SDK chama** — a pública volta inteira, a privada volta
  `Não existe no vault: 'notas/pessoal/terapia.md'` com `is_error`, e o texto da recusa é
  igual para caminho privado, `..`, fora do vault e inexistente (parametrizado).
- **`perguntar --fakes` pela CLI**: imprime resposta e fontes; duas chamadas seguidas deixam
  quatro turnos na chave `terminal` de `conversas.json` ao lado da configuração, e a segunda
  chamada entrega os dois primeiros turnos à busca; `--sem-fio` não cria o arquivo; não achou
  sai `3`; `ErroDeBusca` e pergunta vazia saem `1` com o motivo em `bandeja.log`.

**Não provado — e é o que falta para esta camada valer**: **nenhuma conversa com o Claude
de verdade.** O teste `test_busca_real_cita_a_nota_e_nao_ve_a_privada` existe, é
`@pytest.mark.rede` e **gasta a assinatura**; não foi rodado porque a regra da casa é pedir
antes. É ele que confirma a única coisa que o sem-rede não alcança: que o nome
`mcp__vault__<ferramenta>` em `allowed_tools` casa com o que o CLI espera. Se não casar,
em `dontAsk` toda chamada é negada em silêncio e a resposta vira "não achei" sem busca
nenhuma (está no DEFERRED). Para rodar:

```
.venv/Scripts/python.exe -m pytest tests/test_busca_claude.py -m rede -o addopts="" -q
```

ou, contra o vault real: `second-brain perguntar "o que ficou decidido sobre a retenção de 180 dias?"`.

**Achados fora do escopo** no DEFERRED, marcados "Recuperação de contexto, camada 02".

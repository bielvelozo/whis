# 01 — A costura e a fronteira

**What to build:** `responder(pergunta) → Resposta` com as ferramentas de vault atrás dela, a
fronteira da pasta privada, as chaves de configuração e o fake da porta. É a camada que torna
todas as outras testáveis sem rede.

Contrato: **[contrato-busca.md](../contrato-busca.md)**, seções 1 a 4. Leia inteiras.

**Blocked by:** nada

**Status:** ready-for-agent

- [ ] `busca.py` com `Citacao`, `Resposta`, `ErroDeBusca` e `PortaBusca`, como o contrato fixa
- [ ] `ferramentas.py` com `buscar_no_vault`, `ler_nota` e `listar`, e `ForaDaFronteira`
- [ ] `pergunta.py` com `responder`, na ordem fixa da seção 3
- [ ] `[privacidade].pastas_privadas` e `[busca].maximo_de_notas`, com os campos achatados, a
      validação e as linhas em `MODELO_DE_CONFIGURACAO`
- [ ] `BuscaFake` em `fakes.py`, guardando a pergunta e as ferramentas que recebeu
- [ ] **A fronteira sondada nos dois sentidos**: arquivo sob a pasta privada não aparece na
      busca, não é lido, não é listado, e `..` no caminho não escapa nem para fora do vault
- [ ] A recusa diz "não existe", nunca "é privado" — dizer que há algo escondido já vaza
- [ ] Pergunta vazia é recusada com mensagem em português
- [ ] Lista vazia de pastas privadas = vault inteiro visível
- [ ] Suíte inteira verde (**610 hoje**), sem editar teste existente

## Notas para o executor

- A checagem de fronteira é **uma função só**, usada pelas três ferramentas. Espalhá-la faria a
  privacidade depender de nenhuma delas esquecer — é a mesma lição do filtro de exclusão do
  diário, que age num ponto só.
- Compare caminhos **resolvidos**, como `vault.escrever` já faz. Há teste de traversal lá para
  copiar o espírito.
- `maximo_de_notas` existe para uma pergunta não varrer o vault inteiro e estourar o limite do
  Claude. Ele é do contrato, não do adaptador.

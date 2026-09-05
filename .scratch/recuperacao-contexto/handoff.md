# Handoff: recuperação de contexto — o agente no Slack

Documento de continuação. Reescrito em 2026-09-04, no fim da sessão que **construiu as cinco
camadas** desta entrega. Assume **zero contexto**: leia isto inteiro antes de tocar em
qualquer coisa.

Seu trabalho: **fechar a entrega com o usuário** — o passo humano do bot, a demo-mestra pela
DM, e o que o uso real revelar. Nenhuma linha de código está faltando para isso.

---

## 1. Onde as coisas estão

**As cinco camadas estão construídas e provadas sem rede.** Nenhuma foi provada com o Claude
de verdade nem com o Slack de verdade: a regra da casa é pedir antes de gastar a assinatura, e
o usuário não estava na sessão.

| | |
|---|---|
| suíte | **859 verdes**, 8 desselecionados (7 antigos + o teste de rede da busca) |
| último commit | a camada 05 (`git log --oneline -6` mostra as cinco) |
| tickets | 01, 02, 03 `resolved`; 04 e 05 `ready-for-human` |
| contrato | `contrato-busca.md`, seções 8 a 12 são os adendos de cada camada — **leia-as**, é a API real |

### Verifique antes de começar

```bash
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m second_brain perguntar --fakes --sem-fio "teste"
git log --oneline -8
```

859 passam, 8 desselecionados. O `perguntar --fakes` imprime a resposta de exemplo e sai `0`.

## 2. O que ler, nesta ordem

1. `CONTEXT.md`, depois `spec.md` e `contrato-busca.md` (seções 1–7 são o desenho, 8–12 o
   que foi construído por cima).
2. Os cinco tickets em `issues/`, **do fim para o começo**: cada `## Comments` tem as provas
   executadas, as decisões surfaceadas e o que **não** foi provado.
3. `docs/smoke-atendente.md` — o roteiro do passo humano e da demo-mestra. É o que o usuário
   vai seguir.
4. `.scratch/fontes-passivas/DEFERRED.md` — os achados desta entrega estão marcados
   "Recuperação de contexto, camada NN".

## 3. As decisões do usuário — herde, não reabra

As da versão anterior deste handoff continuam valendo (DM do Slack, fio de 24h por silêncio,
pasta privada, ferramentas em vez de vault cru, recusa "não existe", fontes ao vivo pelos
coletores, bot e não user token, processo separado da bandeja, toda resposta cita). Ele
**ainda não escolheu a pasta privada**: `[privacidade].pastas_privadas` continua vazia na
máquina dele.

## 4. As decisões desta sessão, tomadas sem o usuário

Tudo está nos comentários dos tickets; o resumo do que ele pode querer reabrir:

- **`slack_sdk` virou dependência** (camada 04). O ambiente não tinha websocket nenhum.
- **`anotar <texto>` na DM** é a única escrita em `notas/` — prefixo explícito, sem passar
  pelo modelo, pelo mesmo `vault.anotar_ponto` do `daily --anotar`.
- **`LimiteDeNotas`** em `Ferramentas.ler_nota`: o freio de `[busca].maximo_de_notas`, que
  senão seria letra morta.
- **A resposta do modelo é JSON obrigatório**; prosa vira `ErroDeBusca`.
- **`--fakes` no `atender` troca só a busca**: a DM é sempre o Slack real. É o ensaio barato.
- **A camada 04 editou `configuracao.py`** (os dois tokens), contra a regra do contrato; está
  registrado na seção 11.

## 5. O passo humano, e o que ele destrava

Está inteiro em `docs/smoke-atendente.md`, passos 1 a 6: bot na app existente, scopes
`im:history`, `im:read`, `chat:write`, `reactions:write`, Socket Mode, app-level token
`xapp-` com `connections:write`, evento `message.im`, **pedido novo ao admin** (texto pronto no
passo 5), reinstalar, colar `bot_token` e `app_token` no `config.toml`.

**Atenção**: reinstalar a app **troca o user token** do coletor. O roteiro avisa.

## 6. A ordem para provar, quando ele autorizar

1. `second-brain atender --fakes` + uma mensagem na DM → reação 👀 e resposta de exemplo.
   Prova o Slack sem gastar nada.
2. `second-brain perguntar --sem-fio "..."` → prova o Claude sem o Slack. **Gasta a
   assinatura.** É aqui que se confirma a única coisa que o sem-rede não alcança: que
   `mcp__vault__<ferramenta>` em `allowed_tools` casa com o que o CLI espera (DEFERRED,
   camada 02). Se toda resposta vier "não achei" com `0 notas lidas` no log, é isso.
3. `.venv/Scripts/python.exe -m pytest tests/test_busca_claude.py -m rede -o addopts="" -q`
   — o teste de rede, com vault de fixture e pasta privada.
4. `second-brain atender` e a demo-mestra do passo 8 do roteiro, pelo celular.
5. Passo 9: a pasta privada, com um fato plantado.

## 7. Armadilhas já pagas — não redescubra

As dos handoffs anteriores continuam (python do venv, nada de heredoc Python com acento,
logger `second_brain.fonte_slack`, `total_cost_usd` não é cobrança, Socket Mode exige
app-level + bot). Acrescente:

- **`startswith(pasta_privada)` é armadilha de prefixo**: `notas/pessoal-trabalho.md` não está
  sob `notas/pessoal/`. O cenário de teste planta a vizinha de propósito; compare com `/`.
- **`Path("/fora").is_absolute()` é falso no Windows.** A validação confere o `/` inicial.
- **Link simbólico exige privilégio; junção não.** `_winapi.CreateJunction` é o que faz o
  teste de link rodar nesta máquina.
- **`create_sdk_mcp_server` valida os argumentos com `jsonschema`** antes do handler: um
  parâmetro opcional precisa de `"required": []` em esquema JSON, não de dict-style.
- **O `caplog` não vê o que foi logado antes de o handler de arquivo entrar**: no `atender`,
  o arquivo de log é ligado antes de `montar_busca`, para o aviso de FAKE ficar no rastro.

## 8. O padrão de trabalho desta casa

Continua o da versão anterior: contrato antes, executor por camada, orquestrador executa as
provas, **mutação em cada linha que importa** (as contagens estão nos tickets), achados no
DEFERRED, comentário de entrega com provas, `Status` no ticket, teste existente não se edita.
Os quatro cenários de teste desta entrega vivem em `tests/fixtures/busca.py`; o harness HTTP
do Slack é importado de `tests/test_fonte_slack.py`.

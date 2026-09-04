# Contrato: a busca, as ferramentas e a fronteira

Decisão do orquestrador, fixada **antes** de abrir qualquer camada, para que a costura, o
adaptador real, as duas entradas e as fontes ao vivo sejam construídos contra o mesmo formato.
Não substitui nenhuma decisão da [spec](spec.md) — fecha o que ela deixou em aberto entre
camadas. Executor que discordar **surfaceia ao orquestrador**, não altera sozinho.

A lição das duas entregas anteriores vale aqui: **a camada 01 escreve todas as chaves de
configuração de uma vez**, e ninguém mais toca `configuracao.py`.

---

## 1. Os tipos (`src/second_brain/busca.py`, dono: camada 01)

```python
@dataclass(frozen=True)
class Citacao:
    """De onde uma afirmação veio — sempre um arquivo do vault ou uma fonte."""
    origem: str            # "diario/2026-09-03.md" | "linear:FN-1610" | "slack:#dev-codereview"
    trecho: str = ""       # o pedaço que sustentou a afirmação, quando houver


@dataclass(frozen=True)
class Resposta:
    """O que a busca devolve. `texto` vazio com `achou=False` é 'não sei'."""
    texto: str
    citacoes: tuple[Citacao, ...] = ()
    achou: bool = True
    custo_usd: float | None = None


class ErroDeBusca(RuntimeError):
    """A busca não pôde ser feita — sem credencial, sem rede, resposta ilegível."""


@runtime_checkable
class PortaBusca(Protocol):
    def perguntar(self, pergunta: str, ferramentas: "Ferramentas") -> Resposta: ...
```

`Resposta.achou=False` é **resposta legítima**, não erro: "não achei isso no vault" é o que
impede o usuário de confundir invenção com memória. `ErroDeBusca` é para o que impediu a busca
de acontecer.

## 2. As ferramentas (`src/second_brain/ferramentas.py`, dono: camada 01)

O agente **não recebe o vault cru**. Recebe este objeto, e é aqui que a fronteira mora:

```python
class Ferramentas:
    def __init__(self, configuracao: Configuracao) -> None: ...

    def buscar_no_vault(self, termo: str, *, limite: int = 30) -> tuple[Achado, ...]: ...
    def ler_nota(self, caminho: str) -> str: ...
    def listar(self, pasta: str = "") -> tuple[str, ...]: ...
```

Regras que valem para **todas** elas, e que a camada 01 fixa em um ponto só:

- **Nenhuma abre nada fora do vault.** A checagem é no caminho **resolvido**, como
  `vault.escrever` já faz: `..` no meio não escapa.
- **Nenhuma abre nada sob `[privacidade].pastas_privadas`.** Nem em busca, nem em leitura, nem em
  listagem, nem sob pedido explícito do usuário. Um arquivo privado **não existe** para o agente.
- **Nenhuma escreve.** Escrita é outro caminho, sob pedido explícito, por `vault.escrever` com
  zonas (camada 03).
- Caminho recusado levanta `ForaDaFronteira`, que o adaptador traduz para o modelo como "esse
  arquivo não existe" — e **não** como "esse arquivo é privado". Dizer que existe algo escondido
  já é vazar o que a pasta privada promete esconder.

```python
@dataclass(frozen=True)
class Achado:
    caminho: str       # relativo ao vault
    linha: int
    trecho: str


class ForaDaFronteira(RuntimeError): ...
```

## 3. A costura (`src/second_brain/pergunta.py`, dono: camada 01)

```python
def responder(
    pergunta: str,
    *,
    configuracao: Configuracao,
    busca: PortaBusca,
) -> Resposta
```

Ordem fixa:

1. Recusa pergunta vazia, com mensagem em português.
2. Monta `Ferramentas(configuracao)`.
3. Chama `busca.perguntar(pergunta, ferramentas)`.
4. `ErroDeBusca` sobe para a CLI, que decide o código de saída.
5. Registra no log o que foi perguntado, quantas citações voltaram e o custo.

## 4. Configuração — todas as chaves de uma vez (dono: camada 01)

```toml
[privacidade]
pastas_privadas = []       # pastas do vault que a busca nunca abre (relativas ao vault)

[busca]
maximo_de_notas = 40       # teto de notas lidas numa pergunta, para uma pergunta não varrer o vault
```

Campos achatados: `privacidade_pastas_privadas: tuple[str, ...] = ()` e
`busca_maximo_de_notas: int = 40`. `MODELO_DE_CONFIGURACAO` ganha as duas com comentário.
Configuração antiga continua carregando.

## 5. Como cada camada entra

| camada | entrega | não toca |
|---|---|---|
| 01 | `busca.py`, `ferramentas.py`, `pergunta.py`, as chaves, o fake | — |
| 02 | `busca_claude.py`: o adaptador real, o prompt, as tool definitions | `pergunta.py`, `ferramentas.py` |
| 03 | `perguntar` e `chat` na CLI, e a escrita em `notas/` sob pedido | `busca.py` |
| 04 | as fontes ao vivo como ferramentas, pelos coletores existentes | a fronteira da camada 01 |
| 05 | log, códigos de saída, custo, `docs/smoke-busca.md` | — |

## 6. O que nenhuma camada deve fazer

- **Nenhuma dá ao modelo acesso a shell, a `Bash` ou ao sistema de arquivos direto.** A fronteira
  da pasta privada só existe porque todo acesso passa por `Ferramentas`.
- **Nenhuma camada além da 01 edita** `configuracao.py`, `busca.py`, `ferramentas.py` ou
  `pergunta.py`. Precisou? Surfaceia.
- **Nenhuma reimplementa coletor de fonte.** A camada 04 chama `fonte_git`, `fonte_linear` e
  `fonte_slack` pelas fábricas `de_configuracao` — é o que faz a blocklist do Slack e o
  `so_com_mencao` continuarem valendo na consulta ao vivo.
- **Nenhum teste novo fala com serviço real** fora de `@pytest.mark.rede`.
- **Nenhum segredo em teste, fixture ou doc.**

## 7. A demo-mestra

A pergunta que fecha a entrega, feita na máquina do usuário, com o vault real:

> `second-brain perguntar "o que ficou decidido sobre a retenção de 180 dias?"`

**Sucesso**: a resposta cita pelo menos um arquivo do vault que o usuário reconhece, diz o que
foi decidido, e ele confere abrindo o arquivo citado. Se a decisão não estiver no vault, a
resposta diz que não achou — e isso também é sucesso.

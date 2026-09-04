# Contrato: a busca, as ferramentas e a fronteira

Decisão do orquestrador, fixada **antes** de abrir qualquer camada, para que a costura, o
adaptador real, as fontes ao vivo e a DM do Slack sejam construídos contra o mesmo formato.
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
    def perguntar(
        self,
        pergunta: str,
        ferramentas: "Ferramentas",
        historico: tuple["Turno", ...] = (),
    ) -> Resposta: ...
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
- **Nenhuma escreve.** Escrita é outro caminho, sob pedido explícito na conversa, por
  `vault.escrever` com zonas (camada 04).
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
    conversa: Conversa | None = None,
) -> Resposta
```

Ordem fixa:

1. Recusa pergunta vazia, com mensagem em português.
2. Monta `Ferramentas(configuracao)`.
3. Chama `busca.perguntar(pergunta, ferramentas, historico=conversa.historico if conversa else ())`.
4. Acrescenta a pergunta e a resposta ao fio da conversa.
5. `ErroDeBusca` sobe para quem chamou, que decide o que fazer.
6. Registra no log o que foi perguntado, quantas citações voltaram e o custo.

### O fio de 24 horas (`src/second_brain/conversa.py`, dono: camada 01)

```python
@dataclass(frozen=True)
class Turno:
    quem: str          # "usuario" | "agente"
    texto: str
    momento: datetime  # aware


class Conversa:
    """O fio de uma DM, que expira depois de 24h de silêncio."""
    def historico(self) -> tuple[Turno, ...]: ...
    def acrescentar(self, quem: str, texto: str, *, agora: datetime) -> None: ...
```

- **Expira por silêncio, não por relógio de parede**: 24 horas desde o **último** turno. Uma
  conversa ativa às 23h continua no dia seguinte; uma parada há 25 horas começa limpa.
- **Mora ao lado do `config.toml`**, em `conversas.json`, e **não no vault**: é rascunho de
  conversa, e o vault guarda memória durável, não rascunho.
- **O relógio é injetado** (`agora`), porque a expiração é comportamento e precisa de teste sem
  esperar 24 horas.
- Arquivo corrompido ou ilegível **não derruba o atendimento**: vale como conversa vazia.

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
| 01 | `busca.py`, `ferramentas.py`, `conversa.py`, `pergunta.py`, as chaves, o fake | — |
| 02 | `busca_claude.py`: o adaptador real, o prompt, as tool definitions | `pergunta.py`, `ferramentas.py` |
| 03 | as fontes ao vivo como ferramentas, pelos coletores existentes | a fronteira da camada 01 |
| 04 | `atendente.py` + `second-brain atender`: a DM do Slack por Socket Mode | `busca.py`, `conversa.py` |
| 05 | logon, log, custo, `docs/smoke-atendente.md` | — |

A camada 04 é a única que depende da aprovação do admin. As três primeiras se provam pelo
comando de diagnóstico `second-brain perguntar`, que existe **para teste**, não como caminho
principal.

## 6. O que nenhuma camada deve fazer

- **Nenhuma dá ao modelo acesso a shell, a `Bash` ou ao sistema de arquivos direto.** A fronteira
  da pasta privada só existe porque todo acesso passa por `Ferramentas`.
- **Nenhuma camada além da 01 edita** `configuracao.py`, `busca.py`, `ferramentas.py` ou
  `pergunta.py`. Precisou? Surfaceia.
- **Nenhuma reimplementa coletor de fonte.** A camada 03 chama `fonte_git`, `fonte_linear` e
  `fonte_slack` pelas fábricas `de_configuracao` — é o que faz a blocklist do Slack e o
  `so_com_mencao` continuarem valendo na consulta ao vivo.
- **Nenhum teste novo fala com serviço real** fora de `@pytest.mark.rede`.
- **Nenhum segredo em teste, fixture ou doc.**

## 7. A demo-mestra

O gesto que fecha a entrega, na máquina do usuário, com o vault real:

> O usuário manda **na DM do Slack**, do celular: *"o que ficou decidido sobre a retenção de 180
> dias?"* — e a resposta chega ali, citando um arquivo do vault.

**Sucesso**: ele reconhece o arquivo citado, abre e confere. Depois manda uma pergunta de
acompanhamento (*"e quem levantou isso?"*) e o agente responde **sem ele repetir o assunto** —
que é a prova do fio de 24 horas. Se a decisão não estiver no vault, a resposta diz que não
achou, e isso também é sucesso.

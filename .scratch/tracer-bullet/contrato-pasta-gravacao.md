# Contrato: pasta de gravação e configuração

Decisão do orquestrador, tomada antes de abrir as camadas 01 e 02 em paralelo, para
que os dois lados construam contra o mesmo formato e não haja retrabalho. Não
substitui nenhuma decisão da spec — só fixa o que a spec deixou em aberto entre
camadas. Executor que discordar **surfaceia ao orquestrador**, não altera sozinho.

## Pasta de gravação

Produzida pelo ticket 02 (gravador), consumida pelos tickets 01, 03 e 06 (pipeline):

```
<gravacoes>/YYYY-MM-DD-HHMM-<slug>/
  microfone.wav     # minha voz
  sistema.wav       # a voz dos outros (loopback WASAPI)
  gravacao.json     # metadados, escritos pelo gravador ao parar
  estado.json       # escrito pelo pipeline (ticket 01), nunca pelo gravador
```

- `<slug>`: slug do título informado ao iniciar a gravação; **`reuniao`** quando não houver.
- Os dois WAV são **mono, PCM 16-bit**, cada um na taxa nativa do seu dispositivo
  (sem resample no gravador — o STT aceita taxas distintas). Canais separados são
  o que garante "eu vs. os outros" sem depender de diarização.
- A pasta vive **fora do vault**, no caminho `gravacoes` da configuração.

### `gravacao.json` (dono: ticket 02)

```json
{
  "versao": 1,
  "titulo": "daily do time",
  "inicio": "2026-08-20T14:30:12-03:00",
  "fim": "2026-08-20T15:02:44-03:00",
  "duracao_s": 1952.4,
  "canais": {
    "microfone": {"arquivo": "microfone.wav", "taxa_hz": 48000, "canais": 1,
                  "dispositivo": "Grupo de microfones (Realtek(R) Audio)", "offset_inicio_s": 0.0},
    "sistema":   {"arquivo": "sistema.wav", "taxa_hz": 48000, "canais": 1,
                  "dispositivo": "Voicemeeter In 5 [Loopback]", "offset_inicio_s": 0.04}
  }
}
```

`titulo` pode ser `null`. Um canal ausente (ex.: falha no loopback) é registrado como
`null` em `canais` — o pipeline decide o que fazer, o gravador só reporta.

### `estado.json` (dono: ticket 01, estendido por 03 e 06)

```json
{
  "versao": 1,
  "status": "transcrito",
  "processado_em": "2026-08-20T15:05:10-03:00",
  "nota": "reunioes/2026-08-20-1430-daily-do-time.md",
  "transcricao": "transcricoes/2026-08-20-1430-daily-do-time.md",
  "erro": null
}
```

`status` ∈ `pendente` | `transcrito` | `falhou`. É a fonte de verdade da retenção
(ticket 06): só `transcrito` com mais de N dias é apagado; `falhou` e `pendente`
nunca são apagados. É também a base da idempotência: reprocessar uma pasta já
`transcrito` não duplica notas.

## Nomes no vault

- Nota: `reunioes/YYYY-MM-DD-HHMM-<slug>.md`
- Transcrição: `transcricoes/YYYY-MM-DD-HHMM-<slug>.md` (mesmo basename)

O prefixo vem **da pasta de gravação**, não do relógio do processamento — é o que
torna o reprocesso determinístico. O `HHMM` é acréscimo ao `YYYY-MM-DD-nome` da
spec: mantém a navegação por data (user story 10) e elimina colisão entre duas
reuniões no mesmo dia sem título distinto.

## Configuração

Arquivo TOML local, lido de `%APPDATA%\second-brain\config.toml`, com override pela
variável de ambiente `SECOND_BRAIN_CONFIG` (é assim que os testes apontam para um
tmp_path). Nunca versionado — `config.toml` está no `.gitignore`.

```toml
vault = "C:/Users/gabri/second-brain-vault"
gravacoes = "C:/Users/gabri/second-brain-gravacoes"
retencao_dias = 7

[deepgram]
api_key = ""       # crédito de US$ 200; vazio = adapter real indisponível

[audio]
dispositivo_microfone = ""   # vazio = dispositivo de entrada padrão
dispositivo_sistema = ""     # vazio = get_default_wasapi_loopback()
```

Chaves em português, como o resto do projeto. Quem precisar de uma chave nova
acrescenta sem renomear as existentes.

## Portabilidade: a máquina de destino não é a de desenvolvimento

O usuário rodará o coletor **em outra máquina** (o mapa registra: desenvolvimento
neste notebook, destino no PC desktop). Nada pode ser amarrado ao hardware daqui.

- **Nenhum índice ou nome de dispositivo fixo no código.** A seleção vem da
  configuração; vazio significa "padrão do sistema"
  (`get_default_wasapi_loopback()` / dispositivo de entrada padrão).
- Um subcomando **lista os dispositivos** de forma legível — é a ferramenta com que
  o usuário preenche a configuração numa máquina que o agente nunca viu.
- O aviso de **canal de sistema mudo** é obrigatório e precisa dizer como consertar:
  num ambiente de roteamento desconhecido, sair mudo é o modo de falha esperado.
- Roteiros e exemplos de configuração usam placeholder, nunca valores desta máquina.

Como referência de desenvolvimento apenas — **não é o ambiente de destino e não
entra no código**: esta máquina tem Voicemeeter + VB-Cable e a saída padrão do
Windows é um dispositivo virtual (`Voicemeeter In 5`), não o fone físico. Serviu
para confirmar que `get_default_wasapi_loopback()` não garante capturar o áudio do
Meet — o que é exatamente a razão de o dispositivo ser configurável.

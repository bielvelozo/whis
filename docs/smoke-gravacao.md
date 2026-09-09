# Smoke manual: gravação de reunião

Roteiro curto para validar o gravador (`python -m whis.gravador`) numa
máquina Windows 11 nativa, com fone conectado e um Google Meet real. É a
validação do que fica fora da costura de teste automatizada: a captura WASAPI.

Tempo: ~10 minutos, sendo ~1 minuto de reunião real.

Rode tudo de dentro do repositório, com o interpretador do ambiente virtual. Nos
exemplos abaixo, `python` significa `.venv\Scripts\python.exe`.

## Passo 0 — Pré-requisitos

1. Fone **conectado** e sendo usado como saída de áudio do Windows.
2. Um `config.toml` em `%APPDATA%\whis\` com, no mínimo:

   ```toml
   gravacoes = "C:/Users/<seu-usuario>/whis-gravacoes"

   [audio]
   dispositivo_microfone = ""   # vazio = microfone padrão do Windows
   dispositivo_sistema   = ""   # vazio = loopback da saída padrão do Windows
   ```

   Use barras normais (`/`) nos caminhos.

**Sucesso:** o arquivo existe e a pasta de `gravacoes` fica **fora** do vault.

## Passo 1 — Conferir qual dispositivo cada canal vai usar

```
python -m whis.gravador dispositivos
```

Lê a lista e olhe o bloco **"Seleção atual"** no final.

**Sucesso:** as duas linhas terminam com o nome de um dispositivo real:

```
  microfone: vazio (padrão do sistema) → '<nome do seu microfone>'
  sistema: vazio (padrão do sistema) → '<nome da sua saída> [Loopback]'
```

**Falha:** se alguma linha disser `NÃO RESOLVE`, copie o nome **completo** do
dispositivo certo da lista acima e cole na chave correspondente do `config.toml`
(`dispositivo_microfone` ou `dispositivo_sistema`). Nunca use o número entre
colchetes: o índice muda entre reinícios e entre máquinas.

## Passo 2 — Teste de 10 segundos antes de entrar na reunião

Deixe **um vídeo ou música tocando no fone** e rode:

```
python -m whis.gravador testar --segundos 10
```

Fale alguma coisa durante os 10 segundos.

**Sucesso:** as duas últimas linhas marcam `OK` e o comando termina com código 0:

```
  microfone.wav: OK · ... · RMS 300.5 · ...
  sistema.wav:   OK · ... · RMS 2100.3 · ...
```

**Falha:** se `sistema.wav` sair `MUDO`, vá para [Quando o canal de sistema sai
mudo](#quando-o-canal-de-sistema-sai-mudo) antes de continuar. Se `microfone.wav`
sair `MUDO`, confira se o microfone não está no mudo/desconectado e se a linha
`microfone:` do passo 1 aponta para o microfone que você usa.

## Passo 3 — Iniciar a gravação já dentro do Meet

Entre na reunião, confira que você ouve o outro lado, e rode:

```
python -m whis.gravador gravar --titulo "smoke do gravador"
```

**Sucesso:** aparece `GRAVANDO em <pasta>` com a pasta datada
(`YYYY-MM-DD-HHMM-smoke-do-gravador`) e duas linhas de log dizendo de qual
dispositivo cada canal está gravando. Nenhuma interação é necessária daqui até o
passo 5.

## Passo 4 — Um minuto de reunião de verdade

Com a gravação rodando:

1. Fale por ~20 segundos.
2. Peça para o outro lado falar por ~20 segundos (você só ouve, calado).
3. Fale mais ~20 segundos.

**Sucesso:** passou ~1 minuto sem nenhum aviso `MUDO` no terminal. Se o aviso
aparecer, pare agora e vá para a seção de conserto — a reunião inteira sairia sem
a voz dos outros.

## Passo 5 — Parar

Pressione **ENTER** no terminal.

**Sucesso:** aparece `gravação encerrada: <pasta>` seguido da conferência, com as
duas linhas `OK` e o `gravacao.json` listado:

```
  gravacao.json: versao=1 titulo='smoke do gravador' inicio=... fim=... duracao_s=6x.xx
  microfone.wav: OK · 48000 Hz · 1 canal(is) · 16 bits · 6x.x s · RMS ... · pico ...
  sistema.wav:   OK · 44100 Hz · 1 canal(is) · 16 bits · 6x.x s · RMS ... · pico ...
```

As taxas dos dois arquivos **podem ser diferentes** — cada canal grava na taxa
nativa do seu dispositivo, e isso é esperado. As durações devem bater entre si com
diferença de menos de 1 segundo.

## Passo 6 — Ouvir os dois arquivos

Abra a pasta indicada e toque os dois WAV em qualquer player.

**Sucesso, e este é o critério que fecha o smoke:**

- `microfone.wav` — **só a sua voz**, audível; os ~20 segundos em que o outro lado
  falou são silêncio.
- `sistema.wav` — **só a voz dos outros**, audível; os trechos em que só você falou
  são silêncio.

É essa separação que dá o "eu vs. os outros" na transcrição sem depender de
diarização. Se as duas vozes aparecerem misturadas nos dois arquivos, reporte: a
máquina tem um roteamento de áudio devolvendo o microfone para a saída.

## Passo 7 — Conferir os metadados

```
python -m whis.gravador conferir "<caminho da pasta>"
```

**Sucesso:** código de saída 0 e o `gravacao.json` com `versao`, `titulo`,
`inicio`, `fim`, `duracao_s` e um bloco por canal (`arquivo`, `taxa_hz`,
`canais: 1`, `dispositivo`, `offset_inicio_s`). Nenhum canal pode estar `null`.

Guarde a pasta: ela é exatamente o que o pipeline consome depois.

## Quando o canal de sistema sai mudo

É a falha mais provável, e quase sempre significa "o loopback capturado não é o
dispositivo por onde o som está saindo de verdade" — comum quando existe um mixer
ou cabo de áudio virtual instalado, porque aí a saída padrão do Windows pode ser
um dispositivo virtual em vez do fone.

1. Descubra por onde o som está saindo: **Configurações → Sistema → Som → Saída**
   (ou o ícone de volume na bandeja), com um vídeo tocando.
2. Liste os dispositivos:

   ```
   python -m whis.gravador dispositivos
   ```

3. Ache na lista a entrada marcada como `loopback` cujo nome corresponde à saída
   do item 1 (o nome termina em `[Loopback]`).
4. Cole o nome **completo** no `config.toml`:

   ```toml
   [audio]
   dispositivo_sistema = "<nome exato copiado da lista, com [Loopback]>"
   ```

5. Repita o **passo 2** até `sistema.wav` sair `OK`.

Se não estiver claro qual é o dispositivo certo, teste os candidatos um a um:
troque `dispositivo_sistema`, deixe um áudio tocando e rode
`python -m whis.gravador testar --segundos 5`. O certo é o que dá `OK` com
RMS bem acima de zero.

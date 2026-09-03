# 02 — Gravador WASAPI sob demanda

**What to build:** A captura de áudio da reunião: um script/CLI que, ao iniciar, grava simultaneamente o microfone e o loopback WASAPI (a voz dos outros no fone) em **canais/arquivos separados** dentro de uma pasta de gravação datada, e para sob comando. É a matéria-prima do pipeline: a pasta produzida aqui é exatamente o que o ticket 01 consome. Validação por smoke manual (fora da costura de teste, conforme a spec): gravar ~1 minuto de um Meet real e conferir os dois arquivos audíveis.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] Iniciar/parar gravação por comando, sem interação extra durante a reunião
- [x] Microfone e áudio do sistema gravados em canais/arquivos separados, sincronizados o suficiente para transcrição
- [x] Gravações salvas em pasta datada, fora do vault, no local configurado
- [x] Funciona no Windows 11 nativo (sem WSL/Docker), com fone conectado
- [x] Roteiro de smoke manual curto documentado no repo e executado com sucesso num Meet real

## Comments

**Camada 02 entregue** — `src/second_brain/gravador.py` (módulo + CLI `python -m second_brain.gravador`) e `docs/smoke-gravacao.md`.

O que a camada 05 chama, sem lógica própria na bandeja: `Gravador(configuracao=None, *, titulo=None)`, `.iniciar(titulo=None) -> Path`, `.parar() -> Path`, propriedades `.gravando` / `.pasta` / `.configuracao` e `.niveis() -> dict[str, float]` (RMS corrente por canal, para a bandeja mostrar canal mudo). Subcomandos: `dispositivos`, `gravar`, `testar`, `conferir`.

Verificado nesta máquina de desenvolvimento (o ambiente de destino é outro; a audibilidade só o smoke do usuário prova): gravação de 45 s com tom de 440 Hz tocado entre os segundos 15 e 30 na saída padrão — `sistema.wav` deu RMS 0 nas janelas de 0–10 s, 6195 nas de 15–30 s e 0 de novo depois, o que prova captura de loopback e alinhamento entre os dois arquivos; `microfone.wav` 48000 Hz mono 16-bit 45,0 s RMS 461 e `sistema.wav` 48000 Hz mono 16-bit 45,2 s RMS 3666. Também exercitados: canal de sistema mudo (aviso aos 20 s + veredito `MUDO` e código de saída 1), dispositivo inexistente (grava só o microfone e escreve `"sistema": null`), nome ambíguo, configuração ausente e o preenchimento de silêncio pelo relógio (3 s sem frames → 3,0 s de silêncio; áudio real chegando depois não duplica).

Achados registrados em `.scratch/tracer-bullet/DEFERRED.md`: leitura de configuração duplicada entre `gravador.py` e `configuracao.py` (camadas em paralelo, unificação é do orquestrador); não há `parar` a partir de outro processo (a bandeja chama a API no mesmo processo); troca de dispositivo no meio da gravação não é tratada; WAV sem compressão ocupa ~5,3 MB/min por canal; `offset_inicio_s` é registrado mas ninguém consome.

Nenhum conflito com a spec, o ADR 0001 ou o contrato. O único critério de aceite que não fecha sozinho é o último: o roteiro de smoke está escrito, mas a execução num Meet real é do usuário.

**Revisão do orquestrador — código fechado, smoke pendente com o usuário.**

Verificações que eu mesmo executei, sem reaproveitar a análise do executor:
gravei 15 s pela API tocando um tom de 440 Hz apenas entre 5,0 s e 10,0 s; o tom
aparece exatamente nas janelas 5,0 s e 7,5 s do `sistema.wav` (RMS 8375 e 8481),
com zero antes e depois — captura, separação de canais e alinhamento provados.
`gravacao.json` no formato exato do contrato, com `offset_inicio_s` nos dois
canais. `grep` confirma que não há índice nem nome de dispositivo fixo no
código, e `_resolver_dispositivo` não privilegia fabricante — o coletor roda numa
máquina que ninguém conhece.

Um defeito foi encontrado e corrigido na revisão: a CLI quebrava com
`UnicodeEncodeError` quando a saída não era um console interativo (cp1252), o que
derrubava justamente `dispositivos` — o comando de diagnóstico numa máquina nova
e o passo 1 do roteiro de smoke. Corrigido na causa (UTF-8 forçado em
`stdout`/`stderr` na entrada da CLI, cobrindo também o `--help` e os logs), não
no caractere. Revalidado por mim com a saída redirecionada: `dispositivos`,
`conferir` e `--help` em exit 0 e texto legível.

**O que falta:** o critério "roteiro de smoke executado com sucesso num Meet
real". O roteiro está pronto em `docs/smoke-gravacao.md`; a execução é do
usuário, **na máquina de destino** — esta não é ela, e o roteamento de áudio é
justamente o que difere entre as duas. Por isso o status é `ready-for-human` e
não `resolved`.

**Fechada por uma reunião real (2026-09-03).** 40 minutos de reunião de trabalho
gravados nesta máquina, com fone: `microfone.wav` 220 MB e `sistema.wav` 202 MB,
os dois canais com nível saudável do começo ao fim (sistema ~2700, microfone 229
no encerramento) e nenhum aviso de canal mudo em 2403 s de captura.

A prova de que a separação "eu vs. os outros" funciona veio mais forte do que
ouvir os WAV: a transcrição saiu com **223 falas no canal do microfone e 400 no
do sistema**, atribuídas corretamente, e o usuário confirmou que o resumo é fiel
ao que foi discutido. Se os canais estivessem misturados, os dois lados
apareceriam nos dois arquivos e o resumo seria incoerente.

Ressalva de honestidade: o roteiro `docs/smoke-gravacao.md` não foi percorrido
passo a passo — o passo 2 (teste de 8 s) foi executado e deu `OK` nos dois
canais; os demais foram substituídos pela reunião real, que é o que os passos
existem para provar.

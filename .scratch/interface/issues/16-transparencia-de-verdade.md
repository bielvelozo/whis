# 16 — Camada 9: a transparência de verdade, com o de trás desfocado

Type: task
Status: resolved
Blocked by: 15

**What to build:** a quarta prova dele (2026-09-17, com a camada 8 corrigida no ar): *"agora ficou
bom, fundo todo preto mas não está transparente"*. Preto **e** deixando ver o que está atrás, como
o Raycast.

O que já ficou provado e fecha as portas óbvias (tickets 14 e 15): o acrílico do DWM neste build não
amostra as janelas atrás de um popup, só o papel de parede; e um `-alpha` na janela mostra o de
trás **nítido** — texto legível através do painel, que foi o que ele reprovou como "não está preto".

- [x] **Acrílico simulado.** No instante de abrir, com a janela ainda escondida, capturar a tela na
      região onde a palheta vai ficar (GDI, `BitBlt` do DC da tela — em processo sem DPI awareness
      as coordenadas são as do Tk e a captura sai na resolução lógica, ~8 ms), desfocar (reduzir
      4×, Gaussian, ampliar), escurecer com o `FUNDO` e usar como imagem de fundo do canvas. O
      painel deixa de ser opaco na aparência: o que está atrás aparece como manchas desfocadas,
      como no Raycast/macOS. Tudo antes do primeiro `deiconify`, sem piscar.
- [x] Sem o acrílico do DWM (o material somaria por cima da imagem) e sem `-alpha`; cantos pelo DWM
      como antes, e no fallback a própria imagem leva os cantos na cor-chave.
- [x] O campo (`Text`, opaco) recebe a cor média da faixa desfocada embaixo dele; as linhas não
      selecionadas ficam sem preenchimento (o realce só na selecionada); os gestos de apontar e
      clicar passam a ser do canvas por geometria, não por item.
- [x] `acrilico.py` vira `dwm.py` (só `hwnd_da_raiz` e `arredondar_cantos`); a política do acrílico
      sai com os testes dela. O desfoque e a tinta ficam numa função pura testável sem tela.
- [x] Suíte verde; prova de tela sob `pythonw` (abrir, esconder, abrir de novo — o fundo acompanha o
      que está atrás a cada abertura); bandeja dele reiniciada pela rota, esperando a de parar acabar.

## Notas para o executor

- Nunca simule o atalho real dele (`ctrl+space`) com a bandeja no ar.
- O `ImageGrab.grab(bbox)` do Pillow interpreta a caixa em pixels **físicos** e captura a tela inteira
  antes de recortar (~45–90 ms): não serve para a região do Tk. Sonda em
  `research/sonda-acrilico-simulado.py`.

## Comments

**Camada 9 entregue e fechada** (2026-09-17; direto na sessão principal, na quarta prova dele).

- `fundo_desfocado.py`: `capturar_atras` (BitBlt do DC da tela, ~8 ms, coordenadas do Tk porque o
  processo não tem DPI awareness — `HORZRES` do DC é 1536, o lógico), `desfocar` (reduz 4×, Gaussian
  5, amplia, `Image.blend` com o `FUNDO` a 0.84, cantos de fora na cor-chave) e `cor_media` para o
  campo. `dwm.py` fica só com os cantos; o acrílico do DWM e o liga-desliga da camada 8 saíram.
- A janela: `_pintar_o_fundo` a cada `mostrar()`, antes do `deiconify` (sem piscar); a imagem vai
  com a tag `fundo` embaixo de tudo e sobrevive aos redesenhos; realce só na linha selecionada
  (as outras sem preenchimento); apontar e clicar por geometria no canvas (`_linha_em`).
- Prova sob `pythonw` (captura, esconde, bloco vermelho topmost atrás da metade esquerda, captura,
  filtra, esconde, tira o bloco, captura): a metade esquerda do painel fica avermelhada e desfocada
  com o bloco, e sem ele o painel mostra a cena de trás borrada — o fundo acompanha cada abertura.
  `mostrar()` com `update()`: 85 ms na primeira, 45–75 ms depois.
- **Limitação assumida:** o campo (`Text`) é opaco e leva a cor média da faixa; sobre um fundo com
  metade clara e metade escura ele aparece como uma barra lisa. Nos fundos normais some.
- Suíte: **1072 verdes / 8 desselecionados** (`test_fundo_desfocado.py` +4, `test_dwm.py` 1; os 4 do
  acrílico saíram). Bandeja dele reiniciada pela rota.


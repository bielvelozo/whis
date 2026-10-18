Status: resolved
Blocked by: 01

# Proposta automática na 99Freelas

`propostas_auto.py`, chamado pela vigia de freelas com a mesma leitura da listagem. Modo em `[cacada].propostas_auto` (`desligado`, `ensaio`, `ligado`).

- Travas em Python antes do Claude, todas no config: `propostas_auto_horas` (24, contadas de quando o projeto abre para quem não assina), `propostas_auto_max_propostas` (80, decisão dele em 18/10 depois da leitura ao vivo), `propostas_auto_exclusivos` (false), `propostas_auto_por_dia` (3), `propostas_auto_reserva` (3 conexões). Já proposto: o estado, as notas mandadas do vault e o botão "Melhorar proposta" da página logada.
- A página do projeto confere de novo situação, propostas, data e exclusivo; o formulário diz o custo, as conexões que sobram e a oferta mínima. Conexões abaixo da reserva param a rodada antes de chamar o Claude.
- O Claude decide se ele entrega e escreve a proposta no jeito das de 13/10 (os exemplos são as notas mandadas do vault); o preço é a oferta mínima e nunca vai no texto. Python confere: sem contato, sem link fora do portfólio, sem preço, sem IA quando o projeto não fala de IA, até 3000 caracteres.
- Ensaio: nota com `status: ensaio em ...`, formulário preenchido sem clicar quando logado, aviso no celular com o texto inteiro. Ligado: envia, confere pelo "Melhorar proposta" e só então grava `status: enviada em ...`; sem confirmação vira `incerta` e nunca é reenviada.
- Estado em `%LOCALAPPDATA%\whis\cacada\propostas-auto.json`; resumo por dia em `cacada/propostas-auto.md`.
- Deslogado ou caçada correndo: o ligado não envia (um aviso por dia no celular quando deslogado).

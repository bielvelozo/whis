Status: resolved

# Piso de preço do freela

`[cacada].piso_freela` (inteiro em R$, padrão 0 = sem piso). Com ele, o pedido que a triagem, o resumo, o pacote e as mensagens de tentar a sorte leem diz que nenhum preço sugerido fica abaixo do piso (com a conversão de moeda), e o preço que sai no resumo é conferido em Python: abaixo do piso, vira o piso, dizendo o que o Claude tinha sugerido.

## Comments

Feito em 2026-10-17. Mudança: o preço não é trocado pelo piso; o que o Claude sugeriu fica e ganha no fim "Abaixo do seu piso: peça pelo menos R$ N." (valores do orçamento publicado não contam). A linha do piso vai no fim de *O que eu procuro* nos dois modos.

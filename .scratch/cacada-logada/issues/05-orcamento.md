Status: resolved
Blocked by: 02, 03

# Orçamento de lances e conexões

Tentar a sorte limitado por plataforma ao que dá para mandar; Freelancer.com sem lance vira linha 'sem lances até dia X'; chave [cacada].encaixe_minimo_tentar (padrão 40).

## Answer

`cacada.tentar_a_sorte(estado)`: da melhor para a pior, o Freelancer.com fica com uma por lance restante e a 99Freelas até o estoque de conexões, pelo custo de cada proposta (1 quando não se sabe). Sem a leitura logada do site, não há corte. Freelancer.com com 0 lances vira a linha "Freelancer.com: sem lances este mês; N projetos ficaram de fora até a renovação". Os outros cortes por orçamento ficam numa nota recolhida em Tentar a sorte.

Chave `[cacada].encaixe_minimo_tentar` (padrão 40, de 0 a 100): abaixo disso, a oportunidade sai de Tentar a sorte, vai para a lista de Descartadas com o motivo e é contada em Fontes. O mesmo corte vale para as mensagens prontas, para o capricho do extra e para o envio sozinho. O `tentar_a_sorte` do relatório e do resultado conta só o que dá para mandar.

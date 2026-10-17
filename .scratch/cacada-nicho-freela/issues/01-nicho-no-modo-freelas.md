Status: resolved

# Nicho no modo freelas

`[cacada].nicho_freela` (texto, padrão vazio). Com ele, no modo freelas:

- O pedido do modo troca a linha de chance boa: só freela do nicho ou de e-commerce muito perto; fora disso, no máximo tentar a sorte, por melhor que seja o encaixe.
- Depois da triagem, em Python: chance boa cujo título e descrição não citam o nicho nem uma palavra de e-commerce perto dele vira tentar a sorte, com o motivo dizendo isso.
- As buscas do modo no Freelancer.com cujo argumento não tem o nicho saem (python, automation, bug fix, api integration...). As fontes do Freelancer.com que ele escreveu em `criterios.md` ficam: são dele.
- `whis hunt --simular --freelas` diz o nicho, as buscas que saíram e quantas oportunidades coletadas são do nicho (as únicas que podem virar chance boa).

Vazio é como hoje.

## Comments

Feito em 2026-10-17 (test_nicho_freela.py). A simulação real mostrou "e-commerce" de passagem na descrição de vaga de marketing e de site de imobiliária; ficou assim: o nome do nicho (shopify, liquid) vale no título ou na descrição, e o e-commerce perto (loja virtual, woocommerce, nuvemshop...) só no título. `hunt --simular --freelas` com nicho: 7 buscas do modo saíram, 39 de 134 podem ser chance boa.

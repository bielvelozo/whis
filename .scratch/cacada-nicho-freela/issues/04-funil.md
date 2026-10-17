Status: resolved

# Funil das propostas de freela

As propostas de freela mandadas são as notas de `cacada/*/` com link de plataforma de freela e `status:` começando por `enviada` (os pacotes e as notas de `*-propostas/`, que trazem a data em "enviada em AAAA-MM-DD"). No fim da caçada, sem chamada ao Claude em andamento, o Chrome da caçada abre o projeto de cada uma:

- 99Freelas: aberto (aguardando), cliente escolheu outro, cancelado ou fechado (`ler_99freelas`).
- Freelancer.com: a aba `/proposals` diz a posição ("ranqueada em N entre M").

O relatório ganha a seção *Funil*: por semana do envio, quantas foram mandadas, respondidas e fechadas, e o que os sites mostram de cada uma. Respondida e fechada vêm do `status:` que ele escreve na nota (respondida, entrevista, proposta, fechado); o que só o site sabe e não tem marcador conhecido (resposta do cliente na conversa) diz "não lido". Sem Chrome ou deslogado, a seção diz isso e a caçada segue.

## Comments

Feito em 2026-10-17 (test_funil.py), com as fixtures que já existiam (`99freelas_ja_propos`, `99freelas_escolhido`, `freelancer_ja_ofertou_propostas`). Na 99Freelas a página não diz se a proposta aceita é a dele: o texto diz "se não foi você, perdida". Respondida sai só do `status:`.

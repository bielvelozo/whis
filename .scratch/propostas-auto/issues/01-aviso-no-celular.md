Status: resolved

# Aviso no celular pelo Telegram

`[celular].telegram_token` e `[celular].telegram_chat` no config.toml: o bot é dele, criado no @BotFather. `whis celular` pede o token sem mostrar na tela, espera ele mandar uma mensagem para o bot, descobre o chat e grava os dois no config.toml; `whis celular --teste` manda uma mensagem de teste.

- O aviso nunca derruba quem chamou e o token nunca vai ao log (ele está na URL da API).
- Sem token ou sem chat, não avisa e não reclama.
- A vigia de freelas avisa no celular cada projeto novo do nicho no Freelancer.com: título, site, orçamento, propostas até agora e link. O toast continua.
- Nenhum teste fala com o Telegram de verdade (fixture autouse, como a do toast).

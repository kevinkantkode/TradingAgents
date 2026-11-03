---
name: order
description: Suggest one Robinhood equity order for an existing TradingAgents run directory, then place it only after the user confirms that amount in a later message. Use only when the user invokes /order and names the run directory. If the Robinhood tools are not connected, stop.
disable-model-invocation: true
---

# Order

The user names a run directory, `.tradingagents/<TICKER>/<date>/`. Suggest one equity order from the rating and the account, and say that amount in the chat. Do not write a file. Do not re-read the debate. Do not dispatch the research skill. Do not run `tradingagents`.

## Stop

If `get_accounts` is not available, stop. Say the broker tools are not connected. Do not invent a fill.

Read the first line of `rating.md` in that directory. It must be exactly one of Buy, Overweight, Hold, Underweight, or Sell. Any other first line stops the run. Do not open the other files in the directory.

The symbol is the ticker folder name. Call only `get_accounts`, `get_portfolio`, `get_equity_positions`, `get_equity_tradability`, `get_equity_orders`, `review_equity_order`, `place_equity_order`, and `get_trade_approvals`.

## Account

Use the one account this connection can trade. Ignore the others.

`get_portfolio` for buying power. `get_equity_positions` for `shares_available_for_sells` of the symbol. `get_equity_tradability` for that symbol. `get_equity_orders` for a working order in that symbol. A working order stops the run. Do not stack a second order. If the symbol cannot take the order you would send, stop.

## Size

The amount is yours to choose from the account. Say the buying power, the shares available, and the dollars or shares you suggest.

- Hold: no order. Write that and stop.
- Buy: a larger dollar spend of the buying power on hand. A market order, regular hours, good for day, sized with `dollar_amount`.
- Overweight: a smaller dollar spend of that same buying power. The same order type.
- Sell: every `shares_available_for_sells`. A market order, regular hours, good for day, sized with `quantity`.
- Underweight: fewer shares than that full amount, and more than zero. The same order type.

A buy or overweight with buying power under one dollar stops with no order. A sell or underweight of a flat position stops with no order. Do not shrink a Buy into an Overweight. State the cap and the suggestion in the same note.

## Review, then wait

Call `review_equity_order` with that suggestion. Then stop. Tell the user the rating, the buying power, the shares available, the dollars or shares you would send, and what the review said. Do not call `place_equity_order` in this turn. The word "place" in the opening message does not send the order.

On a later message, send the order only if the user accepts the amount you already stated. If they name a different amount, review that amount and wait again. A blocking review alert does not get sent. Generate one UUID as `ref_id` and reuse it if you retry that same order. Call `get_trade_approvals` only when the review says the customer must approve. Tell them what the tool returned. Do not claim a fill it did not return.

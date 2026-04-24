"""
test_circuit_breaker.py

Forzar `DAILY_LOSS_LIMIT` bajo y un `_meta.daily_loss` alto para verificar
que `check_circuit_breaker` bloquea compras. Ejecutar con:

    python test_circuit_breaker.py

"""
import os
import pprint
from dotenv import load_dotenv

load_dotenv()

# Forzar límite muy bajo antes de importar el módulo
os.environ["DAILY_LOSS_LIMIT"] = os.environ.get("DAILY_LOSS_LIMIT", "1.0")

import bot

# Simular modo REAL para que el circuit breaker tenga efecto (no ejecutamos órdenes)
bot.PAPER_TRADING = False

state = bot.load_state()

# Forzar pérdida diaria elevada
state.setdefault("_meta", {})
state["_meta"]["daily_loss"] = float(os.environ.get("FORCED_DAILY_LOSS", 5.0))

# Asegurar un símbolo sin posición y sin haber comprado nunca
symbol = next((s for s in state.keys() if s != '_meta'), bot.SYMBOLS[0])
state[symbol] = {
    "in_position": False,
    "entry_price": 0.0,
    "highest_price": 0.0,
    "stop_loss": 0.0,
    "quantity": 0.0,
    "bought_once": False,
    "last_sell_time": None
}

bot.save_state(state)

print("=== Estado forzado ===")
pprint.pprint(state.get("_meta"))

blocked = bot.check_circuit_breaker(state)
if blocked:
    print("RESULTADO: Circuit breaker ACTIVO — las compras deben ser bloqueadas.")
else:
    print("RESULTADO: Circuit breaker INACTIVO — las compras están permitidas.")

# Simular la lógica de decisión previa a compra (como en run)
print("\n=== Simulación de decisión de compra para symbol:", symbol)
s = state[symbol]
if not s["in_position"] and not s["bought_once"]:
    if blocked:
        print(f"[{symbol}] Compra BLOQUEADA por circuit breaker (daily_loss={state['_meta']['daily_loss']})")
    else:
        print(f"[{symbol}] Compra PERMITIDA — se llamaría a buy_logic()")
else:
    print(f"[{symbol}] No candidata para compra (in_position={s['in_position']}, bought_once={s['bought_once']})")

# simulate_sell.py
"""
Simula una venta con pérdida para actualizar state.json['_meta']['daily_loss']
Uso: python simulate_sell.py
"""
import os
from dotenv import load_dotenv
load_dotenv()
import bot

# Cargar estado
state = bot.load_state()
# Elegir un símbolo válido
symbol = next((s for s in state.keys() if s != '_meta'), None)
if not symbol:
    symbol = bot.SYMBOLS[0]

print('Simulando venta en', symbol)

# Preparar una posición en pérdida (actualizar estado bajo lock, guardar fuera del lock)
with bot.STATE_LOCK:
    state[symbol] = {
        "in_position": True,
        "entry_price": 0.50,
        "highest_price": 0.50,
        "stop_loss": 0.45,
        "quantity": 10.0,
        "bought_once": True
    }

# Guardar fuera del lock para evitar deadlock (save_state usa el mismo lock internamente)
bot.save_state(state)

print('Estado antes de la venta (_meta):', state.get('_meta'))

# Ejecutar venta simulada (paper trading evita órdenes reales)
bot.sell_logic(None, symbol, 0.40, state, 'SIMULATED LOSS')

# Recargar state y mostrar meta
state_after = bot.load_state()
print('Estado después de la venta (_meta):', state_after.get('_meta'))
print('Circuit breaker activo?', bot.check_circuit_breaker(state_after))

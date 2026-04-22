import os
import time
import logging
import requests
import json
from math import floor
from datetime import datetime
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException

load_dotenv()

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────

API_KEY    = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Lista de monedas (puedes editarlas en Railway separadas por coma)
SYMBOLS = os.getenv("SYMBOLS", "BTCUSDT,DOGEUSDT,SHIBUSDT,PEPEUSDT").split(",")

TRADE_AMOUNT     = float(os.getenv("TRADE_AMOUNT", "12")) # Mínimo 12 para evitar errores de Binance
TRAILING_PERCENT = float(os.getenv("TRAILING_PERCENT", "3"))
CHECK_INTERVAL   = int(os.getenv("CHECK_INTERVAL", "15"))
PAPER_TRADING    = os.getenv("PAPER_TRADING", "true").lower() == "true"

# ─── LOGGING ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("bot.log")]
)
log = logging.getLogger(__name__)

# ─── GESTIÓN DE ESTADO ────────────────────────────────────────────────────────

STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            log.error("Error al leer state.json, iniciando de cero.")
    
    # Estado inicial si no existe el archivo
    return {
        symbol: {
            "in_position": False,
            "entry_price": 0.0,
            "highest_price": 0.0,
            "stop_loss": 0.0,
            "quantity": 0.0,
            "bought_once": False
        } for symbol in SYMBOLS
    }

def save_state(current_state):
    with open(STATE_FILE, "w") as f:
        json.dump(current_state, f, indent=4)

# ─── AUXILIARES DE BINANCE ────────────────────────────────────────────────────

def get_client():
    if PAPER_TRADING:
        log.info("🟡 MODO: PAPER TRADING")
        return Client("", "")
    return Client(API_KEY, API_SECRET)

def get_quantity(client, price, usdt_amount, symbol):
    if PAPER_TRADING:
        return round(usdt_amount / price, 2)
    
    info = client.get_symbol_info(symbol)
    step_size = next(f['stepSize'] for f in info['filters'] if f['filterType'] == 'LOT_SIZE')
    precision = step_size.find('1') - 1
    if precision < 0: precision = 0
    
    raw_qty = usdt_amount / price
    return floor(raw_qty * 10**precision) / 10**precision

# ─── ACCIONES DE TRADING ──────────────────────────────────────────────────────

def buy_logic(client, symbol, price, state):
    qty = get_quantity(client, price, TRADE_AMOUNT, symbol)
    stop = price * (1 - TRAILING_PERCENT / 100)

    if not PAPER_TRADING:
        try:
            client.order_market_buy(symbol=symbol, quantity=qty)
            log.info(f"✅ [{symbol}] COMPRA REAL EJECUTADA")
        except Exception as e:
            log.error(f"❌ [{symbol}] Error en compra: {e}")
            return

    state[symbol].update({
        "in_position": True,
        "entry_price": price,
        "highest_price": price,
        "stop_loss": stop,
        "quantity": qty,
        "bought_once": True
    })
    log.info(f"📈 [{symbol}] COMPRA | Precio: ${price:.6f} | Stop: ${stop:.6f}")

def sell_logic(client, symbol, price, state, reason):
    s = state[symbol]
    pnl = (price - s["entry_price"]) * s["quantity"]

    if not PAPER_TRADING:
        try:
            client.order_market_sell(symbol=symbol, quantity=s["quantity"])
            log.info(f"✅ [{symbol}] VENTA REAL EJECUTADA")
        except Exception as e:
            log.error(f"❌ [{symbol}] Error en venta: {e}")
            return

    log.info(f"📉 [{symbol}] VENTA ({reason}) | Precio: ${price:.6f} | PnL: ${pnl:+.4f}")
    
    s.update({
        "in_position": False,
        "entry_price": 0.0,
        "highest_price": 0.0,
        "stop_loss": 0.0,
        "quantity": 0.0,
        "bought_once": False if PAPER_TRADING else True # En paper reinicia, en real espera nueva orden
    })

# ─── LOOP PRINCIPAL ───────────────────────────────────────────────────────────

def run():
    print("La IP de mi bot es:", requests.get('https://api.ipify.org').text)
    client = get_client()
    state = load_state()

    log.info(f"🚀 BOT INICIADO | Monedas: {SYMBOLS}")

    while True:
        for symbol in SYMBOLS:
            try:
                # Asegurarse que el símbolo exista en el estado
                if symbol not in state:
                    state[symbol] = {"in_position": False, "entry_price": 0.0, "highest_price": 0.0, "stop_loss": 0.0, "quantity": 0.0, "bought_once": False}

                ticker = client.get_symbol_ticker(symbol=symbol)
                price = float(ticker["price"])
                s = state[symbol]

                if not s["in_position"]:
                    # Compra automática inicial o tras venta
                    if not s["bought_once"]:
                        buy_logic(client, symbol, price, state)
                        save_state(state)
                else:
                    # Actualizar Trailing Stop
                    if price > s["highest_price"]:
                        s["highest_price"] = price
                        new_stop = price * (1 - TRAILING_PERCENT / 100)
                        if new_stop > s["stop_loss"]:
                            s["stop_loss"] = new_stop
                            log.info(f"⬆️  [{symbol}] Nuevo Stop: ${new_stop:.6f}")
                            save_state(state)

                    # Verificar si tocó el Stop Loss
                    if price <= s["stop_loss"]:
                        sell_logic(client, symbol, price, state, "STOP LOSS")
                        save_state(state)
                    else:
                        # Log de monitoreo cada ciclo
                        pnl_act = (price - s["entry_price"]) * s["quantity"]
                        log.info(f"👀 [{symbol}] ${price:.6f} | PnL: {pnl_act:+.2f}")

            except Exception as e:
                log.error(f"⚠️ Error en {symbol}: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    run()
    
    # """
# Trailing Stop Loss Bot - Binance
# Modo PAPER TRADING por defecto (sin dinero real)
# Para activar dinero real: PAPER_TRADING=false en variables de entorno
# """

# import os
# import time
# import logging
# import requests
# import json
# from datetime import datetime
# from dotenv import load_dotenv
# from binance.client import Client
# from binance.exceptions import BinanceAPIException


# load_dotenv()

# # ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────

# API_KEY    = os.getenv("BINANCE_API_KEY", "")
# API_SECRET = os.getenv("BINANCE_API_SECRET", "")


# SYMBOLS = os.getenv("SYMBOLS", "BTCUSDT,DOGEUSDT,SHIBUSDT,PEPEUSDT").split(",")

# SYMBOL           = os.getenv("SYMBOL", "DOGEUSDT")       # Par a operar
# TRADE_AMOUNT     = float(os.getenv("TRADE_AMOUNT", "5")) # USD a invertir
# TRAILING_PERCENT = float(os.getenv("TRAILING_PERCENT", "3"))  # % de trailing stop
# CHECK_INTERVAL   = int(os.getenv("CHECK_INTERVAL", "10"))     # segundos entre checks
# PAPER_TRADING    = os.getenv("PAPER_TRADING", "true").lower() == "true"

# # ─── LOGGING ──────────────────────────────────────────────────────────────────

# print("La IP de mi bot es:", requests.get('https://api.ipify.org').text)

# # Inicializamos un estado vacío para cada símbolo
# states = {
#     symbol: {
#         "in_position": False,
#         "entry_price": 0.0,
#         "highest_price": 0.0,
#         "stop_loss": 0.0,
#         "quantity": 0.0
#     } for symbol in SYMBOLS
# }

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] %(message)s",
#     handlers=[
#         logging.StreamHandler(),
#         logging.FileHandler("bot.log")
#     ]
# )
# log = logging.getLogger(__name__)

# # ─── ESTADO DEL BOT ───────────────────────────────────────────────────────────

# state = {
#     "in_position": False,
#     "entry_price": 0.0,
#     "highest_price": 0.0,
#     "stop_loss": 0.0,
#     "quantity": 0.0,
#     "pnl": 0.0,
#     "trades": []
# }

# # ─── CLIENTE BINANCE ──────────────────────────────────────────────────────────

# def save_state():
#     with open("state.json", "w") as f:
#         json.dump(state, f)

# def load_state():
#     if os.path.exists("state.json"):
#         with open("state.json", "r") as f:
#             return json.load(f)
#     return None
    
# def get_client():
#     if PAPER_TRADING:
#         log.info("🟡 PAPER TRADING activado — sin dinero real")
#         return Client("", "")  # No necesita keys en paper mode
#     else:
#         if not API_KEY or not API_SECRET:
#             raise ValueError("Faltan BINANCE_API_KEY y BINANCE_API_SECRET en .env")
#         return Client(API_KEY, API_SECRET)

# def get_price(client, symbol):
#     """Obtiene el precio actual del par."""
#     try:
#         ticker = client.get_symbol_ticker(symbol=symbol)
#         return float(ticker["price"])
#     except BinanceAPIException as e:
#         log.error(f"Error obteniendo precio: {e}")
#         return None

# def get_quantity(client, price, usdt_amount, symbol):
#     info = client.get_symbol_info(symbol)
#     step_size = next(f['stepSize'] for f in info['filters'] if f['filterType'] == 'LOT_SIZE')
    
#     # Calcular cantidad bruta
#     raw_qty = usdt_amount / price
    
#     # Ajustar a la precisión permitida por Binance
#     precision = step_size.find('1') - 1
#     if precision < 0: precision = 0
    
#     return floor(raw_qty * 10**precision) / 10**precision

# # ─── LÓGICA DE TRADING ────────────────────────────────────────────────────────

# def buy(client, price):
#     qty = get_quantity(price, TRADE_AMOUNT, SYMBOL)
#     stop = price * (1 - TRAILING_PERCENT / 100)

#     if not PAPER_TRADING:
#         try:
#             order = client.order_market_buy(symbol=SYMBOL, quantity=qty)
#             log.info(f"✅ COMPRA ejecutada: {order}")
#         except BinanceAPIException as e:
#             log.error(f"❌ Error en compra: {e}")
#             return

#     state["in_position"]  = True
#     state["entry_price"]  = price
#     state["highest_price"]= price
#     state["stop_loss"]    = stop
#     state["quantity"]     = qty

#     log.info(f"📈 COMPRA | Precio: ${price:.4f} | Qty: {qty} | Stop Loss: ${stop:.4f}")

# def sell(client, price, reason):
#     pnl = (price - state["entry_price"]) * state["quantity"]
#     state["pnl"] += pnl
#     state["trades"].append({
#         "time": datetime.now().isoformat(),
#         "entry": state["entry_price"],
#         "exit": price,
#         "pnl": round(pnl, 4),
#         "reason": reason
#     })

#     if not PAPER_TRADING:
#         try:
#             order = client.order_market_sell(symbol=SYMBOL, quantity=state["quantity"])
#             log.info(f"✅ VENTA ejecutada: {order}")
#         except BinanceAPIException as e:
#             log.error(f"❌ Error en venta: {e}")
#             return

#     log.info(f"📉 VENTA ({reason}) | Precio: ${price:.4f} | PnL: ${pnl:+.4f} | PnL Total: ${state['pnl']:+.4f}")

#     state["in_position"]  = False
#     state["entry_price"]  = 0.0
#     state["highest_price"]= 0.0
#     state["stop_loss"]    = 0.0
#     state["quantity"]     = 0.0

# def update_trailing_stop(price):
#     """Sube el stop loss si el precio subió."""
#     if price > state["highest_price"]:
#         state["highest_price"] = price
#         new_stop = price * (1 - TRAILING_PERCENT / 100)
#         if new_stop > state["stop_loss"]:
#             old_stop = state["stop_loss"]
#             state["stop_loss"] = new_stop
#             log.info(f"⬆️  Trailing actualizado | Precio: ${price:.4f} | Stop: ${old_stop:.4f} → ${new_stop:.4f}")

# # ─── LOOP PRINCIPAL ───────────────────────────────────────────────────────────

# def run():
#     log.info("="*50)
#     log.info(f"🤖 BOT INICIADO | Par: {SYMBOL} | Capital: ${TRADE_AMOUNT} | Trailing: {TRAILING_PERCENT}%")
#     log.info(f"{'🟡 PAPER TRADING' if PAPER_TRADING else '🔴 DINERO REAL'}")
#     log.info("="*50)

#     client = get_client()
#     bought_once = False  # En paper mode, compra al primer precio disponible

#     while True:
#         try:
#             price = get_price(client, SYMBOL)
#             if price is None:
#                 time.sleep(CHECK_INTERVAL)
#                 continue

#             if not state["in_position"]:
#                 # Estrategia simple: compra al inicio (paper mode)
#                 # En producción: podés agregar condiciones de entrada (RSI, MA, etc.)
#                 if not bought_once or PAPER_TRADING:
#                     buy(client, price)
#                     bought_once = True

#             else:
#                 update_trailing_stop(price)

#                 if price <= state["stop_loss"]:
#                     sell(client, price, "STOP LOSS")
#                     # En paper mode, vuelve a comprar en el próximo ciclo
#                     bought_once = False

#                 else:
#                     log.info(
#                         f"👀 Monitoreando | Precio: ${price:.4f} | "
#                         f"Stop: ${state['stop_loss']:.4f} | "
#                         f"Máx: ${state['highest_price']:.4f} | "
#                         f"PnL: ${((price - state['entry_price']) * state['quantity']):+.4f}"
#                     )

#             time.sleep(CHECK_INTERVAL)

#         except KeyboardInterrupt:
#             log.info("🛑 Bot detenido manualmente")
#             if state["in_position"]:
#                 log.info(f"⚠️  Posición abierta sin cerrar. Precio entrada: ${state['entry_price']:.4f}")
#             break
#         except Exception as e:
#             log.error(f"Error inesperado: {e}")
#             time.sleep(30)

# if __name__ == "__main__":
#     run()

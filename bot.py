import os
import sys
import time
import logging
import requests
import json
from math import floor
from datetime import datetime
from threading import Thread
import threading
import pandas as pd
try:
    import pandas_ta as ta
    RSI_AVAILABLE = True
except Exception:
    RSI_AVAILABLE = False
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Forzar UTF-8 en stdout/stderr en Windows (evita UnicodeEncodeError con emojis)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Intentar importar Flask para el panel HTTP (opcional)
try:
    from flask import Flask, jsonify, request
    FLASK_AVAILABLE = True
except Exception:
    FLASK_AVAILABLE = False

# ─── TELEGRAM NOTIFIER ───────────────────────────────────────────────────────
try:
    from telegram_notifier import (
        init_telegram,
        notify_buy,
        notify_sell,
        notify_trailing_updated,
        notify_critical_error,
    )
    TELEGRAM_AVAILABLE = True
except Exception as e:
    TELEGRAM_AVAILABLE = False
    print(f"⚠️ No se pudo cargar telegram_notifier: {e}")

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
BINANCE_FEE      = float(os.getenv("BINANCE_FEE", "0.001"))  # 0.1% por defecto
TAKE_PROFIT_PERCENT = float(os.getenv("TAKE_PROFIT_PERCENT", "4"))
RSI_BUY_THRESHOLD = float(os.getenv("RSI_BUY_THRESHOLD", "35"))
RSI_SELL_THRESHOLD = float(os.getenv("RSI_SELL_THRESHOLD", "70"))
DAILY_LOSS_LIMIT = float(os.getenv("DAILY_LOSS_LIMIT", "3.0"))
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "10"))

# ─── LOGGING ──────────────────────────────────────────────────────────────────

class _UTF8StreamHandler(logging.StreamHandler):
    """Forzar UTF-8 en la consola de Windows para evitar UnicodeEncodeError con emojis."""
    def __init__(self, stream=None):
        super().__init__(stream)

    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # En Windows, escribir directamente con encoding utf-8 bypass
            if hasattr(stream, 'buffer'):
                stream.buffer.write((msg + self.terminator).encode('utf-8'))
            else:
                stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[_UTF8StreamHandler(sys.stdout), logging.FileHandler("bot.log", encoding="utf-8")]
)
log = logging.getLogger(__name__)

# ─── GESTIÓN DE ESTADO ────────────────────────────────────────────────────────

STATE_FILE = "state.json"
STATE_LOCK = threading.Lock()

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                st = json.load(f)
                # asegurar meta
                if not isinstance(st, dict):
                    st = {}
                if "_meta" not in st:
                    st["_meta"] = {"daily_loss": 0.0, "last_reset": datetime.utcnow().date().isoformat()}
                else:
                    # garantizar campos
                    meta = st.get("_meta", {})
                    meta.setdefault("daily_loss", 0.0)
                    meta.setdefault("last_reset", datetime.utcnow().date().isoformat())
                    st["_meta"] = meta
                return st
        except:
            log.error("Error al leer state.json, iniciando de cero.")
    
    # Estado inicial si no existe el archivo
    st = {
        symbol: {
            "in_position": False,
            "entry_price": 0.0,
            "highest_price": 0.0,
            "stop_loss": 0.0,
            "quantity": 0.0,
            "bought_once": False
            ,"last_sell_time": None
        } for symbol in SYMBOLS
    }
    st["_meta"] = {"daily_loss": 0.0, "last_reset": datetime.utcnow().date().isoformat()}
    return st

def save_state(current_state):
    # Guardar estado de forma thread-safe
    try:
        with STATE_LOCK:
            with open(STATE_FILE, "w") as f:
                json.dump(current_state, f, indent=4)
    except Exception as e:
        log.error(f"Error guardando state.json: {e}")

# ─── AUXILIARES DE BINANCE ────────────────────────────────────────────────────

def get_client():
    if PAPER_TRADING:
        log.info("🟡 MODO: PAPER TRADING")
        return Client("", "")

    try:
        client = Client(API_KEY, API_SECRET)
        # Probar una llamada sencilla para validar las keys
        try:
            client.get_account()
        except Exception as e:
            log.error(f"⚠️ Las API keys parecen inválidas o no autorizadas: {e}")
            return None
        return client
    except Exception as e:
        log.error(f"⚠️ Error creando cliente Binance: {e}")
        return None

def get_quantity(client, price, usdt_amount, symbol):
    if PAPER_TRADING:
        return round(usdt_amount / price, 2)
    
    info = client.get_symbol_info(symbol)
    step_size = next(f['stepSize'] for f in info['filters'] if f['filterType'] == 'LOT_SIZE')
    precision = step_size.find('1') - 1
    if precision < 0: precision = 0
    
    raw_qty = usdt_amount / price
    return floor(raw_qty * 10**precision) / 10**precision


def get_balances(client):
    """Devuelve los saldos no cero de la cuenta Spot.

    En `PAPER_TRADING` devuelve un ejemplo simulado.
    """
    if PAPER_TRADING:
        return {"USDT": {"free": 100.0, "locked": 0.0}}

    if client is None:
        log.warning("get_balances: cliente Binance no disponible")
        return {}

    try:
        acc = client.get_account()
        balances = {}
        for b in acc.get("balances", []):
            asset = b.get("asset")
            try:
                free = float(b.get("free", 0.0))
                locked = float(b.get("locked", 0.0))
            except Exception:
                continue
            if free != 0.0 or locked != 0.0:
                balances[asset] = {"free": free, "locked": locked}
        return balances
    except Exception as e:
        log.error(f"⚠️ Error obteniendo balances: {e}")
        return {}


def get_rsi(client, symbol, period=14, interval="15m"):
    """Obtiene RSI usando `get_klines` y pandas-ta. Devuelve float o None."""
    if not RSI_AVAILABLE:
        log.debug("RSI no disponible (pandas-ta no instalado)")
        return None
    try:
        klines = client.get_klines(symbol=symbol, interval=interval, limit=period + 5)
        closes = pd.Series([float(k[4]) for k in klines])
        rsi_series = ta.rsi(closes, length=period)
        if rsi_series is None or rsi_series.empty:
            return None
        return float(rsi_series.iloc[-1])
    except Exception as e:
        log.debug(f"Error calculando RSI para {symbol}: {e}")
        return None


def _reset_daily_if_needed(state):
    try:
        meta = state.setdefault("_meta", {})
        last = meta.get("last_reset")
        today = datetime.utcnow().date().isoformat()
        if last != today:
            meta["daily_loss"] = 0.0
            meta["last_reset"] = today
            save_state(state)
    except Exception as e:
        log.debug(f"Error al resetear daily meta: {e}")


def update_daily_loss(state, pnl: float):
    """Actualizar la pérdida diaria acumulada (solo contar pérdidas)."""
    try:
        meta = state.setdefault("_meta", {"daily_loss": 0.0, "last_reset": datetime.utcnow().date().isoformat()})
        if pnl < 0:
            add = abs(pnl)
            meta["daily_loss"] = float(meta.get("daily_loss", 0.0)) + add
            save_state(state)
            log.info(f"🧾 Pérdida diaria actualizada: +${add:.4f} -> total ${meta['daily_loss']:.4f}")
    except Exception as e:
        log.debug(f"Error actualizando daily loss: {e}")


def check_circuit_breaker(state) -> bool:
    """Devuelve True si el límite diario de pérdida fue alcanzado o superado."""
    try:
        _reset_daily_if_needed(state)
        meta = state.get("_meta", {})
        daily_loss = float(meta.get("daily_loss", 0.0))
        if daily_loss >= DAILY_LOSS_LIMIT and not PAPER_TRADING:
            log.warning(f"🛑 CIRCUIT BREAKER activo — pérdida diaria ${daily_loss:.2f} >= límite ${DAILY_LOSS_LIMIT:.2f}")
            return True
    except Exception as e:
        log.debug(f"Error comprobando circuit breaker: {e}")
    return False


def calculate_real_pnl(entry_price: float, exit_price: float, quantity: float) -> float:
    """Calcula el PnL real considerando comisiones de compra y venta."""
    try:
        buy_cost = entry_price * quantity * (1 + BINANCE_FEE)
        sell_gain = exit_price * quantity * (1 - BINANCE_FEE)
        return sell_gain - buy_cost
    except Exception:
        return 0.0


def safe_get_price(client, symbol, retries=3):
    """Intentar obtener el precio con backoff exponencial en caso de errores temporales."""
    if client is None:
        return None
    for attempt in range(retries):
        try:
            ticker = client.get_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        except Exception as e:
            wait = 2 ** attempt
            log.warning(f"⚠️ Retry {attempt+1}/{retries} para {symbol}: {e}")
            time.sleep(wait)
    return None


def start_http_panel(client, state):
    """Crea y arranca un pequeño panel HTTP con rutas para estado, balances y logs.

    Ejecutar en un hilo aparte. Si Flask no está disponible, sólo hace log.
    """
    if not FLASK_AVAILABLE:
        log.info("ℹ️ Flask no disponible. Ignorando panel HTTP.")
        return

    app = Flask(__name__)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + "Z"})

    @app.route("/state")
    def get_state():
        # Devolver el estado actual (serializable)
        return jsonify(state)

    @app.route("/balances")
    def balances():
        return jsonify(get_balances(client))

    @app.route("/logs")
    def logs():
        # Parámetro opcional ?lines=n
        try:
            n = int(request.args.get("lines", "200"))
        except Exception:
            n = 200
        logfile = os.path.join(os.getcwd(), "bot.log")
        if not os.path.exists(logfile):
            return jsonify({"error": "log file not found"}), 404
        try:
            with open(logfile, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            return jsonify({"lines": lines[-n:]})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    port = int(os.getenv("PORT", "8080"))
    def run_app():
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    t = Thread(target=run_app, daemon=True)
    t.start()
    log.info(f"🌐 Panel HTTP iniciado en / (port {port})")

# ─── VARIABLES COMPARTIDAS PARA TELEGRAM ─────────────────────────────────────

_global_client = None
_global_state = {}


def _tg_get_state():
    with STATE_LOCK:
        try:
            return dict(_global_state)
        except Exception:
            return {}


def _tg_get_balances():
    if _global_client is None:
        return {}
    return get_balances(_global_client)


def _tg_is_paper():
    return PAPER_TRADING


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
            if TELEGRAM_AVAILABLE:
                notify_critical_error(f"Compra {symbol}", str(e))
            return

    # Actualizar estado de forma thread-safe
    try:
        with STATE_LOCK:
            state[symbol].update({
                "in_position": True,
                "entry_price": price,
                "highest_price": price,
                "stop_loss": stop,
                "quantity": qty,
                "bought_once": True
            })
            save_state(state)
    except Exception as e:
        log.error(f"Error actualizando state en buy_logic: {e}")
    log.info(f"📈 [{symbol}] COMPRA | Precio: ${price:.8f} | Stop: ${stop:.8f}")
    if TELEGRAM_AVAILABLE:
        notify_buy(symbol, price, stop, qty, PAPER_TRADING)



def sell_logic(client, symbol, price, state, reason):
    s = state[symbol]
    pnl = calculate_real_pnl(s.get("entry_price", 0.0), price, s.get("quantity", 0.0))

    if not PAPER_TRADING:
        try:
            client.order_market_sell(symbol=symbol, quantity=s["quantity"])
            log.info(f"✅ [{symbol}] VENTA REAL EJECUTADA")
        except Exception as e:
            log.error(f"❌ [{symbol}] Error en venta: {e}")
            if TELEGRAM_AVAILABLE:
                notify_critical_error(f"Venta {symbol}", str(e))
            return

    log.info(f"📉 [{symbol}] VENTA ({reason}) | Precio: ${price:.8f} | PnL: ${pnl:+.4f}")
    if TELEGRAM_AVAILABLE:
        notify_sell(symbol, price, pnl, reason, PAPER_TRADING)
    # Actualizar pérdida diaria si corresponde (solo pérdidas)
    try:
        update_daily_loss(state, pnl)
    except Exception:
        pass

    try:
        with STATE_LOCK:
            s.update({
                "in_position": False,
                "entry_price": 0.0,
                "highest_price": 0.0,
                "stop_loss": 0.0,
                "quantity": 0.0,
                "bought_once": False if PAPER_TRADING else True, # En paper reinicia, en real espera nueva orden
                "last_sell_time": datetime.utcnow().isoformat()
            })
            save_state(state)
    except Exception as e:
        log.error(f"Error actualizando state en sell_logic: {e}")

# ─── LOOP PRINCIPAL ───────────────────────────────────────────────────────────

def run():
    global _global_client, _global_state

    print("La IP de mi bot es:", requests.get('https://api.ipify.org').text)
    client = get_client()
    if client is None and not PAPER_TRADING:
        log.error("Cliente Binance no válido. Revisa tus API keys o la autorización por IP. Abortando.")
        if TELEGRAM_AVAILABLE:
            try:
                notify_critical_error("Cliente Binance", "API keys inválidas o IP no autorizada")
            except Exception:
                pass
        return
    state = load_state()

    # Compartir estado con el módulo Telegram
    _global_client = client
    _global_state = state

    # ─── INICIAR SERVICIOS EN HILOS ──────────────────────────────────────────
    start_http_panel(client, state)

    tg_cmd_bot = None
    tg_reporter = None
    if TELEGRAM_AVAILABLE:
        try:
            uptime_start = datetime.utcnow()
            tg_cmd_bot, tg_reporter = init_telegram(
                get_state_fn=_tg_get_state,
                get_balances_fn=_tg_get_balances,
                is_paper_fn=_tg_is_paper,
                symbols=SYMBOLS,
                uptime_start=uptime_start,
            )
            log.info("📬 Notificaciones de Telegram activadas.")
        except Exception as e:
            log.error(f"⚠️ Error iniciando Telegram: {e}")

    log.info(f"🚀 BOT INICIADO | Monedas: {SYMBOLS}")
    if TELEGRAM_AVAILABLE:
        from telegram_notifier import notify_event
        notify_event("Bot iniciado", f"Monedas: {', '.join(SYMBOLS)}\nModo: {'PAPER' if PAPER_TRADING else 'REAL'}")

    while True:
        for symbol in SYMBOLS:
            try:
                # Asegurarse que el símbolo exista en el estado
                if symbol not in state:
                    state[symbol] = {"in_position": False, "entry_price": 0.0, "highest_price": 0.0, "stop_loss": 0.0, "quantity": 0.0, "bought_once": False}

                price = safe_get_price(client, symbol)
                if price is None:
                    continue
                s = state[symbol]

                if not s["in_position"]:
                    # Compra automática inicial o tras venta
                    if not s["bought_once"]:
                        do_buy = True
                        # Usar RSI como filtro de entrada si está disponible
                        if client is not None and RSI_AVAILABLE:
                            try:
                                rsi = get_rsi(client, symbol)
                                if rsi is None:
                                    log.debug(f"RSI no disponible para {symbol}, permitiendo compra de fallback")
                                else:
                                    log.info(f"[{symbol}] RSI={rsi:.2f}")
                                    if rsi >= RSI_BUY_THRESHOLD:
                                        do_buy = False
                                        log.info(f"[{symbol}] RSI >= {RSI_BUY_THRESHOLD}, no comprar ahora")
                            except Exception as e:
                                log.debug(f"Error obteniendo RSI: {e}")

                        if do_buy:
                            # Chequear circuit breaker antes de comprar
                            if check_circuit_breaker(state):
                                log.info(f"[{symbol}] Circuit breaker activo — no se realizan compras.")
                            else:
                                # Comprobar cooldown por venta reciente
                                try:
                                    last = s.get("last_sell_time")
                                    if last:
                                        last_dt = datetime.fromisoformat(last)
                                        elapsed = datetime.utcnow() - last_dt
                                        if elapsed.total_seconds() < COOLDOWN_MINUTES * 60:
                                            mins = elapsed.total_seconds() / 60.0
                                            log.info(f"[{symbol}] En cooldown ({mins:.1f}m < {COOLDOWN_MINUTES}m), no comprar ahora.")
                                            continue
                                except Exception as e:
                                    log.debug(f"Error comprobando cooldown para {symbol}: {e}")

                                buy_logic(client, symbol, price, state)
                                save_state(state)
                        
                else:
                    # Actualizar Trailing Stop
                    # Take profit fijo
                    try:
                        entry = s.get("entry_price", 0.0)
                        if entry and entry > 0:
                            profit_pct = ((price - entry) / entry) * 100
                            if profit_pct >= TAKE_PROFIT_PERCENT:
                                sell_logic(client, symbol, price, state, "TAKE PROFIT")
                                save_state(state)
                                continue
                    except Exception as e:
                        log.debug(f"Error calculando take profit para {symbol}: {e}")
                    if price > s["highest_price"]:
                        s["highest_price"] = price
                        new_stop = price * (1 - TRAILING_PERCENT / 100)
                        if new_stop > s["stop_loss"]:
                            s["stop_loss"] = new_stop
                            log.info(f"⬆️  [{symbol}] Nuevo Stop: ${new_stop:.6f}")
                            save_state(state)
                            if TELEGRAM_AVAILABLE:
                                notify_trailing_updated(symbol, new_stop)

                    # Verificar si tocó el Stop Loss
                    if price <= s["stop_loss"]:
                        sell_logic(client, symbol, price, state, "STOP LOSS")
                        save_state(state)
                    else:
                        # Log de monitoreo cada ciclo
                        pnl_act = (price - s["entry_price"]) * s["quantity"]
                        log.info(f"👀 [{symbol}] ${price:.8f} | PnL: {pnl_act:+.2f}")

            except Exception as e:
                log.error(f"⚠️ Error en {symbol}: {e}")
                if TELEGRAM_AVAILABLE:
                    try:
                        notify_critical_error(f"Loop {symbol}", str(e))
                    except Exception:
                        pass

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    run()
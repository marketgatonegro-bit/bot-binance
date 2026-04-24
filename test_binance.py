# test_binance.py
import os
from dotenv import load_dotenv
load_dotenv()
from binance.client import Client

try:
    c = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_API_SECRET"))
    acc = c.get_account()
    print("Conexión OK. Keys válidas y respuesta recibida.")
    print("Ejemplo balance USDT:", next((b for b in acc.get("balances",[]) if b["asset"]=="USDT"), None))
except Exception as e:
    print("Error al conectar con Binance:", repr(e))
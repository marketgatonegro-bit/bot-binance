"""
🌐 Panel Visual para obtener tu IP pública
─────────────────────────────────────────────
Sirve una interfaz web simple que muestra tu IP pública,
la que tenés que cargar en Binance → API Management → 
"Restrict access to trusted IPs only" para autorizar la conexión.

Uso:
    python ip_panel.py

Después abrí en el navegador: http://localhost:5000
"""

import os
import sys
import re
import requests
from flask import Flask, render_template_string, jsonify, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

ENV_FILE = ".env"
API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


# ─── HTML (una sola página, todo embebido) ───────────────────────────────────

HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 Bot Binance — IP para API Key</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            color: #fff;
        }
        .card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 40px;
            max-width: 600px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        }
        h1 {
            font-size: 28px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .subtitle {
            color: #a0a0c0;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .ip-box {
            background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            margin-bottom: 25px;
            position: relative;
        }
        .ip-label {
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 2px;
            opacity: 0.9;
            margin-bottom: 10px;
        }
        .ip-value {
            font-size: 36px;
            font-weight: bold;
            font-family: 'Courier New', monospace;
            letter-spacing: 2px;
            user-select: all;
        }
        .copy-btn {
            margin-top: 15px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 8px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        }
        .copy-btn:hover {
            background: rgba(0, 0, 0, 0.5);
        }
        .status {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 15px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 8px;
            margin-bottom: 15px;
            font-size: 14px;
        }
        .status.ok { border-left: 3px solid #2ecc71; }
        .status.fail { border-left: 3px solid #e74c3c; }
        .status.pending { border-left: 3px solid #f39c12; }
        .dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            flex-shrink: 0;
        }
        .dot.ok { background: #2ecc71; box-shadow: 0 0 10px #2ecc71; }
        .dot.fail { background: #e74c3c; box-shadow: 0 0 10px #e74c3c; }
        .dot.pending { background: #f39c12; box-shadow: 0 0 10px #f39c12; }
        .steps {
            background: rgba(0, 0, 0, 0.2);
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
        }
        .steps h3 {
            font-size: 14px;
            margin-bottom: 12px;
            color: #f39c12;
        }
        .steps ol {
            margin-left: 20px;
            font-size: 13px;
            line-height: 1.8;
            color: #c0c0d0;
        }
        .steps a {
            color: #3498db;
            text-decoration: none;
        }
        .steps a:hover { text-decoration: underline; }
        .refresh {
            display: block;
            width: 100%;
            margin-top: 20px;
            padding: 12px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .refresh:hover { background: #2980b9; }
        .toast {
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            background: #2ecc71;
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 14px;
        }
        .toast.show { opacity: 1; }
    </style>
</head>
<body>
    <div class="card">
        <h1>🤖 Bot Binance</h1>
        <p class="subtitle">Configurá tu IP en Binance para autorizar la API Key</p>

        <div class="ip-box">
            <div class="ip-label">📡 Tu IP pública</div>
            <div class="ip-value" id="ip">{{ ip }}</div>
            <button class="copy-btn" onclick="copyIP()">📋 Copiar IP</button>
        </div>

        <div class="status {{ 'ok' if api_key_set else 'fail' }}">
            <div class="dot {{ 'ok' if api_key_set else 'fail' }}"></div>
            <span>API Key configurada en .env: <strong>{{ '✅ Sí' if api_key_set else '❌ No (revisá tu .env)' }}</strong></span>
        </div>

        <div class="status {{ 'ok' if binance_ok else ('pending' if not api_key_set else 'fail') }}">
            <div class="dot {{ 'ok' if binance_ok else ('pending' if not api_key_set else 'fail') }}"></div>
            <span>Conexión con Binance: <strong>{{ binance_msg }}</strong></span>
        </div>

        <div class="steps">
            <h3>📋 Pasos para autorizar la IP</h3>
            <ol>
                <li>Copiá la IP de arriba</li>
                <li>Entrá a <a href="https://www.binance.com/en/my/settings/api-management" target="_blank">Binance API Management</a></li>
                <li>Editá tu API Key → <strong>"Restrict access to trusted IPs only"</strong></li>
                <li>Pegá la IP y guardá</li>
                <li>Refrescá esta página para verificar la conexión ✅</li>
            </ol>
        </div>

        <button class="refresh" onclick="location.reload()">🔄 Verificar conexión</button>
    </div>

    <div class="toast" id="toast">✅ IP copiada al portapapeles</div>

    <script>
        function copyIP() {
            const ip = document.getElementById('ip').textContent.trim();
            navigator.clipboard.writeText(ip).then(() => {
                const t = document.getElementById('toast');
                t.classList.add('show');
                setTimeout(() => t.classList.remove('show'), 2000);
            });
        }
    </script>
</body>
</html>
"""

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def get_public_ip():
    """Obtiene la IP pública desde varios servicios (con fallback)."""
    services = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ]
    for url in services:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                return r.text.strip()
        except Exception:
            continue
    return "No se pudo obtener"


def check_binance():
    """Intenta conectarse a Binance con las credenciales del .env."""
    # Leer las credenciales al momento de la verificación (no sólo al importar)
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        return False, "⏳ Falta configurar API Key/Secret"
    try:
        # DEBUG: mostrar metadatos de las claves (no imprimir secretos completos)
        try:
            print(f"[DEBUG] check_binance using api_key prefix={api_key[:6]} secret_len={len(api_secret)}")
        except Exception:
            pass
        # Escribir un log de depuración en disco (no incluir secretos completos)
        try:
            with open('ip_panel_debug.log', 'a', encoding='utf-8') as _f:
                _f.write(f"[DEBUG] {__name__} check_binance api_key_prefix={api_key[:6]} secret_len={len(api_secret)}\n")
        except Exception:
            pass
        from binance.client import Client
        from binance.exceptions import BinanceAPIException
        client = Client(api_key, api_secret)
        # Llamada simple que requiere autenticación
        acc = client.get_account()
        # Mostrar saldo USDT si existe
        usdt = next((b for b in acc.get("balances", []) if b["asset"] == "USDT"), None)
        bnb = next((b for b in acc.get("balances", []) if b["asset"] == "BNB"), None)
        msg = "✅ Conectado"
        if usdt:
            msg += f" | USDT: {float(usdt['free']):.2f}"
        if bnb:
            msg += f" | BNB: {float(bnb['free']):.6f}"
        return True, msg
    except Exception as e:
        # Manejo robusto de BinanceAPIException y otros errores
        code = getattr(e, 'code', None)
        estr = str(e)
        if code is not None and (code == -2014 or code == -2015):
            pub = get_public_ip()
            return False, f"❌ API Key inválida o IP no autorizada (cód {code}) | public_ip={pub} | err={estr[:200]}"
        if "restricted location" in estr.lower():
            pub = get_public_ip()
            return False, f"❌ Ubicación restringida: {estr} | public_ip={pub}"
        pub = get_public_ip()
        return False, f"❌ Binance: {estr[:200]} | public_ip={pub}"


# ─── RUTAS ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    ip = get_public_ip()
    binance_ok, binance_msg = check_binance()
    return render_template_string(
        HTML,
        ip=ip,
        api_key_set=bool(API_KEY and API_SECRET),
        binance_ok=binance_ok,
        binance_msg=binance_msg,
    )


@app.route("/api/ip")
def api_ip():
    return jsonify({"ip": get_public_ip()})


@app.route("/api/check")
def api_check():
    ok, msg = check_binance()
    return jsonify({"ok": ok, "message": msg})


# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Forzar UTF-8 en stdout para Windows (evita UnicodeEncodeError con emojis)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    port = int(os.getenv("PANEL_PORT", "5000"))
    print("=" * 60)
    print("[OK] Panel iniciado")
    print(f"     Abri en tu navegador: http://localhost:{port}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=False)



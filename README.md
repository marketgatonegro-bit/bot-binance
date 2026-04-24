# 🤖 Trailing Stop Loss Bot — Binance

Bot de trading automático con trailing stop loss. Compra un par de cripto,
sigue la suba actualizando el stop loss, y vende automáticamente si el precio cae.

---

## 🌐 Panel visual para autorizar tu IP en Binance

Antes de arrancar el bot, Binance te pide whitelistear la IP desde donde se conecta tu API Key.
Este proyecto incluye un panel web simple para mostrarte tu IP pública y testear la conexión.

```bash
# 1. Copiá .env.example a .env y completá tus claves
copy .env.example .env

# 2. Instalá dependencias
pip install -r requirements.txt

# 3. Arrancá el panel
python ip_panel.py
```

Luego abrí en tu navegador: **http://localhost:5000**

Vas a ver:
- 📡 Tu **IP pública** (con botón para copiar)
- ✅ Si las API Keys están cargadas
- ✅ Si la conexión con Binance funciona (y tu balance USDT/BNB)

Pegá esa IP en Binance → API Management → *Restrict access to trusted IPs only*.

---


## ¿Cómo funciona?

```
Compra DOGE a $0.10
Stop loss inicial: $0.097 (-3%)

DOGE sube a $0.12 → stop loss sube a $0.1164
DOGE sube a $0.15 → stop loss sube a $0.1455
DOGE cae a $0.1455 → VENTA AUTOMÁTICA ✅ (ganaste ~$0.045 por DOGE)
```

---

## 📁 Archivos

```
bot.py                 ← el bot principal
telegram_notifier.py   ← módulo de notificaciones Telegram
ip_panel.py            ← panel web para whitelist de IP
requirements.txt       ← dependencias Python
.env.example           ← plantilla de configuración
```

---

## 📬 Notificaciones Telegram

El bot puede enviarte alertas en tiempo real a través de Telegram para que estés al tanto de todo sin mirar los logs.

### ¿Qué notifica?

| Evento | Descripción |
|--------|-------------|
| 📈 **Compras** | Cuando se ejecuta una compra (precio, cantidad, stop inicial) |
| 📉 **Ventas** | Cuando se ejecuta una venta (precio, PnL, razón: stop loss) |
| ⬆️ **Trailing Stop** | Cada vez que el stop loss se actualiza al alza |
| 🚨 **Errores críticos** | Fallas en compras/ventas o errores del loop que requieren tu atención |
| 📊 **Reporte diario** | Resumen automático cada día con balances y posiciones abiertas |
| 🤖 **Estado del bot** | Al iniciar el bot confirma que está corriendo |

### Configuración

1. **Creá tu bot en Telegram** (ya lo tenés: `@Trader161183_bot`)
2. **Copiá el token** al `.env`:
   ```
   TELEGRAM_TOKEN="8585394380:AAGmQJ4CXRF6TimrEw4chft7tWeA791D9Sg"
   TELEGRAM_ENABLED="true"
   DAILY_REPORT_HOUR=9
   ```
3. **Iniciá el bot y enviale `/start`** por Telegram para registrar tu chat
4. **Listo** — ahora recibirás todas las notificaciones

> 💡 **Tip:** El `chat_id` se guarda automáticamente en `telegram_chat_ids.json`. Si querés agregar otro celular, solo hay que enviarle `/start` al bot desde esa cuenta.

### Comandos disponibles en Telegram

Escribile al bot (`@Trader161183_bot`):

| Comando | Qué hace |
|---------|----------|
| `/start` | Registra tu chat para recibir notificaciones |
| `/status` | Muestra las posiciones abiertas y estado actual |
| `/balances` | Muestra los balances de tu cuenta Binance |
| `/help` | Lista de comandos disponibles |

### Reporte diario automático

Cada día a la hora configurada (`DAILY_REPORT_HOUR`, por defecto 09:00 UTC / 06:00 hora Argentina) el bot envía un resumen con:
- ⏱ Uptime del bot
- 💰 Balances actuales
- 📂 Posiciones abiertas (entry, stop loss, cantidad)

Para desactivar las notificaciones cambiá `TELEGRAM_ENABLED="false"` en el `.env`.

---

## 🚀 Paso a paso para subir a Railway
------- REPLACE


---

## 🚀 Paso a paso para subir a Railway

### 1. Crear el repositorio en GitHub

1. Entrá a https://github.com y creá una cuenta si no tenés
2. Click en **"New repository"**
3. Nombre: `trailing-bot` (o el que quieras)
4. Público o privado, da igual
5. Click **"Create repository"**
6. Subí los 3 archivos: `bot.py`, `requirements.txt`, `.env.example`
   - Click en **"uploading an existing file"**
   - Arrastrá los archivos
   - Click **"Commit changes"**

> ⚠️ **NUNCA subas el archivo `.env` con tus keys reales.** Solo sube `.env.example`.

---

### 2. Crear las API Keys en Binance

1. Entrá a Binance → **Perfil → Gestión de API**
2. Click **"Crear API"** → dale un nombre (ej: "mi-bot")
3. Verificá identidad si te pide
4. En permisos, marcá **SOLO** "Habilitar trading Spot"
   - ❌ NO habilites retiros
   - ❌ NO habilites futuros (por ahora)
5. Guardá el **API Key** y el **Secret** en algún lugar seguro

---

### 3. Desplegar en Railway

1. Entrá a https://railway.app y creá cuenta con tu GitHub
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Seleccioná tu repo `trailing-bot`
4. Railway va a detectar el proyecto Python automáticamente
5. Antes de que inicie, andá a **Variables** (pestaña del proyecto)
6. Agregá estas variables una por una:

   | Variable | Valor |
   |---|---|
   | `BINANCE_API_KEY` | tu key de Binance |
   | `BINANCE_API_SECRET` | tu secret de Binance |
   | `SYMBOLS` | `DOGEUSDT` |
   | `TRADE_AMOUNT` | `5` |
   | `TRAILING_PERCENT` | `3` |
   | `CHECK_INTERVAL` | `10` |
   | `PAPER_TRADING` | `true` |
   | `TELEGRAM_TOKEN` | token de @BotFather |
   | `TELEGRAM_ENABLED` | `true` |
   | `DAILY_REPORT_HOUR` | `9` (UTC) |

7. Click **"Deploy"** y listo 🎉

---

### 4. Ver los logs

En Railway, click en tu servicio → pestaña **"Logs"**.
Vas a ver algo así:

```
2024-01-15 10:23:01 [INFO] 🤖 BOT INICIADO | Par: DOGEUSDT | Capital: $5 | Trailing: 3%
2024-01-15 10:23:01 [INFO] 🟡 PAPER TRADING
2024-01-15 10:23:02 [INFO] 📈 COMPRA | Precio: $0.0823 | Qty: 60.75 | Stop Loss: $0.0798
2024-01-15 10:23:12 [INFO] 👀 Monitoreando | Precio: $0.0825 | Stop: $0.0800 | PnL: +$0.0012
```

---

### 5. Pasar a dinero real

Cuando estés cómodo con los resultados en paper trading:

1. En Railway → Variables
2. Cambiá `PAPER_TRADING` de `true` a `false`
3. Asegurate de tener USDT en tu cuenta Binance
4. Railway reinicia automáticamente el bot

---

## ⚙️ Configuración recomendada para $5

| Variable | Valor sugerido | Por qué |
|---|---|---|
| `SYMBOL` | `DOGEUSDT` | Mínimo de orden bajo (~$1) |
| `TRADE_AMOUNT` | `5` | Tu capital |
| `TRAILING_PERCENT` | `3` | Balance entre protección y aguantar volatilidad normal |
| `CHECK_INTERVAL` | `10` | Cada 10 segundos (no es tan agresivo con la API) |

---

## ⚠️ Riesgos importantes

- **El trading tiene riesgo de pérdida**. Este bot no garantiza ganancias.
- Empezá siempre en paper trading para entender el comportamiento.
- Con $5 las comisiones de Binance (~0.1% por operación) impactan bastante.
- No inviertas dinero que no podés permitirte perder.
# bot-binance
# bot-binance

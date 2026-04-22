# 🤖 Trailing Stop Loss Bot — Binance

Bot de trading automático con trailing stop loss. Compra un par de cripto,
sigue la suba actualizando el stop loss, y vende automáticamente si el precio cae.

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
bot.py            ← el bot
requirements.txt  ← dependencias Python
.env.example      ← plantilla de configuración
```

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
   | `SYMBOL` | `DOGEUSDT` |
   | `TRADE_AMOUNT` | `5` |
   | `TRAILING_PERCENT` | `3` |
   | `CHECK_INTERVAL` | `10` |
   | `PAPER_TRADING` | `true` |

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

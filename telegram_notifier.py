"""
📬 Notificador Telegram para el Bot de Trading
─────────────────────────────────────────────
Módulo de notificaciones que envía:
  • Alertas de compra/venta
  • Errores críticos que requieren intervención
  • Reporte diario automático (balances + rendimiento)
  • Estado del bot bajo demanda

Usa python-telegram-bot para manejar comandos y
requests como fallback para enviar mensajes simples.
"""

import os
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable

import requests

log = logging.getLogger(__name__)

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"

CHAT_IDS_FILE = "telegram_chat_ids.json"
DAILY_REPORT_HOUR = int(os.getenv("DAILY_REPORT_HOUR", "9"))   # Hora UTC del reporte diario

# ─── PERSISTENCIA DE CHAT IDs ────────────────────────────────────────────────

def _load_chat_ids() -> List[str]:
    if os.path.exists(CHAT_IDS_FILE):
        try:
            with open(CHAT_IDS_FILE, "r") as f:
                data = json.load(f)
                return data.get("chat_ids", [])
        except Exception:
            pass
    return []


def _save_chat_ids(chat_ids: List[str]):
    try:
        with open(CHAT_IDS_FILE, "w") as f:
            json.dump({"chat_ids": chat_ids}, f, indent=2)
    except Exception as e:
        log.warning(f"No se pudieron guardar chat_ids: {e}")


# chat_ids en memoria (se leen al importar el módulo)
_registered_chat_ids: List[str] = _load_chat_ids()


def _get_all_chat_ids() -> List[str]:
    return list(set(_registered_chat_ids))


# ─── ENVÍO DE MENSAJES ───────────────────────────────────────────────────────

def send_telegram_message(text: str, parse_mode: str = "HTML") -> bool:
    """Envía un mensaje a todos los chat_ids registrados usando la HTTP API."""
    if not TELEGRAM_ENABLED or not TELEGRAM_TOKEN:
        return False

    chat_ids = _get_all_chat_ids()
    if not chat_ids:
        log.debug("No hay chat_ids registrados para notificar.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    ok = True
    for chat_id in chat_ids:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        try:
            r = requests.post(url, json=payload, timeout=15)
            data = r.json()
            if not data.get("ok"):
                log.warning(f"Telegram API error para {chat_id}: {data}")
                ok = False
        except Exception as e:
            log.warning(f"Error enviando mensaje a {chat_id}: {e}")
            ok = False
    return ok


def notify_event(title: str, message: str, emoji: str = "📢"):
    """Envía una notificación de evento genérico."""
    text = f"<b>{emoji} {title}</b>\n\n{message}\n\n<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"
    return send_telegram_message(text)


def notify_buy(symbol: str, price: float, stop: float, qty: float, paper: bool = True):
    modo = "🟡 PAPER" if paper else "🔴 REAL"
    text = (
        f"📈 <b>COMPRA EJECUTADA</b>  <code>{modo}</code>\n\n"
        f"<b>Par:</b> <code>{symbol}</code>\n"
        f"<b>Precio:</b> <code>${price:,.8f}</code>\n"
        f"<b>Cantidad:</b> <code>{qty:,.4f}</code>\n"
        f"<b>Stop inicial:</b> <code>${stop:,.8f}</code>\n\n"
        f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"
    )
    return send_telegram_message(text)


def notify_sell(symbol: str, price: float, pnl: float, reason: str, paper: bool = True):
    modo = "🟡 PAPER" if paper else "🔴 REAL"
    emoji_pnl = "🟢" if pnl >= 0 else "🔴"
    text = (
        f"📉 <b>VENTA EJECUTADA</b>  <code>{modo}</code>\n\n"
        f"<b>Par:</b> <code>{symbol}</code>\n"
        f"<b>Precio:</b> <code>${price:,.8f}</code>\n"
        f"<b>Razón:</b> <code>{reason}</code>\n"
        f"<b>PnL:</b> {emoji_pnl} <code>${pnl:+.4f}</code>\n\n"
        f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"
    )
    return send_telegram_message(text)


def notify_trailing_updated(symbol: str, new_stop: float):
    text = (
        f"⬆️ <b>TRAILING STOP ACTUALIZADO</b>\n\n"
        f"<b>Par:</b> <code>{symbol}</code>\n"
        f"<b>Nuevo stop:</b> <code>${new_stop:,.8f}</code>\n\n"
        f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"
    )
    return send_telegram_message(text)


def notify_critical_error(context: str, error: str):
    text = (
        f"🚨 <b>ERROR CRÍTICO — REQUIERE INTERVENCIÓN</b>\n\n"
        f"<b>Contexto:</b> <code>{context}</code>\n"
        f"<b>Error:</b> <pre>{error[:800]}</pre>\n\n"
        f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"
    )
    return send_telegram_message(text)


def notify_daily_report(balances: Dict, state: Dict, uptime_hours: float, paper: bool = True):
    modo = "🟡 PAPER TRADING" if paper else "🔴 TRADING REAL"

    # Construir bloque de balances
    lines_bal = [f"  • <b>{asset}:</b> <code>{info['free']:.6f}</code> (locked: {info['locked']:.6f})"
                 for asset, info in balances.items()]
    bal_text = "\n".join(lines_bal) if lines_bal else "  <i>No hay balances visibles</i>"

    # Posiciones abiertas
    open_pos = []
    for sym, st in state.items():
        if st.get("in_position"):
            open_pos.append(f"  • <b>{sym}</b> — Entry: <code>${st['entry_price']:,.8f}</code> | "
                            f"Stop: <code>${st['stop_loss']:,.8f}</code> | "
                            f"Qty: <code>{st['quantity']:,.4f}</code>")
    pos_text = "\n".join(open_pos) if open_pos else "  <i>Sin posiciones abiertas</i>"

    text = (
        f"📊 <b>REPORTE DIARIO</b>  <code>{modo}</code>\n\n"
        f"⏱ <b>Uptime:</b> <code>{uptime_hours:.1f}h</code>\n\n"
        f"💰 <b>Balances:</b>\n{bal_text}\n\n"
        f"📂 <b>Posiciones abiertas:</b>\n{pos_text}\n\n"
        f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"
    )
    return send_telegram_message(text)


# ─── BOT DE COMANDOS (polling en hilo aparte) ────────────────────────────────

def _get_updates(offset: Optional[int] = None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": offset, "limit": 10} if offset else {"limit": 10}
    try:
        r = requests.get(url, params=params, timeout=15)
        return r.json()
    except Exception:
        return {}


def _send_reply(chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=15)
    except Exception:
        pass


def _format_status(state: Dict, paper: bool, symbols: List[str]) -> str:
    modo = "🟡 PAPER" if paper else "🔴 REAL"
    lines = [f"🤖 <b>ESTADO DEL BOT</b>  <code>{modo}</code>\n"]
    for sym in symbols:
        st = state.get(sym, {})
        if st.get("in_position"):
            lines.append(
                f"📂 <b>{sym}</b> — Entry: <code>${st['entry_price']:,.8f}</code> | "
                f"Stop: <code>${st['stop_loss']:,.8f}</code> | "
                f"Qty: <code>{st['quantity']:,.4f}</code>"
            )
        else:
            lines.append(f"👀 <b>{sym}</b> — Sin posición")
    return "\n".join(lines)


def _format_balances(balances: Dict) -> str:
    lines = ["💰 <b>BALANCES</b>\n"]
    if not balances:
        lines.append("<i>No se pudieron obtener los balances.</i>")
        return "\n".join(lines)
    for asset, info in balances.items():
        lines.append(f"  <b>{asset}:</b> <code>{info['free']:.6f}</code> (locked {info['locked']:.6f})")
    return "\n".join(lines)


class TelegramCommandBot:
    """
    Pequeño bot de polling que corre en un hilo daemon.
    Responde a /start, /status, /balances y /help.
    """

    def __init__(self,
                 get_state_fn: Optional[Callable] = None,
                 get_balances_fn: Optional[Callable] = None,
                 is_paper_fn: Optional[Callable] = None,
                 symbols: Optional[List[str]] = None):
        self.get_state = get_state_fn
        self.get_balances = get_balances_fn
        self.is_paper = is_paper_fn
        self.symbols = symbols or []
        self._offset: Optional[int] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = False

    def start(self):
        if not TELEGRAM_ENABLED or not TELEGRAM_TOKEN:
            log.info("Telegram deshabilitado o sin token. Bot de comandos no iniciado.")
            return
        self._stop = False
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="tg-cmd-bot")
        self._thread.start()
        log.info("🤖 Bot de comandos de Telegram iniciado.")

    def stop(self):
        self._stop = True

    def _poll_loop(self):
        while not self._stop:
            try:
                data = _get_updates(self._offset)
                for upd in data.get("result", []):
                    self._offset = upd["update_id"] + 1
                    self._handle_update(upd)
            except Exception as e:
                log.debug(f"Error en polling Telegram: {e}")
            time.sleep(3)

    def _handle_update(self, upd: dict):
        msg = upd.get("message")
        if not msg:
            return
        text = msg.get("text", "").strip()
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if not chat_id:
            return

        # Registrar chat_id automáticamente al interactuar
        if chat_id not in _registered_chat_ids:
            _registered_chat_ids.append(chat_id)
            _save_chat_ids(_registered_chat_ids)
            log.info(f"Nuevo chat_id registrado: {chat_id}")

        cmd = text.lower().split()[0] if text else ""

        if cmd == "/start":
            _send_reply(
                chat_id,
                "👋 <b>¡Bienvenido!</b>\n\n"
                "Este bot te notificará de:\n"
                "  • Compras y ventas\n"
                "  • Errores críticos\n"
                "  • Reportes diarios automáticos\n\n"
                "Comandos disponibles:\n"
                "  /status — Estado del bot\n"
                "  /balances — Tus balances\n"
                "  /help — Ayuda"
            )

        elif cmd == "/help":
            _send_reply(
                chat_id,
                "📖 <b>Comandos</b>\n\n"
                "<b>/start</b> — Registra este chat para recibir notificaciones\n"
                "<b>/status</b> — Ver posiciones abiertas y estado\n"
                "<b>/balances</b> — Ver balances de la cuenta\n"
                "<b>/help</b> — Mostrar este mensaje"
            )

        elif cmd == "/status":
            if self.get_state and self.is_paper:
                try:
                    state = self.get_state()
                    paper = self.is_paper()
                    reply = _format_status(state, paper, self.symbols)
                except Exception as e:
                    reply = f"⚠️ Error obteniendo estado: {e}"
            else:
                reply = "ℹ️ El estado no está disponible aún."
            _send_reply(chat_id, reply)

        elif cmd == "/balances":
            if self.get_balances:
                try:
                    balances = self.get_balances()
                    reply = _format_balances(balances)
                except Exception as e:
                    reply = f"⚠️ Error obteniendo balances: {e}"
            else:
                reply = "ℹ️ Los balances no están disponibles aún."
            _send_reply(chat_id, reply)

        else:
            _send_reply(chat_id, "❓ Comando no reconocido. Usá /help para ver los disponibles.")


# ─── REPORTE DIARIO AUTOMÁTICO ───────────────────────────────────────────────

class DailyReporter:
    """
    Hilo que cada ~hora verifica si ya pasó la hora configurada
    (UTC) y dispara el reporte diario una vez por día.
    """

    def __init__(self,
                 get_balances_fn: Callable,
                 get_state_fn: Callable,
                 is_paper_fn: Callable,
                 uptime_start: datetime):
        self.get_balances = get_balances_fn
        self.get_state = get_state_fn
        self.is_paper = is_paper_fn
        self.uptime_start = uptime_start
        self._thread: Optional[threading.Thread] = None
        self._stop = False
        self._last_report_date: Optional[str] = None

    def start(self):
        if not TELEGRAM_ENABLED or not TELEGRAM_TOKEN:
            log.info("Telegram deshabilitado. Reporte diario no iniciado.")
            return
        self._stop = False
        self._thread = threading.Thread(target=self._loop, daemon=True, name="daily-reporter")
        self._thread.start()
        log.info(f"📅 Reporte diario configurado para las {DAILY_REPORT_HOUR:02d}:00 UTC.")

    def stop(self):
        self._stop = True

    def _loop(self):
        while not self._stop:
            try:
                now = datetime.utcnow()
                today_str = now.strftime("%Y-%m-%d")
                if now.hour >= DAILY_REPORT_HOUR and self._last_report_date != today_str:
                    self._send_report()
                    self._last_report_date = today_str
            except Exception as e:
                log.warning(f"Error en reporte diario: {e}")
            # Verificar cada 30 minutos
            for _ in range(1800):
                if self._stop:
                    break
                time.sleep(1)

    def _send_report(self):
        try:
            balances = self.get_balances() if self.get_balances else {}
            state = self.get_state() if self.get_state else {}
            uptime = (datetime.utcnow() - self.uptime_start).total_seconds() / 3600.0
            paper = self.is_paper() if self.is_paper else True
            notify_daily_report(balances, state, uptime, paper)
            log.info("📊 Reporte diario enviado por Telegram.")
        except Exception as e:
            log.error(f"Error enviando reporte diario: {e}")


# ─── FUNCIONES DE CONVENIENCIA ───────────────────────────────────────────────

def init_telegram(get_state_fn, get_balances_fn, is_paper_fn, symbols, uptime_start):
    """
    Inicia el bot de comandos y el reporte diario.
    Devuelve una tupla (command_bot, daily_reporter) para poder detenerlos luego.
    """
    cmd_bot = TelegramCommandBot(
        get_state_fn=get_state_fn,
        get_balances_fn=get_balances_fn,
        is_paper_fn=is_paper_fn,
        symbols=symbols,
    )
    reporter = DailyReporter(
        get_balances_fn=get_balances_fn,
        get_state_fn=get_state_fn,
        is_paper_fn=is_paper_fn,
        uptime_start=uptime_start,
    )
    cmd_bot.start()
    reporter.start()
    return cmd_bot, reporter

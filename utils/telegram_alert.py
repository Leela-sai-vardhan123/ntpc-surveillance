"""
Telegram Alert System
Sends violation photo + details to Telegram bot instantly.
Setup:
  1. Message @BotFather on Telegram → /newbot → get token
  2. Message @userinfobot → get your chat_id
  3. Add to .env:  TELEGRAM_TOKEN=xxx  TELEGRAM_CHAT_ID=xxx
"""

import os
import threading
import requests
from datetime import datetime


class TelegramAlerter:
    def __init__(self, token: str = None, chat_id: str = None):
        self.token   = token   or os.getenv("TELEGRAM_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id)
        self._cooldown = {}  # vehicle_id -> last sent time

        if self.enabled:
            print(f"[Telegram] Alerts enabled → chat_id: {self.chat_id}")
        else:
            print("[Telegram] Not configured — set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID")

    def _send_message(self, text: str):
        if not self.enabled:
            return
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            requests.post(url, data={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
            }, timeout=5)
        except Exception as e:
            print(f"[Telegram] Message failed: {e}")

    def _send_photo(self, image_path: str, caption: str):
        if not self.enabled:
            return
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
            with open(image_path, "rb") as photo:
                requests.post(url, data={
                    "chat_id": self.chat_id,
                    "caption": caption,
                    "parse_mode": "HTML",
                }, files={"photo": photo}, timeout=10)
        except Exception as e:
            print(f"[Telegram] Photo failed: {e}")

    def send_violation(self, violation_type: str, plate: str,
                       speed=None, vehicle_type="vehicle",
                       camera_id="CAM_01", evidence_path=None,
                       vehicle_id=0):
        """Send violation alert — non-blocking."""
        import time
        now  = time.time()
        last = self._cooldown.get(vehicle_id, 0)
        if now - last < 10:  # 10s cooldown per vehicle
            return
        self._cooldown[vehicle_id] = now

        ts    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        icon  = "🚨" if "SPEED" in violation_type else "⛑️"
        speed_str = f"\n🚗 <b>Speed:</b> {speed:.1f} km/h" if speed else ""

        caption = (
            f"{icon} <b>VIOLATION DETECTED</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>Type:</b> {violation_type}\n"
            f"🔢 <b>Plate:</b> <code>{plate}</code>\n"
            f"🚙 <b>Vehicle:</b> {vehicle_type.upper()}"
            f"{speed_str}\n"
            f"📷 <b>Camera:</b> {camera_id}\n"
            f"🕐 <b>Time:</b> {ts}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<i>NTPC Smart Surveillance System</i>"
        )

        def _send():
            if evidence_path and os.path.exists(evidence_path):
                self._send_photo(evidence_path, caption)
            else:
                self._send_message(caption)

        threading.Thread(target=_send, daemon=True).start()

    def send_startup(self, camera_id="CAM_01"):
        """Notify when system starts."""
        msg = (
            f"✅ <b>NTPC Surveillance System ONLINE</b>\n"
            f"📷 Camera: {camera_id}\n"
            f"🕐 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        threading.Thread(target=self._send_message, args=(msg,), daemon=True).start()

    def send_summary(self, total, n_speed, n_helmet, camera_id="CAM_01"):
        """Send session summary when detection stops."""
        msg = (
            f"📊 <b>Session Summary</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📷 Camera: {camera_id}\n"
            f"🚨 Total Violations: <b>{total}</b>\n"
            f"⚡ Overspeed: <b>{n_speed}</b>\n"
            f"⛑️ No Helmet: <b>{n_helmet}</b>\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<i>NTPC Smart Surveillance System 2025</i>"
        )
        threading.Thread(target=self._send_message, args=(msg,), daemon=True).start()

    @staticmethod
    def test_connection(token: str, chat_id: str) -> tuple[bool, str]:
        """Test if token + chat_id are valid. Returns (success, message)."""
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            r = requests.post(url, data={
                "chat_id": chat_id,
                "text": "✅ NTPC Surveillance System — Telegram connected successfully!",
            }, timeout=5)
            if r.status_code == 200:
                return True, "Connected successfully!"
            else:
                return False, r.json().get("description", "Unknown error")
        except Exception as e:
            return False, str(e)

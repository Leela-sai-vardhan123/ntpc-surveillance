"""
Alert System Module
Plays custom .wav sound files for each violation type.
Place your sound files in E:/NTPC-INT/assets/
  - overspeed.wav  → plays on OVERSPEED violation
  - helmet.wav     → plays on NO_HELMET violation
Falls back to winsound.Beep() if file not found.
"""

import threading
import time
import os

_HERE  = os.path.dirname(os.path.abspath(__file__))
_ROOT  = os.path.abspath(os.path.join(_HERE, ".."))
ASSETS = os.path.join(_ROOT, "assets")


def _play_wav(path):
    """Play a .wav file using winsound (Windows built-in, no install needed)."""
    try:
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME)
    except Exception as e:
        print(f"[Alert] Could not play {path}: {e}")


def _play_mp3(path):
    """Play .mp3 using playsound library."""
    try:
        from playsound import playsound
        playsound(path, block=True)
    except ImportError:
        print("[Alert] playsound not installed. Run: pip install playsound==1.2.2")
        _beep_fallback("generic")
    except Exception as e:
        print(f"[Alert] Could not play {path}: {e}")
        _beep_fallback("generic")


def _play_file(path):
    """Auto-detect format and play."""
    if not path or not os.path.exists(path):
        return False
    ext = os.path.splitext(path)[1].lower()
    if ext == ".wav":
        _play_wav(path)
    elif ext == ".mp3":
        _play_mp3(path)
    else:
        print(f"[Alert] Unsupported format: {ext}. Use .wav or .mp3")
        return False
    return True


def _beep_fallback(vtype):
    """Fallback beeps if no sound file found."""
    try:
        import winsound
        if "speed" in vtype.lower():
            # Fast urgent beeps for overspeed
            for _ in range(4):
                winsound.Beep(1400, 150)
                time.sleep(0.05)
        elif "helmet" in vtype.lower():
            # Slow warning tone for helmet
            for _ in range(2):
                winsound.Beep(600, 500)
                time.sleep(0.1)
        else:
            winsound.Beep(1000, 400)
    except Exception as e:
        print(f"[Alert] Beep fallback error: {e}")


class AlertSystem:
    def __init__(self, sound_path=None, cooldown_sec=4):
        """
        sound_path  : ignored (kept for compatibility)
        cooldown_sec: seconds between alerts per vehicle
        
        Sound files expected at:
          assets/overspeed.wav  (or .mp3)
          assets/helmet.wav     (or .mp3)
        """
        self.cooldown_sec = cooldown_sec
        self._last_alert  = {}

        # Auto-find sound files in assets/
        self.sounds = {
            "overspeed": self._find_sound("overspeed"),
            "helmet":    self._find_sound("helmet"),
        }

        # Print what was found
        for key, path in self.sounds.items():
            if path:
                print(f"[Alert] {key:10s} sound → {path}")
            else:
                print(f"[Alert] {key:10s} sound → NOT FOUND — will use beep fallback")
                print(f"[Alert] To add sound: put overspeed.wav or helmet.wav in {ASSETS}")

    def _find_sound(self, name):
        """Look for name.wav or name.mp3 in assets folder."""
        os.makedirs(ASSETS, exist_ok=True)
        for ext in [".wav", ".mp3"]:
            path = os.path.join(ASSETS, name + ext)
            if os.path.exists(path):
                return path
        return None

    def trigger(self, vehicle_id, violation_type, plate_text, speed=None):
        """
        Trigger alert for a violation.
        Non-blocking — plays in background thread.
        """
        now  = time.time()
        last = self._last_alert.get(vehicle_id, 0)

        if now - last < self.cooldown_sec:
            return False

        self._last_alert[vehicle_id] = now

        # Console log
        ts  = time.strftime("%H:%M:%S")
        spd = f" | Speed: {speed:.1f} km/h" if speed else ""
        print(f"\n[{ts}] ALERT {violation_type} | ID:{vehicle_id} | Plate:{plate_text}{spd}\n")

        # Pick sound file
        if "SPEED" in violation_type.upper():
            sound_path = self.sounds.get("overspeed")
            vtype_key  = "speed"
        else:
            sound_path = self.sounds.get("helmet")
            vtype_key  = "helmet"

        def _play():
            played = _play_file(sound_path)
            if not played:
                _beep_fallback(vtype_key)

        threading.Thread(target=_play, daemon=True).start()
        return True

    def generate_buzzer_wav(self, output_path=None):
        """Kept for API compatibility only."""
        return None

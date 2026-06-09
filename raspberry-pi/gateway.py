"""
BLE Gateway Middleware — Raspberry Pi
======================================
Scan BLE advertisement → publish ke MQTT broker → diterima Flask dashboard.

Jalankan:
    python gateway.py

Dependensi (install di Pi):
    pip install bleak paho-mqtt python-dotenv
"""

import asyncio
import json
import time
import logging
import os
import signal
import sys

from bleak import BleakScanner
from dotenv import load_dotenv

load_dotenv()

# ─── Konfigurasi ──────────────────────────────────────────────────────────────
GATEWAY_ID      = os.getenv("GATEWAY_ID",      "GW-001")
MQTT_HOST       = os.getenv("MQTT_HOST",       "36.92.47.218")
MQTT_PORT       = int(os.getenv("MQTT_PORT",   "14583"))
RSSI_MIN        = int(os.getenv("RSSI_MIN",    "-80"))
DEBOUNCE_LOCAL  = int(os.getenv("DEBOUNCE_LOCAL", "30"))
SCAN_INTERVAL   = float(os.getenv("SCAN_INTERVAL", "0"))   # 0 = continuous
HEARTBEAT_SECS  = int(os.getenv("HEARTBEAT_SECS", "30"))

TOPIC_EVENTS    = f"ble/events/{GATEWAY_ID}"
TOPIC_HEARTBEAT = f"ble/heartbeat/{GATEWAY_ID}"

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("BLEGateway")

# ─── State ────────────────────────────────────────────────────────────────────
_last_sent: dict[str, float] = {}
_mqtt_client = None


# ─── MQTT Setup ───────────────────────────────────────────────────────────────

def build_mqtt_client():
    import paho.mqtt.client as mqtt

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.error(f"MQTT gagal: {reason_code}")
        else:
            log.info(f"MQTT OK — {MQTT_HOST}:{MQTT_PORT} | topic: {TOPIC_EVENTS}")

    def on_disconnect(client, userdata, flags, reason_code, properties):
        log.warning(f"MQTT terputus ({reason_code}), akan reconnect otomatis...")

    def on_publish(client, userdata, mid, reason_code, properties):
        log.debug(f"Publish OK mid={mid}")

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"pi-{GATEWAY_ID}",
        clean_session=True
    )
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish    = on_publish
    client.reconnect_delay_set(min_delay=3, max_delay=60)

    return client


def mqtt_connect():
    global _mqtt_client
    _mqtt_client = build_mqtt_client()
    try:
        _mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        _mqtt_client.loop_start()
        log.info(f"Menghubungkan ke MQTT {MQTT_HOST}:{MQTT_PORT}...")
    except Exception as e:
        log.error(f"Tidak bisa connect ke MQTT: {e}")
        log.error("Pastikan MQTT_HOST dan MQTT_PORT di .env sudah benar.")
        sys.exit(1)


def mqtt_publish(topic: str, payload: dict):
    if _mqtt_client is None:
        return
    try:
        _mqtt_client.publish(
            topic,
            json.dumps(payload),
            qos=1          # QoS 1: guaranteed at least once delivery
        )
    except Exception as e:
        log.error(f"Publish gagal: {e}")


# ─── Debounce lokal ───────────────────────────────────────────────────────────

def is_debounced(mac: str) -> bool:
    now  = time.time()
    last = _last_sent.get(mac, 0)
    if now - last < DEBOUNCE_LOCAL:
        return True
    _last_sent[mac] = now
    return False


# ─── BLE Callback ─────────────────────────────────────────────────────────────

def on_ble_detected(device, advertisement_data):
    mac  = device.address.upper()
    rssi = advertisement_data.rssi

    # Filter sinyal terlalu lemah
    if rssi < RSSI_MIN:
        return

    # Debounce lokal — jangan spam broker
    if is_debounced(mac):
        return

    payload = {
        "mac_address": mac,
        "gateway_id":  GATEWAY_ID,
        "rssi":        rssi
    }
    log.info(f"DETECT | {mac} | {rssi} dBm → publish {TOPIC_EVENTS}")
    mqtt_publish(TOPIC_EVENTS, payload)


# ─── Heartbeat Task ───────────────────────────────────────────────────────────

async def heartbeat_task():
    """Kirim heartbeat periodik agar server tahu gateway masih Online."""
    while True:
        await asyncio.sleep(HEARTBEAT_SECS)
        payload = {
            "gateway_id": GATEWAY_ID,
            "timestamp":  time.strftime("%Y-%m-%d %H:%M:%S")
        }
        mqtt_publish(TOPIC_HEARTBEAT, payload)
        log.debug(f"HEARTBEAT → {TOPIC_HEARTBEAT}")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    log.info("=" * 50)
    log.info(f"BLE Gateway Middleware")
    log.info(f"  Gateway ID     : {GATEWAY_ID}")
    log.info(f"  MQTT Broker    : {MQTT_HOST}:{MQTT_PORT}")
    log.info(f"  Topic events   : {TOPIC_EVENTS}")
    log.info(f"  RSSI minimum   : {RSSI_MIN} dBm")
    log.info(f"  Debounce lokal : {DEBOUNCE_LOCAL} detik")
    log.info("=" * 50)

    mqtt_connect()

    # Jalankan heartbeat di background
    asyncio.create_task(heartbeat_task())

    # Mulai BLE scan continuous
    log.info("Mulai scanning BLE...")
    async with BleakScanner(detection_callback=on_ble_detected):
        # Scan terus sampai di-interrupt
        while True:
            await asyncio.sleep(1)


def handle_shutdown(sig, frame):
    log.info("Shutdown...")
    if _mqtt_client:
        _mqtt_client.loop_stop()
        _mqtt_client.disconnect()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT,  handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    asyncio.run(main())

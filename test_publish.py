"""
test_publish.py — Simulasi Raspberry Pi kirim data BLE ke MQTT broker
Jalankan: python test_publish.py
"""

import paho.mqtt.client as mqtt
import json, time, random, sys

# ─── Config ───────────────────────────────────────────────────────────────────
MQTT_HOST = "36.92.47.218"
MQTT_PORT = 14583
INTERVAL  = 3          # detik antar publish (ubah sesuka hati)

# MAC address yang sudah terdaftar di dashboard (ble_tags)
TAGS = [
    {"mac": "AA:BB:CC:DD:01:01", "container": "CONT-001"},
    {"mac": "AA:BB:CC:DD:01:02", "container": "CONT-002"},
    {"mac": "AA:BB:CC:DD:01:03", "container": "CONT-003"},
    {"mac": "AA:BB:CC:DD:01:04", "container": "CONT-004"},
    {"mac": "AA:BB:CC:DD:01:05", "container": "CONT-005"},
]

# Gateway yang sudah terdaftar di dashboard
GATEWAYS = ["GW-001", "GW-002", "GW-003", "GW-004"]

# ─── MQTT ─────────────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc, props):
    if rc.is_failure:
        print(f"[ERROR] Gagal konek: {rc}")
        sys.exit(1)
    print(f"[OK] Terhubung ke {MQTT_HOST}:{MQTT_PORT}")
    print(f"[INFO] Mulai publish setiap {INTERVAL} detik... (Ctrl+C untuk stop)\n")

client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id="test-publisher"
)
client.on_connect = on_connect
client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
client.loop_start()
time.sleep(1.5)  # tunggu on_connect

# ─── Loop publish ─────────────────────────────────────────────────────────────
counter = 0
try:
    while True:
        counter += 1
        tag = random.choice(TAGS)
        gw  = random.choice(GATEWAYS)
        rssi = random.randint(-80, -55)

        payload = {
            "mac_address": tag["mac"],
            "gateway_id":  gw,
            "rssi":        rssi
        }
        topic = f"ble/events/{gw}"

        client.publish(topic, json.dumps(payload), qos=1)

        print(f"[{counter:04d}] PUBLISH -> topic: {topic}")
        print(f"        MAC: {tag['mac']}  container: {tag['container']}")
        print(f"        RSSI: {rssi} dBm  gateway: {gw}")
        print()

        time.sleep(INTERVAL)

except KeyboardInterrupt:
    print("\n[STOP] Publisher dihentikan.")
    client.loop_stop()
    client.disconnect()

# Middleware Plan — BLE Gateway → MQTT → Dashboard

## 1. Arsitektur

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AREA DEPO / GATE                            │
│                                                                     │
│  [BLE TAG]      [BLE TAG]      [BLE TAG]                           │
│  (di container) (di container) (di container)                      │
│      │               │               │                             │
│      └─── BLE Advertise (broadcast MAC tiap ~100ms) ───┘           │
│                           │                                         │
│                  ┌────────▼────────┐                                │
│                  │  Raspberry Pi   │  ← 1 Pi per gate               │
│                  │  gateway.py     │                                 │
│                  │  (bleak scan)   │                                 │
│                  └────────┬────────┘                                │
└───────────────────────────┼─────────────────────────────────────────┘
                            │ MQTT Publish QoS 1
                            │ topic: ble/events/GW-001
                            │ (internet / VPN)
                            ▼
              ┌─────────────────────────────────┐
              │         VM (Public IP)          │
              │                                 │
              │  ┌─────────────────────────┐    │
              │  │  Mosquitto Broker :1883 │    │
              │  └────────────┬────────────┘    │
              │               │ subscribe       │
              │               │ ble/events/#    │
              │  ┌────────────▼────────────┐    │
              │  │  Flask app.py           │    │
              │  │  start_mqtt_client()    │    │
              │  │                         │    │
              │  │  process_ble_event()    │    │
              │  │  ├─ debounce check      │    │
              │  │  ├─ lookup MAC → tag    │    │
              │  │  ├─ lookup GW → zone    │    │
              │  │  ├─ INSERT event_logs   │    │
              │  │  └─ emit WebSocket      │    │
              │  └──────────┬──────────────┘    │
              │             │                   │
              │  ┌──────────▼──────┐            │
              │  │   SQLite DB     │            │
              │  └─────────────────┘            │
              └────────────────┬────────────────┘
                               │ WebSocket
                               ▼
                      ┌─────────────────┐
                      │  Dashboard      │
                      │  Browser        │
                      │  (real-time)    │
                      └─────────────────┘
```

---

## 2. Kenapa MQTT, Bukan HTTP Langsung?

| | HTTP POST langsung | MQTT (dipilih) |
|---|---|---|
| Koneksi Pi putus sesaat | Event **hilang** | QoS 1: tersimpan, dikirim saat reconnect |
| Pi di sinyal lemah | Timeout, perlu retry manual | Built-in reconnect + backoff otomatis |
| Banyak Pi/gateway | Semua harus tahu IP VM | Cukup tahu IP broker |
| VM restart sebentar | Event lost | Broker buffer pesan |
| Overhead data | HTTP header ~500 byte/req | MQTT payload ~50 byte/msg |
| Fallback jika MQTT mati | — | HTTP endpoint `/api/ble/event` tetap ada |

---

## 3. MQTT Topic Design

```
ble/events/{gateway_id}      ← deteksi BLE dari Pi
ble/heartbeat/{gateway_id}   ← heartbeat Pi (setiap 30 detik)
```

**Payload event:**
```json
{
  "mac_address": "AA:BB:CC:DD:01:01",
  "gateway_id":  "GW-001",
  "rssi":        -65
}
```

**Payload heartbeat:**
```json
{
  "gateway_id": "GW-001",
  "timestamp":  "2025-06-09 14:32:00"
}
```

---

## 4. Struktur File

```
dashboard-skripsi/
├── app.py                    ← Flask + MQTT subscriber (sudah diupdate)
├── mosquitto.conf            ← Konfigurasi broker untuk VM
├── requirements.txt          ← Tambah paho-mqtt>=2.1.0
│
└── raspberry-pi/             ← Deploy ini ke Raspberry Pi
    ├── gateway.py            ← Script utama Pi
    ├── .env.example          ← Template konfigurasi (salin jadi .env)
    ├── requirements-pi.txt   ← bleak, paho-mqtt, python-dotenv
    └── ble-gateway.service   ← Systemd service (auto-start)
```

---

## 5. Setup VM

### Install Mosquitto
```bash
sudo apt update && sudo apt install -y mosquitto mosquitto-clients

# Copy konfigurasi
sudo cp mosquitto.conf /etc/mosquitto/conf.d/ble-monitor.conf
sudo systemctl restart mosquitto
sudo systemctl enable  mosquitto

# Cek berjalan
sudo systemctl status mosquitto
```

### Buka port di firewall VM
```bash
sudo ufw allow 1883    # MQTT
sudo ufw allow 5000    # Flask dashboard
sudo ufw reload
```

### Jalankan dashboard
```bash
cd dashboard-skripsi
pip install -r requirements.txt
python app.py
```

### Test broker dari terminal
```bash
# Terminal 1 — subscribe (pantau)
mosquitto_sub -h localhost -t "ble/#" -v

# Terminal 2 — simulate publish dari Pi
mosquitto_pub -h localhost -t "ble/events/GW-001" \
  -m '{"mac_address":"AA:BB:CC:DD:01:01","gateway_id":"GW-001","rssi":-65}'
```

---

## 6. Setup Raspberry Pi

### Copy file ke Pi
```bash
# Dari PC/laptop
scp -r raspberry-pi/ pi@<ip-pi>:/home/pi/ble-gateway/
```

### Install di Pi
```bash
ssh pi@<ip-pi>
cd /home/pi/ble-gateway

pip3 install -r requirements-pi.txt

# Buat file konfigurasi
cp .env.example .env
nano .env          # Isi GATEWAY_ID dan MQTT_HOST
```

### Isi `.env` di Pi
```env
GATEWAY_ID=GW-001
MQTT_HOST=103.45.67.89    # ← IP publik VM
MQTT_PORT=1883
RSSI_MIN=-80
DEBOUNCE_LOCAL=30
```

### Jalankan manual dulu (test)
```bash
python3 gateway.py
```

Output yang diharapkan:
```
14:32:01 [INFO] BLE Gateway Middleware
14:32:01 [INFO]   Gateway ID     : GW-001
14:32:01 [INFO]   MQTT Broker    : 103.45.67.89:1883
14:32:01 [INFO] Menghubungkan ke MQTT 103.45.67.89:1883...
14:32:02 [INFO] MQTT OK — 103.45.67.89:1883 | topic: ble/events/GW-001
14:32:02 [INFO] Mulai scanning BLE...
14:32:05 [INFO] DETECT | AA:BB:CC:DD:01:01 | -67 dBm → publish ble/events/GW-001
```

### Auto-start saat Pi nyala
```bash
sudo cp ble-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ble-gateway
sudo systemctl start  ble-gateway

# Monitor log
journalctl -u ble-gateway -f
```

---

## 7. Multi-Gateway (Banyak Pi)

Setiap Pi punya `.env` sendiri dengan `GATEWAY_ID` berbeda:

```
Pi #1 → GATEWAY_ID=GW-001 → topic: ble/events/GW-001
Pi #2 → GATEWAY_ID=GW-002 → topic: ble/events/GW-002
Pi #3 → GATEWAY_ID=GW-003 → topic: ble/events/GW-003
```

Flask subscribe `ble/events/#` — otomatis tangkap semua.  
Zone IN/OUT ditentukan dari setting gateway di dashboard, **bukan** dari Pi.

---

## 8. Logika IN/OUT (di Server)

```
Pi #1 (GW-001, zone=IN)  detect "AA:BB:CC:DD:01:01"
   → event_type = "IN"   (dari zone gateway GW-001)

Pi #2 (GW-002, zone=OUT) detect "AA:BB:CC:DD:01:01"
   → event_type = "OUT"  (dari zone gateway GW-002)
```

Konfigurasi zone dilakukan di halaman **Manajemen Gateway** dashboard.

---

## 9. Urutan Kerja End-to-End

```
1. Container masuk gate
2. BLE Tag broadcast MAC setiap ~100ms
3. Raspberry Pi scan → terdeteksi MAC + RSSI
4. Pi cek: RSSI < -80? → skip
5. Pi cek: debounce lokal (30 detik)? → skip
6. Pi publish ke MQTT topic ble/events/GW-001 (QoS 1)
7. Mosquitto broker terima → forward ke Flask subscriber
8. Flask process_ble_event():
   a. Cek debounce server (60 detik)
   b. SELECT ble_tags WHERE mac = "AA:BB:CC:DD:01:01" → dapat container_id
   c. SELECT gateways WHERE gateway_id = "GW-001" → dapat zone = "IN"
   d. INSERT event_logs
   e. UPDATE ble_tags.last_seen
   f. UPDATE gateways.last_active, status = "Online"
   g. socketio.emit("new_event", {...})
9. Dashboard browser terima WebSocket → update feed + KPI real-time
```

---

## 10. Troubleshooting

| Masalah | Sebab | Solusi |
|---|---|---|
| `MQTT gagal: Broker tidak tersedia` | IP/port salah atau firewall | Cek `MQTT_HOST`, buka port 1883 di VM |
| Gateway tetap Offline di dashboard | Heartbeat tidak sampai | Cek log Pi: MQTT terhubung? topic heartbeat benar? |
| `tag not found` di log Flask | MAC belum didaftarkan | Daftarkan di halaman BLE Tags |
| `gateway not found` | GATEWAY_ID di .env ≠ di dashboard | Samakan GATEWAY_ID |
| `debounced` | Normal | Tunggu 60 detik (server) atau 30 detik (Pi) |
| Pi tidak detect BLE | Bluetooth mati | `sudo hciconfig hci0 up` |
| Dashboard tidak update | WebSocket terputus | Refresh browser, cek console |

---

## 11. Test Tanpa Raspberry Pi

```bash
# Publish langsung dari PC (simulasi Pi)
mosquitto_pub -h <vm-ip> -t "ble/events/GW-001" \
  -m '{"mac_address":"AA:BB:CC:DD:01:01","gateway_id":"GW-001","rssi":-65}'

# Atau gunakan tombol Simulasi di dashboard
# Atau hit HTTP fallback
curl -X POST http://<vm-ip>:5000/api/ble/event \
  -H "Content-Type: application/json" \
  -d '{"mac_address":"AA:BB:CC:DD:01:01","gateway_id":"GW-001","rssi":-65}'
```

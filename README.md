# 📦 BLE Container Monitoring System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0.3-000000?style=for-the-badge&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-660066?style=for-the-badge&logo=eclipse-mosquitto&logoColor=white)
![Raspberry Pi](https://img.shields.io/badge/Raspberry_Pi-A22846?style=for-the-badge&logo=raspberry-pi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Sistem monitoring kontainer berbasis BLE (Bluetooth Low Energy) secara real-time.**  
Deteksi otomatis kontainer masuk/keluar depo menggunakan BLE Tag + Raspberry Pi Gateway + MQTT.

[Fitur](#-fitur) • [Arsitektur](#-arsitektur) • [Instalasi](#-instalasi) • [Konfigurasi](#%EF%B8%8F-konfigurasi) • [Cara Kerja](#-cara-kerja)

</div>

---

## ✨ Fitur

| Fitur | Keterangan |
|---|---|
| 🟢 **Real-time Dashboard** | Feed aktivitas IN/OUT kontainer via WebSocket |
| 📡 **Live BLE Monitor** | Stream deteksi BLE mentah dari semua gateway secara langsung |
| 🧠 **RSSI Voting Buffer** | Akumulasi N deteksi, pilih gateway terdekat berdasarkan rata-rata RSSI |
| 🔁 **State Machine** | Event hanya dicatat saat status berubah (IN→OUT atau OUT→IN), skip jika sama |
| 🛡️ **RSSI Filter** | Blokir false-positive: deteksi OUT hanya valid jika sinyal cukup kuat |
| 📊 **Analytics** | Grafik tren IN/OUT harian, bulanan, dan tahunan per depo |
| 📋 **Log Transaksi** | Riwayat lengkap dengan filter pencarian, export Excel & PDF |
| 🏷️ **Manajemen BLE Tag** | CRUD tag dengan status posisi IN/OUT langsung dari tabel |
| 📶 **Manajemen Gateway** | CRUD gateway, setting zone IN/OUT, status online/offline otomatis |
| 🔌 **Multi-Gateway** | Banyak Raspberry Pi secara bersamaan, zone dikonfigurasi di server |

---

## 🏗️ Arsitektur

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AREA DEPO / GATE                            │
│                                                                     │
│  [BLE TAG]      [BLE TAG]      [BLE TAG]                            │
│  (di container) (di container) (di container)                       │
│      │               │               │                              │
│      └───────── BLE Advertise (broadcast MAC tiap ~100ms) ──────────┘
│                              │
│                   ┌──────────▼──────────┐
│                   │   Raspberry Pi      │  ← 1 Pi per gate
│                   │   gateway.py        │
│                   │   (bleak BLE scan)  │
│                   └──────────┬──────────┘
└──────────────────────────────┼──────────────────────────────────────┘
                               │ MQTT Publish QoS 1
                               │ topic: ble/events/GW-001
                               ▼
              ┌────────────────────────────────────┐
              │            VM / Server             │
              │                                    │
              │  ┌──────────────────────────────┐  │
              │  │   Mosquitto Broker :1883     │  │
              │  └──────────────┬───────────────┘  │
              │                 │ subscribe         │
              │                 │ ble/events/#      │
              │  ┌──────────────▼───────────────┐  │
              │  │        Flask app.py          │  │
              │  │                              │  │
              │  │  Detection Buffer            │  │
              │  │  ├─ akumulasi N deteksi      │  │
              │  │  └─ pilih best avg RSSI      │  │
              │  │                              │  │
              │  │  process_ble_event()         │  │
              │  │  ├─ RSSI filter (OUT gate)   │  │
              │  │  ├─ state machine check      │  │
              │  │  ├─ INSERT event_logs        │  │
              │  │  ├─ UPDATE ble_tags.position │  │
              │  │  └─ emit WebSocket           │  │
              │  └──────────────┬───────────────┘  │
              │                 │                   │
              │  ┌──────────────▼───────────────┐  │
              │  │         SQLite DB            │  │
              │  └──────────────────────────────┘  │
              └────────────────────┬───────────────┘
                                   │ WebSocket (Socket.IO)
                                   ▼
                        ┌─────────────────────┐
                        │   Browser Dashboard │
                        │   (real-time)       │
                        └─────────────────────┘
```

---

## 🛠️ Tech Stack

**Backend**
- [Flask 3.0](https://flask.palletsprojects.com/) + [Flask-SocketIO](https://flask-socketio.readthedocs.io/) — web framework & real-time WebSocket
- [eventlet](https://eventlet.net/) — async concurrency untuk MQTT + WebSocket secara bersamaan
- [paho-mqtt 2.x](https://pypi.org/project/paho-mqtt/) — MQTT subscriber (VERSION2 API)
- [SQLite](https://www.sqlite.org/) — database lokal ringan
- [openpyxl](https://openpyxl.readthedocs.io/) + [reportlab](https://www.reportlab.com/) — export Excel & PDF

**Frontend**
- [Chart.js 4](https://www.chartjs.org/) — grafik analytics
- [Socket.IO 4.7](https://socket.io/) — WebSocket client
- [Lucide Icons](https://lucide.dev/) — icon set

**IoT / Edge**
- [Raspberry Pi](https://www.raspberrypi.com/) — BLE gateway hardware
- [bleak](https://bleak.readthedocs.io/) — BLE scanner (Python, cross-platform)
- [Mosquitto](https://mosquitto.org/) — MQTT broker

---

## 📁 Struktur Proyek

```
dashboard-skripsi/
│
├── app.py                    # Flask app, MQTT subscriber, REST API, WebSocket
├── database.py               # Schema, init, seed data
├── requirements.txt          # Dependensi Python server
├── mosquitto.conf            # Konfigurasi broker Mosquitto
├── .env.example              # Template environment variables
│
├── templates/
│   ├── base.html             # Layout utama + sidebar navigasi
│   ├── dashboard.html        # Halaman utama: KPI + activity feed
│   ├── tags.html             # Manajemen BLE Tag + status posisi
│   ├── gateways.html         # Manajemen Gateway
│   ├── logs.html             # Log transaksi + filter + export
│   ├── analytics.html        # Grafik tren IN/OUT
│   └── deteksi.html          # Live BLE detection stream monitor
│
├── static/
│   ├── css/style.css         # Stylesheet global
│   └── js/main.js            # JS global (WebSocket, clock, simulasi)
│
└── raspberry-pi/
    ├── gateway.py            # Script utama Pi (BLE scan → MQTT publish)
    ├── .env.example          # Template konfigurasi Pi
    ├── requirements-pi.txt   # Dependensi Python Pi
    └── ble-gateway.service   # Systemd service (auto-start saat Pi nyala)
```

---

## 🚀 Instalasi

### Prasyarat
- Python 3.11+
- Mosquitto MQTT Broker
- Raspberry Pi (opsional — bisa pakai simulasi)

### 1. Clone & Install

```bash
git clone https://github.com/razorbold/dashboard-skripsi.git
cd dashboard-skripsi

pip install -r requirements.txt
```

### 2. Konfigurasi Environment

```bash
cp .env.example .env
# Edit .env sesuai kebutuhan
```

### 3. Setup Mosquitto Broker

```bash
sudo apt install -y mosquitto mosquitto-clients
sudo cp mosquitto.conf /etc/mosquitto/conf.d/ble-monitor.conf
sudo systemctl restart mosquitto && sudo systemctl enable mosquitto
```

### 4. Jalankan Dashboard

```bash
python app.py
```

Buka browser: **http://localhost:5000**

---

## ⚙️ Konfigurasi

Salin `.env.example` menjadi `.env` lalu sesuaikan:

```env
# MQTT Broker
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_ENABLED=true

# Detection Buffer — akumulasi N deteksi sebelum proses
BULK_MIN_COUNT=4          # Minimum jumlah deteksi sebelum flush
BULK_WINDOW_SECS=8        # Maksimum waktu tunggu (detik)

# RSSI Filter — cegah false-positive
RSSI_MIN_OUT=-65          # Sinyal minimum untuk event OUT (dBm)
RSSI_MIN_IN=-99           # Sinyal minimum untuk event IN (-99 = no filter)
```

### Konfigurasi Raspberry Pi

```env
# raspberry-pi/.env
GATEWAY_ID=GW-001
MQTT_HOST=<ip-publik-vm>
MQTT_PORT=1883
RSSI_MIN=-80              # Filter sinyal lemah di sisi Pi
DEBOUNCE_LOCAL=30         # Debounce lokal Pi (detik)
```

---

## ⚡ Cara Kerja

### 1. Detection Buffer (RSSI Voting)

Setiap deteksi BLE ditampung terlebih dahulu. Setelah **N deteksi** terkumpul **atau** timeout habis, sistem memilih gateway dengan **rata-rata RSSI terbaik** sebagai pemenang.

```
Pi GW-001 (zone=IN)  detect MAC → 4x avg -62 dBm  ← PEMENANG
Pi GW-002 (zone=OUT) detect MAC → 2x avg -78 dBm
                                              ↓
                              process_ble_event(mac, "GW-001", -62)
```

### 2. State Machine per Kontainer

Event **hanya dicatat saat status berubah**. Jika container sudah IN dan terdeteksi lagi di IN → di-skip.

```
Status sekarang │ Deteksi di │ Aksi
────────────────┼────────────┼──────────────────────
None            │ IN         │ ✅ Catat → IN
IN              │ OUT        │ ✅ Catat → OUT
OUT             │ IN         │ ✅ Catat → IN
IN              │ IN         │ ⏭️  Skip (sama)
OUT             │ OUT        │ ⏭️  Skip (sama)
```

### 3. RSSI Filter (Anti False-Positive)

Container yang parkir di dalam depo bisa masih terdeteksi oleh gate OUT dari jarak jauh (sinyal lemah). Filter ini memblokir OUT event jika RSSI di bawah threshold:

```
Container di dalam depo → terdeteksi GW-002 (OUT) RSSI -78 dBm
  → -78 < -65 (RSSI_MIN_OUT) → ❌ DITOLAK "SINYAL LEMAH"

Container keluar lewat gate → terdeteksi GW-002 (OUT) RSSI -58 dBm
  → -58 ≥ -65 → ✅ DITERIMA → event OUT dicatat
```

---

## 🧪 Testing Tanpa Raspberry Pi

**Simulasi via tombol di dashboard** (tombol "Simulasi" di pojok kanan atas)

atau

**Publish MQTT manual:**

```bash
mosquitto_pub -h localhost -t "ble/events/GW-001" \
  -m '{"mac_address":"AA:BB:CC:DD:01:01","gateway_id":"GW-001","rssi":-62}'
```

atau

**HTTP fallback endpoint:**

```bash
curl -X POST http://localhost:5000/api/ble/event \
  -H "Content-Type: application/json" \
  -d '{"mac_address":"AA:BB:CC:DD:01:01","gateway_id":"GW-001","rssi":-62}'
```

---

## 📡 Setup Raspberry Pi Gateway

```bash
# Copy ke Pi
scp -r raspberry-pi/ pi@<ip-pi>:/home/pi/ble-gateway/

# Install di Pi
ssh pi@<ip-pi>
cd /home/pi/ble-gateway
pip3 install -r requirements-pi.txt
cp .env.example .env && nano .env

# Test manual
python3 gateway.py

# Auto-start saat Pi nyala
sudo cp ble-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable ble-gateway
sudo systemctl start ble-gateway
```

---

## 🔌 Multi-Gateway

Setiap Raspberry Pi memiliki `.env` dengan `GATEWAY_ID` unik. Zone IN/OUT **dikonfigurasi di dashboard server**, bukan di Pi.

```
Pi #1 → GATEWAY_ID=GW-001 → topic: ble/events/GW-001  (zone: IN)
Pi #2 → GATEWAY_ID=GW-002 → topic: ble/events/GW-002  (zone: OUT)
Pi #3 → GATEWAY_ID=GW-003 → topic: ble/events/GW-003  (zone: IN)
```

Flask subscribe `ble/events/#` — otomatis tangkap semua gateway.

---

## 🗄️ Skema Database

```
ble_tags       ← MAC address + container mapping + status posisi
containers     ← data kontainer (ID, tipe)
gateways       ← gateway BLE (zone IN/OUT, depo, status)
event_logs     ← riwayat semua event IN/OUT
depo           ← data depo
wilayah        ← data wilayah/region
```

---

## 🐛 Troubleshooting

| Masalah | Sebab | Solusi |
|---|---|---|
| Gateway tetap Offline | Heartbeat tidak masuk | Cek koneksi Pi ke broker MQTT |
| `tag not found` di log | MAC belum didaftarkan | Daftarkan di halaman BLE Tags |
| `gateway not found` | `GATEWAY_ID` di Pi ≠ di dashboard | Samakan di halaman Gateways |
| Posisi tidak update | Tidak ada state change | Normal — sudah IN tidak akan update lagi sampai OUT |
| Dashboard tidak real-time | WebSocket terputus | Refresh browser, cek status koneksi di sidebar |
| `MQTT_ENABLED=false` diperlukan | paho-mqtt tidak terinstall | `pip install paho-mqtt` atau set `MQTT_ENABLED=false` |

---

## 📜 Lisensi

MIT License — bebas digunakan dan dimodifikasi.

---

<div align="center">
Dibuat sebagai Tugas Akhir (Skripsi) — BLE Container Monitoring System
</div>

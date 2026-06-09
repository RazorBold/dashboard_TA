import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "ble_monitor.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS containers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            container_id TEXT UNIQUE NOT NULL,
            type TEXT DEFAULT 'Standard',
            status TEXT DEFAULT 'Active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ble_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mac_address TEXT UNIQUE NOT NULL,
            container_id TEXT,
            status TEXT DEFAULT 'Active',
            last_seen DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (container_id) REFERENCES containers(container_id)
        );

        CREATE TABLE IF NOT EXISTS wilayah (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS depo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            wilayah_id INTEGER,
            FOREIGN KEY (wilayah_id) REFERENCES wilayah(id)
        );

        CREATE TABLE IF NOT EXISTS gateways (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gateway_id TEXT UNIQUE NOT NULL,
            nama TEXT NOT NULL,
            depo_id INTEGER,
            zone TEXT DEFAULT 'IN',
            ip_address TEXT,
            status TEXT DEFAULT 'Offline',
            last_active DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (depo_id) REFERENCES depo(id)
        );

        CREATE TABLE IF NOT EXISTS event_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            container_id TEXT NOT NULL,
            mac_address TEXT NOT NULL,
            gateway_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            rssi INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_event_container ON event_logs(container_id);
        CREATE INDEX IF NOT EXISTS idx_event_timestamp ON event_logs(timestamp);
        CREATE INDEX IF NOT EXISTS idx_event_gateway ON event_logs(gateway_id);
    """)

    # Seed data — setiap tabel dicek independen agar partial-reset tidak melewatkan tabel lain
    c.execute("SELECT COUNT(*) FROM wilayah")
    if c.fetchone()[0] == 0:
        c.executescript("""
            INSERT INTO wilayah (nama) VALUES ('Jakarta'), ('Surabaya'), ('Medan');
            INSERT INTO depo (nama, wilayah_id) VALUES
                ('Depo Tanjung Priok', 1),
                ('Depo Koja', 1),
                ('Depo Tanjung Perak', 2),
                ('Depo Belawan', 3);
        """)

    c.execute("SELECT COUNT(*) FROM gateways")
    if c.fetchone()[0] == 0:
        c.executescript("""
            INSERT INTO gateways (gateway_id, nama, depo_id, zone, ip_address, status) VALUES
                ('GW-001', 'Gate IN Priok',  1, 'IN',  '192.168.1.10', 'Online'),
                ('GW-002', 'Gate OUT Priok', 1, 'OUT', '192.168.1.11', 'Online'),
                ('GW-003', 'Gate IN Koja',   2, 'IN',  '192.168.1.20', 'Offline'),
                ('GW-004', 'Gate IN Perak',  3, 'IN',  '192.168.1.30', 'Online');
        """)

    c.execute("SELECT COUNT(*) FROM containers")
    if c.fetchone()[0] == 0:
        c.executescript("""
            INSERT INTO containers (container_id, type, status) VALUES
                ('CONT-001', 'Standard', 'Active'),
                ('CONT-002', 'Reefer',   'Active'),
                ('CONT-003', 'Standard', 'Active'),
                ('CONT-004', 'Tank',     'Active'),
                ('CONT-005', 'Standard', 'Active');
        """)

    c.execute("SELECT COUNT(*) FROM ble_tags")
    if c.fetchone()[0] == 0:
        c.executescript("""
            INSERT INTO ble_tags (mac_address, container_id, status) VALUES
                ('AA:BB:CC:DD:01:01', 'CONT-001', 'Active'),
                ('AA:BB:CC:DD:01:02', 'CONT-002', 'Active'),
                ('AA:BB:CC:DD:01:03', 'CONT-003', 'Active'),
                ('AA:BB:CC:DD:01:04', 'CONT-004', 'Active'),
                ('AA:BB:CC:DD:01:05', 'CONT-005', 'Active');
        """)

    c.execute("SELECT COUNT(*) FROM event_logs")
    if c.fetchone()[0] == 0:
        c.executescript("""
            INSERT INTO event_logs (container_id, mac_address, gateway_id, event_type, timestamp, rssi) VALUES
                ('CONT-001', 'AA:BB:CC:DD:01:01', 'GW-001', 'IN',  datetime('now','-5 hours'), -65),
                ('CONT-002', 'AA:BB:CC:DD:01:02', 'GW-001', 'IN',  datetime('now','-4 hours'), -72),
                ('CONT-003', 'AA:BB:CC:DD:01:03', 'GW-002', 'OUT', datetime('now','-3 hours'), -68),
                ('CONT-001', 'AA:BB:CC:DD:01:01', 'GW-002', 'OUT', datetime('now','-2 hours'), -70),
                ('CONT-004', 'AA:BB:CC:DD:01:04', 'GW-001', 'IN',  datetime('now','-1 hours'), -61),
                ('CONT-005', 'AA:BB:CC:DD:01:05', 'GW-004', 'IN',  datetime('now','-30 minutes'), -75);
        """)

    # Tambah kolom position ke ble_tags jika belum ada (migrasi aman)
    try:
        conn.execute("ALTER TABLE ble_tags ADD COLUMN position TEXT")
        conn.commit()
    except Exception:
        pass  # kolom sudah ada

    # Backfill position dari event_logs untuk row yang belum punya nilai
    conn.execute("""
        UPDATE ble_tags SET position = (
            SELECT event_type FROM event_logs
            WHERE event_logs.container_id = ble_tags.container_id
            ORDER BY timestamp DESC LIMIT 1
        )
        WHERE position IS NULL AND container_id IS NOT NULL
    """)

    conn.commit()
    conn.close()

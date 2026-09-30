import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_NAME = "sala_reuniones.db"

SECTOR_PALETTE = [
    "#2563eb",  # Blue
    "#059669",  # Emerald
    "#d97706",  # Amber
    "#7c3aed",  # Violet
    "#db2777",  # Pink
    "#0891b2",  # Cyan
    "#ea580c",  # Orange
    "#dc2626",  # Red
    "#4f46e5",  # Indigo
    "#16a34a",  # Green
    "#0284c7",  # Sky
    "#9333ea",  # Purple
    "#c026d3",  # Fuchsia
    "#0d9488",  # Teal
    "#475569"   # Slate
]

KNOWN_COLORS = {
    "admin": "#dc2626",
    "dirección general": "#dc2626",
    "sistemas / ti": "#059669",
    "sistemas": "#059669",
    "recursos humanos": "#2563eb",
    "rrhh": "#2563eb",
    "administración": "#d97706",
    "administracion": "#d97706",
    "finanzas": "#7c3aed",
    "comercial / ventas": "#db2777",
    "ventas": "#db2777",
    "operaciones": "#0891b2",
    "marketing": "#ea580c",
    "legal": "#475569"
}

SECTORS = []

def get_sector_color(sector_name):
    if not sector_name:
        return "#64748b"
    clean_name = sector_name.strip().lower()
    if clean_name in KNOWN_COLORS:
        return KNOWN_COLORS[clean_name]
    hash_val = sum((i + 1) * ord(c) for i, c in enumerate(clean_name))
    return SECTOR_PALETTE[hash_val % len(SECTOR_PALETTE)]

import os
import sqlite3
from werkzeug.security import generate_password_hash

DATABASE_URL = os.environ.get("DATABASE_URL")
DB_NAME = "sala_reuniones.db"

# Render a veces entrega postgres:// en lugar de postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

class DBCursor:
    def __init__(self, raw_cursor, is_postgres=False):
        self.raw_cursor = raw_cursor
        self.is_postgres = is_postgres

    def execute(self, query, params=None):
        if self.is_postgres:
            pg_query = query.replace("?", "%s")
            if params is not None:
                return self.raw_cursor.execute(pg_query, params)
            else:
                return self.raw_cursor.execute(pg_query)
        else:
            if params is not None:
                return self.raw_cursor.execute(query, params)
            else:
                return self.raw_cursor.execute(query)

    def fetchall(self):
        return self.raw_cursor.fetchall()

    def fetchone(self):
        return self.raw_cursor.fetchone()

    @property
    def lastrowid(self):
        return getattr(self.raw_cursor, "lastrowid", None)

    @property
    def rowcount(self):
        return self.raw_cursor.rowcount

class DBConnection:
    def __init__(self, raw_conn, is_postgres=False):
        self.raw_conn = raw_conn
        self.is_postgres = is_postgres

    def execute(self, query, params=None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def commit(self):
        self.raw_conn.commit()

    def close(self):
        self.raw_conn.close()

    def cursor(self):
        return DBCursor(self.raw_conn.cursor(), self.is_postgres)

def get_db_connection():
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        raw_conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
        return DBConnection(raw_conn, is_postgres=True)
    else:
        raw_conn = sqlite3.connect(DB_NAME)
        raw_conn.row_factory = sqlite3.Row
        raw_conn.execute("PRAGMA foreign_keys = ON")
        return DBConnection(raw_conn, is_postgres=False)

def get_active_sectors():
    try:
        conn = get_db_connection()
        rows = conn.execute("SELECT DISTINCT sector FROM users WHERE sector IS NOT NULL AND TRIM(sector) != '' ORDER BY sector ASC").fetchall()
        conn.close()
        return [{"name": r["sector"], "color": get_sector_color(r["sector"])} for r in rows]
    except Exception:
        return []

def init_db():
    conn = get_db_connection()
    if conn.is_postgres:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name VARCHAR(150) NOT NULL,
                sector VARCHAR(100) NOT NULL,
                role VARCHAR(50) NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS reservations (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                date VARCHAR(20) NOT NULL,
                start_time VARCHAR(10) NOT NULL,
                end_time VARCHAR(10) NOT NULL,
                duration_minutes INTEGER NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'active',
                cancelled_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                cancelled_at TIMESTAMP,
                cancellation_reason TEXT,
                recurrence_id VARCHAR(100),
                recurrence_type VARCHAR(50) DEFAULT 'none',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        cur.execute("SELECT COUNT(*) as cnt FROM users;")
        row = cur.fetchone()
        count = row['cnt'] if isinstance(row, dict) or hasattr(row, '__getitem__') else row[0]
        if count == 0:
            cur.execute(
                "INSERT INTO users (username, password_hash, full_name, sector, role) VALUES (%s, %s, %s, %s, %s)",
                ("admin", generate_password_hash("admin123"), "Administrador General", "Admin", "admin")
            )
        else:
            cur.execute("UPDATE users SET sector = 'Admin' WHERE username = 'admin' AND sector = 'Dirección General';")
        conn.commit()
        conn.close()
    else:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                sector TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                cancelled_by INTEGER,
                cancelled_at TIMESTAMP,
                cancellation_reason TEXT,
                recurrence_id TEXT,
                recurrence_type TEXT DEFAULT 'none',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (cancelled_by) REFERENCES users (id)
            )
        ''')
        cursor.execute("PRAGMA table_info(reservations)")
        columns = [col[1] for col in cursor.fetchall()]
        if "cancellation_reason" not in columns:
            cursor.execute("ALTER TABLE reservations ADD COLUMN cancellation_reason TEXT")
        if "recurrence_id" not in columns:
            cursor.execute("ALTER TABLE reservations ADD COLUMN recurrence_id TEXT")
        if "recurrence_type" not in columns:
            cursor.execute("ALTER TABLE reservations ADD COLUMN recurrence_type TEXT DEFAULT 'none'")
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO users (username, password_hash, full_name, sector, role) VALUES (?, ?, ?, ?, ?)",
                ("admin", generate_password_hash("admin123"), "Administrador General", "Admin", "admin")
            )
            conn.commit()
        else:
            cursor.execute("UPDATE users SET sector = 'Admin' WHERE username = 'admin' AND sector = 'Dirección General'")
            conn.commit()

        conn.close()

if __name__ == "__main__":
    init_db()
    print("Base de datos inicializada correctamente.")

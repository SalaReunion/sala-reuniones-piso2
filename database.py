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

def get_active_sectors():
    try:
        conn = get_db_connection()
        rows = conn.execute("SELECT DISTINCT sector FROM users WHERE sector IS NOT NULL AND TRIM(sector) != '' ORDER BY sector ASC").fetchall()
        conn.close()
        return [{"name": r["sector"], "color": get_sector_color(r["sector"])} for r in rows]
    except Exception:
        return []

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tabla de Usuarios
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

    # Tabla de Reservas
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

    # Migración segura: agregar columnas si la tabla ya existía
    cursor.execute("PRAGMA table_info(reservations)")
    columns = [col[1] for col in cursor.fetchall()]
    if "cancellation_reason" not in columns:
        cursor.execute("ALTER TABLE reservations ADD COLUMN cancellation_reason TEXT")
    if "recurrence_id" not in columns:
        cursor.execute("ALTER TABLE reservations ADD COLUMN recurrence_id TEXT")
    if "recurrence_type" not in columns:
        cursor.execute("ALTER TABLE reservations ADD COLUMN recurrence_type TEXT DEFAULT 'none'")
    conn.commit()

    # Usuarios iniciales de prueba si la tabla está vacía
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        sample_users = [
            ("admin", generate_password_hash("admin123"), "Administrador General", "Dirección General", "admin"),
            ("sistemas", generate_password_hash("sistemas123"), "Lucas Cardozo", "Sistemas / TI", "user"),
            ("rrhh", generate_password_hash("rrhh123"), "Mariana Gómez", "Recursos Humanos", "user"),
            ("ventas", generate_password_hash("ventas123"), "Carlos Fernández", "Comercial / Ventas", "user"),
            ("finanzas", generate_password_hash("finanzas123"), "Valeria Rossi", "Finanzas", "user")
        ]
        cursor.executemany(
            "INSERT INTO users (username, password_hash, full_name, sector, role) VALUES (?, ?, ?, ?, ?)",
            sample_users
        )
        conn.commit()

        # Insertar reservas de demostración para los próximos días
        import datetime
        today = datetime.date.today()
        d1 = today.strftime("%Y-%m-%d")
        d2 = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        d3 = (today + datetime.timedelta(days=2)).strftime("%Y-%m-%d")

        sample_reservations = [
            (2, "Planificación Sprint de TI", "Revisión de infraestructura y servidores", d1, "10:00", "11:30", 90, "active"),
            (3, "Entrevistas de Selección", "Candidatos para área comercial", d1, "14:00", "15:30", 90, "active"),
            (4, "Reunión Trimestral con Clientes", "Presentación de resultados comerciales", d2, "09:30", "11:00", 90, "active"),
            (5, "Cierre de Balance Mensual", "Auditoría de estados financieros", d2, "15:00", "17:00", 120, "active"),
            (1, "Comité Directivo", "Reunión mensual de directores", d3, "11:00", "12:30", 90, "active")
        ]
        cursor.executemany(
            "INSERT INTO reservations (user_id, title, description, date, start_time, end_time, duration_minutes, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            sample_reservations
        )
        conn.commit()

    conn.close()

if __name__ == "__main__":
    init_db()
    print("Base de datos inicializada correctamente.")

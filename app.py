import os
import csv
from io import StringIO
import uuid
import calendar
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
from functools import wraps
from datetime import datetime, timedelta, date
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection, init_db, SECTORS, get_sector_color, get_active_sectors

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sala_reuniones_piso_2_secret_key_super_segura")

# Iniciar BD si es necesario
init_db()

# Decoradores de autenticación
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Por favor inicia sesión para acceder.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Por favor inicia sesión.", "warning")
            return redirect(url_for("login"))
        if session.get("user_role") != "admin":
            flash("Acceso restringido a Administradores.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_global_data():
    current_user = None
    if "user_id" in session:
        conn = get_db_connection()
        current_user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        conn.close()
    return {
        "current_user": current_user,
        "SECTORS": get_active_sectors(),
        "now": datetime.now()
    }

# ----------------- RUTAS DE AUTENTICACIÓN -----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["sector"] = user["sector"]
            session["user_role"] = user["role"]
            flash(f"¡Bienvenido/a {user['full_name']} ({user['sector']})!", "success")
            return redirect(url_for("index"))
        else:
            flash("Usuario o contraseña incorrectos.", "danger")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        sector = request.form.get("sector", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not full_name or not sector or not password:
            flash("Todos los campos son obligatorios.", "danger")
            return render_template("register.html")

        if password != confirm_password:
            flash("Las contraseñas no coinciden.", "danger")
            return render_template("register.html")

        conn = get_db_connection()
        existing = conn.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (username,)).fetchone()
        if existing:
            conn.close()
            flash("El nombre de usuario ya está registrado. Elige otro.", "danger")
            return render_template("register.html")

        hashed = generate_password_hash(password)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, full_name, sector, role) VALUES (?, ?, ?, ?, 'user')",
            (username, hashed, full_name, sector)
        )
        new_user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        session["user_id"] = new_user_id
        session["username"] = username
        session["full_name"] = full_name
        session["sector"] = sector
        session["user_role"] = "user"

        flash(f"¡Cuenta creada con éxito! Bienvenido al sistema de reservas, {full_name}.", "success")
        return redirect(url_for("index"))

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Has cerrado sesión correctamente.", "info")
    return redirect(url_for("login"))

# ----------------- DASHBOARD Y CALENDARIO -----------------

@app.route("/")
@login_required
def index():
    conn = get_db_connection()
    today_str = date.today().strftime("%Y-%m-%d")

    # Reservas activas de hoy
    todays_reservations = conn.execute('''
        SELECT r.*, u.full_name, u.sector, u.username
        FROM reservations r
        JOIN users u ON r.user_id = u.id
        WHERE r.date = ? AND r.status = 'active'
        ORDER BY r.start_time ASC
    ''', (today_str,)).fetchall()

    # Contadores
    total_active = conn.execute("SELECT COUNT(*) FROM reservations WHERE status = 'active'").fetchone()[0]
    my_active = conn.execute(
        "SELECT COUNT(*) FROM reservations WHERE user_id = ? AND status = 'active' AND date >= ?",
        (session["user_id"], today_str)
    ).fetchone()[0]

    conn.close()

    return render_template(
        "index.html",
        todays_reservations=todays_reservations,
        total_active=total_active,
        my_active=my_active,
        today_str=today_str
    )

# ----------------- API DEL CALENDARIO -----------------

@app.route("/api/reservations")
@login_required
def api_reservations():
    conn = get_db_connection()
    cur_user_id = session.get("user_id")
    is_admin = session.get("user_role") == "admin"

    rows = conn.execute('''
        SELECT r.*, u.full_name, u.sector, u.username
        FROM reservations r
        JOIN users u ON r.user_id = u.id
        WHERE r.status = 'active'
    ''').fetchall()
    conn.close()

    events = []
    for row in rows:
        color = get_sector_color(row["sector"])
        can_cancel = (is_admin or row["user_id"] == cur_user_id)
        
        # Formato de visualización de duración
        hours = row["duration_minutes"] // 60
        mins = row["duration_minutes"] % 60
        duration_text = []
        if hours > 0:
            duration_text.append(f"{hours}h")
        if mins > 0:
            duration_text.append(f"{mins}m")
        duration_str = " ".join(duration_text) if duration_text else f"{row['duration_minutes']} min"

        events.append({
            "id": row["id"],
            "title": f"[{row['sector']}] {row['title']}",
            "start": f"{row['date']}T{row['start_time']}:00",
            "end": f"{row['date']}T{row['end_time']}:00",
            "backgroundColor": color,
            "borderColor": color,
            "textColor": "#ffffff",
            "extendedProps": {
                "id": row["id"],
                "raw_title": row["title"],
                "description": row["description"] or "Sin descripción adicional.",
                "date": row["date"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "duration_minutes": row["duration_minutes"],
                "duration_text": duration_str,
                "user_id": row["user_id"],
                "user_name": row["full_name"],
                "sector": row["sector"],
                "can_cancel": can_cancel,
                "is_owner": row["user_id"] == cur_user_id,
                "is_admin": is_admin,
                "recurrence_id": row["recurrence_id"],
                "recurrence_type": row["recurrence_type"] or "none",
                "is_recurring": bool(row["recurrence_id"])
            }
        })

    return jsonify(events)

# ----------------- GESTIÓN DE RESERVAS -----------------

def calculate_end_time(start_time_str, duration_minutes):
    t = datetime.strptime(start_time_str, "%H:%M")
    end_t = t + timedelta(minutes=int(duration_minutes))
    return end_t.strftime("%H:%M")

def get_monthly_ordinal_date(year, month, ordinal, target_weekday):
    cal = calendar.monthcalendar(year, month)
    matching_days = [week[target_weekday] for week in cal if week[target_weekday] != 0]
    if not matching_days:
        return None
    if ordinal == -1:  # Último
        day = matching_days[-1]
    elif 1 <= ordinal <= len(matching_days):
        day = matching_days[ordinal - 1]
    else:
        day = matching_days[-1]
    return date(year, month, day)

def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    return year, month

def generate_recurrence_dates(
    start_date_str, freq, days_list, end_mode, end_date_str, count_str,
    monthly_interval=1, monthly_type="by_day", monthly_day=None, monthly_ordinal=1, monthly_weekday=0
):
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    dates = []
    selected_weekdays = [int(d) for d in days_list if d.isdigit()]
    if not selected_weekdays:
        selected_weekdays = [start_dt.weekday()]

    max_occurrences = 40
    if end_mode == "by_count":
        try:
            target_count = min(max(2, int(count_str)), max_occurrences)
        except (ValueError, TypeError):
            target_count = 5
        limit_date = None
    elif end_mode == "no_end":
        target_count = 12
        limit_date = start_dt + timedelta(days=365)
    else:
        target_count = max_occurrences
        try:
            limit_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except Exception:
            limit_date = start_dt + timedelta(days=90)

    if freq == "monthly":
        try:
            m_interval = max(1, int(monthly_interval))
        except (ValueError, TypeError):
            m_interval = 1

        curr_year = start_dt.year
        curr_month = start_dt.month
        loop_count = 0

        while len(dates) < target_count and loop_count < 60:
            if monthly_type == "by_day":
                target_day = int(monthly_day) if monthly_day else start_dt.day
                _, max_days = calendar.monthrange(curr_year, curr_month)
                day_val = min(target_day, max_days)
                d = date(curr_year, curr_month, day_val)
            else:
                ord_val = int(monthly_ordinal)
                w_val = int(monthly_weekday)
                d = get_monthly_ordinal_date(curr_year, curr_month, ord_val, w_val)

            if d and d >= start_dt:
                if limit_date and d > limit_date:
                    break
                if d not in dates:
                    dates.append(d)

            curr_year, curr_month = add_months(date(curr_year, curr_month, 1), m_interval)
            loop_count += 1

        if not dates:
            dates = [start_dt]

    else:
        dates = [start_dt]
        curr = start_dt
        day_step = timedelta(days=1)

        while len(dates) < target_count:
            if freq == "daily":
                curr += day_step
                # Omitir sábados y domingos
                if curr.weekday() in (5, 6):
                    continue
                dates.append(curr)
            elif freq == "weekly":
                curr += timedelta(days=7)
                dates.append(curr)
            elif freq == "custom_days":
                curr += day_step
                if curr.weekday() in selected_weekdays:
                    dates.append(curr)
            else:
                break

            if limit_date and curr > limit_date:
                if dates and dates[-1] > limit_date:
                    dates.pop()
                break

    return sorted(list(set(dates)))

@app.route("/reservar", methods=["POST"])
@login_required
def create_reservation():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    date_val = request.form.get("date", "").strip()
    start_time_val = request.form.get("start_time", "").strip()
    duration_val = request.form.get("duration", "").strip()

    is_recurring = request.form.get("is_recurring") == "1"
    recurrence_freq = request.form.get("recurrence_freq", "weekly")
    recurrence_days = request.form.getlist("recurrence_days")
    recurrence_end_mode = request.form.get("recurrence_end_mode", "by_date")
    recurrence_end_date = request.form.get("recurrence_end_date", "").strip()
    recurrence_count = request.form.get("recurrence_count", "5").strip()

    monthly_interval = request.form.get("monthly_interval", "1").strip()
    monthly_type = request.form.get("monthly_type", "by_day")
    monthly_day = request.form.get("monthly_day")
    monthly_ordinal = request.form.get("monthly_ordinal", "1")
    monthly_weekday = request.form.get("monthly_weekday", "0")

    if not title or not date_val or not start_time_val or not duration_val:
        flash("Todos los campos obligatorios deben completarse.", "danger")
        return redirect(url_for("index"))

    try:
        duration_mins = int(duration_val)
        end_time_val = calculate_end_time(start_time_val, duration_mins)
    except Exception as e:
        flash("El formato de horario o duración es inválido.", "danger")
        return redirect(url_for("index"))

    # Validar que la primera reserva no sea en el pasado
    now = datetime.now()
    try:
        res_start_dt = datetime.strptime(f"{date_val} {start_time_val}", "%Y-%m-%d %H:%M")
        if res_start_dt < now - timedelta(minutes=10):
            flash("No es posible realizar una reserva en una fecha u hora pasada.", "danger")
            return redirect(url_for("index"))
    except ValueError:
        flash("Formato de fecha u hora incorrecto.", "danger")
        return redirect(url_for("index"))

    # Generar lista de fechas a reservar
    if is_recurring:
        dates_to_book = generate_recurrence_dates(
            date_val, recurrence_freq, recurrence_days, recurrence_end_mode, recurrence_end_date, recurrence_count,
            monthly_interval=monthly_interval, monthly_type=monthly_type, monthly_day=monthly_day,
            monthly_ordinal=monthly_ordinal, monthly_weekday=monthly_weekday
        )
    else:
        dates_to_book = [datetime.strptime(date_val, "%Y-%m-%d").date()]

    # Validar superposición de horarios en TODAS las fechas objetivo
    conn = get_db_connection()
    conflicts = []
    for d in dates_to_book:
        d_str = d.strftime("%Y-%m-%d")
        overlap = conn.execute('''
            SELECT r.*, u.full_name, u.sector
            FROM reservations r
            JOIN users u ON r.user_id = u.id
            WHERE r.date = ?
              AND r.status = 'active'
              AND (r.start_time < ? AND r.end_time > ?)
        ''', (d_str, end_time_val, start_time_val)).fetchall()
        for ov in overlap:
            conflicts.append({
                "date": d_str,
                "title": ov["title"],
                "owner": ov["full_name"],
                "sector": ov["sector"],
                "time": f"{ov['start_time']} a {ov['end_time']}"
            })

    if conflicts:
        conn.close()
        first_c = conflicts[0]
        c_dates = ", ".join(sorted(list(set(c['date'] for c in conflicts))))
        flash(
            f"¡Conflicto de horario! La sala ya está ocupada el día {c_dates} de {first_c['time']} "
            f"por {first_c['owner']} ({first_c['sector']}) para '{first_c['title']}'. "
            f"Por favor modifica el horario o las fechas.",
            "danger"
        )
        return redirect(url_for("index"))

    # Insertar reservas
    rec_id = f"rec_{int(datetime.now().timestamp())}_{session['user_id']}" if is_recurring else None
    rec_type = recurrence_freq if is_recurring else "none"

    for d in dates_to_book:
        conn.execute('''
            INSERT INTO reservations (user_id, title, description, date, start_time, end_time, duration_minutes, status, recurrence_id, recurrence_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        ''', (session["user_id"], title, description, d.strftime("%Y-%m-%d"), start_time_val, end_time_val, duration_mins, rec_id, rec_type))

    conn.commit()
    conn.close()

    if len(dates_to_book) > 1:
        flash(f"¡Reserva recurrente confirmada con éxito! Se crearon {len(dates_to_book)} turnos para {start_time_val} a {end_time_val} hs.", "success")
    else:
        flash(f"¡Reserva confirmada con éxito! Sala reservada para el {date_val} de {start_time_val} a {end_time_val} hs.", "success")
    return redirect(url_for("index"))

@app.route("/reservas/<int:reservation_id>/cancelar", methods=["POST"])
@login_required
def cancel_reservation(reservation_id):
    conn = get_db_connection()
    res = conn.execute('''
        SELECT r.*, u.full_name, u.sector
        FROM reservations r
        JOIN users u ON r.user_id = u.id
        WHERE r.id = ?
    ''', (reservation_id,)).fetchone()

    if not res:
        conn.close()
        flash("La reserva solicitada no existe.", "danger")
        return redirect(request.referrer or url_for("index"))

    if res["status"] != "active":
        conn.close()
        flash("Esta reserva ya fue cancelada con anterioridad.", "warning")
        return redirect(request.referrer or url_for("index"))

    cur_user_id = session["user_id"]
    is_admin = session.get("user_role") == "admin"

    # Verificación estricta de permisos: Solo creador o Administrador
    if res["user_id"] != cur_user_id and not is_admin:
        conn.close()
        flash(
            f"Permiso denegado. Solamente {res['full_name']} (quien realizó la reserva) o un Administrador pueden cancelarla.",
            "danger"
        )
        return redirect(request.referrer or url_for("index"))

    cancel_series = request.form.get("cancel_series") == "1"
    reason = request.form.get("reason", "Cancelada por usuario / admin").strip()

    if cancel_series and res["recurrence_id"]:
        conn.execute('''
            UPDATE reservations
            SET status = 'cancelled', cancelled_by = ?, cancelled_at = CURRENT_TIMESTAMP, cancellation_reason = ?
            WHERE recurrence_id = ? AND date >= ? AND status = 'active'
        ''', (cur_user_id, reason, res["recurrence_id"], res["date"]))
        conn.commit()
        conn.close()
        flash("La serie recurrente (este turno y todas las reuniones futuras) fue cancelada exitosamente.", "success")
    else:
        conn.execute('''
            UPDATE reservations
            SET status = 'cancelled', cancelled_by = ?, cancelled_at = CURRENT_TIMESTAMP, cancellation_reason = ?
            WHERE id = ?
        ''', (cur_user_id, reason, reservation_id))
        conn.commit()
        conn.close()
        flash("La reserva ha sido cancelada exitosamente y el horario quedó disponible para otros sectores.", "success")

    return redirect(request.referrer or url_for("index"))

# ----------------- MIS RESERVAS -----------------

@app.route("/mis-reservas")
@login_required
def my_bookings():
    conn = get_db_connection()
    cur_user_id = session["user_id"]

    reservations = conn.execute('''
        SELECT r.*, u.full_name, u.sector
        FROM reservations r
        JOIN users u ON r.user_id = u.id
        WHERE r.user_id = ?
        ORDER BY r.date DESC, r.start_time DESC
    ''', (cur_user_id,)).fetchall()

    conn.close()
    return render_template("my_bookings.html", reservations=reservations)

# ----------------- PANEL ADMIN -----------------

@app.route("/admin")
@admin_required
def admin_panel():
    conn = get_db_connection()
    all_reservations = conn.execute('''
        SELECT r.*, u.full_name, u.sector, u.username,
               cb.full_name as cancelled_by_name
        FROM reservations r
        JOIN users u ON r.user_id = u.id
        LEFT JOIN users cb ON r.cancelled_by = cb.id
        ORDER BY r.date DESC, r.start_time DESC
    ''').fetchall()

    all_users = conn.execute('''
        SELECT u.*, COUNT(r.id) as total_bookings
        FROM users u
        LEFT JOIN reservations r ON u.id = r.user_id AND r.status = 'active'
        GROUP BY u.id
        ORDER BY u.role DESC, u.sector ASC
    ''').fetchall()

    # Estadísticas por sector
    sector_stats = conn.execute('''
        SELECT u.sector, COUNT(r.id) as total_reservas,
               COALESCE(SUM(r.duration_minutes), 0) as total_minutos
        FROM reservations r
        JOIN users u ON r.user_id = u.id
        WHERE r.status = 'active'
        GROUP BY u.sector
        ORDER BY total_reservas DESC
    ''').fetchall()

    conn.close()

    return render_template(
        "admin.html",
        all_reservations=all_reservations,
        all_users=all_users,
        sector_stats=sector_stats
    )

@app.route("/admin/exportar-csv")
@admin_required
def export_csv():
    conn = get_db_connection()
    reservations = conn.execute('''
        SELECT r.id, r.title, r.date, r.start_time, r.end_time, r.duration_minutes,
               r.recurrence_type, r.status, r.description, r.created_at,
               u.full_name, u.sector, u.username,
               cb.full_name as cancelled_by_name, r.cancellation_reason, r.cancelled_at
        FROM reservations r
        JOIN users u ON r.user_id = u.id
        LEFT JOIN users cb ON r.cancelled_by = cb.id
        ORDER BY r.date DESC, r.start_time DESC
    ''').fetchall()
    conn.close()

    si = StringIO()
    writer = csv.writer(si)
    # Cabecera amigable con Google Sheets y Excel
    writer.writerow([
        "ID", "Título", "Sector", "Solicitante", "Usuario", "Fecha",
        "Hora Inicio", "Hora Fin", "Duración (min)", "Tipo Recurrencia",
        "Estado", "Motivo / Descripción", "Fecha Creación", "Cancelado Por", "Motivo Cancelación", "Fecha Cancelación"
    ])

    for row in reservations:
        writer.writerow([
            row["id"],
            row["title"],
            row["sector"],
            row["full_name"],
            row["username"],
            row["date"],
            row["start_time"],
            row["end_time"],
            row["duration_minutes"],
            row["recurrence_type"] or "Única",
            "Activa" if row["status"] == "active" else "Cancelada",
            row["description"] or "",
            row["created_at"],
            row["cancelled_by_name"] or "",
            row["cancellation_reason"] or "",
            row["cancelled_at"] or ""
        ])

    output = si.getvalue().encode('utf-8-sig')  # BOM utf-8 para compatibilidad perfecta con Excel y Google Sheets
    filename = f"reservas_sala_piso2_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@app.route("/admin/cambiar-password", methods=["POST"])
@admin_required
def admin_change_password():
    new_password = request.form.get("new_password", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()

    if not new_password or len(new_password) < 4:
        flash("La nueva contraseña debe tener al menos 4 caracteres.", "danger")
        return redirect(url_for("admin_panel"))

    if new_password != confirm_password:
        flash("Las contraseñas no coinciden.", "danger")
        return redirect(url_for("admin_panel"))

    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), session["user_id"])
    )
    conn.commit()
    conn.close()

    flash("¡Contraseña de administrador actualizada con éxito!", "success")
    return redirect(url_for("admin_panel"))

@app.route("/admin/usuarios/<int:target_user_id>/toggle-rol", methods=["POST"])
@admin_required
def toggle_user_role(target_user_id):
    if target_user_id == session["user_id"]:
        flash("No puedes cambiarte el rol a ti mismo.", "warning")
        return redirect(url_for("admin_panel"))

    conn = get_db_connection()
    target_user = conn.execute("SELECT * FROM users WHERE id = ?", (target_user_id,)).fetchone()
    if not target_user:
        conn.close()
        flash("Usuario no encontrado.", "danger")
        return redirect(url_for("admin_panel"))

    new_role = "admin" if target_user["role"] == "user" else "user"
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, target_user_id))
    conn.commit()
    conn.close()

    action_text = "ahora es Administrador" if new_role == "admin" else "ahora es Usuario regular"
    flash(f"El usuario {target_user['full_name']} (@{target_user['username']}) {action_text}.", "success")
    return redirect(url_for("admin_panel"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode, host="0.0.0.0", port=port)

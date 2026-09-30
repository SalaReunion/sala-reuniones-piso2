import unittest
from app import app
from database import init_db, get_db_connection

class ReservationSystemTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        init_db()
        conn = get_db_connection()
        conn.execute("DELETE FROM reservations WHERE date >= '2026-11-01'")
        conn.execute("DELETE FROM users WHERE username IN ('smartinez', 'testuser_temp')")
        conn.commit()
        conn.close()

    def login(self, username, password):
        return self.client.post('/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_login_and_logout(self):
        # Login válido con usuario de Sistemas
        rv = self.login('sistemas', 'sistemas123')
        self.assertIn('Lucas Cardozo', rv.data.decode('utf-8'))
        self.assertIn('Sistemas / TI', rv.data.decode('utf-8'))

        # Logout
        rv = self.logout()
        self.assertIn('Has cerrado sesión', rv.data.decode('utf-8'))

    def test_api_reservations(self):
        self.login('sistemas', 'sistemas123')
        rv = self.client.get('/api/reservations')
        self.assertEqual(rv.status_code, 200)
        json_data = rv.get_json()
        self.assertIsInstance(json_data, list)
        self.assertGreater(len(json_data), 0)
        # Verificar atributos devueltos para FullCalendar
        first_event = json_data[0]
        self.assertIn('title', first_event)
        self.assertIn('start', first_event)
        self.assertIn('end', first_event)
        self.assertIn('extendedProps', first_event)
        self.assertIn('can_cancel', first_event['extendedProps'])

    def test_create_reservation_and_overlap_detection(self):
        # Iniciar sesión como Mariana de RRHH
        self.login('rrhh', 'rrhh123')
        
        # Crear reserva para una fecha futura
        test_date = '2026-11-15'
        rv = self.client.post('/reservar', data=dict(
            title='Entrevista Jefe de Marketing',
            date=test_date,
            start_time='10:00',
            duration='60',
            description='Sala equipada con videoconferencia'
        ), follow_redirects=True)
        
        self.assertIn('Reserva confirmada con éxito', rv.data.decode('utf-8'))

        # Intentar reservar en el mismo horario (superposición exacta 10:00 - 11:00)
        rv_overlap = self.client.post('/reservar', data=dict(
            title='Reunión conflictiva',
            date=test_date,
            start_time='10:00',
            duration='60',
            description=''
        ), follow_redirects=True)
        self.assertIn('Conflicto de horario', rv_overlap.data.decode('utf-8'))

        # Intentar reservar en horario parcial superpuesto (10:30 - 11:30)
        rv_overlap2 = self.client.post('/reservar', data=dict(
            title='Reunión superpuesta mitad',
            date=test_date,
            start_time='10:30',
            duration='60',
            description=''
        ), follow_redirects=True)
        self.assertIn('Conflicto de horario', rv_overlap2.data.decode('utf-8'))

    def test_cancellation_permissions(self):
        # 1. Crear una reserva con RRHH
        self.login('rrhh', 'rrhh123')
        test_date = '2026-12-01'
        self.client.post('/reservar', data=dict(
            title='Capacitación RRHH',
            date=test_date,
            start_time='09:00',
            duration='60',
            description=''
        ), follow_redirects=True)

        conn = get_db_connection()
        res = conn.execute("SELECT id FROM reservations WHERE title = 'Capacitación RRHH' AND status = 'active'").fetchone()
        conn.close()
        res_id = res['id']

        # 2. Iniciar sesión como usuario de Ventas (persona diferente)
        self.logout()
        self.login('ventas', 'ventas123')

        # Intentar cancelar la reserva de RRHH -> DEBE SER DENEGADO
        rv_denied = self.client.post(f'/reservas/{res_id}/cancelar', follow_redirects=True)
        self.assertIn('Permiso denegado', rv_denied.data.decode('utf-8'))

        # 3. Iniciar sesión como ADMIN -> DEBE PODER CANCELAR
        self.logout()
        self.login('admin', 'admin123')
        rv_admin_cancel = self.client.post(f'/reservas/{res_id}/cancelar', follow_redirects=True)
        self.assertIn('cancelada exitosamente', rv_admin_cancel.data.decode('utf-8'))

        # Verificar que el status cambió a 'cancelled'
        conn = get_db_connection()
        res_updated = conn.execute("SELECT status FROM reservations WHERE id = ?", (res_id,)).fetchone()
        conn.close()
        self.assertEqual(res_updated['status'], 'cancelled')

    def test_free_text_sector_registration(self):
        # Registrar un usuario con sector escrito en campo libre
        rv = self.client.post('/register', data=dict(
            full_name='Sofía Martínez',
            username='smartinez',
            sector='Comercio Exterior y Aduanas',
            password='pass1234',
            confirm_password='pass1234'
        ), follow_redirects=True)
        self.assertIn('Comercio Exterior y Aduanas', rv.data.decode('utf-8'))

        # Realizar una reserva con este usuario
        rv_res = self.client.post('/reservar', data=dict(
            title='Reunión de Despachos',
            date='2026-11-20',
            start_time='11:00',
            duration='60',
            description=''
        ), follow_redirects=True)
        self.assertIn('Reserva confirmada con éxito', rv_res.data.decode('utf-8'))

        # Comprobar que en la API del calendario figura el sector libre exacto
        rv_api = self.client.get('/api/reservations')
        events = rv_api.get_json()
        matching = [e for e in events if 'Comercio Exterior y Aduanas' in e['title']]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]['extendedProps']['sector'], 'Comercio Exterior y Aduanas')

    def test_recurring_reservation_and_series_cancel(self):
        self.login('sistemas', 'sistemas123')
        test_date = '2026-11-02' # Lunes

        # Crear reserva recurrente semanal de 4 reuniones
        rv = self.client.post('/reservar', data=dict(
            title='Revisión Semanal de Servidores',
            date=test_date,
            start_time='15:00',
            duration='60',
            description='Monitoreo periódico',
            is_recurring='1',
            recurrence_freq='weekly',
            recurrence_days=['0'],
            recurrence_end_mode='by_count',
            recurrence_count='4'
        ), follow_redirects=True)
        self.assertIn('Reserva recurrente confirmada con éxito', rv.data.decode('utf-8'))

        # Verificar que se crearon 4 registros en la BD con el mismo recurrence_id
        conn = get_db_connection()
        series = conn.execute("SELECT id, recurrence_id, status FROM reservations WHERE title = 'Revisión Semanal de Servidores'").fetchall()
        conn.close()
        self.assertEqual(len(series), 4)
        rec_id = series[0]['recurrence_id']
        self.assertIsNotNone(rec_id)

        # Cancelar la serie completa
        first_id = series[0]['id']
        rv_cancel = self.client.post(f'/reservas/{first_id}/cancelar', data=dict(
            cancel_series='1',
            reason='Cancelación de proyecto'
        ), follow_redirects=True)
        self.assertIn('serie recurrente', rv_cancel.data.decode('utf-8'))

        # Verificar que los 4 registros quedaron en 'cancelled'
        conn = get_db_connection()
        active_in_series = conn.execute("SELECT COUNT(*) FROM reservations WHERE recurrence_id = ? AND status = 'active'", (rec_id,)).fetchone()[0]
        conn.close()
        self.assertEqual(active_in_series, 0)

    def test_monthly_recurrence_options(self):
        self.login('rrhh', 'rrhh123')
        test_date = '2026-11-03' # Primer martes de noviembre 2026

        # Crear recurrencia mensual: "Primero Martes de cada mes", 3 reuniones
        rv = self.client.post('/reservar', data=dict(
            title='Comité de Recursos Humanos Mensual',
            date=test_date,
            start_time='10:00',
            duration='90',
            description='Reunión mensual fija',
            is_recurring='1',
            recurrence_freq='monthly',
            monthly_interval='1',
            monthly_type='by_ordinal',
            monthly_ordinal='1',  # Primero
            monthly_weekday='1',  # Martes
            recurrence_end_mode='by_count',
            recurrence_count='3'
        ), follow_redirects=True)
        self.assertIn('Reserva recurrente confirmada con éxito', rv.data.decode('utf-8'))

        conn = get_db_connection()
        monthly_series = conn.execute(
            "SELECT date FROM reservations WHERE title = 'Comité de Recursos Humanos Mensual' ORDER BY date ASC"
        ).fetchall()
        conn.close()

        # Las fechas deben ser: 2026-11-03, 2026-12-01, 2027-01-05 (los primeros martes de cada mes)
        expected_dates = ['2026-11-03', '2026-12-01', '2027-01-05']
        actual_dates = [r['date'] for r in monthly_series]
        self.assertEqual(actual_dates, expected_dates)

    def test_export_csv_admin(self):
        # Usuario normal no puede exportar
        self.login('rrhh', 'rrhh123')
        rv_user = self.client.get('/admin/exportar-csv', follow_redirects=True)
        self.assertIn('Acceso restringido a Administradores', rv_user.data.decode('utf-8'))
        self.logout()

        # Admin sí puede exportar
        self.login('admin', 'admin123')
        rv_admin = self.client.get('/admin/exportar-csv')
        self.assertEqual(rv_admin.status_code, 200)
        self.assertIn('text/csv', rv_admin.headers.get('Content-Type', ''))
        self.assertIn('attachment;filename=reservas_sala_piso2_', rv_admin.headers.get('Content-Disposition', ''))
        csv_content = rv_admin.data.decode('utf-8-sig')
        self.assertIn('ID,Título,Sector,Solicitante', csv_content)

if __name__ == '__main__':
    unittest.main()



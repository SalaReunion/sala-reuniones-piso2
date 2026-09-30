# 🏢 Sistema de Reserva - Sala de Reuniones del 2do Piso

Aplicación web completa desarrollada para la gestión, reserva y visualización de la **Sala de Reuniones del 2do Piso** por sectores de la empresa.

---

## 🌟 Características Principales

1. **Autenticación por Sectores**:
   - Cada persona inicia sesión con su cuenta asignada a su respectivo sector (Recursos Humanos, Sistemas / TI, Comercial / Ventas, Administración, Finanzas, o cualquier sector libremente escrito).
   - Registro de nuevas cuentas con campo libre de sector.
   - Rol de **Usuario de Sector** y rol de **Administrador**.

2. **Almanaque Interactivo (FullCalendar)**:
   - Vista visual estilo calendario/almanaque con vistas por **Mes, Semana, Día y Agenda**.
   - Colores diferenciados automáticamente por cada sector con leyenda dinámica de sectores registrados.
   - Clic directo en cualquier horario para pre-cargar la fecha y la hora exacta seleccionada.

3. **Motor de Reservas Recurrentes Avanzado**:
   - Repetición: **Diaria, Semanal, Mensual o Días a elección**.
   - Configuración Mensual idéntica a Google Calendar / Outlook:
     - Por día numérico del mes (ej: los días 15).
     - Por día ordinal relativo (ej: el **Primero / Segundo / Tercer / Cuarto / Último** **Lunes / Martes / Miércoles...**).
     - Intervalo de meses (repetir cada 1, 2, 3 meses).
   - Finalización: "Sin fecha de finalización" (hasta 1 año), "Por fecha", o "Después de X reuniones".

4. **Control Estricto de Cancelación**:
   - **Solo la persona que reservó** o un **Administrador** pueden cancelar el turno.
   - Si otra persona hace clic en un turno ajeno, el sistema le muestra los datos pero le bloquea la opción de cancelación.
   - Opción para cancelar solo el turno seleccionado o toda la serie futura si es recurrente.

5. **Exportación a Google Sheets / Excel (.CSV)**:
   - Desde el panel de administración (`/admin`), un botón permite descargar en un clic todas las reservas históricas y activas en formato `.csv` con codificación UTF-8 compatible directa con Google Sheets y Microsoft Excel.

---

## ☁️ Publicación en la Nube (Compartir por Link con la Organización)

Para que toda la organización acceda a través de un enlace web público seguro (`https://sala-reuniones.onrender.com`):

### Paso 1: Subir el proyecto a GitHub
1. Entra a [github.com](https://github.com) y crea un nuevo repositorio (ej: `sala-reuniones-piso2`), déjalo como **Público** o **Privado**.
2. Sube los archivos de este directorio:
   - **Opción con Git (terminal):**
     ```powershell
     git init
     git add .
     git commit -m "Sistema de reserva sala piso 2"
     git branch -M main
     git remote add origin https://github.com/TU_USUARIO/sala-reuniones-piso2.git
     git push -u origin main
     ```
   - **Opción rápida sin consola (Web de GitHub):**
     - En la página del repositorio vacío en GitHub, haz clic en **"uploading an existing file"**.
     - Arrastra todos los archivos de esta carpeta (excepto `sala_reuniones.db` si deseas arrancar con base de datos limpia) y haz clic en **Commit changes**.

### Paso 2: Crear el servicio en Render.com (Gratis)
1. Entra en [render.com](https://render.com) y regístrate o inicia sesión con tu cuenta de GitHub.
2. Haz clic en **New +** y selecciona **Web Service**.
3. Elige **"Build and deploy from a Git repository"** y selecciona tu repositorio `sala-reuniones-piso2`.
4. Render detectará automáticamente el archivo `render.yaml` y la configuración:
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: `Free`
5. Haz clic en **Create Web Service**.

En 2 minutos, Render generará un enlace público HTTPS (ejemplo: `https://sala-reuniones-piso2.onrender.com`) que podrás compartir con todas las personas y sectores de la organización.

---

## 📊 Cómo abrir la exportación en Google Sheets

1. En el panel de Administrador, haz clic en **"Exportar a Excel / Sheets (.CSV)"**.
2. Abre [Google Sheets](https://sheets.google.com) y crea una hoja en blanco.
3. Ve a **Archivo** > **Importar** > **Subir** y selecciona el archivo `.csv` descargado.
4. En "Tipo de separador" selecciona *Detectar automáticamente* o *Coma*.
5. ¡Listo! Tendrás todas las reservas ordenadas en columnas con filtros, estadísticas y gráficos.

---

## 🚀 Cómo Iniciar Localmente (en esta PC)

1. Haz doble clic en el archivo `iniciar.bat` (o ejecuta `python app.py` en la terminal).
2. Abre tu navegador web en: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🔑 Cuentas de Acceso Pre-cargadas

| Usuario | Contraseña | Sector | Rol |
| :--- | :--- | :--- | :--- |
| **`admin`** | `admin123` | Dirección General | **Administrador** (Control total y exportación) |
| **`sistemas`** | `sistemas123` | Sistemas / TI | Usuario regular |
| **`rrhh`** | `rrhh123` | Recursos Humanos | Usuario regular |
| **`ventas`** | `ventas123` | Comercial / Ventas | Usuario regular |
| **`finanzas`** | `finanzas123` | Finanzas | Usuario regular |


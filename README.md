# Notas en Acción

MVP de notas personales con carpetas y listas de tareas. Cada nota muestra cuántas tareas están completadas y el tablero puede mostrar solo notas con tareas pendientes. Cada cuenta accede a sus propios datos.

React + Vite para la web, FastAPI para la API y SQLite como base de datos. La aplicación guarda cinco tablas en un archivo dentro de un volumen Docker.

| Tabla | Datos |
| --- | --- |
| `users` | Nombre de usuario y hash de contraseña. |
| `sessions` | Hash del identificador de sesión, usuario y vencimiento. |
| `folders` | Carpetas asociadas a un usuario. |
| `notes` | Notas de una carpeta. |
| `checklist_items` | Tareas asociadas a una nota y estado de completado. |

## Abrir en tu PC

Con Docker Desktop iniciado, abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
docker compose up -d --build --wait
```

Abre [http://localhost:8080](http://localhost:8080). El entorno local crea dos cuentas de demo.

| Usuario | Contraseña local |
| --- | --- |
| `demo1` | `notas-demo-1` |
| `demo2` | `notas-demo-2` |

Usa `docker compose down` para detener la app conservando el volumen. `docker compose down -v` también elimina las notas locales.

Para trabajar sin Docker, ejecuta el backend y el frontend en dos terminales.

```powershell
# Terminal 1 desde la raíz del proyecto
cd backend
python -m pip install -r requirements-test.txt
$env:NOTES_DEMO = 'true'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
# Terminal 2 desde la raíz del proyecto
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Abre la URL que muestra Vite, normalmente [http://localhost:5173](http://localhost:5173).

## Verificar las pruebas

Desde `backend`, ejecuta `python -m pytest tests -v`. Hay **6 pruebas unitarias** de validación y progreso, y **6 de integración** con FastAPI y SQLite temporal.

Con el stack Docker activo, ejecuta `npx playwright install chromium` y `npm run test:e2e` desde `frontend`. Las **6 E2E** cubren sesión, carpetas, creación, edición, tareas, filtro y borrado. Usa un entorno con datos de prueba. Si usas Vite en vez de Compose, configura `$env:BASE_URL = 'http://localhost:5173'` en la terminal de Playwright.

## GitHub y despliegue

| Servicio | Nombre propuesto |
| --- | --- |
| GitHub | `cuquinata267-afk/notas-en-accion` |
| Docker Hub | `TU_USUARIO/notas-en-accion-api` |
| Docker Hub | `TU_USUARIO/notas-en-accion-web` |

Cada push a `dev` ejecuta las 18 pruebas. Cada push a `main` vuelve a probar y, con las credenciales configuradas, publica las dos imágenes, aplica Terraform y actualiza la app con Ansible. El estado de Terraform y el volumen SQLite se dedican a este proyecto.

Consulta [los pasos para publicar y conectar OCI](docs/DESPLIEGUE.md).

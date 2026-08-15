# 🔐 AnubisTec — Sistema de Autenticación

## 📥 Descargar o clonar el repositorio

Puedes acceder al archivo de este proyecto directamente desde GitHub usando la siguiente URL:

🔗 **https://github.com/VartaxOficial/AnubisTec/edit/main/README.md**

Esta URL te permite visualizar y editar este documento en línea. Para **clonar o descargar** el repositorio completo, sigue los pasos de la sección **"Paso a paso"** que encontrarás más abajo.

---

## 📖 ¿Qué es AnubisTec?

**AnubisTec** es un sistema de autenticación completo con las siguientes funciones:

- ✅ **Registro de usuarios** con contraseña cifrada mediante **bcrypt**.
- ✅ **Verificación de correo** mediante **código OTP de 6 dígitos** enviado por email.
- ✅ **Inicio de sesión seguro** con sesiones protegidas por cookies `HttpOnly`.
- ✅ **Panel de usuario (dashboard)** protegido: solo accesible con sesión activa.
- ✅ **Reenvío de código OTP** desde la página de verificación.
- ✅ **Protecciones de seguridad** integradas (anti fuerza bruta, validación de email/OTP, límite de tamaño de peticiones).

### 🛠️ Tecnologías utilizadas

| Tecnología | Uso |
|------------|-----|
| **Python 3** | Lenguaje de programación del servidor |
| **http.server** | Servidor web (sin frameworks externos) |
| **MongoDB Atlas** | Base de datos (almacenamiento de usuarios y sesiones) |
| **PyMongo** | Conexión de Python con MongoDB |
| **bcrypt** | Cifrado de contraseñas y códigos OTP |
| **SMTP / Gmail** | Envío de correos con el código de verificación |
| **HTML / CSS / JavaScript** | Interfaz de usuario (frontend) |

---

## ⚙️ Requisitos previos

Antes de comenzar, asegúrate de tener instalado lo siguiente en tu computadora:

1. **Python 3.8 o superior** → [Descargar Python](https://www.python.org/downloads/)
   - Durante la instalación marca la casilla **"Add Python to PATH"**.
2. **Git** (opcional, solo para clonar) → [Descargar Git](https://git-scm.com/downloads)
3. **Una cuenta de MongoDB Atlas** (gratuita) → [Crear cuenta](https://www.mongodb.com/cloud/atlas/register)
4. **Una cuenta de Gmail** con **contraseña de aplicación** habilitada → [Ver guía de Google](https://support.google.com/accounts/answer/185833)
   - Para generarla: entra a tu cuenta Google → **Seguridad** → **Verificación en dos pasos** (actívala) → **Contraseñas de aplicaciones**.

---

## 🚀 Paso a paso

### 1. Clonar o descargar el proyecto

**Opción A — Clonar con Git (recomendada):**

```bash
git clone https://github.com/VartaxOficial/AnubisTec.git
cd AnubisTec
```

**Opción B — Descargar como ZIP:**
1. Entra a https://github.com/VartaxOficial/AnubisTec
2. Clic en el botón verde **"Code"** → **"Download ZIP"**.
3. Descomprime el archivo en la carpeta donde quieras guardar el proyecto.
4. Abre una terminal dentro de la carpeta del proyecto.

> 💡 **Nota:** Los comandos siguientes se ejecutan desde la carpeta donde está el archivo `server.py`.

### 2. Crear un entorno virtual (recomendado)

```bash
python -m venv venv
```

Actívalo:

- **Windows:**
  ```bash
  venv\Scripts\activate
  ```
- **macOS / Linux:**
  ```bash
  source venv/bin/activate
  ```

### 3. Instalar las dependencias

```bash
pip install -r requirements.txt
```

> ⚠️ **Importante:** si el archivo `requirements.txt` no existe aún, instala las dependencias manualmente:
>
> ```bash
> pip install bcrypt python-dotenv pymongo[srv]
> ```

### 4. Configurar el archivo `.env`

Copia o crea un archivo llamado `.env` en la raíz del proyecto con la siguiente estructura:

```env
MONGO_URI=mongodb+srv://USUARIO:CONTRASEÑA@cluster0.XXXXX.mongodb.net/
DB_NAME=auth
COLLECTION=users
GMAIL_EMAIL=tu_correo@gmail.com
GMAIL_APP_PASSWORD=tu_contraseña_de_aplicacion
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

Reemplaza los valores por los tuyos:

| Variable | Descripción |
|----------|-------------|
| `MONGO_URI` | Cadena de conexión de tu clúster de MongoDB Atlas |
| `DB_NAME` | Nombre de la base de datos (por defecto: `auth`) |
| `COLLECTION` | Nombre de la colección de usuarios (por defecto: `users`) |
| `GMAIL_EMAIL` | Correo de Gmail que enviará los códigos OTP |
| `GMAIL_APP_PASSWORD` | Contraseña de aplicación generada en Google (sin espacios) |
| `SMTP_HOST` | Servidor SMTP (por defecto: `smtp.gmail.com`) |
| `SMTP_PORT` | Puerto SMTP (por defecto: `587`) |

> 🔒 **Seguridad:** el archivo `.env` **NO se sube a GitHub** (está en `.gitignore`) porque contiene tus credenciales reales. Cualquiera que clone el repositorio debe crear el suyo.

### 5. Ejecutar el servidor

```bash
python server.py
```

Verás algo así:

```
Conectado a MongoDB Atlas (db: auth, colección: users)
Servidor corriendo en http://127.0.0.1:8000
```

### 6. Abrir la aplicación

Abre tu navegador y entra a:

```
http://127.0.0.1:8000
```

### 7. Uso de la aplicación

1. **Registrarte** → completa el formulario con tu correo y una contraseña de al menos 6 caracteres.
2. **Verificar tu correo** → se te enviará un código OTP de 6 dígitos a tu email; ingrésalo en la página de verificación.
3. **Iniciar sesión** → usa tu correo y contraseña.
4. **Dashboard** → una vez dentro verás tu panel de bienvenida. Puedes cerrar sesión con el botón **"Cerrar sesión"**.

---

## 🔒 Seguridad implementada

Este proyecto incluye medidas de seguridad para protegerlo de ataques comunes:

- 🔑 **Contraseñas cifradas** con `bcrypt` (nunca se guardan en texto plano).
- 🍪 **Sesiones con cookies `HttpOnly; SameSite=Strict`** — el token de sesión no es legible desde la consola del navegador.
- 🛑 **Protección contra fuerza bruta** — máximo 20 intentos por IP cada 10 minutos en login, registro y verificación (código 429).
- 📏 **Límite de tamaño de peticiones** — se rechazan cuerpos de más de 64 KB.
- ✅ **Validación estricta de email y OTP** en el servidor (patrones fijos, sin inyección de regex).
- 🗄️ **Sin inyección SQL** — la app usa MongoDB (NoSQL) y todos los valores de usuario se convierten a texto antes de consultar.
- 🚫 **Sin ejecución de comandos** — no se usa `eval`, `exec` ni subprocesos del sistema.
- 🔇 **Sin fugas de información** — los errores internos se responden de forma genérica al cliente.

---

## 📂 Estructura del proyecto

```
├── server.py          # Servidor principal (toda la lógica backend)
├── login.html         # Página de inicio de sesión
├── register.html      # Página de registro
├── verify.html        # Página de verificación de correo (OTP)
├── dashboard.html     # Panel de usuario (requiere sesión)
├── .env               # Configuración (NO se sube a GitHub)
├── .gitignore         # Archivos ignorados por Git
└── requirements.txt   # Dependencias del proyecto
```

---

## ❓ Preguntas frecuentes

**¿Por qué no me llega el correo con el código?**
- Revisa la carpeta de spam.
- Verifica que `GMAIL_EMAIL` y `GMAIL_APP_PASSWORD` sean correctos.
- Confirma que generaste la contraseña de aplicación con la verificación en dos pasos activada.

**¿Cómo cambio el puerto del servidor?**
- Edita la variable `PORT = 8000` en `server.py`.

**¿Qué hago si aparece "Demasiados intentos"?**
- Espera 10 minutos. Es la protección contra fuerza bruta (rate limiting).

---

## 📧 Contacto

Proyecto: **AnubisTec**

📦 Repositorio: https://github.com/VartaxOficial/AnubisTec

Documento principal: https://github.com/VartaxOficial/AnubisTec/edit/main/README.md

---

Hecho con ❤️ por **VartaxOficial**

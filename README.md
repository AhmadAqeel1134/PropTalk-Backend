# PropTalk Backend

AI-Powered Receptionist Service for Real Estate - Backend API

## Tech Stack

- **Framework**: FastAPI
- **Database**: Neon (PostgreSQL)
- **ORM**: SQLAlchemy (async)
- **Authentication**: JWT
- **Voice**: Twilio
- **AI**: OpenAI (LLM, STT, TTS)
- **Storage**: Cloudinary

## Project Structure

```
app/
├── models/          # Database models (SQLAlchemy)
├── controllers/     # API routes (FastAPI endpoints)
├── services/        # Business logic
├── schemas/         # Pydantic schemas
├── database/        # Database connection
└── utils/           # Utilities
```

## Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Create `.env` file:**
```env
DATABASE_URL=postgresql://user:password@host/database
SECRET_KEY=your-secret-key
ADMIN_ONE_EMAIL=i221134@nu.edu.pk
ADMIN_TWO_EMAIL=i221010@nu.edu.pk
ADMIN_THREE_EMAIL=i220776@nu.edu.pk
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
OPENAI_API_KEY=your-openai-key
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

### Local PostgreSQL with Docker (recommended for local dev)

If you are using PostgreSQL through Docker Desktop, run a container first:

```bash
docker run --name proptalk-postgres ^
  -e POSTGRES_USER=proptalk ^
  -e POSTGRES_PASSWORD=proptalk123 ^
  -e POSTGRES_DB=proptalk_db ^
  -p 5432:5432 ^
  -d postgres:16
```

Use this `DATABASE_URL` in `.env`:

```env
DATABASE_URL=postgresql://proptalk:proptalk123@localhost:5432/proptalk_db
```

If the container already exists, start it with:

```bash
docker start proptalk-postgres
```

3. **Run database migrations:**
```bash
# Create initial migration (first time only)
python -m alembic revision --autogenerate -m "Initial migration"

# Apply migrations to create all tables
python -m alembic upgrade head
```

**Important:** All database tables are created through migrations. Run migrations before starting the server.

4. **Start the server:**
```bash
uvicorn app.main:app --reload
```

If `uvicorn` is not available in PATH on Windows, use:

```bash
python -m uvicorn app.main:app --reload
```

If port `8000` is already in use, run backend on another port:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Then point frontend API URL to the same backend port (for example, `http://localhost:8001`).

## Database Migrations

### Create a new migration:
```bash
alembic revision --autogenerate -m "Description of changes"
```

### Apply migrations:
```bash
python -m alembic upgrade head
```

### Rollback last migration:
```bash
python -m alembic downgrade -1
```

### Check current migration status:
```bash
python -m alembic current
```

## Google OAuth Setup

To enable Google Sign-In, you need to configure OAuth credentials in Google Cloud Console:

1. **Go to [Google Cloud Console](https://console.cloud.google.com/)**
2. **Create or select a project**
3. **Enable Google+ API:**
   - Go to "APIs & Services" > "Library"
   - Search for "Google+ API" and enable it
4. **Create OAuth 2.0 Credentials:**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Web application"
   - **Authorized JavaScript origins:** Add your frontend base URLs (NO paths):
     - `http://localhost:3000` (or your frontend port)
     - `http://127.0.0.1:3000` (also add this if using localhost)
     - `https://your-production-domain.com` (for production)
     - ⚠️ **Important:** These must be base URLs only, no paths like `/api/auth/callback`
   - **Authorized redirect URIs:** Add your callback URLs:
     - `http://localhost:3000/api/auth/callback/google` (your callback path)
     - `http://localhost:3000` (base URL, if your frontend handles redirects there)
     - `https://your-production-domain.com/api/auth/callback/google` (for production)
5. **Copy the Client ID and Client Secret** to your `.env` file

**Important:** The "Authorized JavaScript origins" must match exactly where your frontend is running. If you get "no registered origin" error, make sure the frontend URL is added to the authorized origins list.

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Ngrok tunnel activation
& "D:\Ngrok\ngrok-v3-stable-windows-amd64\ngrok.exe" http 8000
## Cloud fare tunnel
D:\cloudflare\cloudflared-windows-amd64.exe tunnel --url http://127.0.0.1:8000

## Backend Start 
python -m uvicorn app.main:app --reload

D:\cloudflare\cloudflared-windows-amd64.exe tunnel --no-autoupdate --protocol http2 --url http://localhost:8000
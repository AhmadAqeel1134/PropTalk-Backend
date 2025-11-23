# PropTalk Backend

AI-Powered Receptionist Service for Real Estate - Backend API

## Tech Stack

- **Framework**: FastAPI
- **Database**: Neon (PostgreSQL)
- **ORM**: Drizzle
- **Authentication**: JWT
- **Voice**: Twilio
- **AI**: OpenAI (LLM, STT, TTS)

## Project Structure

```
app/
├── models/          # Database models (Drizzle)
├── controllers/     # API routes (FastAPI endpoints)
├── services/        # Business logic
├── schemas/         # Pydantic schemas
├── database/        # Database connection
└── utils/           # Utilities
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and fill in your credentials

3. Run migrations:
```bash
# Will be added later
```

4. Start the server:
```bash
uvicorn app.main:app --reload
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc


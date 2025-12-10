# Local PostgreSQL Database Setup with Docker

This guide will help you set up a local PostgreSQL database using Docker for development.

## Prerequisites

- Docker Desktop installed and running
- Docker Compose (usually included with Docker Desktop)

## Quick Start

### 1. Start the Database

```bash
docker-compose up -d
```

This will:
- Download PostgreSQL 15 image (if not already downloaded)
- Create a container named `proptalk-postgres`
- Start PostgreSQL on port `5432`
- Create a database named `proptalk_db`
- Create a user `proptalk` with password `proptalk123`

### 2. Update Your `.env` File

Add or update the `DATABASE_URL` in your `.env` file:

```env
DATABASE_URL=postgresql://proptalk:proptalk123@localhost:5432/proptalk_db
```

**Note:** For local development, you don't need SSL, so no `?sslmode=require` parameter.

### 3. Run Database Migrations

If you're using Alembic for migrations:

```bash
alembic upgrade head
```

Or if you have a script to initialize the database:

```bash
python -m app.database.init_db
```

### 4. Verify Database is Running

```bash
# Check if container is running
docker ps

# View database logs
docker logs proptalk-postgres

# Connect to database (optional)
docker exec -it proptalk-postgres psql -U proptalk -d proptalk_db
```

## Common Commands

### Stop the Database

```bash
docker-compose down
```

### Stop and Remove Data (⚠️ This deletes all data!)

```bash
docker-compose down -v
```

### Restart the Database

```bash
docker-compose restart
```

### View Database Logs

```bash
docker logs -f proptalk-postgres
```

### Access PostgreSQL CLI

```bash
docker exec -it proptalk-postgres psql -U proptalk -d proptalk_db
```

Once inside, you can run SQL commands:
```sql
-- List all tables
\dt

-- View a table
SELECT * FROM contacts LIMIT 10;

-- Exit
\q
```

## Database Credentials

- **Host:** localhost
- **Port:** 5432
- **Database:** proptalk_db
- **Username:** proptalk
- **Password:** proptalk123

## Data Persistence

Your database data is stored in a Docker volume named `postgres_data`. This means:
- ✅ Data persists even if you stop the container
- ✅ Data persists even if you restart Docker
- ⚠️ Data is deleted only if you run `docker-compose down -v`

## Troubleshooting

### Port 5432 Already in Use

If you already have PostgreSQL running on port 5432, you can change the port in `docker-compose.yml`:

```yaml
ports:
  - "5433:5432"  # Use 5433 on your machine, 5432 in container
```

Then update your `.env`:
```env
DATABASE_URL=postgresql://proptalk:proptalk123@localhost:5433/proptalk_db
```

### Container Won't Start

1. Check if port is already in use:
   ```bash
   netstat -an | findstr 5432  # Windows
   lsof -i :5432               # Mac/Linux
   ```

2. Check Docker logs:
   ```bash
   docker logs proptalk-postgres
   ```

3. Remove and recreate:
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

### Connection Refused

1. Make sure Docker Desktop is running
2. Check if container is running: `docker ps`
3. Check container logs: `docker logs proptalk-postgres`
4. Verify the DATABASE_URL in your `.env` file

## Switching Between Local and Remote Database

You can easily switch between local Docker database and remote database (like Neon) by updating your `.env` file:

**Local (Docker):**
```env
DATABASE_URL=postgresql://proptalk:proptalk123@localhost:5432/proptalk_db
```

**Remote (Neon/Cloud):**
```env
DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require
```

Just restart your FastAPI server after changing the `.env` file.

## Backup and Restore

### Backup Database

```bash
docker exec proptalk-postgres pg_dump -U proptalk proptalk_db > backup.sql
```

### Restore Database

```bash
docker exec -i proptalk-postgres psql -U proptalk proptalk_db < backup.sql
```

## Production vs Development

⚠️ **Important:** This Docker setup is for **development only**. For production:
- Use a managed database service (Neon, Supabase, AWS RDS, etc.)
- Use strong passwords
- Enable SSL/TLS
- Set up proper backups
- Use connection pooling

# Database Migration Guide

This guide explains how to work with Alembic migrations for PropTalk Backend.

## Prerequisites

- Database connection string configured in `.env` file
- All dependencies installed (`pip install -r requirements.txt`)

## Migration Commands

### 1. Create a New Migration

To create a new migration after modifying models:

```bash
python -m alembic revision --autogenerate -m "Description of changes"
```

**Example:**
```bash
python -m alembic revision --autogenerate -m "Add new field to properties table"
```

**What it does:**
- Analyzes your SQLAlchemy models
- Compares with current database schema
- Generates a migration file in `alembic/versions/`
- Does NOT apply changes to database yet

---

### 2. Apply Migrations

To apply all pending migrations to the database:

```bash
python -m alembic upgrade head
```

**What it does:**
- Applies all migrations that haven't been run yet
- Creates/updates tables in your database
- Updates the `alembic_version` table to track current migration

**First time setup:**
```bash
# Create initial migration
python -m alembic revision --autogenerate -m "Initial migration"

# Apply it to create all tables
python -m alembic upgrade head
```

---

### 3. Check Current Migration Status

To see which migration is currently applied:

```bash
python -m alembic current
```

**Output example:**
```
8f9c20ebaeab (head)
```

---

### 4. View Migration History

To see all migrations (applied and pending):

```bash
python -m alembic history
```

---

### 5. Rollback Migrations

#### Rollback Last Migration

```bash
python -m alembic downgrade -1
```

#### Rollback to Specific Migration

```bash
python -m alembic downgrade <revision_id>
```

**Example:**
```bash
python -m alembic downgrade 8f9c20ebaeab
```

#### Rollback All Migrations

```bash
python -m alembic downgrade base
```

**⚠️ Warning:** Rolling back will delete data! Use with caution.

---

### 6. Create Empty Migration (Manual)

To create a migration file without autogenerate:

```bash
python -m alembic revision -m "Description"
```

Then manually edit the generated file in `alembic/versions/` to add your SQL commands.

---

## Step-by-Step Workflow

### Initial Setup (First Time)

1. **Ensure `.env` file has correct `DATABASE_URL`:**
   ```env
   DATABASE_URL=postgresql://user:password@host/database?sslmode=require
   ```

2. **Create initial migration:**
   ```bash
   python -m alembic revision --autogenerate -m "Initial migration"
   ```

3. **Review the generated migration file:**
   - Check `alembic/versions/xxxx_initial_migration.py`
   - Verify all tables are included

4. **Apply migration:**
   ```bash
   python -m alembic upgrade head
   ```

5. **Verify tables created:**
   - Check Neon dashboard or run: `python -m alembic current`

---

### Making Schema Changes

1. **Modify your SQLAlchemy models** in `app/models/`

2. **Create migration:**
   ```bash
   python -m alembic revision --autogenerate -m "Add new column"
   ```

3. **Review the migration file** to ensure changes are correct

4. **Apply migration:**
   ```bash
   python -m alembic upgrade head
   ```

---

## Common Issues

### Issue: "Target database is not up to date"

**Solution:**
```bash
# Check current status
python -m alembic current

# Apply pending migrations
python -m alembic upgrade head
```

### Issue: "Can't locate revision identified by 'xxxx'"

**Solution:**
```bash
# Check migration history
python -m alembic history

# If migration file is missing, recreate it or sync manually
```

### Issue: Migration conflicts

**Solution:**
1. Check `alembic/versions/` for duplicate revisions
2. Resolve conflicts manually in migration files
3. Or rollback and recreate migration

---

## Migration File Structure

Migration files are located in: `alembic/versions/`

**File naming:** `{revision_id}_{description}.py`

**Example:** `8f9c20ebaeab_initial_migration.py`

Each migration file contains:
- `revision`: Unique ID for this migration
- `down_revision`: ID of previous migration
- `upgrade()`: Function to apply changes
- `downgrade()`: Function to rollback changes

---

## Best Practices

1. **Always review** generated migration files before applying
2. **Test migrations** on development database first
3. **Commit migration files** to version control
4. **Use descriptive names** for migrations
5. **Never edit** applied migrations (create new ones instead)
6. **Backup database** before major migrations in production

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `python -m alembic revision --autogenerate -m "msg"` | Create new migration |
| `python -m alembic upgrade head` | Apply all pending migrations |
| `python -m alembic downgrade -1` | Rollback last migration |
| `python -m alembic current` | Show current migration |
| `python -m alembic history` | Show migration history |
| `python -m alembic downgrade base` | Rollback all migrations |

---

## Notes

- Migrations are **version controlled** - commit them to Git
- The `alembic_version` table tracks which migrations are applied
- Always run migrations **before** starting the server in production
- Use `--autogenerate` carefully - it may miss some changes


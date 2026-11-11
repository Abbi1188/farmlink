# Database

| File | Purpose |
| --- | --- |
| `init_db.py` | Creates all tables and loads the starting catalogue (grains, dairy, vegetables, fruits, eggs, honey). Safe to run repeatedly. |
| `seed_demo.py` | Adds an admin, a farmer with an approved farm, a buyer and three demo listings. Development only. |
| `schema.sql` | Reference PostgreSQL schema that mirrors `backend/app/models`. |
| `migrations/` | Reserved for Alembic migrations once the schema stabilises. |
| `farmlink.db` | SQLite file created on first run. Ignored by git. |

## Development (SQLite, nothing to install)

```bash
python database/init_db.py
python database/seed_demo.py
```

## Production (PostgreSQL)

1. Create a database and a user.
2. In `backend/.env` set `DATABASE_URL=postgresql+psycopg2://user:password@host:5432/farmlink`.
3. Run `python database/init_db.py`.
4. Before going live, move to Alembic migrations (`alembic init database/migrations`) and use `NUMERIC(10,2)` instead of floats for money columns.
5. For large volumes of location searches, add PostGIS and index a geography column.

# Database Migrations

This directory contains database migration scripts for making schema changes.

## Available Migrations

### add_metadata_to_booking.py

This migration adds the `booking_metadata` column to the `moving_bookings` table to fix compatibility with the Python model.

**How to run:**

1. Make sure the application environment variables are set (especially DATABASE_URL)
2. Run the migration script:

```bash
cd project_root/backend
source .env  # if you have environment variables in a .env file
python src/migrations/add_metadata_to_booking.py
```

You should see output indicating the migration was successful.

### add_metadata_direct.py (Recommended)

This is an alternative migration script that adds the `booking_metadata` column using a direct psycopg2 connection. This approach doesn't require Flask or SQLAlchemy and is more reliable when there are configuration issues.

**Prerequisites:**
- Python with psycopg2 installed (`pip install psycopg2-binary`)

**How to run:**

```bash
cd project_root/backend
python src/migrations/add_metadata_direct.py
```

This script will:
1. Try to find database connection information from environment variables or .env file
2. If not found, it will interactively prompt you for connection details
3. Connect directly to the database and make the schema change

**Troubleshooting:**

If you're not sure about your database credentials, you can find them:
1. Check your app's config files or environment variables
2. In a Flask app, the database URI is usually in a config file or .env file
3. You may need to ask your database administrator for credentials 
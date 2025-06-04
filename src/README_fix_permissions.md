# Moving Quote Request Permissions Fix

This documentation explains how to fix the "permission denied for table moving_quote_requests" error that occurs when submitting moving quote requests from the cost calculator.

## The Issue

The application doesn't have sufficient permissions to insert records into the `moving_quote_requests` table in the database, causing quote submissions to fail.

## Solution

You need to grant the appropriate permissions to ALL database users to ensure that any application connection can insert records. There are three ways to fix this:

### Option 1: Using the SQL Script (Recommended)

1. Connect to your PostgreSQL database as a superuser (or a user with permission to grant privileges)
2. Run the SQL script:

```bash
# For local development
psql -U postgres -d chatbotdb -f fix_moving_quotes_permissions.sql

# For production (example)
psql -U postgres -h your-db-host -d your-db-name -f fix_moving_quotes_permissions.sql
```

### Option 2: Using Python Script

If you prefer an automated approach:

1. Make sure your environment has access to the database with superuser privileges
2. Review and adjust the database connection in `fix_moving_quote_permissions.py` if necessary
3. Run the script:

```bash
python fix_moving_quote_permissions.py
```

### Option 3: Direct Database Commands

If you prefer to run commands directly in PostgreSQL:

1. Connect to your database as a superuser:

```bash
psql -U postgres -d chatbotdb
```

2. Run the following commands to grant permissions to ALL database users:

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON moving_quote_requests TO PUBLIC;
GRANT USAGE, SELECT ON SEQUENCE moving_quote_requests_id_seq TO PUBLIC;
```

## Security Note

Granting permissions to PUBLIC means that any database user can access and modify this table. This is appropriate for tables that need to be accessed by multiple application users, but if you need more restrictive security, you should consider:

1. Creating a specific application role with the necessary permissions
2. Granting permissions only to specific database users
3. Implementing row-level security if needed

## Verification

After applying the permissions fix, you can verify it worked by:

1. Trying to submit a quote from the moving cost calculator page
2. Checking the database permissions:

```sql
SELECT grantee, table_name, privilege_type 
FROM information_schema.table_privileges 
WHERE table_name = 'moving_quote_requests';
```

## Troubleshooting

If you're still having issues:

1. Check the server logs for more detailed error messages
2. Make sure the `moving_quote_requests` table exists in the database
3. Check if the sequence associated with the ID column has the correct permissions
4. Verify that the user connecting to the database has proper permissions

For additional help, please contact your system administrator or database administrator. 
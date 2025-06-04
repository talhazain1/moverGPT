# Fixing Booking Records

This document provides instructions for fixing booking records in the database where the session_id might have been stored as a string instead of an integer.

## Background

There was a discrepancy between the database schema (where `session_id` is defined as an integer) and the ORM model (where it was defined as a string). This might have caused some bookings to not appear in the confirmed bookings table.

We've fixed the MovingBooking model to use integer type for session_id, and created a script to fix any existing records in the database.

## Running the Fix

Follow these steps to run the fix:

1. Make sure you've updated the `MovingBooking` model in `backend/src/chatbot/moving_models.py` to use `Integer` type for `session_id`

2. Run the fix script:

```bash
cd project_root/backend
python -m src.fix_bookings
```

3. The script will:
   - Connect to the database
   - Find any bookings with string session IDs that should be integers
   - Convert those session IDs to integers
   - Report how many records were fixed

4. After running the script, restart the server:

```bash
# If using Docker
docker-compose restart

# If running directly
kill -HUP <pid>  # Where <pid> is the process ID of the backend server
# Then start the server again
```

5. Verify that bookings now appear correctly in the chat analysis page

## Troubleshooting

If the fix doesn't work:

1. Check the logs from the fix_bookings.py script for any errors
2. Verify that the database connection parameters in the script match your environment
3. You may need to manually update the booking records in the database if automatic conversion fails

For manual updates, you can use SQL:

```sql
-- View problematic records
SELECT id, session_id FROM moving_bookings;

-- Update a specific record
UPDATE moving_bookings SET session_id = 123 WHERE id = 456;
```

## Contact

If you encounter any issues with this fix, please contact the development team. 
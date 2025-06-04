-- Fix permissions for moving_quote_requests table
-- This grants the necessary permissions to ALL database users

-- Grant SELECT, INSERT, UPDATE, DELETE on the table to all users
GRANT SELECT, INSERT, UPDATE, DELETE ON moving_quote_requests TO PUBLIC;

-- Grant usage and sequence permissions for auto-increment ID to all users
GRANT USAGE, SELECT ON SEQUENCE moving_quote_requests_id_seq TO PUBLIC;

-- Verify the permissions
SELECT grantee, table_name, privilege_type 
FROM information_schema.table_privileges 
WHERE table_name = 'moving_quote_requests';

-- Note: Using PUBLIC means ALL database users will get these permissions 
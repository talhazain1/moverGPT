-- Check if ticket_number column exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'support_tickets' 
        AND column_name = 'ticket_number'
    ) THEN
        -- Add ticket_number column
        ALTER TABLE support_tickets ADD COLUMN ticket_number VARCHAR(20);
        
        -- Update existing records with generated ticket numbers
        WITH numbered_tickets AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY id) as row_num
            FROM support_tickets
        )
        UPDATE support_tickets 
        SET ticket_number = 'TICKET-' || LPAD(CAST(numbered_tickets.row_num AS TEXT), 6, '0')
        FROM numbered_tickets
        WHERE support_tickets.id = numbered_tickets.id;
        
        -- Make the column NOT NULL
        ALTER TABLE support_tickets ALTER COLUMN ticket_number SET NOT NULL;
        
        -- Add unique constraint
        ALTER TABLE support_tickets ADD CONSTRAINT uq_support_tickets_ticket_number UNIQUE (ticket_number);
        
        RAISE NOTICE 'Added ticket_number column to support_tickets table';
    ELSE
        RAISE NOTICE 'ticket_number column already exists in support_tickets table';
    END IF;
END $$; 
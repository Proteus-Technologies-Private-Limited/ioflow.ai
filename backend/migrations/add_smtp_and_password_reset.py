"""
Migration script to add SMTP configuration and password reset fields
"""
import sqlite3
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate():
    # Connect to the database
    conn = sqlite3.connect('backend/ioflow.db')
    cursor = conn.cursor()
    
    try:
        # Add password reset fields to users table
        print("Adding password reset fields to users table...")
        cursor.execute("""
            ALTER TABLE users ADD COLUMN reset_token VARCHAR(255)
        """)
        cursor.execute("""
            ALTER TABLE users ADD COLUMN reset_token_expires TIMESTAMP
        """)
        print("✓ Added reset_token and reset_token_expires to users table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("✓ Password reset fields already exist in users table")
        else:
            raise
    
    try:
        # Create SMTP configuration table
        print("Creating smtp_configuration table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS smtp_configuration (
                id VARCHAR(36) PRIMARY KEY,
                tenant_id VARCHAR(36) UNIQUE NOT NULL,
                smtp_host VARCHAR(255) NOT NULL,
                smtp_port INTEGER NOT NULL DEFAULT 587,
                smtp_username VARCHAR(255) NOT NULL,
                smtp_password VARCHAR(255) NOT NULL,
                smtp_from_email VARCHAR(255) NOT NULL,
                smtp_from_name VARCHAR(255) DEFAULT 'IOFlow',
                use_tls BOOLEAN DEFAULT 1,
                use_ssl BOOLEAN DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
            )
        """)
        print("✓ Created smtp_configuration table")
    except sqlite3.OperationalError as e:
        if "already exists" in str(e).lower():
            print("✓ smtp_configuration table already exists")
        else:
            raise
    
    # Commit the changes
    conn.commit()
    print("\n✅ Migration completed successfully!")
    
    conn.close()

if __name__ == "__main__":
    migrate()
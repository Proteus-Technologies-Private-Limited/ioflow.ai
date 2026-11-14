#!/usr/bin/env python3
"""Create admin user for IOFlow"""
import sqlite3
import uuid
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_admin_user():
    """Create the admin user"""
    conn = sqlite3.connect('ioflow.db')
    cursor = conn.cursor()
    
    try:
        # Check if proteus-technologies tenant exists
        cursor.execute("SELECT tenant_id FROM tenants WHERE tenant_name = ?", ('proteus-technologies',))
        tenant = cursor.fetchone()
        
        if not tenant:
            # Create proteus-technologies tenant
            tenant_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO tenants (tenant_id, tenant_name, schema_name, email_domain, status)
                VALUES (?, ?, ?, ?, ?)
            """, (tenant_id, 'proteus-technologies', 'tenant_proteus_technologies', 'proteus.com', 'active'))
            print(f"Created tenant 'proteus-technologies' with ID: {tenant_id}")
        else:
            tenant_id = tenant[0]
            print(f"Using existing tenant 'proteus-technologies' with ID: {tenant_id}")
        
        # Check if admin user exists
        cursor.execute("SELECT user_id FROM users WHERE email = ?", ('admin@ioflow.com',))
        if cursor.fetchone():
            print("Admin user already exists")
            # Update password
            password_hash = pwd_context.hash("admin123")
            cursor.execute("""
                UPDATE users 
                SET pass_wd_sha = ?, role = 'INSTANCE_ADMIN', tenant_id = ?
                WHERE email = ?
            """, (password_hash, tenant_id, 'admin@ioflow.com'))
            print("Updated admin user password and role")
        else:
            # Create admin user
            user_id = str(uuid.uuid4())
            password_hash = pwd_context.hash("admin123")
            
            cursor.execute("""
                INSERT INTO users (user_id, user_name, email, pass_wd_sha, tenant_id, role, is_active, auth_provider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, 'Admin User', 'admin@ioflow.com', password_hash, tenant_id, 'INSTANCE_ADMIN', 1, 'email'))
            print(f"Created admin user with ID: {user_id}")
        
        conn.commit()
        print("Admin user setup completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"Error creating admin user: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_admin_user()
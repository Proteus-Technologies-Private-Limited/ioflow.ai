#!/usr/bin/env python3
"""Reset user password"""
import sqlite3
import sys
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def reset_password(email, new_password):
    """Reset password for a user"""
    conn = sqlite3.connect('ioflow.db')
    cursor = conn.cursor()
    
    try:
        # Hash the new password
        password_hash = pwd_context.hash(new_password)
        
        # Update the user's password
        cursor.execute("""
            UPDATE users 
            SET pass_wd_sha = ?
            WHERE email = ?
        """, (password_hash, email))
        
        if cursor.rowcount == 0:
            print(f"No user found with email: {email}")
            return False
        
        conn.commit()
        print(f"Password successfully reset for {email}")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"Error resetting password: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python reset_user_password.py <email> <new_password>")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    if reset_password(email, password):
        print(f"You can now login with email: {email} and your new password")
    else:
        sys.exit(1)
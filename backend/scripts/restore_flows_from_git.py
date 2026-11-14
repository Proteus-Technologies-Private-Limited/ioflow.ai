#!/usr/bin/env python3
"""Restore flows from git database while preserving current user data"""
import sqlite3
import sys

def restore_flows():
    """Restore flows and related data from git database"""
    current_db = sqlite3.connect('ioflow.db')
    git_db = sqlite3.connect('ioflow_from_git.db')
    
    try:
        current_cursor = current_db.cursor()
        git_cursor = git_db.cursor()
        
        # Start transaction
        current_cursor.execute("BEGIN TRANSACTION")
        
        # 1. Clear current flows and executions (they're empty anyway)
        print("Clearing current flow data...")
        current_cursor.execute("DELETE FROM flows")
        current_cursor.execute("DELETE FROM flow_executions")
        current_cursor.execute("DELETE FROM execution_logs")
        
        # 2. Copy flows from git database
        print("Copying flows from git database...")
        git_cursor.execute("SELECT * FROM flows")
        flows = git_cursor.fetchall()
        
        # Get column names
        git_cursor.execute("PRAGMA table_info(flows)")
        columns = [col[1] for col in git_cursor.fetchall()]
        
        # Insert flows
        placeholders = ','.join(['?' for _ in columns])
        insert_query = f"INSERT INTO flows ({','.join(columns)}) VALUES ({placeholders})"
        
        for flow in flows:
            current_cursor.execute(insert_query, flow)
        
        print(f"Restored {len(flows)} flows")
        
        # 3. Copy flow_executions
        print("Copying flow executions...")
        git_cursor.execute("SELECT * FROM flow_executions")
        executions = git_cursor.fetchall()
        
        if executions:
            git_cursor.execute("PRAGMA table_info(flow_executions)")
            exec_columns = [col[1] for col in git_cursor.fetchall()]
            
            exec_placeholders = ','.join(['?' for _ in exec_columns])
            exec_insert_query = f"INSERT INTO flow_executions ({','.join(exec_columns)}) VALUES ({exec_placeholders})"
            
            for execution in executions:
                try:
                    current_cursor.execute(exec_insert_query, execution)
                except sqlite3.IntegrityError:
                    pass  # Skip if already exists
            
            print(f"Restored {len(executions)} flow executions")
        
        # 4. Copy execution_logs
        print("Copying execution logs...")
        git_cursor.execute("SELECT * FROM execution_logs")
        logs = git_cursor.fetchall()
        
        if logs:
            git_cursor.execute("PRAGMA table_info(execution_logs)")
            log_columns = [col[1] for col in git_cursor.fetchall()]
            
            log_placeholders = ','.join(['?' for _ in log_columns])
            log_insert_query = f"INSERT INTO execution_logs ({','.join(log_columns)}) VALUES ({log_placeholders})"
            
            for log in logs:
                try:
                    current_cursor.execute(log_insert_query, log)
                except sqlite3.IntegrityError:
                    pass  # Skip if already exists
            
            print(f"Restored {len(logs)} execution logs")
        
        # 5. Copy applications if they don't exist
        print("Checking applications...")
        current_cursor.execute("SELECT COUNT(*) FROM applications")
        current_app_count = current_cursor.fetchone()[0]
        
        if current_app_count == 0:
            git_cursor.execute("SELECT * FROM applications")
            apps = git_cursor.fetchall()
            
            if apps:
                git_cursor.execute("PRAGMA table_info(applications)")
                app_columns = [col[1] for col in git_cursor.fetchall()]
                
                app_placeholders = ','.join(['?' for _ in app_columns])
                app_insert_query = f"INSERT INTO applications ({','.join(app_columns)}) VALUES ({app_placeholders})"
                
                for app in apps:
                    try:
                        current_cursor.execute(app_insert_query, app)
                    except sqlite3.IntegrityError:
                        pass
                
                print(f"Restored {len(apps)} applications")
        
        # 6. Copy application subscriptions
        print("Checking application subscriptions...")
        git_cursor.execute("SELECT * FROM application_subscriptions")
        subs = git_cursor.fetchall()
        
        if subs:
            git_cursor.execute("PRAGMA table_info(application_subscriptions)")
            sub_columns = [col[1] for col in git_cursor.fetchall()]
            
            sub_placeholders = ','.join(['?' for _ in sub_columns])
            sub_insert_query = f"INSERT OR IGNORE INTO application_subscriptions ({','.join(sub_columns)}) VALUES ({sub_placeholders})"
            
            for sub in subs:
                current_cursor.execute(sub_insert_query, sub)
            
            print(f"Restored {len(subs)} application subscriptions")
        
        # Commit changes
        current_db.commit()
        print("\nSuccessfully restored all flow data from git!")
        
    except Exception as e:
        current_db.rollback()
        print(f"Error during restoration: {e}")
        sys.exit(1)
    finally:
        current_db.close()
        git_db.close()

if __name__ == "__main__":
    print("Restoring flows from git database while preserving current user data...")
    restore_flows()
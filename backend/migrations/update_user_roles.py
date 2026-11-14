#!/usr/bin/env python3
"""
Migration script to update user roles from old values to new values:
- ADMIN -> INSTANCE_ADMIN
- PROJECT_OWNER -> FLOW_DESIGNER
- Add TENANT_ADMIN role for existing tenant owners
"""

import os
import sys
import logging
from datetime import datetime

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from core.config import settings
from db.models import User, Tenant, UserRole

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_user_roles():
    """Migrate user roles to new structure"""
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        logger.info("Starting user role migration...")
        
        # Check if we're using SQLite or PostgreSQL
        is_sqlite = settings.database_url.startswith("sqlite")
        
        if is_sqlite:
            # SQLite migration
            logger.info("Migrating SQLite database...")
            
            # Update ADMIN to INSTANCE_ADMIN
            result = session.execute(
                text("UPDATE users SET role = 'INSTANCE_ADMIN' WHERE role = 'ADMIN'")
            )
            logger.info(f"Updated {result.rowcount} ADMIN users to INSTANCE_ADMIN")
            
            # Update PROJECT_OWNER to FLOW_DESIGNER
            result = session.execute(
                text("UPDATE users SET role = 'FLOW_DESIGNER' WHERE role = 'PROJECT_OWNER'")
            )
            logger.info(f"Updated {result.rowcount} PROJECT_OWNER users to FLOW_DESIGNER")
            
        else:
            # PostgreSQL migration
            logger.info("Migrating PostgreSQL database...")
            
            # Update ADMIN to INSTANCE_ADMIN
            result = session.execute(
                text("UPDATE ioflow.users SET role = 'INSTANCE_ADMIN' WHERE role = 'ADMIN'")
            )
            logger.info(f"Updated {result.rowcount} ADMIN users to INSTANCE_ADMIN")
            
            # Update PROJECT_OWNER to FLOW_DESIGNER
            result = session.execute(
                text("UPDATE ioflow.users SET role = 'FLOW_DESIGNER' WHERE role = 'PROJECT_OWNER'")
            )
            logger.info(f"Updated {result.rowcount} PROJECT_OWNER users to FLOW_DESIGNER")
        
        # Add a TENANT_ADMIN for each tenant (if they don't have one)
        logger.info("Checking for tenants without TENANT_ADMIN...")
        
        # Get all tenants
        tenants = session.query(Tenant).all()
        
        for tenant in tenants:
            # Check if tenant has a TENANT_ADMIN
            tenant_admin = session.query(User).filter(
                User.tenant_id == tenant.tenant_id,
                User.role == UserRole.TENANT_ADMIN
            ).first()
            
            if not tenant_admin:
                # Check if the tenant owner exists and make them TENANT_ADMIN
                if tenant.user_id_own:
                    owner = session.query(User).filter(
                        User.user_id == tenant.user_id_own
                    ).first()
                    
                    if owner and owner.role != UserRole.INSTANCE_ADMIN:
                        owner.role = UserRole.TENANT_ADMIN
                        logger.info(f"Made user {owner.email} TENANT_ADMIN for tenant {tenant.tenant_name}")
                    else:
                        # Find the first active user in the tenant
                        first_user = session.query(User).filter(
                            User.tenant_id == tenant.tenant_id,
                            User.is_active == True,
                            User.role != UserRole.INSTANCE_ADMIN
                        ).first()
                        
                        if first_user:
                            first_user.role = UserRole.TENANT_ADMIN
                            logger.info(f"Made user {first_user.email} TENANT_ADMIN for tenant {tenant.tenant_name}")
                        else:
                            logger.warning(f"No suitable user found to be TENANT_ADMIN for tenant {tenant.tenant_name}")
        
        # Update proteus-technologies tenant if it doesn't exist
        proteus_tenant = session.query(Tenant).filter(
            Tenant.tenant_name == 'proteus-technologies'
        ).first()
        
        if not proteus_tenant:
            # Find the first INSTANCE_ADMIN user
            instance_admin = session.query(User).filter(
                User.role == UserRole.INSTANCE_ADMIN
            ).first()
            
            if instance_admin:
                # Create proteus-technologies tenant
                import uuid
                new_tenant = Tenant(
                    tenant_id=str(uuid.uuid4()),
                    tenant_name='proteus-technologies',
                    schema_name='tenant_proteus_technologies',
                    email_domain=instance_admin.email.split('@')[1],
                    user_id_own=instance_admin.user_id,
                    status='active'
                )
                session.add(new_tenant)
                
                # Update instance admin's tenant
                instance_admin.tenant_id = new_tenant.tenant_id
                logger.info(f"Created proteus-technologies tenant and assigned to {instance_admin.email}")
        
        # Commit all changes
        session.commit()
        logger.info("Migration completed successfully!")
        
        # Print summary
        logger.info("\nMigration Summary:")
        
        # Count users by role
        if is_sqlite:
            role_counts = session.execute(
                text("SELECT role, COUNT(*) as count FROM users GROUP BY role")
            ).fetchall()
        else:
            role_counts = session.execute(
                text("SELECT role, COUNT(*) as count FROM ioflow.users GROUP BY role")
            ).fetchall()
        
        logger.info("User counts by role:")
        for role, count in role_counts:
            logger.info(f"  {role}: {count}")
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    migrate_user_roles()
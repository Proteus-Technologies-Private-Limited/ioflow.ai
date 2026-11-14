"""
Migration script to add marketplace tables and update FrontendFlowApplication
Run this script to add marketplace functionality to IOFlow

Usage:
    python migrations/add_marketplace_tables.py
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import create_engine, text
from core.config import settings
from db.database import get_db_context
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Run marketplace migration for SQLite database"""

    logger.info("Starting marketplace migration...")

    # Get database session using context manager
    with get_db_context() as db:
        # 1. Create app_categories table
        logger.info("Creating app_categories table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS app_categories (
                category_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                slug TEXT NOT NULL UNIQUE,
                description TEXT,
                icon TEXT,
                display_order INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """))

        # Create indexes for app_categories
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_category_slug ON app_categories(slug)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_category_active ON app_categories(is_active)"))

        # 2. Create app_tags table
        logger.info("Creating app_tags table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS app_tags (
                tag_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                slug TEXT NOT NULL UNIQUE,
                color TEXT,
                is_active BOOLEAN DEFAULT 1,
                usage_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create indexes for app_tags
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_tag_slug ON app_tags(slug)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_tag_usage ON app_tags(usage_count)"))

        # 3. Create app_category_mapping table
        logger.info("Creating app_category_mapping table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS app_category_mapping (
                mapping_id TEXT PRIMARY KEY,
                app_id TEXT NOT NULL,
                category_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (app_id) REFERENCES frontend_flow_applications(frontend_app_id),
                FOREIGN KEY (category_id) REFERENCES app_categories(category_id)
            )
        """))

        # Create indexes
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_app_category ON app_category_mapping(app_id, category_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_category_apps ON app_category_mapping(category_id)"))

        # 4. Create app_tag_mapping table
        logger.info("Creating app_tag_mapping table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS app_tag_mapping (
                mapping_id TEXT PRIMARY KEY,
                app_id TEXT NOT NULL,
                tag_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (app_id) REFERENCES frontend_flow_applications(frontend_app_id),
                FOREIGN KEY (tag_id) REFERENCES app_tags(tag_id)
            )
        """))

        # Create indexes
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_app_tag ON app_tag_mapping(app_id, tag_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_tag_apps ON app_tag_mapping(tag_id)"))

        # 5. Create app_reviews table
        logger.info("Creating app_reviews table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS app_reviews (
                review_id TEXT PRIMARY KEY,
                app_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                rating INTEGER NOT NULL,
                title TEXT,
                review_text TEXT,
                helpful_count INTEGER DEFAULT 0,
                verified_subscriber BOOLEAN DEFAULT 0,
                is_visible BOOLEAN DEFAULT 1,
                is_edited BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (app_id) REFERENCES frontend_flow_applications(frontend_app_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
            )
        """))

        # Create indexes
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_review_app ON app_reviews(app_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_review_user ON app_reviews(user_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_review_rating ON app_reviews(rating)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_review_created ON app_reviews(created_at)"))
        db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_user_app_review ON app_reviews(app_id, user_id)"))

        # 6. Create review_helpful table
        logger.info("Creating review_helpful table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS review_helpful (
                id TEXT PRIMARY KEY,
                review_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (review_id) REFERENCES app_reviews(review_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """))

        # Create indexes
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_helpful_review ON review_helpful(review_id)"))
        db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_helpful ON review_helpful(review_id, user_id)"))

        # 7. Create creator_tiers table
        logger.info("Creating creator_tiers table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS creator_tiers (
                tier_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL UNIQUE,
                tier_level TEXT NOT NULL DEFAULT 'new',
                auto_approve BOOLEAN DEFAULT 0,
                total_apps_created INTEGER DEFAULT 0,
                total_subscribers INTEGER DEFAULT 0,
                avg_app_rating REAL DEFAULT 0.0,
                total_revenue REAL DEFAULT 0.0,
                assigned_by TEXT,
                assigned_at TIMESTAMP,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (assigned_by) REFERENCES users(user_id)
            )
        """))

        # Create indexes
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_creator_user ON creator_tiers(user_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_creator_tier ON creator_tiers(tier_level)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_creator_auto_approve ON creator_tiers(auto_approve)"))

        # 8. Create marketplace_approvals table
        logger.info("Creating marketplace_approvals table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS marketplace_approvals (
                approval_id TEXT PRIMARY KEY,
                app_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                submitted_by TEXT NOT NULL,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_by TEXT,
                reviewed_at TIMESTAMP,
                review_notes TEXT,
                rejection_reason TEXT,
                version INTEGER DEFAULT 1,
                previous_approval_id TEXT,
                FOREIGN KEY (app_id) REFERENCES frontend_flow_applications(frontend_app_id),
                FOREIGN KEY (submitted_by) REFERENCES users(user_id),
                FOREIGN KEY (reviewed_by) REFERENCES users(user_id),
                FOREIGN KEY (previous_approval_id) REFERENCES marketplace_approvals(approval_id)
            )
        """))

        # Create indexes
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_approval_app ON marketplace_approvals(app_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_approval_status ON marketplace_approvals(status)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_approval_submitted_at ON marketplace_approvals(submitted_at)"))

        # 9. Create app_metrics table
        logger.info("Creating app_metrics table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS app_metrics (
                metric_id TEXT PRIMARY KEY,
                app_id TEXT NOT NULL UNIQUE,
                total_subscribers INTEGER DEFAULT 0,
                active_subscribers INTEGER DEFAULT 0,
                subscribers_last_7_days INTEGER DEFAULT 0,
                subscribers_last_30_days INTEGER DEFAULT 0,
                total_reviews INTEGER DEFAULT 0,
                avg_rating REAL DEFAULT 0.0,
                rating_distribution TEXT,
                total_executions INTEGER DEFAULT 0,
                executions_last_7_days INTEGER DEFAULT 0,
                executions_last_30_days INTEGER DEFAULT 0,
                avg_execution_time REAL,
                success_rate REAL,
                total_revenue REAL DEFAULT 0.0,
                revenue_last_30_days REAL DEFAULT 0.0,
                trending_score REAL DEFAULT 0.0,
                featured_rank INTEGER,
                featured_until TIMESTAMP,
                last_calculated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (app_id) REFERENCES frontend_flow_applications(frontend_app_id)
            )
        """))

        # Create indexes
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_metrics_app ON app_metrics(app_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_metrics_trending ON app_metrics(trending_score)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_metrics_featured ON app_metrics(featured_rank)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_metrics_rating ON app_metrics(avg_rating)"))

        # 10. Create marketplace_settings table
        logger.info("Creating marketplace_settings table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS marketplace_settings (
                setting_id TEXT PRIMARY KEY,
                key TEXT NOT NULL UNIQUE,
                value TEXT,
                description TEXT,
                updated_by TEXT,
                updated_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (updated_by) REFERENCES users(user_id)
            )
        """))

        # Create index
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_setting_key ON marketplace_settings(key)"))

        # 11. Add new columns to frontend_flow_applications table
        logger.info("Updating frontend_flow_applications table...")

        # Check if columns exist before adding
        result = db.execute(text("PRAGMA table_info(frontend_flow_applications)"))
        existing_columns = {row[1] for row in result.fetchall()}

        columns_to_add = [
            ("marketplace_status", "TEXT DEFAULT 'draft'"),
            ("approval_notes", "TEXT"),
            ("approved_by", "TEXT"),
            ("approved_at", "TIMESTAMP"),
            ("icon_url", "TEXT"),
            ("screenshots", "TEXT"),
            ("demo_url", "TEXT"),
            ("categories", "TEXT"),
            ("tags", "TEXT"),
            ("featured_rank", "INTEGER"),
            ("trending_score", "REAL DEFAULT 0.0"),
            ("total_subscribers", "INTEGER DEFAULT 0"),
            ("active_subscribers", "INTEGER DEFAULT 0"),
            ("avg_rating", "REAL DEFAULT 0.0"),
            ("total_reviews", "INTEGER DEFAULT 0"),
        ]

        for column_name, column_def in columns_to_add:
            if column_name not in existing_columns:
                logger.info(f"Adding column {column_name}...")
                db.execute(text(f"ALTER TABLE frontend_flow_applications ADD COLUMN {column_name} {column_def}"))
            else:
                logger.info(f"Column {column_name} already exists, skipping...")

        # 12. Insert default categories
        logger.info("Inserting default categories...")
        default_categories = [
            ("productivity", "Productivity", "Tools to boost productivity and efficiency"),
            ("marketing", "Marketing & Sales", "Marketing automation and sales tools"),
            ("analytics", "Analytics & Reporting", "Data analysis and reporting tools"),
            ("communication", "Communication", "Email, SMS, and messaging tools"),
            ("ai", "AI & Machine Learning", "AI-powered tools and integrations"),
            ("ecommerce", "E-commerce", "Online store and payment integrations"),
            ("social-media", "Social Media", "Social media management and posting"),
            ("finance", "Finance & Accounting", "Financial management and accounting"),
            ("hr", "Human Resources", "HR management and recruitment tools"),
            ("developer-tools", "Developer Tools", "APIs and developer utilities"),
        ]

        for slug, name, desc in default_categories:
            # Check if category already exists
            result = db.execute(text("SELECT category_id FROM app_categories WHERE slug = :slug"), {"slug": slug})
            if not result.fetchone():
                import uuid
                db.execute(text("""
                    INSERT INTO app_categories (category_id, name, slug, description, display_order)
                    VALUES (:id, :name, :slug, :desc, :order)
                """), {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "slug": slug,
                    "desc": desc,
                    "order": len([c for c in default_categories if default_categories.index(c) < default_categories.index((slug, name, desc))])
                })
                logger.info(f"Inserted category: {name}")

        # 13. Insert default tags
        logger.info("Inserting default tags...")
        default_tags = [
            ("ai", "AI", "#6366f1"),
            ("email", "Email", "#ef4444"),
            ("wordpress", "WordPress", "#21759b"),
            ("google", "Google", "#4285f4"),
            ("database", "Database", "#10b981"),
            ("automation", "Automation", "#f59e0b"),
            ("api", "API", "#8b5cf6"),
            ("integration", "Integration", "#ec4899"),
        ]

        for slug, name, color in default_tags:
            result = db.execute(text("SELECT tag_id FROM app_tags WHERE slug = :slug"), {"slug": slug})
            if not result.fetchone():
                import uuid
                db.execute(text("""
                    INSERT INTO app_tags (tag_id, name, slug, color)
                    VALUES (:id, :name, :slug, :color)
                """), {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "slug": slug,
                    "color": color
                })
                logger.info(f"Inserted tag: {name}")

        logger.info("Migration completed successfully!")


if __name__ == "__main__":
    run_migration()

from logging.config import fileConfig
import sys
from pathlib import Path

from sqlalchemy import engine_from_config, pool, create_engine

from alembic import context

# Add the backend directory to sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models to ensure they are registered with Base.metadata
# This is required for autogenerate to detect all tables
from db.models import Base
from db.application_models import (
    Application, ApplicationEvent, ApplicationService,
    OAuthState, ApplicationSubscription, PublishedApplication,
    PublishedApplicationVersion, FlowApplicationDependency,
    ParameterMapping, FlowExecutionBridge, FrontendFlowApplication,
    FrontendAppAccessLog, FrontendAppEmbedConfig
)
from db.pricing_models import (
    ApplicationPricing, ServicePricing, TenantApplicationSubscription,
    ExecutionCostLog, ApplicationInvoice, TenantBalance,
    BalanceTransaction, UsageLimit
)
from db.collaboration_models import (
    CollaborationSession, CollaborationParticipant
)
from db.ai_conversation_models import (
    AITransformConversation, AITransformMessage, AITransformSnapshot
)
from db.marketplace_models import (
    AppCategory, AppTag, AppReview, CreatorTier,
    MarketplaceApproval, AppMetrics, MicroSaasSubscriber
)
from db.documentation_models import AppDocumentationPage
from db.polling_models import PollingState

# Set the target metadata for autogenerate support
target_metadata = Base.metadata

# Get database URL from settings
def get_url():
    return settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="ioflow",
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_engine(
        get_url(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema="ioflow",
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

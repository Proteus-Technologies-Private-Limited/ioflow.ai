"""
Polling State Management Models - PostgreSQL and SQLite
"""
from sqlalchemy import Column, String, Text, Boolean, TIMESTAMP, Integer, UniqueConstraint
from sqlalchemy.sql import func
import uuid

from .models import Base
from .db_compat import JSONB, schema_table_args


class PollingState(Base):
    """Track polling state for each flow/event combination"""
    __tablename__ = 'polling_states'
    __table_args__ = schema_table_args(
        UniqueConstraint('flow_id', 'app_id', 'event_name', name='uq_polling_state'),
        extend_existing=True
    )

    polling_state_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flow_id = Column(String(36), nullable=False, index=True)
    app_id = Column(String(36), nullable=False)
    tenant_id = Column(String(36), nullable=False, index=True)

    event_name = Column(String(255), nullable=False)

    # State tracking
    last_poll_state = Column(JSONB)
    last_poll_timestamp = Column(TIMESTAMP)
    last_successful_poll = Column(TIMESTAMP)

    # Track processed items to avoid duplicates
    items_processed = Column(JSONB, default=list)
    items_processed_count = Column(Integer, default=0)

    # Error tracking
    consecutive_errors = Column(Integer, default=0)
    last_error = Column(Text)
    last_error_timestamp = Column(TIMESTAMP)

    # Metadata
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    def get_state_value(self, key, default=None):
        """Get a value from the last_poll_state JSON"""
        if not self.last_poll_state:
            return default
        return self.last_poll_state.get(key, default)

    def update_state(self, new_state):
        """Update the polling state"""
        if not self.last_poll_state:
            self.last_poll_state = {}
        self.last_poll_state.update(new_state)
        self.last_poll_timestamp = func.current_timestamp()

    def add_processed_items(self, items, max_items=10000):
        """Add items to processed list, maintaining a maximum size"""
        if not self.items_processed:
            self.items_processed = []

        # Add new items
        if isinstance(items, list):
            self.items_processed.extend(items)
        else:
            self.items_processed.append(items)

        # Trim to maximum size (keep most recent)
        if len(self.items_processed) > max_items:
            self.items_processed = self.items_processed[-max_items:]

        self.items_processed_count = len(self.items_processed)

    def has_processed_item(self, item_id):
        """Check if an item has already been processed"""
        if not self.items_processed:
            return False
        return item_id in self.items_processed

    def reset_error_count(self):
        """Reset error tracking after successful poll"""
        self.consecutive_errors = 0
        self.last_error = None
        self.last_error_timestamp = None
        self.last_successful_poll = func.current_timestamp()

    def record_error(self, error_message):
        """Record a polling error"""
        if self.consecutive_errors is None:
            self.consecutive_errors = 0
        self.consecutive_errors += 1
        self.last_error = str(error_message)[:1000]
        self.last_error_timestamp = func.current_timestamp()

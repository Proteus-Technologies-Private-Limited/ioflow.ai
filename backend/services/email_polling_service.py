"""
Email Polling Service for IOFlow
Monitors email inboxes and triggers flows based on incoming emails
"""
import asyncio
import logging
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import json
import re
from sqlalchemy.orm import Session
from sqlalchemy import and_

from db.database import get_db_context, get_tenant_db
from db.models import Flow, FlowStatus
from db.application_models import (
    ApplicationSubscription, 
    Application,
    TriggerType
)
from services.execution_engine import ExecutionEngine
from core.config import settings
from utils.crypto_utils import decrypt_credentials

logger = logging.getLogger(__name__)


class EmailPollingService:
    """Service to handle email-based triggers (IMAP/POP3)"""

    def __init__(self):
        self.polling_tasks: Dict[str, asyncio.Task] = {}
        self.execution_engine = ExecutionEngine
        self.running = False
        self.poll_interval = 60  # Check every minute by default
        self.lock_manager = None  # Will be injected by BackgroundServiceManager
        
    async def start(self):
        """Start the email polling service"""
        logger.info("Starting email polling service...")
        self.running = True
        
        # Load all active flows with email triggers
        await self._load_email_flows()
        
        # Start monitoring task
        asyncio.create_task(self._monitor_flows())
        
        logger.info("Email polling service started")
        
    async def stop(self):
        """Stop the email polling service"""
        logger.info("Stopping email polling service...")
        self.running = False
        
        # Cancel all polling tasks
        for task_id, task in self.polling_tasks.items():
            task.cancel()
            
        self.polling_tasks.clear()
        logger.info("Email polling service stopped")
        
    async def _monitor_flows(self):
        """Monitor for changes in flows and update polling tasks"""
        while self.running:
            try:
                await self._load_email_flows()
                await asyncio.sleep(300)  # Check every 5 minutes
            except Exception as e:
                logger.error(f"Error in email flow monitor: {str(e)}")
                await asyncio.sleep(300)
                
    async def _load_email_flows(self):
        """Load all active flows with email triggers"""
        try:
            with get_db_context() as db:
                # Get all tenants
                from sqlalchemy import text
                tenants = db.execute(text("SELECT DISTINCT tenant_id FROM users WHERE tenant_id IS NOT NULL")).fetchall()
                
                for tenant_row in tenants:
                    tenant_id = tenant_row[0]
                    await self._load_tenant_email_flows(db, tenant_id)
                    
        except Exception as e:
            logger.error(f"Error loading email flows: {str(e)}")
            
    async def _load_tenant_email_flows(self, db: Session, tenant_id: str):
        """Load email flows for a specific tenant"""
        try:
            # Get tenant schema
            from api.flows import get_tenant_schema
            from db.models import User
            
            # Get a user from this tenant to get schema
            user = db.query(User).filter(User.tenant_id == tenant_id).first()
            if not user:
                return
                
            schema_name = get_tenant_schema(user, db)
            
            with get_tenant_db(schema_name) as tenant_db:
                # Get active flows with email triggers for this specific tenant.
                # Flows live in the shared ioflow.flows table (models are
                # schema-qualified, so the tenant search_path does not isolate
                # them) — without the tenant_id filter every tenant's pass
                # would start a duplicate email polling task for every flow.
                flows = tenant_db.query(Flow).filter(
                    Flow.tenant_id == tenant_id,
                    Flow.status == FlowStatus.ACTIVE
                ).all()
                
                # Filter flows with email triggers
                flows = [f for f in flows if f.trigger_config and f.trigger_config.get('type') == 'email']
                
                for flow in flows:
                    task_id = f"{tenant_id}:{flow.flow_id}"
                    
                    # Check if task already exists
                    if task_id in self.polling_tasks:
                        if not self.polling_tasks[task_id].done():
                            continue
                            
                    # Create new polling task
                    task = asyncio.create_task(
                        self._poll_email_for_flow(tenant_id, schema_name, flow)
                    )
                    self.polling_tasks[task_id] = task
                    
        except Exception as e:
            logger.error(f"Error loading tenant email flows: {str(e)}")
            
    async def _poll_email_for_flow(self, tenant_id: str, schema_name: str, flow: Flow):
        """Poll email for a specific flow"""
        task_id = f"{tenant_id}:{flow.flow_id}"
        logger.info(f"Starting email polling for flow {flow.flow_name} (ID: {flow.flow_id})")
        
        try:
            trigger_config = flow.trigger_config
            email_config = trigger_config.get('email_config', {})
            
            # Get email server configuration
            server_type = email_config.get('server_type', 'imap')
            host = email_config.get('host')
            port = email_config.get('port', 993 if server_type == 'imap' else 995)
            username = email_config.get('username')
            password = email_config.get('password')
            
            # Email filter criteria
            filter_criteria = email_config.get('filter', {})
            
            if not all([host, username, password]):
                logger.error(f"Invalid email config for flow {flow.flow_id}")
                return
                
            # Decrypt password if stored as encrypted credentials
            if isinstance(password, dict) and 'encrypted' in password:
                decrypted = decrypt_credentials(password)
                password = decrypted.get('password', password)
            elif password.startswith('encrypted:'):
                # Handle legacy format - just strip the prefix for now
                password = password[len('encrypted:'):]
                
            # Track processed emails
            processed_emails = set()
            
            while self.running and task_id in self.polling_tasks:
                try:
                    # Connect to email server and fetch new emails
                    new_emails = await asyncio.to_thread(
                        self._fetch_new_emails,
                        server_type, host, port, username, password,
                        filter_criteria, processed_emails
                    )
                    
                    # Trigger flow for each new email
                    for email_data in new_emails:
                        await self._trigger_flow_for_email(
                            tenant_id, schema_name, flow, email_data
                        )
                        
                except Exception as e:
                    logger.error(f"Error polling email for flow {flow.flow_id}: {str(e)}")
                    
                # Wait before next poll
                await asyncio.sleep(self.poll_interval)
                
        except Exception as e:
            logger.error(f"Fatal error in email polling task for flow {flow.flow_id}: {str(e)}")
        finally:
            # Remove task from tracking
            if task_id in self.polling_tasks:
                del self.polling_tasks[task_id]
                
    def _fetch_new_emails(
        self, 
        server_type: str,
        host: str, 
        port: int, 
        username: str, 
        password: str,
        filter_criteria: Dict[str, Any],
        processed_emails: set
    ) -> List[Dict[str, Any]]:
        """Fetch new emails from server"""
        new_emails = []
        
        try:
            if server_type == 'imap':
                # Connect to IMAP server
                if port == 993:
                    mail = imaplib.IMAP4_SSL(host, port)
                else:
                    mail = imaplib.IMAP4(host, port)
                    
                mail.login(username, password)
                mail.select('INBOX')
                
                # Build search criteria
                search_criteria = self._build_imap_search_criteria(filter_criteria)
                
                # Search for emails
                _, message_numbers = mail.search(None, search_criteria)
                
                for num in message_numbers[0].split():
                    # Fetch email
                    _, msg_data = mail.fetch(num, '(RFC822)')
                    
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            # Parse email
                            msg = email.message_from_bytes(response_part[1])
                            
                            # Get message ID
                            message_id = msg.get('Message-ID', '')
                            
                            # Skip if already processed
                            if message_id in processed_emails:
                                continue
                                
                            # Extract email data
                            email_data = self._extract_email_data(msg)
                            
                            # Check if email matches filter criteria
                            if self._matches_filter(email_data, filter_criteria):
                                new_emails.append(email_data)
                                processed_emails.add(message_id)
                                
                mail.close()
                mail.logout()
                
        except Exception as e:
            logger.error(f"Error fetching emails: {str(e)}")
            
        return new_emails
        
    def _build_imap_search_criteria(self, filter_criteria: Dict[str, Any]) -> str:
        """Build IMAP search criteria from filter configuration"""
        criteria_parts = []
        
        # Add UNSEEN to only get unread emails
        criteria_parts.append('UNSEEN')
        
        # From filter
        if 'from' in filter_criteria:
            from_filter = filter_criteria['from']
            if isinstance(from_filter, str):
                criteria_parts.append(f'FROM "{from_filter}"')
            elif isinstance(from_filter, list):
                # Multiple from addresses
                from_criteria = ' OR '.join(f'FROM "{addr}"' for addr in from_filter)
                criteria_parts.append(f'({from_criteria})')
                
        # Subject filter
        if 'subject' in filter_criteria:
            subject_filter = filter_criteria['subject']
            if 'contains' in subject_filter:
                criteria_parts.append(f'SUBJECT "{subject_filter["contains"]}"')
            elif 'regex' in subject_filter:
                # IMAP doesn't support regex, use contains as fallback
                criteria_parts.append(f'SUBJECT "{subject_filter["regex"]}"')
                
        # Date filter
        if 'since' in filter_criteria:
            # Calculate date
            since_days = filter_criteria['since']
            since_date = (datetime.now() - timedelta(days=since_days)).strftime('%d-%b-%Y')
            criteria_parts.append(f'SINCE {since_date}')
            
        # Combine criteria
        if len(criteria_parts) > 1:
            return f'({" ".join(criteria_parts)})'
        elif criteria_parts:
            return criteria_parts[0]
        else:
            return 'ALL'
            
    def _extract_email_data(self, msg: email.message.Message) -> Dict[str, Any]:
        """Extract data from email message"""
        email_data = {
            'message_id': msg.get('Message-ID', ''),
            'from': self._decode_header(msg.get('From', '')),
            'to': self._decode_header(msg.get('To', '')),
            'subject': self._decode_header(msg.get('Subject', '')),
            'date': msg.get('Date', ''),
            'headers': dict(msg.items()),
            'body': {},
            'attachments': []
        }
        
        # Extract body and attachments
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get('Content-Disposition', ''))
            
            if 'attachment' in content_disposition:
                # Extract attachment info
                filename = part.get_filename()
                if filename:
                    email_data['attachments'].append({
                        'filename': self._decode_header(filename),
                        'content_type': content_type,
                        'size': len(part.get_payload(decode=True))
                    })
            else:
                # Extract body
                if content_type == 'text/plain':
                    body = part.get_payload(decode=True)
                    if body:
                        email_data['body']['plain'] = body.decode('utf-8', errors='ignore')
                elif content_type == 'text/html':
                    body = part.get_payload(decode=True)
                    if body:
                        email_data['body']['html'] = body.decode('utf-8', errors='ignore')
                        
        return email_data
        
    def _decode_header(self, header_value: str) -> str:
        """Decode email header value"""
        if not header_value:
            return ''
            
        decoded_parts = decode_header(header_value)
        decoded_string = ''
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_string += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                decoded_string += part
                
        return decoded_string
        
    def _matches_filter(self, email_data: Dict[str, Any], filter_criteria: Dict[str, Any]) -> bool:
        """Check if email matches filter criteria"""
        # If no filter criteria, match all
        if not filter_criteria:
            return True
            
        # Check subject regex
        if 'subject' in filter_criteria and 'regex' in filter_criteria['subject']:
            regex_pattern = filter_criteria['subject']['regex']
            if not re.search(regex_pattern, email_data['subject'], re.IGNORECASE):
                return False
                
        # Check body contains
        if 'body' in filter_criteria and 'contains' in filter_criteria['body']:
            search_text = filter_criteria['body']['contains'].lower()
            body_text = email_data['body'].get('plain', '') + email_data['body'].get('html', '')
            if search_text not in body_text.lower():
                return False
                
        return True
        
    async def _trigger_flow_for_email(
        self, 
        tenant_id: str,
        schema_name: str,
        flow: Flow,
        email_data: Dict[str, Any]
    ):
        """Trigger flow execution for an email"""
        try:
            trigger_data = {
                'type': 'email',
                'timestamp': datetime.utcnow().isoformat(),
                'email': email_data
            }
            
            # Use distributed lock if available to prevent duplicate execution
            if self.lock_manager:
                from services.distributed_lock import DistributedLockManager

                # Generate unique lock key for this email
                lock_key = DistributedLockManager.get_execution_lock_key(
                    flow.flow_id,
                    trigger_data
                )

                # Try to acquire lock (don't retry, skip if already processing)
                acquired = await self.lock_manager.acquire_lock(
                    lock_key,
                    ttl=300,  # 5 minutes should be enough for most flows
                    retry_count=0
                )

                if acquired:
                    try:
                        # Start flow execution
                        engine = self.execution_engine(schema_name)
                        try:
                            await engine.execute_flow(
                                flow_id=flow.flow_id,
                                trigger_data=trigger_data,
                                trigger_type='email'
                            )
                            logger.info(f"Triggered flow {flow.flow_id} for email from {email_data['from']}")
                        finally:
                            await engine.close()
                    finally:
                        # Release lock after execution
                        await self.lock_manager.release_lock(lock_key)
                else:
                    # Another worker is already processing this email
                    logger.debug(
                        f"Skipping duplicate execution for flow {flow.flow_id}, "
                        f"email already being processed by another worker"
                    )
            else:
                # Fallback to direct execution (backward compatibility)
                engine = self.execution_engine(schema_name)
                try:
                    await engine.execute_flow(
                        flow_id=flow.flow_id,
                        trigger_data=trigger_data,
                        trigger_type='email'
                    )
                    logger.info(f"Triggered flow {flow.flow_id} for email from {email_data['from']}")
                finally:
                    await engine.close()
                
        except Exception as e:
            logger.error(f"Error triggering flow for email: {str(e)}")


# Global email polling service instance
email_polling_service = EmailPollingService()


async def start_email_polling_service():
    """Start the global email polling service"""
    await email_polling_service.start()
    
    
async def stop_email_polling_service():
    """Stop the global email polling service"""
    await email_polling_service.stop()
from fastapi import APIRouter, Request, HTTPException, Depends, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
import asyncio
import logging
from typing import Dict, Any
from datetime import datetime
import json

from db.database import get_db, get_tenant_db
from db.models import Flow, FlowStatus, Tenant
from db.application_models import ApplicationSubscription
from db.application_models import Application, ApplicationEvent
from .execution_engine import ExecutionEngine
from .webhook_verification import webhook_verification_service, get_signature_config, verify_body_signature
from .distributed_lock import DistributedLockManager
from utils.crypto_utils import decrypt_credentials
from core.config import settings

logger = logging.getLogger(__name__)

def deserialize_json_field(value):
    """Deserialize JSON field for SQLite compatibility"""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value

# Global distributed lock manager for webhook handler
webhook_lock_manager = None

async def get_webhook_lock_manager():
    """Get or initialize the webhook lock manager"""
    global webhook_lock_manager
    if webhook_lock_manager is None:
        webhook_lock_manager = DistributedLockManager("webhook-handler")
        await webhook_lock_manager.initialize()
    return webhook_lock_manager

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Also create a router for API calls
api_router = APIRouter(prefix="/api/v1/events", tags=["events"])

@router.post("/{app_id}/{event_name}")
async def handle_webhook(
    app_id: str,
    event_name: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle incoming webhooks from external applications."""
    try:
        # Verify application exists
        app = db.query(Application).filter(Application.app_id == app_id).first()
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Get application configuration
        app_config = {
            'webhook_config': app.webhook_config or {}
        }
        
        # For webhook verification, we need to get any subscription's credentials
        # that might contain signing secrets
        sample_subscription = db.query(ApplicationSubscription).filter(
            ApplicationSubscription.app_id == app_id,
            ApplicationSubscription.status == 'active'
        ).first()
        
        credentials = {}
        if sample_subscription and sample_subscription.auth_credentials:
            try:
                credentials = decrypt_credentials(sample_subscription.auth_credentials)
            except Exception as e:
                logger.warning(f"Failed to decrypt credentials: {e}")
        
        # Verify webhook
        is_valid, response_data = await webhook_verification_service.verify_webhook(
            request, app_config, credentials
        )
        
        # Handle verification challenges (e.g., Slack URL verification, META/Facebook)
        if response_data:
            # Check if plain text response is requested (required by META/Facebook)
            if isinstance(response_data, dict) and "__plain_text__" in response_data:
                return PlainTextResponse(content=str(response_data["__plain_text__"]))
            return response_data
        
        if not is_valid:
            raise HTTPException(status_code=401, detail="Webhook verification failed")
        
        # Get request body - use stored body if available
        if hasattr(request, '_body'):
            body = json.loads(request._body)
        else:
            body = await request.json()
        
        # Extract API key from headers
        api_key = None

        # First check if application has configured a custom API key header name
        # or a custom query-param name (for receivers that can't send headers, e.g. WATI)
        if app.webhook_config:
            webhook_config = deserialize_json_field(app.webhook_config)
            if webhook_config and isinstance(webhook_config, dict):
                custom_api_key_header = webhook_config.get("api_key_header_name")
                if custom_api_key_header:
                    api_key = request.headers.get(custom_api_key_header)
                    if api_key:
                        logger.info(f"API key extracted from custom header: {custom_api_key_header}")

                if not api_key:
                    custom_api_key_query = webhook_config.get("api_key_query_param")
                    if custom_api_key_query:
                        api_key = request.query_params.get(custom_api_key_query)
                        if api_key:
                            logger.info(f"API key extracted from query param: {custom_api_key_query}")

        # If no custom header configured or no API key found, use standard headers
        if not api_key:
            # Prefer standard Bearer token format
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                api_key = auth_header[7:]  # Remove "Bearer " prefix

        # Fallback to x-api-key for backward compatibility
        if not api_key:
            api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
        
        # Verify event exists in application (query from ApplicationEvent table)
        event = db.query(ApplicationEvent).filter(
            ApplicationEvent.app_id == app_id,
            ApplicationEvent.event_name == event_name,
            ApplicationEvent.is_active == True
        ).first()
        
        if not event:
            raise HTTPException(status_code=404, detail=f"Event '{event_name}' not found for application")
        
        # API key is required for webhook authentication
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Please provide API key using 'Authorization: Bearer <api_key>' header"
            )
        
        # Validate API key and get associated subscriptions
        subscriptions = db.query(ApplicationSubscription).filter(
            ApplicationSubscription.app_id == app_id,
            ApplicationSubscription.invocation_api_key == api_key,
            ApplicationSubscription.status == 'active'
        ).all()
        
        if not subscriptions:
            # Log the invalid attempt
            logger.warning(f"Invalid API key attempt for app {app_id}, event {event_name}")
            raise HTTPException(
                status_code=401, 
                detail="Invalid API key or no active subscription found"
            )

        # Opt-in body signature check (event_configuration.signature, else the
        # application's webhook_config.signature), verified per subscription
        # against THAT connection's secret - e.g. Shopify X-Shopify-Hmac-Sha256.
        signature_config = get_signature_config(
            deserialize_json_field(event.event_configuration),
            deserialize_json_field(app.webhook_config)
        )
        if signature_config:
            raw_body = await request.body()
            verified_subscriptions = []
            for candidate in subscriptions:
                candidate_credentials = {}
                if candidate.auth_credentials:
                    try:
                        candidate_credentials = decrypt_credentials(candidate.auth_credentials) or {}
                    except Exception as e:
                        logger.error(f"Webhook signature: cannot decrypt credentials of subscription "
                                     f"{candidate.subscription_id}: {e}")
                        continue
                is_signed, reason = verify_body_signature(raw_body, request.headers, signature_config,
                                                          candidate_credentials)
                if is_signed:
                    verified_subscriptions.append(candidate)
                else:
                    logger.warning(f"Webhook signature rejected for app {app_id}, event {event_name}, "
                                   f"subscription {candidate.subscription_id}: {reason}")
            if not verified_subscriptions:
                raise HTTPException(status_code=401, detail="Webhook signature verification failed")
            subscriptions = verified_subscriptions
            logger.info(f"Webhook signature verified for {len(subscriptions)} subscription(s)")
        
        # Update last used timestamp for all matching subscriptions
        for subscription in subscriptions:
            subscription.api_key_last_used_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Valid API key for {len(subscriptions)} subscription(s)")
        
        # Process webhook for each subscribed tenant
        tasks = []
        
        logger.info(f"Found {len(subscriptions)} active subscriptions for app {app_id}")
        
        for subscription in subscriptions:
            # Get tenant schema - use ORM instead of raw SQL for compatibility
            tenant = db.query(Tenant).filter(
                Tenant.tenant_id == subscription.tenant_id
            ).first()
            
            if tenant:
                logger.info(f"Processing webhook for tenant {tenant.tenant_id} (schema: {tenant.schema_name})")
                task = process_webhook_for_tenant(
                    schema_name=tenant.schema_name,
                    tenant_id=tenant.tenant_id,
                    app_id=app_id,
                    event_id=str(event.event_id),  # Pass event_id
                    event_name=event_name,
                    webhook_data=body
                )
                tasks.append(task)
            else:
                logger.warning(f"Tenant not found for subscription {subscription.tenant_id}")
        
        # Execute all tenant processing in parallel
        results = []
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
        # Log webhook processing summary and any errors
        success_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {i} failed with exception: {result}")
            elif result is True:
                success_count += 1
                
        logger.info(f"Webhook processed: app_id={app_id}, event={event_name}, tenants={len(tasks)}, successful={success_count}")
        
        return {
            "status": "accepted",
            "message": f"Webhook processed for {len(tasks)} tenants",
            "details": {
                "app_id": app_id,
                "event_name": event_name,
                "event_id": str(event.event_id),
                "tenants_notified": len(tasks),
                "successful": success_count
            }
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions to preserve specific error messages
        raise
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@api_router.post("/{app_id}/{event_name}")
async def handle_api_call_trigger(
    app_id: str,
    event_name: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle API call triggers for application events."""
    try:
        logger.info(f"API call trigger received: app_id={app_id}, event_name={event_name}")
        
        # Get request body - use stored body if available
        try:
            if hasattr(request, '_body'):
                body = json.loads(request._body)
            else:
                body = await request.json()
            logger.info(f"Request body parsed successfully: {body}")
        except Exception as e:
            logger.error(f"Failed to parse request body: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid JSON in request body")
        
        # Verify application exists
        app = db.query(Application).filter(Application.app_id == app_id).first()
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Extract API key from headers
        api_key = None

        # First check if application has configured a custom API key header name
        # or a custom query-param name (for receivers that can't send headers, e.g. WATI)
        if app.webhook_config:
            webhook_config = deserialize_json_field(app.webhook_config)
            if webhook_config and isinstance(webhook_config, dict):
                custom_api_key_header = webhook_config.get("api_key_header_name")
                if custom_api_key_header:
                    api_key = request.headers.get(custom_api_key_header)
                    if api_key:
                        logger.info(f"API key extracted from custom header: {custom_api_key_header}")

                if not api_key:
                    custom_api_key_query = webhook_config.get("api_key_query_param")
                    if custom_api_key_query:
                        api_key = request.query_params.get(custom_api_key_query)
                        if api_key:
                            logger.info(f"API key extracted from query param: {custom_api_key_query}")

        # If no custom header configured or no API key found, use standard headers
        if not api_key:
            # Prefer standard Bearer token format
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                api_key = auth_header[7:]  # Remove "Bearer " prefix

        # Fallback to x-api-key for backward compatibility
        if not api_key:
            api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
        
        # Verify event exists in application and is for API calls
        event = db.query(ApplicationEvent).filter(
            ApplicationEvent.app_id == app_id,
            ApplicationEvent.event_name == event_name,
            ApplicationEvent.is_active == True,
            ApplicationEvent.event_type == 'api_call'
        ).first()
        
        if not event:
            logger.error(f"API event not found: {event_name} (app_id: {app_id})")
            raise HTTPException(status_code=404, detail=f"API call event '{event_name}' not found for application")
        
        logger.info(f"API event found: {event.display_name} (event_id: {event.event_id})")
        
        # API key is required for API call authentication
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Please provide API key using 'Authorization: Bearer <api_key>' header"
            )
        
        # Validate API key and get associated subscriptions
        subscriptions = db.query(ApplicationSubscription).filter(
            ApplicationSubscription.app_id == app_id,
            ApplicationSubscription.invocation_api_key == api_key,
            ApplicationSubscription.status == 'active'
        ).all()
        
        if not subscriptions:
            # Log the invalid attempt
            logger.warning(f"Invalid API key attempt for app {app_id}, event {event_name}")
            raise HTTPException(
                status_code=401, 
                detail="Invalid API key or no active subscription found"
            )
        
        # Update last used timestamp for all matching subscriptions
        for subscription in subscriptions:
            subscription.api_key_last_used_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Valid API key for {len(subscriptions)} subscription(s)")
        
        logger.info(f"Found {len(subscriptions)} active subscriptions for app {app_id}")
        
        # Process API call for each subscribed tenant
        tasks = []
        
        for subscription in subscriptions:
            # Get tenant schema - use ORM instead of raw SQL for compatibility
            tenant = db.query(Tenant).filter(
                Tenant.tenant_id == subscription.tenant_id
            ).first()
            
            if tenant:
                logger.info(f"Processing API call for tenant {tenant.tenant_id} (schema: {tenant.schema_name})")
                task = process_api_event_for_tenant(
                    schema_name=tenant.schema_name,
                    tenant_id=tenant.tenant_id,
                    app_id=app_id,
                    event_id=str(event.event_id),  # Pass event_id
                    event_name=event_name,
                    webhook_data=body,
                    is_api_call=True
                )
                tasks.append(task)
            else:
                logger.warning(f"Tenant not found for subscription {subscription.tenant_id}")
        
        # Execute all tenant processing in parallel
        results = []
        sync_response = None  # Store synchronous flow response
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
        # Log API call processing summary and any errors
        success_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {i} failed with exception: {result}")
            elif isinstance(result, dict) and 'sync_response' in result:
                sync_response = result
                success_count += 1
            elif result is True:
                success_count += 1
                
        logger.info(f"API call processed: app_id={app_id}, event={event_name}, tenants={len(tasks)}, successful={success_count}")
        
        # If we have a synchronous response, return it directly
        if sync_response:
            # Extract response data, headers, and status code
            response_data = sync_response.get('sync_response', sync_response)
            headers = sync_response.get('headers', {})
            status_code = sync_response.get('status_code', 200)
            
            # If it's an error response, raise HTTPException with the error data
            if status_code >= 400:
                # Pass the error data as detail - our custom handler will format it
                raise HTTPException(status_code=status_code, detail=response_data)
            
            # Return the actual flow response data
            return response_data
        
        return {
            "status": "accepted",
            "message": f"API call processed for {len(tasks)} tenants",
            "details": {
                "app_id": app_id,
                "event_name": event_name,
                "event_id": str(event.event_id),
                "tenants_notified": len(tasks),
                "successful": success_count
            }
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions to preserve specific error messages
        raise
    except Exception as e:
        logger.error(f"API call processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

async def process_api_event_for_tenant(schema_name: str, tenant_id: str, app_id: str, event_id: str, event_name: str, 
                                      webhook_data: Dict[str, Any], is_api_call: bool = False):
    """Process API event for a specific tenant, handling synchronous flows."""
    try:
        with get_tenant_db(schema_name) as tenant_db:
            # Find flows triggered by this event. Flows live in the shared
            # ioflow.flows table (models are schema-qualified, so the tenant
            # search_path does not isolate them) — the tenant_id filter is
            # what prevents triggering other tenants' flows.
            flows = tenant_db.query(Flow).filter(
                Flow.tenant_id == tenant_id,
                Flow.status.in_([FlowStatus.ACTIVE, FlowStatus.DRAFT])
            ).all()
            
            triggered_flows = []
            logger.info(f"Checking {len(flows)} active/draft flows in tenant {schema_name}")
            
            for flow in flows:
                trigger_config = flow.trigger_config or {}
                
                # Match by event_id (primary) or event_name (fallback for backward compatibility)
                if trigger_config.get('type') == 'event':
                    config_app_id = trigger_config.get('app_id')
                    config_event_id = trigger_config.get('event_id')
                    config_event_name = trigger_config.get('event_name')
                    
                    # More flexible matching - handle case and whitespace differences
                    event_name_matches = False
                    if config_event_name and event_name:
                        # Normalize event names for comparison (lowercase, replace spaces with underscores)
                        normalized_config = config_event_name.lower().replace(' ', '_').replace('-', '_')
                        normalized_webhook = event_name.lower().replace(' ', '_').replace('-', '_')
                        event_name_matches = normalized_config == normalized_webhook
                    
                    if (config_app_id == app_id and 
                        (config_event_id == event_id or event_name_matches or config_event_name == event_name)):
                        logger.info(f"Flow {flow.flow_id} matches event criteria")
                        triggered_flows.append(flow)
            
            # Handle synchronous flows for API calls
            if is_api_call and triggered_flows:
                # Check if any flow is synchronous
                for flow in triggered_flows:
                    if flow.is_synchronous:
                        logger.info(f"Found synchronous flow {flow.flow_id} for API call")
                        is_simulation = flow.status == FlowStatus.DRAFT
                        
                        trigger_data = {
                            "event_id": event_id,
                            "event_name": event_name,
                            "app_id": app_id,
                            "webhook_data": webhook_data,
                            "is_simulation": is_simulation
                        }
                        
                        # Execute synchronously with distributed lock
                        lock_manager = await get_webhook_lock_manager()
                        lock_key = DistributedLockManager.get_execution_lock_key(
                            flow.flow_id,
                            trigger_data
                        )

                        acquired = await lock_manager.acquire_lock(
                            lock_key,
                            ttl=max(flow.sync_timeout or 30, 60),  # Use timeout or minimum 60s
                            retry_count=0
                        )

                        if not acquired:
                            # Return error if can't acquire lock
                            return {
                                'sync_response': {
                                    'data': None,
                                    'error': {
                                        'code': 'DUPLICATE_REQUEST',
                                        'message': 'This request is already being processed'
                                    },
                                    'headers': {},
                                    'status_code': 409
                                }
                            }

                        # Execute synchronously and return the response
                        engine = ExecutionEngine(schema_name, tenant_id)
                        try:
                            result = await engine.execute_flow_sync(
                                flow_id=flow.flow_id,
                                trigger_data=trigger_data,
                                trigger_type='event',
                                timeout=flow.sync_timeout or 30
                            )
                            
                            # Return the synchronous response
                            # The result is already structured from execute_flow_sync
                            # Handle both cases: when result is the data directly or when it has a 'data' key
                            if isinstance(result, dict) and 'data' in result:
                                response_data = result['data']
                                headers = result.get('headers', {})
                                status_code = result.get('status', 200)
                            else:
                                # Result is the actual response data
                                response_data = result
                                headers = {}
                                status_code = 200
                            
                            return {
                                'sync_response': response_data,
                                'headers': headers,
                                'status_code': status_code
                            }
                        except Exception as e:
                            # For synchronous flows, we need to return error response
                            logger.error(f"Synchronous flow execution failed: {str(e)}")
                            return {
                                'sync_response': {
                                    'error': True,
                                    'message': str(e),
                                    'type': 'flow_execution_error'
                                },
                                'headers': {},
                                'status_code': 500
                            }
                        finally:
                            await engine.close()
                            # Release the lock after execution
                            await lock_manager.release_lock(lock_key)
            
            # For async flows or webhooks, process normally
            if triggered_flows:
                logger.info(f"Processing {len(triggered_flows)} async flows for tenant {schema_name}")
                engine = ExecutionEngine(schema_name, tenant_id)
                try:
                    for flow in triggered_flows:
                        if not flow.is_synchronous:  # Skip sync flows in async processing
                            is_simulation = flow.status == FlowStatus.DRAFT
                            logger.info(f"Triggering async flow {flow.flow_id} for tenant {schema_name}")
                            
                            trigger_data = {
                                "event_id": event_id,
                                "event_name": event_name,
                                "app_id": app_id,
                                "webhook_data": webhook_data,
                                "is_simulation": is_simulation
                            }
                            
                            # Use distributed lock to prevent duplicate execution
                            lock_manager = await get_webhook_lock_manager()
                            lock_key = DistributedLockManager.get_execution_lock_key(
                                flow.flow_id,
                                trigger_data
                            )

                            acquired = await lock_manager.acquire_lock(
                                lock_key,
                                ttl=300,
                                retry_count=0
                            )

                            if acquired:
                                try:
                                    await engine.execute_flow(
                                        flow_id=flow.flow_id,
                                        trigger_data=trigger_data,
                                        trigger_type='event'
                                    )
                                finally:
                                    await lock_manager.release_lock(lock_key)
                            else:
                                logger.debug(f"Skipping duplicate webhook execution for flow {flow.flow_id}")
                finally:
                    await engine.close()
            else:
                logger.info(f"No flows found for tenant {schema_name} matching event {event_name}")

            # Check for waiting event waits (Wait for Event nodes)
            try:
                from services.event_wait_service import event_wait_service
                matched_waits = await event_wait_service.complete_wait_by_correlation(
                    app_id=app_id,
                    event_name=event_name,
                    event_data=webhook_data,
                    schema_name=schema_name,
                    tenant_id=tenant_id,
                )
                if matched_waits:
                    logger.info(f"Matched {len(matched_waits)} event wait(s) for app {app_id}, event {event_name} in tenant {schema_name}")
            except Exception as ew_error:
                logger.error(f"Error checking event waits: {ew_error}", exc_info=True)

            return True  # Return success for async processing

    except Exception as e:
        logger.error(f"Failed to process API event for tenant {schema_name}: {str(e)}", exc_info=True)
        raise

async def process_webhook_for_tenant(schema_name: str, tenant_id: str, app_id: str, event_id: str, event_name: str, webhook_data: Dict[str, Any]):
    """Process webhook for a specific tenant."""
    try:
        with get_tenant_db(schema_name) as tenant_db:
            # Find flows triggered by this event (both ACTIVE and DRAFT for testing).
            # Flows live in the shared ioflow.flows table (models are
            # schema-qualified, so the tenant search_path does not isolate
            # them) — the tenant_id filter is what prevents triggering other
            # tenants' flows.
            flows = tenant_db.query(Flow).filter(
                Flow.tenant_id == tenant_id,
                Flow.status.in_([FlowStatus.ACTIVE, FlowStatus.DRAFT])
            ).all()
            
            triggered_flows = []
            logger.info(f"Checking {len(flows)} active/draft flows in tenant {schema_name}")
            
            for flow in flows:
                trigger_config = flow.trigger_config or {}
                logger.info(f"Flow {flow.flow_id} trigger config: {trigger_config}")
                
                # Match by event_id (primary) or event_name (fallback for backward compatibility)
                if trigger_config.get('type') == 'event':
                    config_app_id = trigger_config.get('app_id')
                    config_event_id = trigger_config.get('event_id')
                    config_event_name = trigger_config.get('event_name')
                    
                    logger.info(f"Checking flow {flow.flow_id}: type=event, app_id={config_app_id}, event_id={config_event_id}, event_name={config_event_name}")
                    logger.info(f"Matching against: app_id={app_id}, event_id={event_id}, event_name={event_name}")
                    
                    # More flexible matching - handle case and whitespace differences
                    event_name_matches = False
                    if config_event_name and event_name:
                        # Normalize event names for comparison (lowercase, replace spaces with underscores)
                        normalized_config = config_event_name.lower().replace(' ', '_').replace('-', '_')
                        normalized_webhook = event_name.lower().replace(' ', '_').replace('-', '_')
                        event_name_matches = normalized_config == normalized_webhook
                    
                    if (config_app_id == app_id and 
                        (config_event_id == event_id or event_name_matches or config_event_name == event_name)):
                        logger.info(f"Flow {flow.flow_id} matches webhook criteria")
                        triggered_flows.append(flow)
            
            # Execute each triggered flow
            if triggered_flows:
                logger.info(f"Found {len(triggered_flows)} flows to trigger for tenant {schema_name}")
                engine = ExecutionEngine(schema_name, tenant_id)
                try:
                    for flow in triggered_flows:
                        is_simulation = flow.status == FlowStatus.DRAFT
                        logger.info(f"Triggering flow {flow.flow_id} for tenant {schema_name} with event {event_name} (simulation={is_simulation})")
                        
                        trigger_data = {
                            "event_id": event_id,
                            "event_name": event_name,
                            "app_id": app_id,
                            "webhook_data": webhook_data,
                            "is_simulation": is_simulation  # Mark as simulation for draft flows
                        }
                        
                        # Use distributed lock to prevent duplicate execution
                        lock_manager = await get_webhook_lock_manager()
                        lock_key = DistributedLockManager.get_execution_lock_key(
                            flow.flow_id,
                            trigger_data
                        )

                        acquired = await lock_manager.acquire_lock(
                            lock_key,
                            ttl=300,
                            retry_count=0
                        )

                        if acquired:
                            try:
                                await engine.execute_flow(
                                    flow_id=flow.flow_id,
                                    trigger_data=trigger_data,
                                    trigger_type='event'  # Use 'event' as trigger type
                                )
                            finally:
                                await lock_manager.release_lock(lock_key)
                        else:
                            logger.debug(f"Skipping duplicate webhook execution for flow {flow.flow_id}")
                finally:
                    await engine.close()
            else:
                logger.info(f"No flows found for tenant {schema_name} matching event {event_name} (app_id: {app_id}, event_id: {event_id})")

            # Check for waiting event waits (Wait for Event nodes)
            try:
                from services.event_wait_service import event_wait_service
                matched_waits = await event_wait_service.complete_wait_by_correlation(
                    app_id=app_id,
                    event_name=event_name,
                    event_data=webhook_data,
                    schema_name=schema_name,
                    tenant_id=tenant_id,
                )
                if matched_waits:
                    logger.info(f"Matched {len(matched_waits)} event wait(s) for app {app_id}, event {event_name} in tenant {schema_name}")
            except Exception as ew_error:
                logger.error(f"Error checking event waits: {ew_error}", exc_info=True)

            return True  # Return success

    except Exception as e:
        logger.error(f"Failed to process webhook for tenant {schema_name}: {str(e)}", exc_info=True)
        return False  # Return failure

# Webhook verification endpoints for specific providers
@router.get("/{app_id}/{event_name}")
async def verify_webhook_get(
    app_id: str,
    event_name: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle GET webhook verification requests (e.g., for Facebook)."""
    try:
        # Verify application exists
        app = db.query(Application).filter(Application.app_id == app_id).first()
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Get application configuration
        app_config = {
            'webhook_config': app.webhook_config or {}
        }
        
        # For webhook verification, we need to get any subscription's credentials
        sample_subscription = db.query(ApplicationSubscription).filter(
            ApplicationSubscription.app_id == app_id,
            ApplicationSubscription.status == 'active'
        ).first()
        
        credentials = {}
        if sample_subscription and sample_subscription.auth_credentials:
            try:
                credentials = decrypt_credentials(sample_subscription.auth_credentials)
            except Exception as e:
                logger.warning(f"Failed to decrypt credentials: {e}")
        
        # Verify webhook (handles GET challenges like Facebook)
        is_valid, response_data = await webhook_verification_service.verify_webhook(
            request, app_config, credentials
        )
        
        if response_data:
            # Check if plain text response is requested (required by META/Facebook)
            if isinstance(response_data, dict) and "__plain_text__" in response_data:
                return PlainTextResponse(content=str(response_data["__plain_text__"]))
            return response_data

        if not is_valid:
            raise HTTPException(status_code=401, detail="Webhook verification failed")

        return {"status": "verified"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook verification failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
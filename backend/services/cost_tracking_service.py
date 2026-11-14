"""
Enhanced Cost Tracking Service for Flow Executions
This service tracks costs for all service calls and creates cost logs
"""
import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
import json
import uuid

from sqlalchemy.orm import Session
from db.database import get_db
from db.pricing_models import (
    ApplicationPricing, ExecutionCostLog,
    ServicePricing, BillingMode
)
from services.cost_calculator import cost_calculator

logger = logging.getLogger(__name__)


class CostTrackingService:
    """Service to track execution costs"""

    def __init__(self):
        self.execution_costs = {}  # Store costs per execution

    def start_execution(self, execution_id: str, tenant_id: str, flow_id: str, flow_name: str, trigger_type: str):
        """Initialize cost tracking for a new execution"""
        self.execution_costs[execution_id] = {
            'tenant_id': tenant_id,
            'flow_id': flow_id,
            'flow_name': flow_name,
            'trigger_type': trigger_type,
            'services': [],
            'total_incoming_events': 0,
            'total_outgoing_services': 0,
            'total_data_transfer_kb': 0,
            'total_token_count': 0,
            'start_time': datetime.utcnow()
        }
        logger.info(f"Started cost tracking for execution {execution_id}")

    def track_incoming_event(self, execution_id: str, app_id: str, data: Dict[str, Any]):
        """Track an incoming event"""
        if execution_id not in self.execution_costs:
            logger.warning(f"Execution {execution_id} not tracked")
            return

        self.execution_costs[execution_id]['total_incoming_events'] += 1

        # Estimate data size
        if data:
            kb = cost_calculator.estimate_data_transfer_kb(data)
            self.execution_costs[execution_id]['total_data_transfer_kb'] += kb

    def track_service_call(self, execution_id: str, app_id: str, service_id: str,
                          service_name: str, request_data: Dict[str, Any],
                          response_data: Dict[str, Any]):
        """Track a service call for cost calculation"""
        if execution_id not in self.execution_costs:
            logger.warning(f"Execution {execution_id} not tracked")
            return

        # Track the service call
        service_info = {
            'app_id': app_id,
            'service_id': service_id,
            'service_name': service_name,
            'timestamp': datetime.utcnow().isoformat()
        }

        self.execution_costs[execution_id]['services'].append(service_info)
        self.execution_costs[execution_id]['total_outgoing_services'] += 1

        # Track data transfer
        if request_data:
            kb = cost_calculator.estimate_data_transfer_kb(request_data)
            self.execution_costs[execution_id]['total_data_transfer_kb'] += kb
        if response_data:
            kb = cost_calculator.estimate_data_transfer_kb(response_data)
            self.execution_costs[execution_id]['total_data_transfer_kb'] += kb

        logger.info(f"Tracked service call for {app_id}/{service_name} in execution {execution_id}")

    def finalize_execution(self, execution_id: str) -> Optional[ExecutionCostLog]:
        """Finalize cost tracking and create cost log"""
        if execution_id not in self.execution_costs:
            logger.warning(f"No cost data for execution {execution_id}")
            return None

        cost_data = self.execution_costs[execution_id]

        # Skip if no services were called
        if not cost_data['services']:
            logger.info(f"No services tracked for execution {execution_id}")
            del self.execution_costs[execution_id]
            return None

        # Get unique app IDs from services
        app_ids = list(set(s['app_id'] for s in cost_data['services']))

        # Create cost logs for each app
        cost_logs = []
        for app_id in app_ids:
            # Count services for this app
            app_services = [s for s in cost_data['services'] if s['app_id'] == app_id]
            outgoing_count = len(app_services)

            if outgoing_count == 0:
                continue

            # Create cost log
            try:
                with next(get_db()) as db:
                    # Check if app has pricing configured
                    pricing = db.query(ApplicationPricing).filter(
                        ApplicationPricing.app_id == app_id,
                        ApplicationPricing.is_active == True
                    ).first()

                    if not pricing:
                        logger.info(f"No active pricing for app {app_id}")
                        continue

                    # Skip if free
                    if pricing.is_free or pricing.billing_mode == BillingMode.FREE.value:
                        logger.info(f"App {app_id} is free, skipping cost log")
                        continue

                    # Calculate costs
                    total_cost, cost_breakdown = cost_calculator.calculate_execution_cost(
                        app_id=app_id,
                        tenant_id=cost_data['tenant_id'],
                        incoming_events=cost_data['total_incoming_events'] if app_services == cost_data['services'] else 0,
                        outgoing_services=outgoing_count,
                        data_transfer_kb=cost_data['total_data_transfer_kb'],
                        token_count=cost_data['total_token_count'],
                        db=db
                    )

                    # Create cost log
                    cost_log = ExecutionCostLog(
                        cost_log_id=str(uuid.uuid4()),
                        execution_id=execution_id,
                        app_id=app_id,
                        tenant_id=cost_data['tenant_id'],
                        flow_id=cost_data['flow_id'],
                        flow_name=cost_data['flow_name'],
                        trigger_type=cost_data['trigger_type'],
                        incoming_event_count=cost_data['total_incoming_events'] if app_services == cost_data['services'] else 0,
                        outgoing_service_count=outgoing_count,
                        incoming_event_cost=cost_breakdown.get('incoming_events', Decimal(0)),
                        outgoing_service_cost=cost_breakdown.get('outgoing_services', Decimal(0)),
                        data_transfer_kb=cost_data['total_data_transfer_kb'],
                        data_transfer_cost=cost_breakdown.get('data_transfer', Decimal(0)),
                        token_count=cost_data['total_token_count'],
                        token_cost=cost_breakdown.get('tokens', Decimal(0)),
                        total_cost=total_cost,
                        currency=pricing.currency if pricing else 'USD',
                        billing_mode=pricing.billing_mode if pricing else 'PREPAID',
                        was_free=False,
                        service_breakdown=json.dumps({
                            s['service_id']: {
                                'service_name': s['service_name'],
                                'cost': 0  # Per-service cost can be calculated if needed
                            }
                            for s in app_services
                        })
                    )

                    db.add(cost_log)
                    db.commit()
                    cost_logs.append(cost_log)

                    logger.info(f"Created cost log for app {app_id} in execution {execution_id}: {total_cost} {cost_log.currency}")

            except Exception as e:
                logger.error(f"Error creating cost log for app {app_id}: {str(e)}")

        # Clean up execution data
        del self.execution_costs[execution_id]

        return cost_logs[0] if cost_logs else None

    def cleanup_stale_executions(self, max_age_hours: int = 24):
        """Clean up old execution data"""
        now = datetime.utcnow()
        stale_executions = []

        for exec_id, data in self.execution_costs.items():
            age = (now - data['start_time']).total_seconds() / 3600
            if age > max_age_hours:
                stale_executions.append(exec_id)

        for exec_id in stale_executions:
            logger.info(f"Cleaning up stale execution {exec_id}")
            del self.execution_costs[exec_id]


# Global instance
cost_tracking_service = CostTrackingService()
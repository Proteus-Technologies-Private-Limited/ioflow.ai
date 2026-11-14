"""
Cost Calculator Service for tracking and calculating execution costs
"""
import logging
from typing import Dict, Optional, Tuple
from decimal import Decimal
from datetime import datetime
import json

from sqlalchemy.orm import Session
from db.database import get_db
from db.pricing_models import (
    ApplicationPricing, ExecutionCostLog, TenantApplicationSubscription,
    ServicePricing, PricingModel, UsageMetricType, BillingMode
)
from db.application_models import Application
from db.application_models import ApplicationService

logger = logging.getLogger(__name__)


class CostCalculator:
    """Service for calculating execution costs based on pricing models"""
    
    def __init__(self):
        self.token_counters = {}  # Cache for token counting functions
    
    def calculate_execution_cost(
        self,
        app_id: str,
        tenant_id: str,
        incoming_events: int,
        outgoing_services: int,
        data_transfer_kb: int = 0,
        token_count: int = 0,
        service_id: Optional[str] = None,
        db: Session = None
    ) -> Tuple[Decimal, Dict[str, Decimal]]:
        """
        Calculate the total cost for a flow execution
        Returns: (total_cost, cost_breakdown)
        """
        owns_db = False
        if not db:
            db = next(get_db())
            owns_db = True

        try:
            # Get active pricing for the application
            pricing = db.query(ApplicationPricing).filter(
                ApplicationPricing.app_id == app_id,
                ApplicationPricing.is_active == True
            ).first()

            if not pricing:
                logger.warning(f"No active pricing found for app {app_id}")
                return Decimal(0), {}

            # Check if application is free
            if pricing.is_free or pricing.billing_mode == BillingMode.FREE.value:
                return Decimal(0), {"free_execution": Decimal(0)}

            # Check for service-specific pricing
            if service_id and pricing.service_pricing_enabled:
                service_cost = self.get_service_cost(
                    service_id=service_id,
                    data_transfer_kb=data_transfer_kb,
                    token_count=token_count,
                    db=db
                )

                if service_cost is not None:
                    return service_cost

            # Check if tenant has subscription
            subscription = db.query(TenantApplicationSubscription).filter(
                TenantApplicationSubscription.app_id == app_id,
                TenantApplicationSubscription.tenant_id == tenant_id,
                TenantApplicationSubscription.status == 'active'
            ).first()

            # If subscription exists and pricing model is subscription-only, no usage cost
            if subscription and pricing.pricing_model == PricingModel.SUBSCRIPTION.value:
                return Decimal(0), {"subscription_covered": Decimal(0)}

            # Calculate costs
            cost_breakdown = {}

            # Incoming event cost
            incoming_cost = Decimal(str(incoming_events)) * pricing.incoming_event_cost
            cost_breakdown['incoming_events'] = incoming_cost

            # Outgoing service cost
            outgoing_cost = Decimal(str(outgoing_services)) * pricing.outgoing_service_cost
            cost_breakdown['outgoing_services'] = outgoing_cost

            # Data transfer cost
            data_cost = Decimal(0)
            if pricing.cost_per_kb and data_transfer_kb > 0:
                data_cost = Decimal(str(data_transfer_kb)) * pricing.cost_per_kb
                cost_breakdown['data_transfer'] = data_cost

            # Token cost (for LLM usage)
            token_cost = Decimal(0)
            if pricing.cost_per_token and token_count > 0:
                token_cost = Decimal(str(token_count)) * pricing.cost_per_token
                cost_breakdown['tokens'] = token_cost

            total_cost = incoming_cost + outgoing_cost + data_cost + token_cost

            return total_cost, cost_breakdown

        except Exception as e:
            logger.error(f"Error calculating execution cost: {str(e)}")
            return Decimal(0), {}
        finally:
            if owns_db:
                db.close()

    def create_cost_log(
        self,
        execution_id: str,
        app_id: str,
        tenant_id: str,
        flow_id: str,
        flow_name: str,
        trigger_type: str,
        incoming_events: int,
        outgoing_services: int,
        data_transfer_kb: int = 0,
        token_count: int = 0,
        db: Session = None
    ) -> Optional[ExecutionCostLog]:
        """
        Create a cost log entry for an execution
        """
        owns_db = False
        if not db:
            db = next(get_db())
            owns_db = True
        
        try:
            # Calculate costs
            total_cost, cost_breakdown = self.calculate_execution_cost(
                app_id=app_id,
                tenant_id=tenant_id,
                incoming_events=incoming_events,
                outgoing_services=outgoing_services,
                data_transfer_kb=data_transfer_kb,
                token_count=token_count,
                db=db
            )
            
            # Get pricing to determine currency
            pricing = db.query(ApplicationPricing).filter(
                ApplicationPricing.app_id == app_id,
                ApplicationPricing.is_active == True
            ).first()
            
            currency = pricing.currency if pricing else 'USD'
            
            # Create cost log
            cost_log = ExecutionCostLog(
                execution_id=execution_id,
                app_id=app_id,
                tenant_id=tenant_id,
                flow_id=flow_id,
                flow_name=flow_name,
                trigger_type=trigger_type,
                incoming_event_count=incoming_events,
                outgoing_service_count=outgoing_services,
                incoming_event_cost=cost_breakdown.get('incoming_events', Decimal(0)),
                outgoing_service_cost=cost_breakdown.get('outgoing_services', Decimal(0)),
                data_transfer_kb=data_transfer_kb,
                data_transfer_cost=cost_breakdown.get('data_transfer', Decimal(0)),
                token_count=token_count,
                token_cost=cost_breakdown.get('tokens', Decimal(0)),
                total_cost=total_cost,
                currency=currency
            )
            
            db.add(cost_log)
            db.commit()
            
            # Update subscription usage if exists
            if total_cost > 0:
                subscription = db.query(TenantApplicationSubscription).filter(
                    TenantApplicationSubscription.app_id == app_id,
                    TenantApplicationSubscription.tenant_id == tenant_id,
                    TenantApplicationSubscription.status == 'active'
                ).first()
                
                if subscription:
                    subscription.total_usage_cost += total_cost
                    db.commit()
            
            logger.info(f"Created cost log for execution {execution_id}: {total_cost} {currency}")
            return cost_log
            
        except Exception as e:
            logger.error(f"Error creating cost log: {str(e)}")
            db.rollback()
            return None
        finally:
            if owns_db:
                db.close()

    def estimate_data_transfer_kb(self, data: Dict) -> int:
        """
        Estimate data transfer size in KB from request/response data
        """
        try:
            # Convert to JSON string to estimate size
            json_str = json.dumps(data)
            size_bytes = len(json_str.encode('utf-8'))
            size_kb = (size_bytes + 1023) // 1024  # Round up to nearest KB
            return size_kb
        except:
            return 0
    
    def count_llm_tokens(self, text: str, model: str = "gpt-3.5") -> int:
        """
        Estimate token count for LLM usage
        This is a simplified estimation - in production, use tiktoken or model-specific tokenizer
        """
        # Simple estimation: ~4 characters per token for English text
        # This should be replaced with proper tokenization for production
        return len(text) // 4
    
    def get_tenant_usage_summary(
        self,
        tenant_id: str,
        app_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        db: Session = None
    ) -> Dict:
        """
        Get usage summary for a tenant
        """
        owns_db = False
        if not db:
            db = next(get_db())
            owns_db = True
        
        try:
            query = db.query(ExecutionCostLog).filter(
                ExecutionCostLog.tenant_id == tenant_id
            )
            
            if app_id:
                query = query.filter(ExecutionCostLog.app_id == app_id)
            
            if start_date:
                query = query.filter(ExecutionCostLog.timestamp >= start_date)
            
            if end_date:
                query = query.filter(ExecutionCostLog.timestamp <= end_date)
            
            logs = query.all()
            
            # Aggregate costs
            summary = {
                'total_executions': len(logs),
                'total_cost': sum(log.total_cost for log in logs),
                'incoming_events': sum(log.incoming_event_count for log in logs),
                'outgoing_services': sum(log.outgoing_service_count for log in logs),
                'data_transfer_kb': sum(log.data_transfer_kb for log in logs),
                'tokens_used': sum(log.token_count for log in logs),
                'cost_breakdown': {
                    'incoming_events': sum(log.incoming_event_cost for log in logs),
                    'outgoing_services': sum(log.outgoing_service_cost for log in logs),
                    'data_transfer': sum(log.data_transfer_cost for log in logs),
                    'tokens': sum(log.token_cost for log in logs)
                }
            }
            
            # Get currency from first log or default
            summary['currency'] = logs[0].currency if logs else 'USD'
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting usage summary: {str(e)}")
            return {}
        finally:
            if owns_db:
                db.close()

    def get_service_cost(
        self,
        service_id: str,
        data_transfer_kb: int = 0,
        token_count: int = 0,
        db: Session = None
    ) -> Optional[Tuple[Decimal, Dict[str, Decimal]]]:
        """
        Get cost for a specific service
        Returns: (total_cost, cost_breakdown) or None if no service pricing
        """
        owns_db = False
        if not db:
            db = next(get_db())
            owns_db = True

        try:
            # Get service-specific pricing
            service_pricing = db.query(ServicePricing).filter(
                ServicePricing.service_id == service_id,
                ServicePricing.is_active == True
            ).first()

            if not service_pricing:
                return None

            # If service is free
            if service_pricing.is_free:
                return Decimal(0), {"free_service": Decimal(0)}

            # Calculate service-specific costs
            cost_breakdown = {}

            # Request cost
            request_cost = service_pricing.cost_per_request
            cost_breakdown['request'] = request_cost

            # Data transfer cost
            data_cost = Decimal(0)
            if service_pricing.cost_per_kb and data_transfer_kb > 0:
                data_cost = Decimal(str(data_transfer_kb)) * service_pricing.cost_per_kb
                cost_breakdown['data_transfer'] = data_cost

            # Token cost
            token_cost = Decimal(0)
            if service_pricing.cost_per_token and token_count > 0:
                token_cost = Decimal(str(token_count)) * service_pricing.cost_per_token
                cost_breakdown['tokens'] = token_cost

            total_cost = request_cost + data_cost + token_cost

            return total_cost, cost_breakdown

        except Exception as e:
            logger.error(f"Error getting service cost: {str(e)}")
            return None
        finally:
            if owns_db:
                db.close()

    def estimate_service_cost(
        self,
        app_id: str,
        service_id: Optional[str] = None,
        estimated_data_kb: int = 0,
        estimated_tokens: int = 0,
        db: Session = None
    ) -> float:
        """
        Estimate the cost for a service execution
        Returns: Estimated cost as float
        """
        owns_db = False
        if not db:
            db = next(get_db())
            owns_db = True

        try:
            # Get application pricing
            app_pricing = db.query(ApplicationPricing).filter(
                ApplicationPricing.app_id == app_id,
                ApplicationPricing.is_active == True
            ).first()

            if not app_pricing:
                return 0.0

            # If free, return 0
            if app_pricing.is_free or app_pricing.billing_mode == BillingMode.FREE.value:
                return 0.0

            # Check for service-specific pricing
            if service_id and app_pricing.service_pricing_enabled:
                service_cost = self.get_service_cost(
                    service_id=service_id,
                    data_transfer_kb=estimated_data_kb,
                    token_count=estimated_tokens,
                    db=db
                )

                if service_cost is not None:
                    return float(service_cost[0])

            # Use application-level pricing
            total_cost = app_pricing.incoming_event_cost + app_pricing.outgoing_service_cost

            if app_pricing.cost_per_kb and estimated_data_kb:
                total_cost += app_pricing.cost_per_kb * Decimal(estimated_data_kb)

            if app_pricing.cost_per_token and estimated_tokens:
                total_cost += app_pricing.cost_per_token * Decimal(estimated_tokens)

            return float(total_cost)

        except Exception as e:
            logger.error(f"Error estimating service cost: {str(e)}")
            return 0.0
        finally:
            if owns_db:
                db.close()

    def should_track_cost(self, app_id: str, db: Session = None) -> bool:
        """
        Check if cost tracking is enabled for an application
        """
        owns_db = False
        if not db:
            db = next(get_db())
            owns_db = True

        try:
            pricing = db.query(ApplicationPricing).filter(
                ApplicationPricing.app_id == app_id,
                ApplicationPricing.is_active == True
            ).first()

            return pricing is not None

        except Exception as e:
            logger.error(f"Error checking cost tracking: {str(e)}")
            return False
        finally:
            if owns_db:
                db.close()


# Singleton instance
cost_calculator = CostCalculator()
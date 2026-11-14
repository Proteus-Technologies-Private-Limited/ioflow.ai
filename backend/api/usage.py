"""
Usage API endpoints for tracking and reporting application usage
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from pydantic import BaseModel
import csv
import json
import io

from db.database import get_db
from db.models import User, Tenant
from db.pricing_models import (
    ExecutionCostLog, ApplicationPricing, ServicePricing,
    TenantApplicationSubscription, BillingMode
)
from db.application_models import Application, ApplicationService
from api.auth import get_current_user
from services.cost_calculator import cost_calculator

logger = logging.getLogger(__name__)

router = APIRouter()


class UsageSummaryResponse(BaseModel):
    """Usage summary response"""
    tenant_id: str
    period_start: datetime
    period_end: datetime
    total_executions: int
    total_cost: float
    total_free_executions: int
    total_data_kb: float
    avg_response_time: Optional[float]
    free_executions: int
    paid_executions: int
    currency: str
    by_application: List[Dict[str, Any]]
    by_service_type: List[Dict[str, Any]]
    daily_usage: List[Dict[str, Any]]
    cost_breakdown: Dict[str, float]


class ApplicationUsageResponse(BaseModel):
    """Application-specific usage response"""
    app_id: str
    app_name: str
    is_free: bool
    billing_mode: str
    total_executions: int
    total_cost: float
    currency: str
    services: List[Dict[str, Any]]
    daily_usage: List[Dict[str, Any]]


class ExportFormat(BaseModel):
    format: str = "csv"  # csv or json


@router.get("/usage/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    start_date: Optional[datetime] = Query(None, description="Start date for usage period"),
    end_date: Optional[datetime] = Query(None, description="End date for usage period"),
    app_id: Optional[str] = Query(None, description="Filter by application ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get overall usage summary for the tenant"""
    try:
        # Store original dates for response
        original_end_date = end_date
        original_start_date = start_date

        # Default to last 30 days if no dates provided
        if not end_date:
            end_date = datetime.utcnow()
        else:
            # If end_date is provided as a date (e.g., 2025-10-30),
            # it becomes 2025-10-30 00:00:00, which excludes today's data.
            # Adjust it to include the full day (end of day 23:59:59)
            if end_date.hour == 0 and end_date.minute == 0 and end_date.second == 0:
                end_date = end_date + timedelta(days=1) - timedelta(seconds=1)

        if not start_date:
            start_date = original_end_date - timedelta(days=30) if original_end_date else end_date - timedelta(days=30)

        # Get all execution logs for the tenant
        logs_query = db.query(ExecutionCostLog).filter(
            ExecutionCostLog.tenant_id == current_user.tenant_id,
            ExecutionCostLog.timestamp >= start_date,
            ExecutionCostLog.timestamp <= end_date
        )

        # Filter by application if app_id is provided
        if app_id:
            logs_query = logs_query.filter(ExecutionCostLog.app_id == app_id)

        logs = logs_query.all()

        # Group by application
        app_usage = {}
        for log in logs:
            app_id = str(log.app_id)
            if app_id not in app_usage:
                # Get application details
                app = db.query(Application).filter(
                    Application.app_id == log.app_id
                ).first()

                # Get pricing details
                pricing = db.query(ApplicationPricing).filter(
                    ApplicationPricing.app_id == log.app_id,
                    ApplicationPricing.is_active == True
                ).first()

                app_usage[app_id] = {
                    'app_id': app_id,
                    'app_name': app.app_name if app else 'Unknown',
                    'is_free': log.was_free or (pricing and pricing.is_free) if pricing else False,
                    'billing_mode': log.billing_mode or (pricing.billing_mode if pricing else 'UNKNOWN'),
                    'total_executions': 0,
                    'total_cost': 0.0,
                    'free_executions': 0,
                    'total_incoming_events': 0,
                    'total_outgoing_services': 0,
                    'total_data_kb': 0,
                    'total_tokens': 0
                }

            app_usage[app_id]['total_executions'] += 1
            app_usage[app_id]['total_cost'] += float(log.total_cost)
            if log.was_free:
                app_usage[app_id]['free_executions'] += 1
            app_usage[app_id]['total_incoming_events'] += log.incoming_event_count
            app_usage[app_id]['total_outgoing_services'] += log.outgoing_service_count
            app_usage[app_id]['total_data_kb'] += log.data_transfer_kb
            app_usage[app_id]['total_tokens'] += log.token_count

        # Calculate totals
        total_executions = sum(app['total_executions'] for app in app_usage.values())
        total_cost = sum(app['total_cost'] for app in app_usage.values())
        total_free = sum(app['free_executions'] for app in app_usage.values())
        total_data_kb = sum(float(log.data_transfer_kb) for log in logs)
        paid_executions = total_executions - total_free
        avg_response_time = None  # Not tracked in current schema

        # Cost breakdown
        cost_breakdown = {
            'incoming_events': sum(float(log.incoming_event_cost) for log in logs),
            'outgoing_services': sum(float(log.outgoing_service_cost) for log in logs),
            'data_transfer': sum(float(log.data_transfer_cost) for log in logs),
            'tokens': sum(float(log.token_cost) for log in logs),
            'service_cost': sum(float(log.incoming_event_cost) for log in logs) + sum(float(log.outgoing_service_cost) for log in logs),
            'data_cost': sum(float(log.data_transfer_cost) for log in logs),
            'token_cost': sum(float(log.token_cost) for log in logs)
        }

        # Group by day for daily usage
        daily_usage_data = {}
        for log in logs:
            day_key = log.timestamp.date().isoformat()
            if day_key not in daily_usage_data:
                daily_usage_data[day_key] = {
                    'date': day_key,
                    'executions': 0,
                    'cost': 0.0,
                    'data_transfer_kb': 0,
                    'tokens_used': 0
                }

            daily_usage_data[day_key]['executions'] += 1
            daily_usage_data[day_key]['cost'] += float(log.total_cost)
            daily_usage_data[day_key]['data_transfer_kb'] += log.data_transfer_kb
            daily_usage_data[day_key]['tokens_used'] += log.token_count

        # Group by service type
        service_type_usage = {}
        for log in logs:
            # Extract service type from service breakdown if available
            if log.service_breakdown:
                # Deserialize JSON if it's stored as a string (SQLite)
                breakdown = log.service_breakdown
                if isinstance(breakdown, str):
                    breakdown = json.loads(breakdown)

                # Handle both dict (new format) and list (old format)
                if isinstance(breakdown, dict):
                    for service_id, service_data in breakdown.items():
                        # Get service details to determine type
                        service = db.query(ApplicationService).filter(
                            ApplicationService.service_id == service_id
                        ).first()

                        if service:
                            service_type = service.service_type or 'Unknown'
                            if service_type not in service_type_usage:
                                service_type_usage[service_type] = {
                                    'service_type': service_type,
                                    'executions': 0,
                                    'cost': 0.0
                                }

                            service_type_usage[service_type]['executions'] += 1
                            service_type_usage[service_type]['cost'] += float(service_data.get('cost', 0) if isinstance(service_data, dict) else 0)
                elif isinstance(breakdown, list):
                    # Handle old list format for backward compatibility
                    for service_info in breakdown:
                        service_id = service_info.get('service_id')
                        if service_id:
                            service = db.query(ApplicationService).filter(
                                ApplicationService.service_id == service_id
                            ).first()

                            if service:
                                service_type = service.service_type or 'Unknown'
                                if service_type not in service_type_usage:
                                    service_type_usage[service_type] = {
                                        'service_type': service_type,
                                        'executions': 0,
                                        'cost': 0.0
                                    }

                                service_type_usage[service_type]['executions'] += 1
                                # Old format doesn't have cost breakdown
                                service_type_usage[service_type]['cost'] += 0

        return UsageSummaryResponse(
            tenant_id=str(current_user.tenant_id),
            period_start=start_date,
            period_end=end_date,
            total_executions=total_executions,
            total_cost=total_cost,
            total_free_executions=total_free,
            total_data_kb=total_data_kb,
            avg_response_time=avg_response_time,
            free_executions=total_free,
            paid_executions=paid_executions,
            currency='USD',  # Get from first log or default
            by_application=list(app_usage.values()),
            by_service_type=list(service_type_usage.values()),
            daily_usage=sorted(daily_usage_data.values(), key=lambda x: x['date']),
            cost_breakdown=cost_breakdown
        )

    except Exception as e:
        logger.error(f"Error getting usage summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get usage summary: {str(e)}"
        )


@router.get("/usage/applications/{app_id}", response_model=ApplicationUsageResponse)
async def get_application_usage(
    app_id: str,
    start_date: Optional[datetime] = Query(None, description="Start date for usage period"),
    end_date: Optional[datetime] = Query(None, description="End date for usage period"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage details for a specific application"""
    try:
        # Verify application exists and user has access
        app = db.query(Application).filter(
            Application.app_id == app_id
        ).first()

        if not app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )

        # Default to last 30 days if no dates provided
        if not end_date:
            end_date = datetime.utcnow()
        else:
            # Adjust end_date to include the full day if it's at midnight
            if end_date.hour == 0 and end_date.minute == 0 and end_date.second == 0:
                end_date = end_date + timedelta(days=1) - timedelta(seconds=1)

        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Get pricing info
        pricing = db.query(ApplicationPricing).filter(
            ApplicationPricing.app_id == app_id,
            ApplicationPricing.is_active == True
        ).first()

        is_free = pricing.is_free if pricing else False
        billing_mode = pricing.billing_mode if pricing else 'UNKNOWN'

        # Get execution logs
        logs = db.query(ExecutionCostLog).filter(
            ExecutionCostLog.tenant_id == current_user.tenant_id,
            ExecutionCostLog.app_id == app_id,
            ExecutionCostLog.timestamp >= start_date,
            ExecutionCostLog.timestamp <= end_date
        ).order_by(desc(ExecutionCostLog.timestamp)).all()

        # Group by service if service breakdown available
        service_usage = {}
        daily_usage = {}

        for log in logs:
            # Process service breakdown if available
            if log.service_breakdown:
                # Deserialize JSON if it's stored as a string (SQLite)
                breakdown = log.service_breakdown
                if isinstance(breakdown, str):
                    breakdown = json.loads(breakdown)

                # Handle both dict (new format) and list (old format)
                if isinstance(breakdown, dict):
                    for service_id, service_data in breakdown.items():
                        if service_id not in service_usage:
                            # Get service details
                            service = db.query(ApplicationService).filter(
                                ApplicationService.service_id == service_id
                            ).first()

                            service_usage[service_id] = {
                                'service_id': service_id,
                                'service_name': service.service_name if service else 'Unknown',
                                'executions': 0,
                                'cost': 0.0
                            }

                        service_usage[service_id]['executions'] += 1
                        service_usage[service_id]['cost'] += float(service_data.get('cost', 0) if isinstance(service_data, dict) else 0)
                elif isinstance(breakdown, list):
                    # Handle old list format for backward compatibility
                    for service_info in breakdown:
                        service_id = service_info.get('service_id')
                        if service_id:
                            if service_id not in service_usage:
                                service_usage[service_id] = {
                                    'service_id': service_id,
                                    'service_name': service_info.get('service_name', 'Unknown'),
                                    'executions': 0,
                                    'cost': 0.0
                                }

                            service_usage[service_id]['executions'] += 1
                            # Old format doesn't have cost breakdown

            # Group by day
            day_key = log.timestamp.date().isoformat()
            if day_key not in daily_usage:
                daily_usage[day_key] = {
                    'date': day_key,
                    'executions': 0,
                    'cost': 0.0,
                    'data_transfer_kb': 0,
                    'tokens_used': 0
                }

            daily_usage[day_key]['executions'] += 1
            daily_usage[day_key]['cost'] += float(log.total_cost)
            daily_usage[day_key]['data_transfer_kb'] += log.data_transfer_kb
            daily_usage[day_key]['tokens_used'] += log.token_count

        # Calculate totals
        total_executions = len(logs)
        total_cost = sum(float(log.total_cost) for log in logs)

        return ApplicationUsageResponse(
            app_id=app_id,
            app_name=app.app_name,
            is_free=is_free,
            billing_mode=billing_mode,
            total_executions=total_executions,
            total_cost=total_cost,
            currency='USD',
            services=list(service_usage.values()),
            daily_usage=sorted(daily_usage.values(), key=lambda x: x['date'])
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting application usage: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get application usage: {str(e)}"
        )


@router.get("/usage/services/{service_id}")
async def get_service_usage(
    service_id: str,
    start_date: Optional[datetime] = Query(None, description="Start date for usage period"),
    end_date: Optional[datetime] = Query(None, description="End date for usage period"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage details for a specific service"""
    try:
        # Verify service exists
        service = db.query(ApplicationService).filter(
            ApplicationService.service_id == service_id
        ).first()

        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found"
            )

        # Get service pricing if exists
        service_pricing = db.query(ServicePricing).filter(
            ServicePricing.service_id == service_id,
            ServicePricing.is_active == True
        ).first()

        # Default to last 30 days
        if not end_date:
            end_date = datetime.utcnow()
        else:
            # Adjust end_date to include the full day if it's at midnight
            if end_date.hour == 0 and end_date.minute == 0 and end_date.second == 0:
                end_date = end_date + timedelta(days=1) - timedelta(seconds=1)

        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Get logs that include this service
        # This is complex because service usage is in service_breakdown JSON
        logs = db.query(ExecutionCostLog).filter(
            ExecutionCostLog.tenant_id == current_user.tenant_id,
            ExecutionCostLog.timestamp >= start_date,
            ExecutionCostLog.timestamp <= end_date
        ).all()

        # Filter logs that used this service
        service_logs = []
        total_cost = 0.0
        for log in logs:
            if log.service_breakdown:
                # Deserialize JSON if it's stored as a string (SQLite)
                breakdown = log.service_breakdown
                if isinstance(breakdown, str):
                    breakdown = json.loads(breakdown)

                # Check if this service was used in this log
                service_found = False
                service_cost = 0.0

                # Handle both dict (new format) and list (old format)
                if isinstance(breakdown, dict):
                    if service_id in breakdown:
                        service_found = True
                        service_data = breakdown[service_id]
                        service_cost = float(service_data.get('cost', 0) if isinstance(service_data, dict) else 0)
                elif isinstance(breakdown, list):
                    # Old list format - check if service_id exists in the list
                    for service_info in breakdown:
                        if service_info.get('service_id') == service_id:
                            service_found = True
                            # Old format doesn't have cost breakdown
                            service_cost = 0.0
                            break

                if service_found:
                    service_logs.append({
                        'execution_id': log.execution_id,
                        'timestamp': log.timestamp,
                        'cost': service_cost,
                        'flow_name': log.flow_name
                    })
                    total_cost += service_cost

        return {
            'service_id': service_id,
            'service_name': service.service_name,
            'app_id': str(service.app_id),
            'has_custom_pricing': service_pricing is not None,
            'is_free': service_pricing.is_free if service_pricing else False,
            'total_executions': len(service_logs),
            'total_cost': total_cost,
            'currency': service_pricing.currency if service_pricing else 'USD',
            'executions': service_logs[:100]  # Limit to recent 100
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting service usage: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service usage: {str(e)}"
        )


@router.post("/usage/export")
async def export_usage_data(
    export_format: ExportFormat,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    app_id: Optional[str] = Query(None, description="Filter by application"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export usage data in CSV or JSON format"""
    try:
        # Default to last 30 days
        if not end_date:
            end_date = datetime.utcnow()
        else:
            # Adjust end_date to include the full day if it's at midnight
            if end_date.hour == 0 and end_date.minute == 0 and end_date.second == 0:
                end_date = end_date + timedelta(days=1) - timedelta(seconds=1)

        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Build query
        query = db.query(ExecutionCostLog).filter(
            ExecutionCostLog.tenant_id == current_user.tenant_id,
            ExecutionCostLog.timestamp >= start_date,
            ExecutionCostLog.timestamp <= end_date
        )

        if app_id:
            query = query.filter(ExecutionCostLog.app_id == app_id)

        logs = query.order_by(desc(ExecutionCostLog.timestamp)).all()

        # Get application names for enrichment
        app_names = {}
        for log in logs:
            if str(log.app_id) not in app_names:
                app = db.query(Application).filter(
                    Application.app_id == log.app_id
                ).first()
                app_names[str(log.app_id)] = app.app_name if app else 'Unknown'

        if export_format.format == "json":
            # Export as JSON
            data = []
            for log in logs:
                data.append({
                    'execution_id': log.execution_id,
                    'timestamp': log.timestamp.isoformat(),
                    'app_id': str(log.app_id),
                    'app_name': app_names.get(str(log.app_id), 'Unknown'),
                    'flow_name': log.flow_name,
                    'trigger_type': log.trigger_type,
                    'incoming_events': log.incoming_event_count,
                    'outgoing_services': log.outgoing_service_count,
                    'data_transfer_kb': log.data_transfer_kb,
                    'token_count': log.token_count,
                    'total_cost': float(log.total_cost),
                    'currency': log.currency,
                    'was_free': log.was_free,
                    'billing_mode': log.billing_mode
                })

            return Response(
                content=json.dumps(data, indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=usage_export_{datetime.now().strftime('%Y%m%d')}.json"
                }
            )

        else:
            # Export as CSV
            output = io.StringIO()
            writer = csv.writer(output)

            # Write headers
            writer.writerow([
                'Execution ID', 'Timestamp', 'App ID', 'App Name',
                'Flow Name', 'Trigger Type', 'Incoming Events',
                'Outgoing Services', 'Data Transfer (KB)', 'Token Count',
                'Total Cost', 'Currency', 'Free Execution', 'Billing Mode'
            ])

            # Write data
            for log in logs:
                writer.writerow([
                    log.execution_id,
                    log.timestamp.isoformat(),
                    str(log.app_id),
                    app_names.get(str(log.app_id), 'Unknown'),
                    log.flow_name,
                    log.trigger_type,
                    log.incoming_event_count,
                    log.outgoing_service_count,
                    log.data_transfer_kb,
                    log.token_count,
                    float(log.total_cost),
                    log.currency,
                    'Yes' if log.was_free else 'No',
                    log.billing_mode
                ])

            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=usage_export_{datetime.now().strftime('%Y%m%d')}.csv"
                }
            )

    except Exception as e:
        logger.error(f"Error exporting usage data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export usage data: {str(e)}"
        )
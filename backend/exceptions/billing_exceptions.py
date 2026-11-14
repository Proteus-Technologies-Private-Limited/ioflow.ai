"""
Custom exceptions for billing and access control
"""
from typing import Optional, Dict, Any


class BillingException(Exception):
    """Base exception for billing-related errors"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class InsufficientBalanceError(BillingException):
    """Raised when tenant has insufficient balance for service execution"""

    def __init__(
        self,
        required_amount: float,
        available_amount: float,
        service_name: Optional[str] = None,
        app_name: Optional[str] = None,
        suggested_topup: Optional[float] = None
    ):
        self.required_amount = required_amount
        self.available_amount = available_amount
        self.service_name = service_name
        self.app_name = app_name
        self.suggested_topup = suggested_topup or (required_amount - available_amount)

        message = f"Insufficient balance: Required ${required_amount:.2f}, Available ${available_amount:.2f}"
        if service_name:
            message = f"{message} for service '{service_name}'"
        if app_name:
            message = f"{message} in application '{app_name}'"

        details = {
            "error_code": "INSUFFICIENT_BALANCE",
            "required_amount": required_amount,
            "available_amount": available_amount,
            "deficit": required_amount - available_amount,
            "suggested_topup": self.suggested_topup,
            "service_name": service_name,
            "app_name": app_name
        }

        super().__init__(message, details)


class ServiceAccessDeniedError(BillingException):
    """Raised when access to a service is denied for billing reasons"""

    def __init__(
        self,
        reason: str,
        service_name: Optional[str] = None,
        app_name: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ):
        self.reason = reason
        self.service_name = service_name
        self.app_name = app_name

        message = f"Service access denied: {reason}"
        if service_name:
            message = f"{message} for service '{service_name}'"
        if app_name:
            message = f"{message} in application '{app_name}'"

        details = {
            "error_code": "SERVICE_ACCESS_DENIED",
            "reason": reason,
            "service_name": service_name,
            "app_name": app_name
        }

        if additional_info:
            details.update(additional_info)

        super().__init__(message, details)


class UsageLimitExceededError(BillingException):
    """Raised when a usage limit has been exceeded"""

    def __init__(
        self,
        limit_type: str,
        current_usage: float,
        limit_value: float,
        period: Optional[str] = None,
        reset_time: Optional[str] = None
    ):
        self.limit_type = limit_type
        self.current_usage = current_usage
        self.limit_value = limit_value
        self.period = period
        self.reset_time = reset_time

        message = f"Usage limit exceeded: {limit_type}"
        if period:
            message = f"{message} for {period} period"
        message = f"{message}. Current: ${current_usage:.2f}, Limit: ${limit_value:.2f}"

        details = {
            "error_code": "USAGE_LIMIT_EXCEEDED",
            "limit_type": limit_type,
            "current_usage": current_usage,
            "limit_value": limit_value,
            "exceeded_by": current_usage - limit_value,
            "period": period,
            "reset_time": reset_time
        }

        super().__init__(message, details)


class PricingNotConfiguredError(BillingException):
    """Raised when pricing is not configured for an application or service"""

    def __init__(
        self,
        entity_type: str = "application",
        entity_id: Optional[str] = None,
        entity_name: Optional[str] = None
    ):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.entity_name = entity_name

        message = f"Pricing not configured for {entity_type}"
        if entity_name:
            message = f"{message} '{entity_name}'"
        elif entity_id:
            message = f"{message} with ID '{entity_id}'"

        details = {
            "error_code": "PRICING_NOT_CONFIGURED",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_name": entity_name
        }

        super().__init__(message, details)


class BalanceReservationError(BillingException):
    """Raised when there's an error with balance reservation"""

    def __init__(
        self,
        operation: str,
        amount: float,
        reason: str,
        execution_id: Optional[str] = None
    ):
        self.operation = operation
        self.amount = amount
        self.reason = reason
        self.execution_id = execution_id

        message = f"Balance {operation} failed for amount ${amount:.2f}: {reason}"
        if execution_id:
            message = f"{message} (Execution ID: {execution_id})"

        details = {
            "error_code": "BALANCE_RESERVATION_ERROR",
            "operation": operation,
            "amount": amount,
            "reason": reason,
            "execution_id": execution_id
        }

        super().__init__(message, details)
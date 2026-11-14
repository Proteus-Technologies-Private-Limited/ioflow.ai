"""
Transform Executor - Uses V2 implementation for better compatibility
This module now uses the V2 executor which provides better compatibility with
complex libraries like reportlab while maintaining security.
"""

# Import V2 executor and use it as the default
from .transform_executor_v2 import TransformExecutorV2 as TransformExecutor

# Export the main class
__all__ = ['TransformExecutor']
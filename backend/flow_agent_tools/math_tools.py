"""
Math tools for Flow Agent System
"""
import math
from typing import Union


def calculate(expression: str) -> dict:
    """
    Safely evaluate a mathematical expression.

    Args:
        expression: A mathematical expression to evaluate (e.g., "2 + 2", "sqrt(16)", "sin(3.14)")

    Returns:
        A dictionary with the result or error message
    """
    try:
        # Create a safe namespace with math functions
        safe_dict = {
            'sqrt': math.sqrt,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'log': math.log,
            'log10': math.log10,
            'exp': math.exp,
            'pow': pow,
            'abs': abs,
            'round': round,
            'pi': math.pi,
            'e': math.e
        }

        # Evaluate the expression in a restricted environment
        result = eval(expression, {"__builtins__": {}}, safe_dict)

        return {
            "success": True,
            "expression": expression,
            "result": result
        }
    except Exception as e:
        return {
            "success": False,
            "expression": expression,
            "error": str(e)
        }


def convert_units(value: float, from_unit: str, to_unit: str) -> dict:
    """
    Convert between different units of measurement.

    Args:
        value: The numeric value to convert
        from_unit: The source unit (e.g., "meters", "feet", "celsius", "fahrenheit")
        to_unit: The target unit

    Returns:
        A dictionary with the converted value or error message
    """
    # Define conversion factors
    conversions = {
        # Length
        ("meters", "feet"): 3.28084,
        ("feet", "meters"): 0.3048,
        ("kilometers", "miles"): 0.621371,
        ("miles", "kilometers"): 1.60934,
        ("inches", "centimeters"): 2.54,
        ("centimeters", "inches"): 0.393701,

        # Weight
        ("kilograms", "pounds"): 2.20462,
        ("pounds", "kilograms"): 0.453592,
        ("grams", "ounces"): 0.035274,
        ("ounces", "grams"): 28.3495,

        # Temperature (special handling)
        ("celsius", "fahrenheit"): lambda c: c * 9/5 + 32,
        ("fahrenheit", "celsius"): lambda f: (f - 32) * 5/9,
        ("celsius", "kelvin"): lambda c: c + 273.15,
        ("kelvin", "celsius"): lambda k: k - 273.15,
    }

    try:
        key = (from_unit.lower(), to_unit.lower())

        if key in conversions:
            conversion = conversions[key]
            if callable(conversion):
                result = conversion(value)
            else:
                result = value * conversion

            return {
                "success": True,
                "value": value,
                "from_unit": from_unit,
                "to_unit": to_unit,
                "result": result
            }
        else:
            return {
                "success": False,
                "error": f"Conversion from {from_unit} to {to_unit} is not supported"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def fibonacci(n: int) -> dict:
    """
    Calculate the nth Fibonacci number.

    Args:
        n: The position in the Fibonacci sequence (0-indexed)

    Returns:
        A dictionary with the Fibonacci number or error message
    """
    try:
        if n < 0:
            return {
                "success": False,
                "error": "n must be non-negative"
            }

        if n <= 1:
            result = n
        else:
            a, b = 0, 1
            for _ in range(2, n + 1):
                a, b = b, a + b
            result = b

        return {
            "success": True,
            "n": n,
            "fibonacci_number": result
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
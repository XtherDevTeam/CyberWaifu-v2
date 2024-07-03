"""
Chat plugins for Gemini-1.5-Pro model
"""


import datetime
import math
import models
import tools


def calculate(expression: str) -> int | float | str:
    """
    Calculate an expression using Python 3 and return the number value.
    You can use the following operators: +, -, *, /, **, %, //, and ().
    You are allowed to use math library.

    Args:
        expression (str): The expression to evaluate.

    Returns:
        int | float | str: The result of the expression.
    """
    return eval(expression, globals(), locals())

def time(dummy_arg: str = None) -> str:
    """
    Get the current time in HH:MM:SS format.
    
    Args:
        dummy_arg (str): Dummy argument to make the function callable. Set this to ""

    Returns:
        str: The current time in HH:MM:SS format.
    """
    return tools.TimeProvider()

def defaultPluginList():
    return [
        calculate,
        time
    ]
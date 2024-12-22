"""
Chat plugins for Gemini-1.5-Pro model
"""


import datetime
import math
import models
import tools
import google.genai.types
import google.generativeai
import typing
import inspect
import json
from typing import get_type_hints


def python_function_to_function_declaration(func, description=None):
    """
    Converts a Python function's signature into an OpenAI Function Declaration.

    Args:
        func: The Python function object.
        description: (Optional) A description of the function. If None, uses docstring if available

    Returns:
        A JSON string representing the Function Declaration.
    """
    if description is None:
        description = inspect.getdoc(func)
        if description is None:
            description = "This function does not have any description yet."

    signature = inspect.signature(func)
    type_hints = get_type_hints(func)

    parameters = {
        "type": "OBJECT",
        "properties": {},
        "required": [],
    }

    for name, param in signature.parameters.items():
        param_info = {}
        param_info['description'] = f"Parameter {name} for the {func.__name__} function."
        
        if name in type_hints:
            type_hint = type_hints[name]
            if type_hint == str:
                param_info["type"] = "STRING"
            elif type_hint == int:
                param_info["type"] = "INTEGER"
            elif type_hint == float:
                param_info["type"] = "NUMBER"
            elif type_hint == bool:
                 param_info["type"] = "BOOLEAN"
            elif hasattr(type_hint, '__origin__') and type_hint.__origin__ == list:
                param_info["type"] = "ARRAY"
            elif hasattr(type_hint, '__origin__') and type_hint.__origin__ == dict:
                param_info["type"] = "OBJECT"
            else:
                 param_info["type"] = "STRING"  # Default for unknown types
                
        else:
            param_info["type"] = "STRING"  #Default to String when no hint is found


        if param.default is inspect.Parameter.empty:
            parameters["required"].append(name)
            
        parameters["properties"][name] = param_info

    return {
        "name": func.__name__,
        "description": description,
        "parameters": parameters,
    }

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
    

def getEncodedPluginList(plugins: list[typing.Callable] = defaultPluginList()) -> list[dict[str, typing.Any]]:
    """
    Get a list of encoded plugins for the chat client.

    Args:
        plugins (list[typing.Callable]): A list of plugins to encode.

    Returns:
        list[dict[str, typing.Any]]: A list of encoded plugins.
    """
    encodedPlugins = []
    tools = []
    for plugin in plugins:
        decl = python_function_to_function_declaration(plugin)
        decl = google.genai.types.FunctionDeclaration(name=decl['name'], description=decl['description'], parameters=decl['parameters'])
        tools.append(google.genai.types.Tool(function_declarations=[decl]))
    tools.append(google.genai.types.Tool(google_search=google.genai.types.GoogleSearch()))
    return tools
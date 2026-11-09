import typing
import inspect
import logging
import math
import os

os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

methods = {}
logger: logging.Logger = logging.getLogger("api")


class APIError(Exception):
    """
    Error that can be raised by an API method, its message is sent back to the caller
    """


def register(obj):
    global methods

    for name, func in inspect.getmembers(obj):
        if not name.startswith("_") and callable(func):
            hints = typing.get_type_hints(func)
            parameters = inspect.signature(func).parameters.values()
            args = [hints.get(parameter.name, None) for parameter in parameters]
            min_args = len(
                [
                    parameter
                    for parameter in parameters
                    if parameter.default is inspect.Parameter.empty
                ]
            )
            result = hints.get("return", None)

            methods[func.__name__] = {
                "func": func,
                "args": args,
                "min_args": min_args,
                "result": result,
            }


def convert_argument(value, hint):
    """
    Converts an argument received from the API to the type hinted in the method signature

    :param value: the value received
    :param hint: the type hint (None if no hint)
    :raises ValueError: if the value can't be converted
    :return: the converted value
    """
    if hint is None:
        return value

    if hint is bool:
        # bool("false") would be True, we only accept real booleans (or 0/1)
        if type(value) is bool or value in (0, 1):
            return bool(value)
        raise ValueError(f"expected a boolean, got {value!r}")

    if hint in (int, float):
        if type(value) is bool or type(value) not in (int, float, str):
            raise ValueError(f"expected a number, got {value!r}")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError(f"expected a finite number, got {value!r}")
        return hint(value)

    if hint is str and type(value) not in (str, int, float):
        raise ValueError(f"expected a string, got {value!r}")

    return hint(value)


def call(command: str, args) -> list:
    """
    Calls an API method

    :param str command: the method name
    :param args: the arguments (list)
    :return list: [1, result] on success, [0, error message] on error
    """
    if command not in methods:
        return [0, f"Command {command} not found"]

    method = methods[command]
    if type(args) is not list:
        return [0, f"Arguments for command {command} should be a list"]

    if not method["min_args"] <= len(args) <= len(method["args"]):
        return [
            0,
            f"Command {command} expects between {method['min_args']} and "
            f"{len(method['args'])} arguments, got {len(args)}",
        ]

    try:
        args = [convert_argument(arg, hint) for arg, hint in zip(args, method["args"])]
    except (ValueError, TypeError) as e:
        return [0, f"Bad argument type for command {command}: {e}"]

    try:
        return [1, method["func"](*args)]
    except APIError as e:
        return [0, str(e)]
    except Exception as e:
        # Unexpected errors (e.g. unknown team name) should not crash the request
        logger.exception(f"Error while running API command {command}")
        return [0, f"Error while running command {command}: {type(e).__name__}: {e}"]

import typing
import inspect
import os

os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

methods = {}


def register(obj):
    global methods

    for name, func in inspect.getmembers(obj):
        if not name.startswith("_") and callable(func):
            hints = typing.get_type_hints(func)
            args = inspect.signature(func).parameters.keys()
            args = list(map(lambda name: hints.get(name, None), args))
            result = hints.get("return", None)

            methods[func.__name__] = {"func": func, "args": args, "result": result}

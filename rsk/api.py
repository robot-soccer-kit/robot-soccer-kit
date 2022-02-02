methods = {}


def slot(*args, result=None):
    global methods

    def decorate(func):
        methods[func.__name__] = {
            'func': func,
            'args': args,
            'result': result
        }

        return func

    return decorate

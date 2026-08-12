from typing import Never, NewType

ComPort = NewType('ComPort', str)


def throw(e: Exception) -> Never:
    raise e

def raises(e: Exception):
    return lambda *_, **__: throw(e)
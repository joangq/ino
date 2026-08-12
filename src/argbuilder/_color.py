from enum import StrEnum

class Color(StrEnum):
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    RESET = '\033[0m'
    RED = '\033[91m'
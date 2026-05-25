"""Stock code utilities for A-share market."""

from __future__ import annotations


def normalize_stock_code(code: str) -> str:
    """Normalize stock code to ts_code format (e.g., 000001.SZ).
    
    Handles various input formats:
    - "000001" -> "000001.SZ" (assumes SZ for 6-digit starting with 0/3)
    - "000001.SZ" -> "000001.SZ" (already normalized)
    - "sz000001" -> "000001.SZ"
    - "600519" -> "600519.SH"
    """
    code = code.strip().upper()
    
    if "." in code:
        return code
    
    if code.startswith(("SH", "SZ", "BJ")):
        exchange = code[:2]
        num = code[2:]
        return f"{num}.{exchange}"
    
    num = code.lstrip("0")
    if not num:
        return "000000.SZ"
    
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    elif code.startswith(("0", "3", "2")):
        return f"{code}.SZ"
    elif code.startswith(("4", "8")):
        return f"{code}.BJ"
    else:
        return f"{code}.SZ"


def get_exchange(code: str) -> str:
    """Get exchange from ts_code."""
    if "." in code:
        return code.split(".")[-1]
    code = normalize_stock_code(code)
    return code.split(".")[-1]


def get_symbol(code: str) -> str:
    """Get symbol (numeric part) from ts_code."""
    if "." in code:
        return code.split(".")[0]
    return code


def is_st_code(name: str) -> bool:
    """Check if stock name indicates ST status."""
    upper_name = name.upper()
    return "ST" in upper_name


def get_board(code: str) -> str:
    """Determine board type from stock code."""
    symbol = get_symbol(code)
    if symbol.startswith("60"):
        return "main"  # Shanghai main board
    elif symbol.startswith("00"):
        return "main"  # Shenzhen main board
    elif symbol.startswith("30"):
        return "chinext"  # ChiNext (创业板)
    elif symbol.startswith("68"):
        return "star"  # STAR Market (科创板)
    elif symbol.startswith(("43", "83", "87")):
        return "bse"  # Beijing Stock Exchange
    else:
        return "main"

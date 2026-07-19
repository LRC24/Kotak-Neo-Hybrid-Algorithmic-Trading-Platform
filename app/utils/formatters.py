import datetime

def format_currency(value: float) -> str:
    """Formats numeric values to Indian Rupee (₹) standard currency representation"""
    prefix = "+" if value > 0 else ""
    return f"{prefix}₹{value:,.2f}"

def format_percentage(value: float) -> str:
    """Formats values as percentages"""
    return f"{value:.2f}%"

def format_timestamp(dt: datetime.datetime) -> str:
    """Converts datetime objects to standard UI strings"""
    if not dt:
        return "N/A"
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def format_milliseconds(seconds: float) -> int:
    """Helper to convert seconds to integer milliseconds representation"""
    return int(seconds * 1000)

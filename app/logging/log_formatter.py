import logging
import colorlog

# Color configuration for console levels
CONSOLE_COLORS = {
    'DEBUG': 'cyan',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'red,bg_white',
}

def get_console_formatter() -> colorlog.ColoredFormatter:
    """Returns a color-coded logging formatter for terminal output"""
    return colorlog.ColoredFormatter(
        fmt="%(log_color)s[%(asctime)s] | %(levelname)-8s | %(threadName)-12s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors=CONSOLE_COLORS
    )

def get_file_formatter() -> logging.Formatter:
    """Returns a standard plain-text formatter for file outputs"""
    return logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(threadName)-12s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

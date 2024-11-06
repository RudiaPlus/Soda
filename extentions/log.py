import datetime
import os
import sys

from loguru import logger

from extentions import config

logging_time = datetime.datetime.now()

def setup_logger():
    # create logger
    output_logger = logger
    output_logger.remove()
    output_logger.add(sys.stderr, format = "{time} {level} {message}", level="INFO")

    if config.logging is True:  # Check if logging is enabled
        # specify that the log file path is the same as `main.py` file path
        dir = os.path.abspath(f"{__file__}/../logs/")
        log_name = f'rhodo_{logging_time.strftime("%Y-%m-%d_%H%M%S")}.log'
        log_path = os.path.join(dir, log_name)
        # create local log handler
        output_logger.add(log_path, format = "{time} {level} {message}", level="DEBUG")

    return output_logger

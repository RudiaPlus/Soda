import datetime
import os
import sys

from loguru import logger
import logging
import requests

from extentions.config import config
from extentions.aclient import client

logging_time = datetime.datetime.now()

class Loggingbot_Handler(logging.Handler):
    def __init__(self, level = logging.WARNING):
        super().__init__(level=level)
        self.log_webhook = os.environ["LOGGING_WEBHOOK"]
    
    def log(self, message):
        request_body = {
            "content": f"```\n{message}\n```",
            "username": "ロード - エラー",
            "avatar_url": client.user.avatar.url if client.user and client.user.avatar else None
        }
        requests.post(self.log_webhook, headers={"Content-Type": "application/json"}, json = request_body)
    
    def emit(self, record):
        if len(record.msg) > 0:
            msg = self.format(record)
        else:
            msg = ""
            
        self.log(msg)
        

def setup_logger():
    # create logger
    output_logger = logger
    output_logger.remove()
    output_logger.add(sys.stderr, format = "[{time:YYYY-MM-DD HH:mm:ss}] {name} [{level}]: {message}", level="INFO")

    if config.logging is True:  # Check if logging is enabled
        # specify that the log file path is the same as `main.py` file path
        dir = os.path.abspath(f"{__file__}/../logs/")
        log_name = f'rhodo_{logging_time.strftime("%Y-%m-%d_%H%M%S")}.log'
        log_path = os.path.join(dir, log_name)
        # create local log handler
        output_logger.add(log_path, format = "[{time:YYYY-MM-DD HH:mm:ss}] {name}:{line} {function} [{level}]: {message}", level="DEBUG")
        output_logger.add(Loggingbot_Handler(), format = "[{time:YYYY-MM-DD HH:mm:ss}] {name}:{line} [{level}]: {message}", level = "WARNING")

    return output_logger

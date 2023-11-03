from extentions import (rhodo, log)

if __name__ == "__main__":
  log.setup_logger("discord")
  log.setup_logger("selenium")
  rhodo.run_discord_bot()
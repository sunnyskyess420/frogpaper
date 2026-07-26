"""
main.py
-------
The old text-based interactive menu has been deprecated in favor of the modern GUI.
Running this script will now automatically launch the GUI.
"""

import logging

logger = logging.getLogger(__name__)

from app import main as app_main


def main() -> None:
    logger.info("FrogPaper CLI is deprecated.")
    logger.info("Launching the beautiful modern GUI (app.py) instead...")
    app_main()


if __name__ == "__main__":
    main()

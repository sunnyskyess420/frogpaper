"""
main.py
-------
The old text-based interactive menu has been deprecated in favor of the modern GUI.
Running this script will now automatically launch the GUI.
"""

from app import main as app_main

def main() -> None:
    print("FrogPaper CLI is deprecated.")
    print("Launching the beautiful modern GUI (app.py) instead...")
    app_main()

if __name__ == "__main__":
    main()

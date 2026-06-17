import json
import sys
from pathlib import Path
from datetime import datetime

from utils import load_json_list

BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
PROMPTS_LOG = LOGS_DIR / "prompts_history.json"
FAVORITES_LOG = LOGS_DIR / "favorites.json"
EXPORT_DIR = BASE_DIR / "exports" / "prompt-packs"

def export_pack(source_path: Path, pack_type: str):
    data = load_json_list(source_path)
    if not data:
        print(f"\n❌ No data found in {source_path.name}.")
        return

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_filename = f"frogpaper_{pack_type}_pack_{timestamp}.json"
    export_path = EXPORT_DIR / export_filename

    try:
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Successfully exported {len(data)} prompts!")
        print(f"📁 Saved to: {export_path}")
    except Exception as e:
        print(f"\n❌ Failed to export: {e}")

def main():
    print("\n🐸 FrogPaper Prompt Pack Exporter")
    print("=" * 40)
    print("1. Export Prompt History")
    print("2. Export Favorites")
    print("3. Quit")
    
    choice = input("\nWhat would you like to export? (1/2/3): ").strip()
    
    if choice == "1":
        export_pack(PROMPTS_LOG, "history")
    elif choice == "2":
        export_pack(FAVORITES_LOG, "favorites")
    elif choice == "3" or choice.lower() in ['q', 'quit']:
        print("Goodbye!")
        sys.exit(0)
    else:
        print("Unknown option. Exiting.")

if __name__ == "__main__":
    main()

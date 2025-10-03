import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Paths to your files
MODELS_FILE = "accounts/models.py"
ADMIN_FILE = "accounts/admin.py"
OUTPUT_FILE = "accounts/models_and_admin.py"

def combine_files():
    """Read models.py + admin.py and merge into one file."""
    with open(MODELS_FILE, "r", encoding="utf-8") as f:
        models_content = f.read()
    with open(ADMIN_FILE, "r", encoding="utf-8") as f:
        admin_content = f.read()

    combined = (
        "# AUTO-GENERATED FILE — DO NOT EDIT MANUALLY\n"
        "# Updated whenever models.py or admin.py changes\n\n"
        + models_content
        + "\n\n"
        + admin_content
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(combined)
    print(f"✅ Combined file updated: {OUTPUT_FILE}")

class ChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith("models.py") or event.src_path.endswith("admin.py"):
            combine_files()

if __name__ == "__main__":
    combine_files()  # initial run
    event_handler = ChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path="accounts", recursive=False)
    observer.start()
    print("👀 Watching for changes in models.py and admin.py...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

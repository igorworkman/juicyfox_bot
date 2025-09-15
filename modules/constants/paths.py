from pathlib import Path

# Путь до корня проекта
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

START_PHOTO = DATA_DIR / "start.jpg"
# REGION AI: vip photo path
VIP_PHOTO = (DATA_DIR / "vip_banner.jpg").resolve()
# END REGION AI

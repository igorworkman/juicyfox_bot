from pathlib import Path

# REGION AI: data paths
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"

START_PHOTO = (DATA_DIR / "start.jpg").resolve()
VIP_PHOTO = (DATA_DIR / "vip_banner.jpg").resolve()
# END REGION AI

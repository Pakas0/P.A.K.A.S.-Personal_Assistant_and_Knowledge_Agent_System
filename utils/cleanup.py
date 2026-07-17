import os
import time
from utils.logger import logger
from config import BASE_DIR

TMP_EXPORT_DIR = os.path.join(BASE_DIR, "data", "tmp_exports")

async def cleanup_stale_exports(max_age_hours: int = 1):
    """
    Hapus file di data/tmp_exports/ yang lebih tua dari max_age_hours.
    Ini jaring pengaman kalau ada file yang gagal terhapus setelah pengiriman
    (misal Discord API error setelah file sudah dibuat).
    """
    if not os.path.exists(TMP_EXPORT_DIR):
        return
        
    try:
        now = time.time()
        for filename in os.listdir(TMP_EXPORT_DIR):
            file_path = os.path.join(TMP_EXPORT_DIR, filename)
            if os.path.isfile(file_path):
                # Check age
                file_age_hours = (now - os.path.getmtime(file_path)) / 3600
                if file_age_hours > max_age_hours:
                    os.remove(file_path)
                    logger.info(f"Cleaned up stale export file: {filename}")
    except Exception as e:
        logger.error(f"Error during stale exports cleanup: {e}")

import os
import logging
import datetime
from config import config

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(PROJECT_ROOT, "temp")
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_LOG_DIR = os.path.join(TEMP_DIR, f"run_{time_str}")
os.makedirs(RUN_LOG_DIR, exist_ok=True)

def cleanup_old_log_dirs():
    max_run_logs = config.get("logging/max_run_logs", 10)
    if max_run_logs < 1:
        return
    subdirs = []
    for d in os.listdir(TEMP_DIR):
        full_path = os.path.join(TEMP_DIR, d)
        if d.startswith("run_") and os.path.isdir(full_path):
            subdirs.append(d)
    subdirs.sort()
    excess = len(subdirs) - max_run_logs
    if excess > 0:
        for i in range(excess):
            old_dir_name = subdirs[i]
            old_dir_path = os.path.join(TEMP_DIR, old_dir_name)
            try:
                for root, dirs, files in os.walk(old_dir_path, topdown=False):
                    for f in files:
                        os.remove(os.path.join(root, f))
                    for dr in dirs:
                        os.rmdir(os.path.join(root, dr))
                os.rmdir(old_dir_path)
            except Exception as e:
                print(f"Error removing old log folder {old_dir_path}: {e}")

cleanup_old_log_dirs()

logger = logging.getLogger("KartenWarp")
logger.setLevel(logging.DEBUG)
logger.handlers = []

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app_log_path = os.path.join(RUN_LOG_DIR, "application.log")
app_handler = logging.FileHandler(app_log_path, encoding="utf-8")
app_handler.setLevel(logging.DEBUG)
app_handler.setFormatter(formatter)
logger.addHandler(app_handler)

err_log_path = os.path.join(RUN_LOG_DIR, "error.log")
error_handler = logging.FileHandler(err_log_path, encoding="utf-8")
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)
logger.addHandler(error_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

logger.info(f"Logging started in {RUN_LOG_DIR}")

# 別ログ（変換処理用）
transform_logger = logging.getLogger("KartenWarp.Transform")
transform_logger.setLevel(logging.DEBUG)
transform_logger.handlers = []
transform_log_path = os.path.join(RUN_LOG_DIR, "transform.log")
transform_handler = logging.FileHandler(transform_log_path, encoding="utf-8")
transform_handler.setLevel(logging.DEBUG)
transform_handler.setFormatter(formatter)
transform_logger.addHandler(transform_handler)

logger.info("Transformation logger configured")

def setup_logger():
    # ログはモジュール読込時に設定済みのため特に何もしません
    pass

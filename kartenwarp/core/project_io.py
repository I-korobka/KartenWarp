import json
from log_config import logger

def save_project(state, file_path):
    logger.debug(f"Saving project to {file_path}")
    try:
        project_data = {
            "game_image_path": state.game_image_path,
            "real_image_path": state.real_image_path,
            "game_points": state.game_points,
            "real_points": state.real_points,
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(project_data, f, indent=4, ensure_ascii=False)
        logger.info(f"Project saved successfully: {file_path}")
        return True
    except Exception as e:
        logger.exception("Error while saving project")
        raise IOError(f"Error while saving project: {str(e)}")

def load_project(file_path):
    logger.debug(f"Loading project from {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            project_data = json.load(f)
        logger.info(f"Project loaded successfully: {file_path}")
        return project_data
    except Exception as e:
        logger.exception("Error while loading project")
        raise IOError(f"Error while loading project: {str(e)}")

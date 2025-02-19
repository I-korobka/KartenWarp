from log_config import logger

logger.debug("Initializing SceneState")

class SceneState:
    """
    シーン共通の状態管理クラス。
    ゲーム画像と実地図画像それぞれの画像情報および対応点情報を保持します。
    """
    def __init__(self):
        logger.debug("SceneState.__init__")
        self.game_pixmap = None
        self.game_qimage = None
        self.game_points = []  # [x, y]
        self.game_image_path = None

        self.real_pixmap = None
        self.real_qimage = None
        self.real_points = []  # [x, y]
        self.real_image_path = None

    def update_game_points(self, points):
        logger.debug(f"Updating game points: {points}")
        self.game_points = points

    def update_real_points(self, points):
        logger.debug(f"Updating real points: {points}")
        self.real_points = points

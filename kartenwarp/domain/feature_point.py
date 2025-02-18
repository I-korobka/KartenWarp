# kartenwarp/domain/feature_point.py
from kartenwarp.localization import tr

class FeaturePoint:
    def __init__(self, point_id, x, y, attributes=None):
        self.id = point_id
        self.x = x
        self.y = y
        self.attributes = attributes if attributes is not None else {}
        self.gui_items = {}  # GUI側の表示アイテム（ellipse, text など）を保持する

    def set_position(self, x, y):
        self.x = x
        self.y = y

class FeaturePointManager:
    def __init__(self):
        self.feature_points = {}  # {id: FeaturePoint}
        self.history = []         # コマンドオブジェクトのリスト
        self.history_index = -1   # 現在の履歴位置
        self.next_id = 1          # 次に発行するID（1から開始）

        self.observers = []       # 変更通知用の observer コールバック

    def register_observer(self, observer):
        if observer not in self.observers:
            self.observers.append(observer)

    def unregister_observer(self, observer):
        if observer in self.observers:
            self.observers.remove(observer)

    def notify_observers(self):
        for observer in self.observers:
            observer()

    def add_feature_point(self, x, y):
        from .commands import AddCommand
        cmd = AddCommand(x, y)
        fp = cmd.execute(self)
        self.history = self.history[:self.history_index + 1]
        self.history.append(cmd)
        self.history_index = len(self.history) - 1
        self.notify_observers()
        return fp

    def move_feature_point(self, point_id, new_x, new_y):
        from .commands import MoveCommand
        cmd = MoveCommand(point_id, new_x, new_y)
        cmd.execute(self)
        self.history = self.history[:self.history_index + 1]
        self.history.append(cmd)
        self.history_index = len(self.history) - 1
        self.notify_observers()

    def delete_feature_point(self, point_id):
        from .commands import DeleteCommand
        cmd = DeleteCommand(point_id)
        cmd.execute(self)
        self.history = self.history[:self.history_index + 1]
        self.history.append(cmd)
        self.history_index = len(self.history) - 1
        self.notify_observers()

    def undo(self):
        if self.history_index < 0:
            return
        cmd = self.history[self.history_index]
        cmd.undo(self)
        self.history_index -= 1
        self.notify_observers()

    def redo(self):
        if self.history_index >= len(self.history) - 1:
            return
        self.history_index += 1
        cmd = self.history[self.history_index]
        cmd.execute(self)
        self.notify_observers()

    def jump_to_history(self, target_index):
        if target_index < -1 or target_index >= len(self.history):
            raise ValueError("Invalid history index")
        while self.history_index > target_index:
            self.undo()
        while self.history_index < target_index:
            self.redo()

    def get_feature_points(self):
        # 座標を [x, y] のリスト形式で返す
        return [[fp.x, fp.y] for fp in sorted(self.feature_points.values(), key=lambda p: p.id)]

    def get_history(self):
        # UI向けに各コマンドの説明文字列の一覧を返す
        return [{"action": cmd.__class__.__name__, "desc": cmd.get_description()} for cmd in self.history]

    def get_history_index(self):
        return self.history_index

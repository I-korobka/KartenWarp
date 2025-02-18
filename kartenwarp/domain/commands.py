# kartenwarp/domain/commands.py
from abc import ABC, abstractmethod
from kartenwarp.localization import tr
from .feature_point import FeaturePoint

class Command(ABC):
    @abstractmethod
    def execute(self, manager):
        pass

    @abstractmethod
    def undo(self, manager):
        pass

    @abstractmethod
    def get_description(self):
        pass

class AddCommand(Command):
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.point_id = None

    def execute(self, manager):
        # 既に point_id が設定されている場合は再利用し、未設定なら新規に割り当てる
        if self.point_id is None:
            self.point_id = manager.next_id
            manager.next_id += 1
        fp = FeaturePoint(self.point_id, self.x, self.y)
        manager.feature_points[self.point_id] = fp
        return fp

    def undo(self, manager):
        if self.point_id in manager.feature_points:
            del manager.feature_points[self.point_id]

    def get_description(self):
        return f"{tr('point_add')}: ({self.x}, {self.y})"

class MoveCommand(Command):
    def __init__(self, point_id, new_x, new_y):
        self.point_id = point_id
        self.new_x = new_x
        self.new_y = new_y
        self.old_x = None
        self.old_y = None

    def execute(self, manager):
        if self.point_id not in manager.feature_points:
            raise ValueError("FeaturePoint not found")
        fp = manager.feature_points[self.point_id]
        self.old_x = fp.x
        self.old_y = fp.y
        fp.set_position(self.new_x, self.new_y)
        return fp

    def undo(self, manager):
        if self.point_id in manager.feature_points:
            fp = manager.feature_points[self.point_id]
            fp.set_position(self.old_x, self.old_y)

    def get_description(self):
        return f"{tr('point_move')} (ID {self.point_id}): ({self.new_x}, {self.new_y})"

class DeleteCommand(Command):
    def __init__(self, point_id):
        self.point_id = point_id
        self.x = None
        self.y = None

    def execute(self, manager):
        if self.point_id not in manager.feature_points:
            raise ValueError("FeaturePoint not found")
        fp = manager.feature_points[self.point_id]
        self.x = fp.x
        self.y = fp.y
        del manager.feature_points[self.point_id]
        return fp

    def undo(self, manager):
        if self.point_id not in manager.feature_points:
            fp = FeaturePoint(self.point_id, self.x, self.y)
            manager.feature_points[self.point_id] = fp

    def get_description(self):
        return f"{tr('point_delete')} (ID {self.point_id})"

"""玩家/任务角色 - 在地图上移动"""

from typing import Tuple, Optional
from item import ItemStack
from backpack.inventory import Inventory


class Player:
    """可在地图上移动的角色"""

    def __init__(self, x: int, y: int, name: str = "冒险者"):
        self.x = x
        self.y = y
        self.name = name
        self.hp = 100
        self.max_hp = 100
        self.level = 1
        self.gold = 0
        self.inventory = Inventory()

    @property
    def position(self) -> Tuple[int, int]:
        return (self.x, self.y)

    @position.setter
    def position(self, pos: Tuple[int, int]):
        self.x, self.y = pos

    def take_damage(self, amount: int):
        self.hp = max(0, self.hp - amount)

    def heal(self, amount: int):
        self.hp = min(self.max_hp, self.hp + amount)

    @property
    def selected_slot(self) -> Optional[ItemStack]:
        """当前选中的物品栏格子（-1=空手）"""
        idx = self.inventory.selected
        if idx < 0 or idx >= len(self.inventory.slots):
            return None
        return self.inventory.slots[idx]

    def status_line(self) -> str:
        """一行状态显示"""
        hp_bar = "#" * (self.hp // 10) + "." * ((self.max_hp - self.hp) // 10)
        return (f"  {self.name} | HP: {self.hp}/{self.max_hp} {hp_bar} "
                f"| Lv.{self.level} | 坐标: ({self.x}, {self.y})")

    def __repr__(self):
        return f"<Player {self.name} at ({self.x},{self.y})>"

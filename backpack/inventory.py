"""背包系统 - 物品存储和管理"""

from typing import List, Optional
from item import ItemStack


class Inventory:
    """背包 - 管理物品堆叠的格子列表"""

    MAX_SLOTS = 24  # 6行 x 4列

    def __init__(self):
        self.slots: List[Optional[ItemStack]] = [None] * self.MAX_SLOTS
        self.selected: int = 0  # 当前选中的格子索引

    def add_item(self, item_id: str, quantity: int = 1) -> int:
        """添加物品，返回实际添加数量"""
        remaining = quantity
        # 先堆叠到已有格子
        for slot in self.slots:
            if slot and slot.item_id == item_id and slot.quantity < slot.item.max_stack:
                added = slot.add(remaining)
                remaining -= added
                if remaining <= 0:
                    return quantity

        # 放到空格
        for i in range(self.MAX_SLOTS):
            if self.slots[i] is None:
                stack = ItemStack(item_id, 0)  # 从0开始，下面add追加
                added = stack.add(remaining)
                self.slots[i] = stack
                remaining -= added
                if remaining <= 0:
                    return quantity

        return quantity - remaining

    def remove_item(self, item_id: str, quantity: int = 1) -> int:
        """移除物品，返回实际移除量"""
        remaining = quantity
        for slot in self.slots:
            if slot and slot.item_id == item_id:
                removed = slot.remove(remaining)
                remaining -= removed
                if remaining <= 0:
                    break
        # 清理空槽
        self.slots = [s if s and s.quantity > 0 else None for s in self.slots]
        return quantity - remaining

    def count(self, item_id: str) -> int:
        """统计某物品总数"""
        return sum(s.quantity for s in self.slots if s and s.item_id == item_id)

    def has(self, item_id: str, quantity: int = 1) -> bool:
        """是否有足够数量的物品"""
        return self.count(item_id) >= quantity

    def is_full(self) -> bool:
        return all(s is not None for s in self.slots)

    def list_items(self) -> List[ItemStack]:
        """列出所有非空格子"""
        return [s for s in self.slots if s is not None]

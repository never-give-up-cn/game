"""物品系统 - 背包中的物品"""

from typing import List, Dict, Optional


class Item:
    """游戏物品"""

    def __init__(self, item_id: str, name: str, icon: str, category: str,
                 description: str = "", stackable: bool = True, max_stack: int = 99):
        self.item_id = item_id
        self.name = name
        self.icon = icon          # 显示的图标字符
        self.category = category  # 分类: material, tool, food, key
        self.description = description
        self.stackable = stackable
        self.max_stack = max_stack

    def __repr__(self):
        return f"<{self.name}>"


# ========== 物品模板 ==========

ITEM_TEMPLATES: Dict[str, Item] = {
    # 材料
    "wood":     Item("wood",     "木材",  "木", "material", "建造用的基础材料"),
    "stone":    Item("stone",    "石头",  "石", "material", "坚硬的建筑材料"),
    "iron":     Item("iron",     "铁锭",  "铁", "material", "用于制作工具和建筑"),
    "steel":    Item("steel",    "钢材",  "钢", "material", "高级建筑材料"),
    "coal":     Item("coal",     "煤炭",  "C",  "material", "燃料资源"),

    # 食物
    "bread":    Item("bread",    "面包",  "B", "food", "恢复 20 HP"),
    "apple":    Item("apple",    "苹果",  "A", "food", "恢复 10 HP"),
    "potion":   Item("potion",   "药水",  "P", "food", "恢复 50 HP"),

    # 工具
    "pickaxe":  Item("pickaxe",  "镐子",  "X", "tool", "采集工具", stackable=False),
    "axe":      Item("axe",      "斧头",  "F", "tool", "砍树工具", stackable=False),

    # 特殊
    "key":      Item("key",      "钥匙",  "K", "key", "开启特殊建筑", max_stack=5),
    "gold":     Item("gold",     "金币",  "$", "currency", "通用货币", max_stack=9999),
}


class ItemStack:
    """物品堆叠"""

    def __init__(self, item_id: str, quantity: int = 1):
        template = ITEM_TEMPLATES.get(item_id)
        if not template:
            raise ValueError(f"未知物品: {item_id}")
        self.item_id = item_id
        self.quantity = quantity

    @property
    def item(self) -> Item:
        return ITEM_TEMPLATES[self.item_id]

    @property
    def name(self) -> str:
        return self.item.name

    @property
    def icon(self) -> str:
        return self.item.icon

    def add(self, amount: int = 1) -> int:
        """添加数量，返回实际添加量（受 max_stack 限制）"""
        can_add = min(amount, self.item.max_stack - self.quantity)
        self.quantity += can_add
        return can_add

    def remove(self, amount: int = 1) -> int:
        """移除数量，返回实际移除量"""
        actual = min(amount, self.quantity)
        self.quantity -= actual
        return actual

    def can_merge(self, other: "ItemStack") -> bool:
        """能否与另一堆合并"""
        return (self.item_id == other.item_id
                and self.item.stackable
                and self.quantity < self.item.max_stack)

    def __repr__(self):
        return f"<{self.name} x{self.quantity}>"


class Inventory:
    """背包"""

    MAX_SLOTS = 24  # 6行 x 4列

    def __init__(self):
        self.slots: List[Optional[ItemStack]] = [None] * self.MAX_SLOTS
        self.selected: int = 0  # 当前选中的格子索引

    def add_item(self, item_id: str, quantity: int = 1) -> int:
        """添加物品，返回实际添加数量"""
        remaining = quantity
        # 先尝试堆叠到已有格子
        for slot in self.slots:
            if slot and slot.item_id == item_id and slot.quantity < slot.item.max_stack:
                added = slot.add(remaining)
                remaining -= added
                if remaining <= 0:
                    return quantity

        # 放到空格
        for i in range(self.MAX_SLOTS):
            if self.slots[i] is None:
                stack = ItemStack(item_id)
                added = stack.add(remaining)
                self.slots[i] = stack
                remaining -= added
                if remaining <= 0:
                    return quantity

        return quantity - remaining  # 返回实际放入量

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

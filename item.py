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

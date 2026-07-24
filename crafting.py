"""合成配方系统 - 手动合成与机器生产"""

from typing import Dict, List, Optional


class Recipe:
    """合成配方"""

    def __init__(self, recipe_id: str, name: str, item_id: str, quantity: int,
                 materials: Dict[str, int],
                 requires_building: Optional[str] = None,
                 description: str = ""):
        self.recipe_id = recipe_id
        self.name = name
        self.item_id = item_id       # 产出物品
        self.quantity = quantity     # 产出数量
        self.materials = materials   # {item_id: amount}
        self.requires_building = requires_building  # None=手动, 否则=建筑名
        self.description = description

    def can_craft(self, inventory) -> bool:
        """检查是否有足够材料"""
        for item_id, amount in self.materials.items():
            if inventory.count(item_id) < amount:
                return False
        return True

    def craft(self, inventory) -> bool:
        """执行合成，成功返回 True"""
        if not self.can_craft(inventory):
            return False
        for item_id, amount in self.materials.items():
            inventory.remove_item(item_id, amount)
        inventory.add_item(self.item_id, self.quantity)
        return True

    def __repr__(self):
        return f"<{self.name}>"


# ========== 配方库 ==========

# 手动合成配方（无需建筑，在背包界面可直接合成）
MANUAL_RECIPES: Dict[str, Recipe] = {
    "apple_bread": Recipe(
        "apple_bread", "苹果面包", "bread", 1,
        {"apple": 2},
        description="2 苹果 → 1 面包",
    ),
    "iron_tool": Recipe(
        "iron_tool", "铁工具", "pickaxe", 1,
        {"iron": 3},
        description="3 铁 → 1 镐子",
    ),
    "stone_axe": Recipe(
        "stone_axe", "石斧头", "axe", 1,
        {"stone": 3, "wood": 2},
        description="石×3 + 木×2 → 1 斧头",
    ),
    "brew_potion": Recipe(
        "brew_potion", "炼药", "potion", 1,
        {"apple": 1, "coal": 2},
        description="苹果×1 + 煤×2 → 药水×1",
    ),
}

# 机器合成配方（需要在对应建筑中生产）
MACHINE_RECIPES: Dict[str, Recipe] = {
    "steel": Recipe(
        "steel", "炼钢", "steel", 1,
        {"iron": 2, "coal": 1},
        requires_building="工厂",
        description="铁×2 + 煤×1 → 钢×1 (需工厂)",
    ),
    "gold_bar": Recipe(
        "gold_bar", "铸金币", "gold", 2,
        {"iron": 5},
        requires_building="工厂",
        description="铁×5 → 金币×2 (需工厂)",
    ),
    "advanced_part": Recipe(
        "advanced_part", "精密零件", "key", 1,
        {"steel": 2, "iron": 3},
        requires_building="研究所",
        description="钢×2 + 铁×3 → 钥匙×1 (需研究所)",
    ),
}


def get_craftable(inventory, recipes: Dict[str, Recipe]) -> List[Recipe]:
    """返回当前材料可合成的配方列表"""
    return [r for r in recipes.values() if r.can_craft(inventory)]


def get_craftable_manual(inventory) -> List[Recipe]:
    """返回当前可手动合成的配方"""
    return get_craftable(inventory, MANUAL_RECIPES)

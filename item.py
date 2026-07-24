"""物品系统 - 全部物品定义"""

from typing import Dict, List, Optional


class Item:
    def __init__(self, item_id: str, name: str, icon: str, category: str,
                 description: str = "", stackable: bool = True, max_stack: int = 99):
        self.item_id = item_id
        self.name = name
        self.icon = icon
        self.category = category
        self.description = description
        self.stackable = stackable
        self.max_stack = max_stack

    def __repr__(self):
        return f"<{self.name}>"


ITEM_TEMPLATES: Dict[str, Item] = {
    # ═══════ 基础材料 ═══════
    "wood":     Item("wood",     "木材",  "木", "material", "建造用的基础材料"),
    "stone":    Item("stone",    "石头",  "石", "material", "坚硬的建筑材料"),
    "iron":     Item("iron",     "铁锭",  "铁", "material", "用于制作工具和建筑"),
    "steel":    Item("steel",    "钢材",  "钢", "material", "高级建筑材料"),
    "coal":     Item("coal",     "煤炭",  "C",  "material", "燃料资源"),

    # ═══════ 食物 ═══════
    "bread":    Item("bread",    "面包",  "B", "food", "恢复 20 HP"),
    "apple":    Item("apple",    "苹果",  "A", "food", "恢复 10 HP"),
    "potion":   Item("potion",   "药水",  "P", "food", "恢复 50 HP"),

    # ═══════ 工具 ═══════
    "pickaxe":  Item("pickaxe",  "镐子",  "X", "tool", "采集工具", stackable=False),
    "axe":      Item("axe",      "斧头",  "F", "tool", "砍树工具", stackable=False),

    # ═══════ 特殊 ═══════
    "key":      Item("key",      "钥匙",  "K", "key", "开启特殊建筑", max_stack=5),
    "gold":     Item("gold",     "金币",  "$", "currency", "通用货币", max_stack=9999),

    # ═══════ 科研瓶 ═══════
    "science_red":   Item("science_red",   "红色科研瓶", "R", "science", "自动化科技"),
    "science_green": Item("science_green", "绿色科研瓶", "G", "science", "物流科技"),
    "science_blue":  Item("science_blue",  "蓝色科研瓶", "B", "science", "化工科技"),
    "science_black": Item("science_black", "黑色科研瓶", "K", "science", "军事科技"),
    "science_purple":Item("science_purple","紫色科研瓶", "P", "science", "生产科技"),
    "science_yellow":Item("science_yellow","黄色科研瓶", "Y", "science", "实用科技"),
    "science_white": Item("science_white", "白色科研瓶", "W", "science", "太空科技"),
    "science_metallurgy": Item("science_metallurgy", "冶金科研瓶", "M", "science", "Vulcanus 冶金"),
    "science_em":        Item("science_em", "电磁科研瓶", "E", "science", "Fulgora 电磁"),
    "science_agriculture":Item("science_agriculture","农业科研瓶", "A", "science", "Gleba 农业"),
    "science_cryo":      Item("science_cryo", "低温科研瓶", "C", "science", "Aquilo 低温"),

    # ═══════ DLC 矿物 ═══════
    "tungsten_ore": Item("tungsten_ore", "钨矿石", "W", "ore", "Vulcanus 钨矿"),
    "tungsten":     Item("tungsten",     "钨板",  "T", "material", "高硬度金属"),
    "calcite":      Item("calcite",      "方解石","C", "material", "Vulcanus 熔岩铸造"),
    "holmium_ore":  Item("holmium_ore",  "钬矿石", "H", "ore", "Fulgora 钬矿"),
    "holmium":      Item("holmium",      "钬板",  "H", "material", "超级电容材料"),
    "super_capacitor": Item("super_capacitor", "超级电容", "S", "material", "闪电储电"),
    "lithium_brine":Item("lithium_brine","锂卤水", "L", "liquid", "Aquilo 锂资源"),
    "fluoride":     Item("fluoride",     "氟化物", "F", "material", "Aquilo 化工"),
    "ammonia":      Item("ammonia",      "氨溶液", "A", "liquid", "Aquilo 制冷"),
    "quantum_chip": Item("quantum_chip", "量子处理器","Q", "material", "终极计算元件"),

    # ═══════ 装备 ═══════
    "light_armor":  Item("light_armor",  "轻型护甲","a", "equip", "基础防护", stackable=False),
    "heavy_armor":  Item("heavy_armor",  "重型护甲","A", "equip", "高级防护", stackable=False),
    "laser_defense":Item("laser_defense","激光防御","L", "equip", "自动反击", stackable=False),
    "exoskeleton":  Item("exoskeleton",  "外骨骼",  "E", "equip", "提升移速", stackable=False),
    "rifle":        Item("rifle",        "步枪",   "r", "weapon", "远程武器", stackable=False),
    "rocket_launcher":Item("rocket_launcher","火箭筒","R","weapon","高伤害", stackable=False),
    "flamethrower": Item("flamethrower",  "喷火器", "F", "weapon", "范围伤害", stackable=False),

    # ═══════ 模块 ═══════
    "speed_module_1":  Item("speed_module_1",  "速度模块1","1", "module", "速度+20%"),
    "speed_module_2":  Item("speed_module_2",  "速度模块2","2", "module", "速度+40%"),
    "production_module_1": Item("production_module_1", "产能模块1","+", "module", "产出+10%"),
    "production_module_2": Item("production_module_2", "产能模块2","+", "module", "产出+20%"),
    "quality_module_1":Item("quality_module_1", "品质模块1","*", "module", "品质+10%"),
    "quality_module_2":Item("quality_module_2", "品质模块2","*", "module", "品质+20%"),
    "quality_module_3":Item("quality_module_3", "品质模块3","*", "module", "品质+30%"),

    # ═══════ 弹药 ═══════
    "ammo_magazine": Item("ammo_magazine", "弹匣",  "=", "ammo", "步枪弹药"),
    "rocket":        Item("rocket",        "火箭弹","!", "ammo", "火箭弹药"),

    # ═══════ 原生矿石（地图直接采集） ═══════
    "iron_ore":     Item("iron_ore",     "铁矿石", "铁", "ore_raw", "铁矿脉"),
    "copper_ore":   Item("copper_ore",   "铜矿石", "铜", "ore_raw", "铜矿脉"),
    "uranium_ore":  Item("uranium_ore",  "铀矿石", "U",  "ore_raw", "铀矿脉"),
    "crude_oil":    Item("crude_oil",    "原油",   "O",  "fluid_raw","原油矿脉"),
    "water":        Item("water",        "水",     "W",  "fluid_raw","水源"),
    "lava":         Item("lava",         "熔岩",   "L",  "fluid_raw","熔岩"),
    "oil_sand":     Item("oil_sand",     "油砂",   "S",  "ore_raw", "油砂矿"),
    "scrap":        Item("scrap",        "古代废料","X", "ore_raw", "废墟"),
    "jellynut":     Item("jellynut",     "水母果", "J",  "bio_raw", "Gleba 生物"),
    "yumako":       Item("yumako",       "玉玛果", "Y",  "bio_raw", "Gleba 生物"),
    "iron_bac":     Item("iron_bac",     "铁细菌", "Fe", "bio_raw", "生物炼铁"),
    "copper_bac":   Item("copper_bac",   "铜细菌", "Cu", "bio_raw", "生物炼铜"),
    "nutrient":     Item("nutrient",     "养分",   "N",  "fluid_raw","生物流体"),
    "bioflux":      Item("bioflux",      "生物通量","B", "fluid_raw","Gleba 流体"),
    "lithium_brine":Item("lithium_brine","锂卤水", "Li", "fluid_raw","卤水矿"),
    "ammonia":      Item("ammonia",      "氨水溶液","A", "fluid_raw","氨冰"),
    "fluoride":     Item("fluoride",     "氟化物", "F",  "fluid_raw","氟矿"),

    # ═══════ 建筑道具（可手持放置） ═══════
    "belt_item":  Item("belt_item",  "传送带",  "=", "building", "基础物流，15件/秒"),
    "inserter_item": Item("inserter_item", "机械臂", ")", "building", "基础电力机械臂"),
}


class ItemStack:
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
        can_add = min(amount, self.item.max_stack - self.quantity)
        self.quantity += can_add
        return can_add

    def remove(self, amount: int = 1) -> int:
        actual = min(amount, self.quantity)
        self.quantity -= actual
        return actual

    def can_merge(self, other: "ItemStack") -> bool:
        return (self.item_id == other.item_id
                and self.item.stackable
                and self.quantity < self.item.max_stack)

    def __repr__(self):
        return f"<{self.name} x{self.quantity}>"

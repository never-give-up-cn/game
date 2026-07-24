"""科技树系统 - 消耗物品解锁科技，不能跳级"""

from typing import Dict, List, Optional, Set


class TechNode:
    """科技节点"""

    def __init__(self, node_id: str, name: str, tier: int,
                 description: str,
                 requirements: Dict[str, int],
                 parent_ids: List[str] = None,
                 unlocks: Dict[str, object] = None):
        self.node_id = node_id
        self.name = name
        self.tier = tier
        self.description = description
        self.requirements = requirements
        self.parent_ids = parent_ids or []
        self.unlocks = unlocks or {}
        self.unlocked = False

    def can_unlock(self, inventory, unlocked_set: Set[str]) -> bool:
        if self.unlocked:
            return False
        for pid in self.parent_ids:
            if pid not in unlocked_set:
                return False
        for item_id, amount in self.requirements.items():
            if inventory.count(item_id) < amount:
                return False
        return True

    def unlock(self, inventory) -> bool:
        if self.unlocked:
            return False
        for item_id, amount in self.requirements.items():
            inventory.remove_item(item_id, amount)
        self.unlocked = True
        return True

    def __repr__(self):
        status = "✓" if self.unlocked else f"T{self.tier}"
        return f"[{status}] {self.name}"


# ========== 科技树定义 ==========

TECH_NODES: Dict[str, TechNode] = {}

def _reg(node: TechNode):
    TECH_NODES[node.node_id] = node


# Tier 1
_reg(TechNode("basic_plugins", "基础插件",
    1, "解锁建筑第 1 个插件槽", {"iron": 10, "wood": 5}, [],
    {"plugin_tier": 1, "efficiency_bonus": 0}))

# Tier 2 — 前置: basic_plugins
_reg(TechNode("efficiency_up", "效率提升",
    2, "建筑生产效率 +20%", {"steel": 5, "iron": 5}, ["basic_plugins"],
    {"efficiency_bonus": 0.2}))

_reg(TechNode("speed_up", "速度提升",
    2, "生产速度 +20%", {"steel": 5, "coal": 5}, ["basic_plugins"],
    {"speed_bonus": 0.2}))

_reg(TechNode("mid_plugins", "中级插件",
    2, "解锁建筑第 2 个插件槽", {"steel": 5, "iron": 10}, ["basic_plugins"],
    {"plugin_tier": 2}))

# Tier 3 — 前置: mid_plugins / efficiency_up + speed_up
_reg(TechNode("adv_plugins", "高级插件",
    3, "解锁建筑第 3 个插件槽", {"steel": 10, "key": 2}, ["mid_plugins"],
    {"plugin_tier": 3}))

_reg(TechNode("quality_up", "质量提升",
    3, "产品质量 +30%", {"steel": 8, "key": 2, "gold": 5},
    ["efficiency_up", "speed_up"],
    {"quality_bonus": 0.3}))

# Tier 4 — 前置: adv_plugins / quality_up
_reg(TechNode("ultra_plugins", "终极插件",
    4, "解锁建筑第 4 个插件槽", {"gold": 10, "key": 5, "steel": 20},
    ["adv_plugins"],
    {"plugin_tier": 4}))

_reg(TechNode("max_efficiency", "极限效率",
    4, "效率 +50%，速度 +50%", {"gold": 15, "key": 8, "steel": 30},
    ["quality_up"],
    {"efficiency_bonus": 0.5, "speed_bonus": 0.5}))


# ========== 查询 ==========

def get_tier(tier: int) -> List[TechNode]:
    return [n for n in TECH_NODES.values() if n.tier == tier]


def get_available(inventory, unlocked_set: Set[str]) -> List[TechNode]:
    return [n for n in TECH_NODES.values()
            if n.can_unlock(inventory, unlocked_set)]


def get_unlocked_set() -> Set[str]:
    return {nid for nid, n in TECH_NODES.items() if n.unlocked}


def max_plugin_tier(unlocked_set: Set[str]) -> int:
    """返回当前科技允许的最高插件等级"""
    best = 0
    for nid in unlocked_set:
        n = TECH_NODES.get(nid)
        if n and n.unlocked:
            best = max(best, n.unlocks.get("plugin_tier", 0))
    return best


def get_building_bonuses(unlocked_set: Set[str]) -> dict:
    """汇总已解锁科技对建筑的加成"""
    bonuses = {"efficiency": 0, "speed": 0, "quality": 0}
    for nid in unlocked_set:
        n = TECH_NODES.get(nid)
        if n and n.unlocked:
            bonuses["efficiency"] += n.unlocks.get("efficiency_bonus", 0)
            bonuses["speed"] += n.unlocks.get("speed_bonus", 0)
            bonuses["quality"] += n.unlocks.get("quality_bonus", 0)
    return bonuses

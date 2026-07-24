"""科技树系统 - 科研瓶 + 研究队列"""

from typing import Dict, List, Optional, Set, Tuple


class TechNode:
    """科技节点"""

    def __init__(self, node_id: str, name: str, tier: int,
                 description: str,
                 requirements: Dict[str, int],
                 parent_ids: List[str] = None,
                 unlocks: Dict[str, object] = None,
                 science_packs: Dict[str, int] = None,
                 rewards: str = ""):
        self.node_id = node_id
        self.name = name
        self.tier = tier
        self.description = description
        self.requirements = requirements       # 解锁消耗物品
        self.parent_ids = parent_ids or []
        self.unlocks = unlocks or {}
        self.science_packs = science_packs or {}  # {science_type: count}
        self.rewards = rewards                 # 解锁内容描述
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

    def has_science(self, inventory) -> bool:
        """检查是否有足够的科研瓶"""
        for sid, cnt in self.science_packs.items():
            if inventory.count(sid) < cnt:
                return False
        return True

    def consume_science(self, inventory) -> bool:
        """消耗科研瓶"""
        for sid, cnt in self.science_packs.items():
            if inventory.count(sid) < cnt:
                return False
        for sid, cnt in self.science_packs.items():
            inventory.remove_item(sid, cnt)
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


# ========== 研究队列 ==========

class ResearchQueue:
    """研究队列 - 管理正在研究和排队中的科技"""

    def __init__(self):
        self.queue: List[str] = []          # 排队科技 ID 列表
        self.current: Optional[str] = None  # 当前研究
        self.progress: float = 0.0          # 0.0~1.0

    def add(self, tech_id: str):
        """添加到队列"""
        if tech_id not in self.queue and tech_id != self.current:
            self.queue.append(tech_id)

    def remove(self, tech_id: str):
        """从队列移除"""
        if tech_id in self.queue:
            self.queue.remove(tech_id)

    def start_next(self):
        """开始队列中的下一个"""
        if self.queue:
            self.current = self.queue.pop(0)
            self.progress = 0.0

    def clear(self):
        self.queue.clear()
        self.current = None
        self.progress = 0.0

    @property
    def current_node(self):
        if self.current:
            return TECH_NODES.get(self.current)
        return None

    def __repr__(self):
        return f"<Queue: current={self.current} pending={len(self.queue)}>"


# ========== 科技树定义 ==========

TECH_NODES: Dict[str, TechNode] = {}

def _reg(node: TechNode):
    TECH_NODES[node.node_id] = node


# Tier 1 基础 - 红色科研瓶
_reg(TechNode("basic_plugins", "基础插件", 1,
    "解锁建筑第 1 个插件槽", {"iron": 10, "wood": 5}, [],
    {"plugin_tier": 1},
    science_packs={"science_red": 10},
    rewards="插件槽 Lv.1"))

# Tier 2 - 绿色科研瓶
_reg(TechNode("efficiency_up", "效率提升", 2,
    "建筑生产效率 +20%", {"steel": 5, "iron": 5}, ["basic_plugins"],
    {"efficiency_bonus": 0.2},
    science_packs={"science_green": 15},
    rewards="效率 +20%"))

_reg(TechNode("speed_up", "速度提升", 2,
    "生产速度 +20%", {"steel": 5, "coal": 5}, ["basic_plugins"],
    {"speed_bonus": 0.2},
    science_packs={"science_green": 15},
    rewards="速度 +20%"))

_reg(TechNode("mid_plugins", "中级插件", 2,
    "解锁建筑第 2 个插件槽", {"steel": 5, "iron": 10}, ["basic_plugins"],
    {"plugin_tier": 2},
    science_packs={"science_green": 20},
    rewards="插件槽 Lv.2"))

# Tier 3 - 蓝色科研瓶
_reg(TechNode("adv_plugins", "高级插件", 3,
    "解锁建筑第 3 个插件槽", {"steel": 10, "key": 2}, ["mid_plugins"],
    {"plugin_tier": 3},
    science_packs={"science_blue": 25},
    rewards="插件槽 Lv.3"))

_reg(TechNode("quality_up", "质量提升", 3,
    "产品质量 +30%", {"steel": 8, "key": 2, "gold": 5},
    ["efficiency_up", "speed_up"],
    {"quality_bonus": 0.3},
    science_packs={"science_blue": 20},
    rewards="质量 +30%"))

# Tier 4 - 紫色/黄色科研瓶
_reg(TechNode("ultra_plugins", "终极插件", 4,
    "解锁建筑第 4 个插件槽", {"gold": 10, "key": 5, "steel": 20},
    ["adv_plugins"],
    {"plugin_tier": 4},
    science_packs={"science_purple": 30, "science_yellow": 15},
    rewards="插件槽 Lv.4"))

_reg(TechNode("max_efficiency", "极限效率", 4,
    "效率 +50%，速度 +50%", {"gold": 15, "key": 8, "steel": 30},
    ["quality_up"],
    {"efficiency_bonus": 0.5, "speed_bonus": 0.5},
    science_packs={"science_purple": 40, "science_yellow": 20},
    rewards="效率+50% 速度+50%"))


# ========== 查询函数 ==========

def get_tier(tier: int) -> List[TechNode]:
    return [n for n in TECH_NODES.values() if n.tier == tier]


def get_available(inventory, unlocked_set: Set[str]) -> List[TechNode]:
    return [n for n in TECH_NODES.values()
            if n.can_unlock(inventory, unlocked_set)]


def get_unlocked_set() -> Set[str]:
    return {nid for nid, n in TECH_NODES.items() if n.unlocked}


def max_plugin_tier(unlocked_set: Set[str]) -> int:
    best = 0
    for nid in unlocked_set:
        n = TECH_NODES.get(nid)
        if n and n.unlocked:
            best = max(best, n.unlocks.get("plugin_tier", 0))
    return best


def get_building_bonuses(unlocked_set: Set[str]) -> dict:
    bonuses = {"efficiency": 0, "speed": 0, "quality": 0}
    for nid in unlocked_set:
        n = TECH_NODES.get(nid)
        if n and n.unlocked:
            bonuses["efficiency"] += n.unlocks.get("efficiency_bonus", 0)
            bonuses["speed"] += n.unlocks.get("speed_bonus", 0)
            bonuses["quality"] += n.unlocks.get("quality_bonus", 0)
    return bonuses

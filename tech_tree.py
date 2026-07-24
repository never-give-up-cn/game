"""完整科技树 - 11种科研瓶 × 5星球主线"""

from typing import Dict, List, Optional, Set


class TechNode:
    def __init__(self, node_id, name, tier, description, requirements,
                 parent_ids=None, unlocks=None, science_packs=None, rewards=""):
        self.node_id = node_id
        self.name = name
        self.tier = tier
        self.description = description
        self.requirements = requirements
        self.parent_ids = parent_ids or []
        self.unlocks = unlocks or {}
        self.science_packs = science_packs or {}
        self.rewards = rewards
        self.unlocked = False

    def can_unlock(self, inventory, unlocked_set):
        if self.unlocked:
            return False
        for pid in self.parent_ids:
            if pid not in unlocked_set:
                return False
        for iid, amt in self.requirements.items():
            if inventory.count(iid) < amt:
                return False
        return True

    def consume_science(self, inventory):
        for sid, cnt in self.science_packs.items():
            if inventory.count(sid) < cnt:
                return False
        for sid, cnt in self.science_packs.items():
            inventory.remove_item(sid, cnt)
        return True

    def unlock(self, inventory):
        if self.unlocked:
            return False
        for iid, amt in self.requirements.items():
            inventory.remove_item(iid, amt)
        self.unlocked = True
        return True

    def __repr__(self):
        return f"[{'✓' if self.unlocked else 'T'+str(self.tier)}] {self.name}"


class ResearchQueue:
    def __init__(self):
        self.queue: List[str] = []
        self.current: Optional[str] = None
        self.progress: float = 0.0

    def add(self, tech_id):
        if tech_id not in self.queue and tech_id != self.current:
            self.queue.append(tech_id)

    def remove(self, tech_id):
        if tech_id in self.queue:
            self.queue.remove(tech_id)

    def start_next(self):
        if self.queue:
            self.current = self.queue.pop(0)
            self.progress = 0.0

    def clear(self):
        self.queue.clear()
        self.current = None
        self.progress = 0.0

    @property
    def current_node(self):
        return TECH_NODES.get(self.current)


TECH_NODES: Dict[str, TechNode] = {}

def _reg(n):
    TECH_NODES[n.node_id] = n

# ════════════ 阶段 1: 红瓶（自动化） ════════════
_reg(TechNode("automation_1", "自动化 1", 1, "解锁组装机1、基础电路", {},
    science_packs={"science_red": 10}, rewards="组装机1"))
_reg(TechNode("electronics", "电子学", 1, "铜线、电路板", {"iron": 5}, ["automation_1"],
    science_packs={"science_red": 10}, rewards="电路板"))
_reg(TechNode("steam_power", "蒸汽机", 1, "锅炉、蒸汽发电", {"stone": 10}, ["electronics"],
    science_packs={"science_red": 15}, rewards="锅炉+蒸汽机"))
_reg(TechNode("automation_2", "自动化 2", 1, "组装机2", {"iron": 10, "steel": 5}, ["steam_power"],
    science_packs={"science_red": 20}, rewards="组装机2"))
_reg(TechNode("basic_plugins", "基础插件", 1, "解锁建筑第1个插件槽", {"iron": 10, "wood": 5},
    ["electronics"], {"plugin_tier": 1}, {"science_red": 15}, "插件槽 Lv.1"))

# ════════════ 阶段 2: 绿瓶（物流） ════════════
_reg(TechNode("logistics_1", "物流学 1", 2, "黄传送带、电力机械臂", {"iron": 10}, ["basic_plugins"],
    science_packs={"science_green": 15}, rewards="传送带+黄爪"))
_reg(TechNode("logistics_2", "物流学 2", 2, "红传送带、加长机械臂、分流器", {"steel": 5}, ["logistics_1"],
    science_packs={"science_green": 20}, rewards="红带+红爪"))
_reg(TechNode("sorter_tech", "分拣技术", 2, "筛选机械臂", {"iron": 10}, ["logistics_1"],
    science_packs={"science_green": 20}, rewards="筛选机械臂"))
_reg(TechNode("stack_sorter", "堆叠分拣", 2, "集装机械臂系列", {"steel": 10}, ["logistics_2", "sorter_tech"],
    science_packs={"science_green": 30}, rewards="集装爪"))
_reg(TechNode("efficiency_up", "效率提升", 2, "建筑效率+20%", {"steel": 5, "iron": 5}, ["logistics_1"],
    {"efficiency_bonus": 0.2}, {"science_green": 15}, "效率+20%"))
_reg(TechNode("speed_up", "速度提升", 2, "生产速度+20%", {"steel": 5, "coal": 5}, ["logistics_1"],
    {"speed_bonus": 0.2}, {"science_green": 15}, "速度+20%"))
_reg(TechNode("mid_plugins", "中级插件", 2, "插件槽 Lv.2", {"steel": 5, "iron": 10}, ["logistics_1"],
    {"plugin_tier": 2}, {"science_green": 20}, "插件槽 Lv.2"))

# ════════════ 阶段 3: 黑瓶（军事） ════════════
_reg(TechNode("military_1", "军备", 2, "机枪炮塔、石墙", {"iron": 10}, ["logistics_1"],
    science_packs={"science_black": 15}, rewards="炮塔+城墙"))
_reg(TechNode("military_2", "进阶军备", 2, "激光炮塔、火箭炮塔", {"steel": 10}, ["military_1"],
    science_packs={"science_black": 25}, rewards="激光+火箭炮塔"))

# ════════════ 阶段 4: 蓝瓶（化工） ════════════
_reg(TechNode("oil_proc", "石油开采", 3, "炼油厂、管道、泵", {"steel": 10}, ["automation_2"],
    science_packs={"science_blue": 20}, rewards="炼油"))
_reg(TechNode("fluid_handling", "流体处理", 3, "管道、储液罐、泵", {"iron": 5}, ["oil_proc"],
    science_packs={"science_blue": 15}, rewards="储液罐"))
_reg(TechNode("logistics_3", "物流学 3", 3, "蓝传送带、高速机械臂", {"steel": 10}, ["logistics_2"],
    science_packs={"science_blue": 25}, rewards="蓝带+蓝爪"))
_reg(TechNode("circuit_net", "电路网络", 3, "信号线、组合器", {"steel": 5, "key": 2}, ["oil_proc"],
    science_packs={"science_blue": 20}, rewards="红绿信号线"))
_reg(TechNode("battery", "电池+太阳能", 3, "电池、太阳能板", {"steel": 8}, ["oil_proc"],
    science_packs={"science_blue": 20}, rewards="太阳能"))
_reg(TechNode("adv_plugins", "高级插件", 3, "插件槽 Lv.3", {"steel": 10, "key": 2}, ["mid_plugins"],
    {"plugin_tier": 3}, {"science_blue": 25}, "插件槽 Lv.3"))

# ════════════ 阶段 5: 紫瓶（生产） ════════════
_reg(TechNode("electric_furnace", "电力冶金", 3, "电熔炉", {"steel": 15, "key": 3}, ["logistics_3"],
    science_packs={"science_purple": 30}, rewards="电熔炉"))
_reg(TechNode("module_1", "模块 1", 3, "速度/产能/节能模块1", {"steel": 10}, ["circuit_net"],
    science_packs={"science_purple": 25}, rewards="模块1"))
_reg(TechNode("module_2", "模块 2", 3, "模块2", {"steel": 15, "key": 5}, ["module_1"],
    science_packs={"science_purple": 35}, rewards="模块2"))
_reg(TechNode("railway", "铁路系统", 3, "铁轨、信号灯、火车站", {"steel": 20}, ["electric_furnace"],
    science_packs={"science_purple": 30}, rewards="铁路"))

# ════════════ 阶段 6: 黄瓶（实用） ════════════
_reg(TechNode("logistic_robot", "物流机器人", 4, "物流机器人平台+机器人", {"steel": 15, "key": 5},
    ["railway"], science_packs={"science_yellow": 40}, rewards="物流机器人"))
_reg(TechNode("construction_robot", "建造机器人", 4, "建造机器人", {"steel": 15, "key": 3},
    ["railway"], science_packs={"science_yellow": 35}, rewards="建造机器人"))
_reg(TechNode("nuclear", "核动力", 4, "核电站、铀处理", {"steel": 25, "key": 8}, ["module_2"],
    science_packs={"science_yellow": 50}, rewards="核电站"))
_reg(TechNode("quality_up", "质量提升", 4, "产品质量+30%", {"steel": 8, "key": 2, "gold": 5},
    ["efficiency_up", "speed_up"], {"quality_bonus": 0.3},
    {"science_yellow": 35}, "质量+30%"))

# ════════════ 阶段 7: 白瓶（太空） ════════════
_reg(TechNode("rocket", "火箭技术", 4, "火箭发射井、卫星", {"steel": 30, "key": 10, "gold": 20},
    ["nuclear", "logistic_robot"], science_packs={"science_white": 60}, rewards="火箭"))
_reg(TechNode("space_platform", "太空平台", 4, "太空平台框架、舱室", {"steel": 40, "key": 15},
    ["rocket"], science_packs={"science_white": 80}, rewards="太空平台"))
_reg(TechNode("ultra_plugins", "终极插件", 4, "插件槽 Lv.4", {"gold": 10, "key": 5, "steel": 20},
    ["adv_plugins"], {"plugin_tier": 4}, {"science_yellow": 40}, "插件槽 Lv.4"))

# ════════════ 阶段 8: 冶金（Vulcanus） ════════════
_reg(TechNode("tungsten_mining", "钨矿开采", 5, "钨矿加工、方解石", {"steel": 30, "key": 10},
    ["space_platform"], science_packs={"science_metallurgy": 50}, rewards="钨矿+方解石"))
_reg(TechNode("foundry", "铸造厂", 5, "大型铸造厂", {"steel": 40, "key": 15}, ["tungsten_mining"],
    science_packs={"science_metallurgy": 60}, rewards="铸造厂"))
_reg(TechNode("turbo_belt", "涡轮传送带", 5, "涡轮级传送带(60/s)", {"steel": 35, "key": 10},
    ["tungsten_mining"], science_packs={"science_metallurgy": 55}, rewards="涡轮传送带"))
_reg(TechNode("big_miner", "大型采矿钻机", 5, "大型采矿钻机", {"steel": 40, "key": 12},
    ["tungsten_mining"], science_packs={"science_metallurgy": 50}, rewards="大型采矿机"))

# ════════════ 阶段 9: 电磁（Fulgora） ════════════
_reg(TechNode("holmium_proc", "钬矿加工", 5, "钬矿、超级电容", {"steel": 30, "key": 10},
    ["space_platform"], science_packs={"science_em": 50}, rewards="钬矿+电容"))
_reg(TechNode("lightning_collect", "闪电收集", 5, "避雷针、闪电收集器", {"steel": 25, "key": 8},
    ["holmium_proc"], science_packs={"science_em": 50}, rewards="闪电发电"))
_reg(TechNode("em_factory", "电磁工厂", 5, "电磁工厂（增产）", {"steel": 40, "key": 15},
    ["holmium_proc"], science_packs={"science_em": 60}, rewards="电磁工厂"))
_reg(TechNode("tesla_turret", "特斯拉炮塔", 5, "特斯拉炮塔", {"steel": 30, "key": 10},
    ["holmium_proc"], science_packs={"science_em": 45}, rewards="特斯拉炮塔"))
_reg(TechNode("quality_3", "品质模块 3", 5, "品质模块3", {"steel": 35, "key": 12, "gold": 10},
    ["lightning_collect"], science_packs={"science_em": 55}, rewards="品质模块3"))

# ════════════ 阶段 10: 农业（Gleba） ════════════
_reg(TechNode("bio_chamber", "生物培养", 5, "生物舱、养分系统", {"steel": 30, "key": 10},
    ["space_platform"], science_packs={"science_agriculture": 50}, rewards="生物舱"))
_reg(TechNode("spoilage_mgmt", "腐败管理", 5, "物品保质期管理", {"steel": 20}, ["bio_chamber"],
    science_packs={"science_agriculture": 40}, rewards="腐败管理"))
_reg(TechNode("spidertron", "蜘蛛机甲", 5, "蜘蛛机甲", {"steel": 45, "key": 15, "gold": 20},
    ["bio_chamber"], science_packs={"science_agriculture": 65}, rewards="蜘蛛机甲"))
_reg(TechNode("rocket_turret", "火箭炮塔", 5, "火箭炮塔进阶", {"steel": 35, "key": 12},
    ["spoilage_mgmt"], science_packs={"science_agriculture": 55}, rewards="火箭炮塔"))

# ════════════ 阶段 11: 低温（Aquilo） ════════════
_reg(TechNode("lithium_proc", "锂氟处理", 5, "锂卤水、氟化物、氨", {"steel": 40, "key": 15},
    ["space_platform"], science_packs={"science_cryo": 60}, rewards="锂/氟/氨"))
_reg(TechNode("heat_tower", "供热塔", 5, "供热塔防冻", {"steel": 35, "key": 10}, ["lithium_proc"],
    science_packs={"science_cryo": 50}, rewards="供热塔"))
_reg(TechNode("fusion_reactor", "聚变反应堆", 5, "终极电源", {"steel": 60, "key": 20, "gold": 30},
    ["heat_tower"], science_packs={"science_cryo": 80}, rewards="聚变堆"))
_reg(TechNode("railgun", "轨道炮炮塔", 5, "轨道炮炮塔", {"steel": 50, "key": 18, "gold": 25},
    ["lithium_proc"], science_packs={"science_cryo": 70}, rewards="轨道炮"))
_reg(TechNode("quantum_proc", "量子处理器", 5, "量子处理器", {"steel": 55, "key": 22, "gold": 35},
    ["fusion_reactor"], science_packs={"science_cryo": 90}, rewards="量子处理器"))
_reg(TechNode("max_efficiency", "极限效率", 5, "效率+50% 速度+50%", {"gold": 15, "key": 8, "steel": 30},
    ["quality_up"], {"efficiency_bonus": 0.5, "speed_bonus": 0.5},
    {"science_cryo": 60}, "极限效率"))


# ========== 查询 ==========

def get_tier(tier):
    return [n for n in TECH_NODES.values() if n.tier == tier]

def get_available(inventory, unlocked_set):
    return [n for n in TECH_NODES.values() if n.can_unlock(inventory, unlocked_set)]

def get_unlocked_set():
    return {nid for nid, n in TECH_NODES.items() if n.unlocked}

def max_plugin_tier(unlocked_set):
    best = 0
    for nid in unlocked_set:
        n = TECH_NODES.get(nid)
        if n and n.unlocked:
            best = max(best, n.unlocks.get("plugin_tier", 0))
    return best

def get_building_bonuses(unlocked_set):
    bonuses = {"efficiency": 0, "speed": 0, "quality": 0}
    for nid in unlocked_set:
        n = TECH_NODES.get(nid)
        if n and n.unlocked:
            bonuses["efficiency"] += n.unlocks.get("efficiency_bonus", 0)
            bonuses["speed"] += n.unlocks.get("speed_bonus", 0)
            bonuses["quality"] += n.unlocks.get("quality_bonus", 0)
    return bonuses

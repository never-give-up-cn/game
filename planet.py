"""星球系统 - Nauvis → Vulcanus → Fulgora → Gleba → Aquilo"""

from typing import Dict, List, Optional


class Planet:
    """星球定义"""

    def __init__(self, pid: str, name: str, description: str,
                 order: int, resources: List[str], buildings: List[str],
                 science_packs: List[str], hazard: str = ""):
        self.pid = pid
        self.name = name
        self.description = description
        self.order = order          # 探索顺序
        self.resources = resources  # 特有资源
        self.buildings = buildings  # 特有建筑
        self.science_packs = science_packs  # 产出的科研瓶
        self.hazard = hazard        # 环境威胁
        self.unlocked: bool = False

    def __repr__(self):
        status = "✓" if self.unlocked else "🔒"
        return f"[{status}] {self.name}"


# 星球列表（按探索顺序）
PLANETS: Dict[str, Planet] = {
    "nauvis": Planet("nauvis", "Nauvis", "起始母星，虫群威胁",
        order=0,
        resources=["铁矿石", "铜矿石", "煤炭", "石头", "原油", "铀矿"],
        buildings=["组装机", "熔炉", "锅炉", "蒸汽机", "化工厂"],
        science_packs=["science_red", "science_green", "science_blue",
                       "science_black", "science_purple", "science_yellow", "science_white"],
        hazard="虫群袭击"),

    "vulcanus": Planet("vulcanus", "Vulcanus", "熔岩行星，高温无水源",
        order=1,
        resources=["钨矿石", "方解石", "熔岩", "硫磺"],
        buildings=["铸造厂", "大型采矿钻机", "涡轮传送带"],
        science_packs=["science_metallurgy"],
        hazard="熔岩蠕虫 BOSS"),

    "fulgora": Planet("fulgora", "Fulgora", "闪电废土，无天然水源",
        order=2,
        resources=["钬矿石", "古代废墟废料", "油砂"],
        buildings=["电磁工厂", "闪电收集器", "回收机", "特斯拉炮塔"],
        science_packs=["science_em"],
        hazard="雷击 + 电弧虫"),

    "gleba": Planet("gleba", "Gleba", "真菌生物星球，物品会腐败",
        order=3,
        resources=["水母果", "玉玛果", "生物通量"],
        buildings=["生物舱", "蜘蛛机甲", "火箭炮塔"],
        science_packs=["science_agriculture"],
        hazard="五足虫 + 物品腐败"),

    "aquilo": Planet("aquilo", "Aquilo", "极寒氨冰行星，需供热防冻",
        order=4,
        resources=["锂卤水", "氟化物", "氨水溶液", "氨冰"],
        buildings=["低温工厂", "供热塔", "聚变反应堆", "轨道炮炮塔"],
        science_packs=["science_cryo"],
        hazard="极寒持续降温"),
}


def get_current_planet(unlocked_science_types: set) -> Planet:
    """根据已解锁的科研瓶类型返回当前所在星球"""
    for p in sorted(PLANETS.values(), key=lambda x: x.order, reverse=True):
        for sp in p.science_packs:
            if sp.replace("science_", "") in unlocked_science_types or sp in unlocked_science_types:
                return p
    return PLANETS["nauvis"]


def unlock_planet(pid: str):
    if pid in PLANETS:
        PLANETS[pid].unlocked = True

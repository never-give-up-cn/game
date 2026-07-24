"""资源生成系统 - 无限地图 + 按星球区域自动生成矿物"""

import random
import math
from typing import Dict, List, Tuple, Optional


# 每星球原始资源定义（地图上直接采集，不含冶炼半成品）
PLANET_RESOURCES = {
    "nauvis": {
        "solid": [
            ("iron_ore",    "铁矿石",  "铁",  "ore", 60),
            ("copper_ore",  "铜矿石",  "铜",  "ore", 50),
            ("coal",        "煤炭",    "C",   "ore", 40),
            ("stone",       "石头",    "石",  "ore", 35),
            ("uranium_ore", "铀矿石",  "U",   "ore", 5),
        ],
        "fluid": [
            ("water",       "水",      "W",   "fluid", 99999),
            ("crude_oil",   "原油",    "O",   "fluid", 80),
        ],
        "biological": [
            ("wood",        "木材",    "木",  "bio",  20),
        ],
        "special": [],
    },
    "vulcanus": {
        "solid": [
            ("tungsten_ore","钨矿石",  "W",   "ore", 40),
            ("calcite",     "方解石",  "C",   "ore", 30),
            ("iron_ore",    "铁矿石",  "铁",  "ore", 15),
            ("copper_ore",  "铜矿石",  "铜",  "ore", 10),
        ],
        "fluid": [
            ("lava",        "熔岩",    "L",   "fluid", 99999),
        ],
        "biological": [],
        "special": [],
    },
    "fulgora": {
        "solid": [
            ("holmium_ore", "钬矿石",  "H",   "ore", 35),
            ("oil_sand",    "油砂",    "S",   "ore", 25),
            ("scrap",       "古代废料","X",   "ore", 20),
        ],
        "fluid": [],
        "biological": [],
        "special": ["lightning"],
    },
    "gleba": {
        "solid": [
            ("stone",       "石头",    "石",  "ore", 20),
        ],
        "fluid": [
            ("nutrient",    "养分",    "N",   "fluid", 50),
            ("bioflux",     "生物通量","B",   "fluid", 30),
        ],
        "biological": [
            ("jellynut",    "水母果",  "J",   "bio", 30),
            ("yumako",      "玉玛果",  "Y",   "bio", 30),
            ("iron_bac",    "铁细菌",  "Fe",  "bio", 25),
            ("copper_bac",  "铜细菌",  "Cu",  "bio", 25),
        ],
        "special": ["spoilage"],
    },
    "aquilo": {
        "solid": [],
        "fluid": [
            ("lithium_brine","锂卤水", "Li",  "fluid", 60),
            ("ammonia",     "氨水溶液","A",   "fluid", 99999),
            ("fluoride",    "氟化物",  "F",   "fluid", 40),
            ("crude_oil",   "原油",    "O",   "fluid", 20),
        ],
        "biological": [],
        "special": ["cryogenic"],
    },
}


class ResourceNode:
    """地图上的资源节点（矿脉/流体/生物）"""

    def __init__(self, x: int, y: int, item_id: str, name: str, icon: str,
                 category: str, max_amount: float, planet: str):
        self.x = x
        self.y = y
        self.item_id = item_id
        self.name = name
        self.icon = icon
        self.category = category  # 'ore', 'fluid', 'bio'
        self.max_amount = max_amount
        self.amount = max_amount
        self.planet = planet
        self.size = random.randint(2, 5)  # 矿脉占地 2~5 格

    @property
    def is_depleted(self) -> bool:
        return self.amount <= 0

    def mine(self, amount: float = 1.0) -> float:
        """开采，返回实际获得量"""
        taken = min(amount, self.amount)
        self.amount -= taken
        return taken

    def get_occupied_cells(self) -> List[Tuple[int, int]]:
        cells = []
        for dx in range(-self.size // 2, self.size // 2 + 1):
            for dy in range(-self.size // 2, self.size // 2 + 1):
                cells.append((self.x + dx, self.y + dy))
        return cells

    def __repr__(self):
        return f"<{self.name} ({self.x},{self.y}) {self.amount:.0f}/{self.max_amount:.0f}>"


def get_planet_at(x: int, y: int) -> str:
    """根据坐标返回所在星球区域"""
    # 地图分区:
    # (0,0) 附近 = Nauvis
    # 往右 (x > 200) = Vulcanus
    # 往下 (y > 200) = Fulgora
    # 往右下 (x > 200, y > 200) = Gleba
    # 往更远 (x > 400, y > 400) = Aquilo
    # 太空空域 (高空): y < -100
    if y < -100:
        return "space"
    if x >= 400 and y >= 400:
        return "aquilo"
    if x >= 200 and y >= 200:
        return "gleba"
    if y >= 200:
        return "fulgora"
    if x >= 200:
        return "vulcanus"
    return "nauvis"


def generate_resources(center_x: int, center_y: int, radius: int = 50) -> List[ResourceNode]:
    """在指定区域周围生成资源节点"""
    random.seed((center_x // 50) * 10000 + (center_y // 50))
    nodes = []
    planet = get_planet_at(center_x, center_y)
    res_defs = PLANET_RESOURCES.get(planet, PLANET_RESOURCES["nauvis"])

    # 固态矿脉
    for res_def in res_defs.get("solid", []):
        count = random.randint(2, 5)
        for _ in range(count):
            rx = center_x + random.randint(-radius, radius)
            ry = center_y + random.randint(-radius, radius)
            nodes.append(ResourceNode(rx, ry, *res_def, planet))

    # 流体资源
    for res_def in res_defs.get("fluid", []):
        count = random.randint(1, 3)
        for _ in range(count):
            rx = center_x + random.randint(-radius, radius)
            ry = center_y + random.randint(-radius, radius)
            nodes.append(ResourceNode(rx, ry, *res_def, planet))

    # 生物资源
    for res_def in res_defs.get("biological", []):
        count = random.randint(3, 8)
        for _ in range(count):
            rx = center_x + random.randint(-radius, radius)
            ry = center_y + random.randint(-radius, radius)
            nodes.append(ResourceNode(rx, ry, *res_def, planet))

    return nodes


class ResourceManager:
    """全局资源管理器 - 管理所有资源节点"""

    def __init__(self):
        self.nodes: Dict[Tuple[int, int], ResourceNode] = {}
        self.seen_chunks: set = set()

    def get_node_at(self, x: int, y: int) -> Optional[ResourceNode]:
        """获取某坐标上的资源节点"""
        for (nx, ny), node in self.nodes.items():
            cells = node.get_occupied_cells()
            if (x, y) in cells:
                return node
        return None

    def ensure_chunk(self, cx: int, cy: int):
        """确保某区块已生成资源"""
        chunk_key = (cx // 50, cy // 50)
        if chunk_key in self.seen_chunks:
            return
        self.seen_chunks.add(chunk_key)
        new_nodes = generate_resources(cx, cy)
        for node in new_nodes:
            key = (node.x, node.y)
            if key not in self.nodes:
                self.nodes[key] = node

    def mine_at(self, x: int, y: int, amount: float = 1.0) -> Tuple[Optional[str], float]:
        """在坐标处开采资源，返回 (item_id, amount_taken)"""
        node = self.get_node_at(x, y)
        if node and not node.is_depleted:
            taken = node.mine(amount)
            if taken > 0:
                return node.item_id, taken
        return None, 0

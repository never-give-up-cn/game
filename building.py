"""建筑系统 - 在地图上占据格子的物体"""

from typing import Dict, Any, Optional


BUILDING_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "工厂": {
        "name": "工厂",
        "width": 2,
        "height": 2,
        "color": "blue",
        "description": "生产建筑，占地 2×2",
    },
    "住宅": {
        "name": "住宅",
        "width": 1,
        "height": 1,
        "color": "green",
        "description": "居住建筑，占地 1×1",
    },
    "仓库": {
        "name": "仓库",
        "width": 2,
        "height": 1,
        "color": "yellow",
        "description": "存储建筑，占地 2×1",
    },
    "研究所": {
        "name": "研究所",
        "width": 2,
        "height": 2,
        "color": "cyan",
        "description": "科技建筑，占地 2×2",
    },
    "城墙": {
        "name": "城墙",
        "width": 3,
        "height": 1,
        "color": "gray",
        "description": "防御建筑，占地 3×1",
    },
}


class Building:
    """建筑，在地图上占据一个矩形区域"""

    def __init__(self, x: int, y: int, template_name: str):
        template = BUILDING_TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"未知建筑模板: {template_name}")
        self.x = x
        self.y = y
        self.w = template["width"]
        self.h = template["height"]
        self.name = template["name"]
        self.color = template["color"]
        self.description = template["description"]
        self.template_name = template_name

    @property
    def occupied_cells(self):
        """返回建筑占用的所有格子坐标列表"""
        cells = []
        for dx in range(self.w):
            for dy in range(self.h):
                cells.append((self.x + dx, self.y + dy))
        return cells

    @property
    def center(self) -> tuple:
        """建筑中心坐标"""
        return (self.x + self.w // 2, self.y + self.h // 2)

    @staticmethod
    def list_templates() -> Dict[str, str]:
        """列出所有建筑模板供用户选择"""
        return {
            name: f"{t['description']} ({t['width']}×{t['height']})"
            for name, t in BUILDING_TEMPLATES.items()
        }

    def __repr__(self):
        return f"<{self.name} ({self.x},{self.y}) {self.w}×{self.h}>"

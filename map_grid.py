"""2D 网格地图系统 - 按格子定位"""

from enum import Enum
from typing import List, Tuple, Optional, Dict, Set


class TileType(Enum):
    """地图格子的类型"""
    EMPTY = "."
    BUILDING = "#"
    PLAYER = "@"
    WALL = "X"
    ROAD = ","
    GOAL = "G"


class MapGrid:
    """基于格子的2D地图"""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # 格子占用表: key=(x,y) -> TileType
        self._tiles: Dict[Tuple[int, int], TileType] = {}
        # 建筑列表
        self.buildings: List["Building"] = []
        # 当前玩家
        self.player: Optional["Player"] = None

    def in_bounds(self, x: int, y: int) -> bool:
        """检查坐标是否在地图范围内"""
        return 0 <= x < self.width and 0 <= y < self.height

    def is_free(self, x: int, y: int) -> bool:
        """检查格子是否空闲（没有被建筑占用）"""
        if not self.in_bounds(x, y):
            return False
        return self._tiles.get((x, y)) not in (TileType.BUILDING, TileType.WALL)

    def area_free(self, x: int, y: int, w: int, h: int) -> bool:
        """检查一个矩形区域是否全部空闲"""
        for dx in range(w):
            for dy in range(h):
                cx, cy = x + dx, y + dy
                if not self.in_bounds(cx, cy) or not self.is_free(cx, cy):
                    return False
        return True

    def set_tile(self, x: int, y: int, tile: TileType):
        """设置某个格子的类型"""
        if self.in_bounds(x, y):
            self._tiles[(x, y)] = tile

    def get_tile(self, x: int, y: int) -> TileType:
        """获取某个格子的类型"""
        return self._tiles.get((x, y), TileType.EMPTY)

    def add_building(self, building: "Building"):
        """在地图上放置一个建筑"""
        if not self.area_free(building.x, building.y, building.w, building.h):
            raise ValueError(
                f"无法放置 {building.name} 在 ({building.x},{building.y})，"
                f"区域被占用或超出地图范围"
            )
        self.buildings.append(building)
        for dx in range(building.w):
            for dy in range(building.h):
                self._tiles[(building.x + dx, building.y + dy)] = TileType.BUILDING

    def remove_building(self, building: "Building"):
        """从地图移除建筑"""
        if building in self.buildings:
            self.buildings.remove(building)
            for dx in range(building.w):
                for dy in range(building.h):
                    self._tiles.pop((building.x + dx, building.y + dy), None)

    def set_player(self, player: "Player"):
        """设置玩家位置"""
        if self.player and self.player is not player:
            # 清除旧玩家占据的格子
            pass
        self.player = player

    def move_player(self, dx: int, dy: int) -> bool:
        """尝试移动玩家，成功返回 True"""
        if not self.player:
            return False
        new_x = self.player.x + dx
        new_y = self.player.y + dy
        if self.in_bounds(new_x, new_y) and self.is_free(new_x, new_y):
            self.player.x = new_x
            self.player.y = new_y
            return True
        return False

    def render(self) -> List[str]:
        """渲染地图为字符串行列表"""
        rows = []
        for y in range(self.height):
            row_chars = []
            for x in range(self.width):
                # 玩家优先显示
                if self.player and (x, y) == (self.player.x, self.player.y):
                    row_chars.append(TileType.PLAYER.value)
                else:
                    row_chars.append(self.get_tile(x, y).value)
            rows.append(" " + " ".join(row_chars))
        return rows

    def render_with_info(self) -> str:
        """渲染完整地图 + 信息（用于终端输出）"""
        lines = []
        # 标题栏
        lines.append(f"  地图 ({self.width}x{self.height})")
        # 列号
        header = "   " + " ".join(str(i % 10) for i in range(self.width))
        lines.append(header)
        # 分隔线
        lines.append("  " + "-" * (self.width * 2))
        # 地图行
        for y, row in enumerate(self.render()):
            lines.append(f"{y:2}|{row}")
        lines.append("  " + "-" * (self.width * 2))
        # 图例
        legend = (
            f"  {TileType.EMPTY.value}=空地 "
            f"{TileType.BUILDING.value}=建筑 "
            f"{TileType.PLAYER.value}=玩家 "
            f"{TileType.ROAD.value}=道路 "
            f"{TileType.WALL.value}=墙壁"
        )
        lines.append(legend)
        return "\n".join(lines)

    def __str__(self):
        return self.render_with_info()

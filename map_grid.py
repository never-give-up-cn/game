"""2D 无限网格地图 - 区块生成 + 资源矿脉"""

import random
from enum import Enum
from typing import List, Tuple, Optional, Dict, Set
from resource_gen import get_planet_at, ResourceManager


class TileType(Enum):
    EMPTY = "."
    BUILDING = "#"
    PLAYER = "@"
    WALL = "X"
    ROAD = ","
    GOAL = "G"
    ORE = "*"
    FLUID = "~"
    BIO = "%"
    TREE = "t"
    WATER = "w"


CHUNK_SIZE = 16


class Chunk:
    """16×16 区块"""

    def __init__(self, cx: int, cy: int):
        self.cx = cx
        self.cy = cy
        self.tiles: List[List[TileType]] = [[TileType.EMPTY for _ in range(CHUNK_SIZE)] for _ in range(CHUNK_SIZE)]
        self.ore_map: Dict[Tuple[int, int], str] = {}  # (lx,ly) -> item_id
        self.generated = False

    def get_global_x(self, lx: int) -> int:
        return self.cx * CHUNK_SIZE + lx

    def get_global_y(self, ly: int) -> int:
        return self.cy * CHUNK_SIZE + ly


class MapGrid:
    """无限地图 - 按需生成区块"""

    def __init__(self):
        self.chunks: Dict[Tuple[int, int], Chunk] = {}
        self.buildings: List["BuildingBase"] = []
        self.player: Optional["Player"] = None
        self.resource_mgr = ResourceManager()

    def _chunk_at(self, gx: int, gy: int) -> Tuple[int, int]:
        return gx // CHUNK_SIZE, gy // CHUNK_SIZE

    def _local(self, gx: int, gy: int) -> Tuple[int, int, int, int]:
        cx, cy = self._chunk_at(gx, gy)
        return cx, cy, gx - cx * CHUNK_SIZE, gy - cy * CHUNK_SIZE

    def _ensure_chunk(self, cx: int, cy: int):
        """确保区块已生成"""
        key = (cx, cy)
        if key in self.chunks:
            return
        chunk = Chunk(cx, cy)
        planet = get_planet_at(cx * CHUNK_SIZE, cy * CHUNK_SIZE)
        random.seed(cx * 100000 + cy)

        # 根据区域生成地貌
        if planet == "nauvis":
            # 随机树木和水
            for _ in range(random.randint(0, 8)):
                tx, ty = random.randint(0, CHUNK_SIZE - 1), random.randint(0, CHUNK_SIZE - 1)
                chunk.tiles[ty][tx] = TileType.TREE if random.random() > 0.3 else TileType.WATER
        elif planet == "vulcanus":
            # 熔岩地表
            for _ in range(random.randint(2, 6)):
                tx, ty = random.randint(0, CHUNK_SIZE - 1), random.randint(0, CHUNK_SIZE - 1)
                chunk.tiles[ty][tx] = TileType.FLUID
        elif planet == "fulgora":
            # 废墟地表
            for _ in range(random.randint(1, 4)):
                tx, ty = random.randint(0, CHUNK_SIZE - 1), random.randint(0, CHUNK_SIZE - 1)
                chunk.tiles[ty][tx] = TileType.WALL
        elif planet == "gleba":
            # 真菌地表
            for _ in range(random.randint(3, 10)):
                tx, ty = random.randint(0, CHUNK_SIZE - 1), random.randint(0, CHUNK_SIZE - 1)
                chunk.tiles[ty][tx] = TileType.BIO
        elif planet == "aquilo":
            # 冰原地表
            for _ in range(random.randint(1, 3)):
                tx, ty = random.randint(0, CHUNK_SIZE - 1), random.randint(0, CHUNK_SIZE - 1)
                chunk.tiles[ty][tx] = TileType.WATER

        # 生成资源矿脉
        self.resource_mgr.ensure_chunk(cx * CHUNK_SIZE, cy * CHUNK_SIZE)
        gx0 = cx * CHUNK_SIZE
        gy0 = cy * CHUNK_SIZE
        for (rx, ry), node in self.resource_mgr.nodes.items():
            if gx0 <= rx < gx0 + CHUNK_SIZE and gy0 <= ry < gy0 + CHUNK_SIZE:
                lx, ly = rx - gx0, ry - gy0
                if 0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_SIZE:
                    if node.category == "fluid":
                        chunk.tiles[ly][lx] = TileType.FLUID
                    elif node.category == "bio":
                        chunk.tiles[ly][lx] = TileType.BIO
                    else:
                        chunk.tiles[ly][lx] = TileType.ORE
                    chunk.ore_map[(lx, ly)] = node.item_id

        chunk.generated = True
        self.chunks[key] = chunk

    def in_bounds(self, x: int, y: int) -> bool:
        """无限地图 - 总是返回 True"""
        return True

    def is_free(self, x: int, y: int) -> bool:
        cx, cy, lx, ly = self._local(x, y)
        self._ensure_chunk(cx, cy)
        chunk = self.chunks.get((cx, cy))
        if not chunk:
            return False
        tile = chunk.tiles[ly][lx]
        # 建筑/WALL 不可通行
        if tile == TileType.BUILDING or tile == TileType.WALL:
            return False
        # 检查是否有建筑占用
        for b in self.buildings:
            if b.x <= x < b.x + b.w and b.y <= y < b.y + b.h:
                return False
        return True

    def area_free(self, x: int, y: int, w: int, h: int) -> bool:
        for dx in range(w):
            for dy in range(h):
                if not self.is_free(x + dx, y + dy):
                    return False
        return True

    def set_tile(self, x: int, y: int, tile: TileType):
        cx, cy, lx, ly = self._local(x, y)
        self._ensure_chunk(cx, cy)
        chunk = self.chunks.get((cx, cy))
        if chunk:
            chunk.tiles[ly][lx] = tile

    def get_tile(self, x: int, y: int) -> TileType:
        cx, cy, lx, ly = self._local(x, y)
        self._ensure_chunk(cx, cy)
        chunk = self.chunks.get((cx, cy))
        if not chunk:
            return TileType.EMPTY
        return chunk.tiles[ly][lx]

    def get_ore(self, x: int, y: int) -> Optional[str]:
        """获取地面的矿石类型"""
        cx, cy, lx, ly = self._local(x, y)
        self._ensure_chunk(cx, cy)
        chunk = self.chunks.get((cx, cy))
        if chunk:
            return chunk.ore_map.get((lx, ly))
        return None

    def add_building(self, building: "BuildingBase"):
        if not self.area_free(building.x, building.y, building.w, building.h):
            raise ValueError(f"无法放置 {building.name}")
        building.game_map = self  # 注入地图引用（机械臂等需要）
        self.buildings.append(building)
        for dx in range(building.w):
            for dy in range(building.h):
                self.set_tile(building.x + dx, building.y + dy, TileType.BUILDING)

    def remove_building(self, building: "BuildingBase"):
        if building in self.buildings:
            self.buildings.remove(building)
            for dx in range(building.w):
                for dy in range(building.h):
                    self.set_tile(building.x + dx, building.y + dy, TileType.EMPTY)

    def set_player(self, player: "Player"):
        self.player = player

    def move_player(self, dx: int, dy: int) -> bool:
        if not self.player:
            return False
        new_x = self.player.x + dx
        new_y = self.player.y + dy
        if self.is_free(new_x, new_y):
            # 斜向检查
            if dx != 0 and dy != 0:
                if not (self.is_free(self.player.x + dx, self.player.y) and
                        self.is_free(self.player.x, self.player.y + dy)):
                    return False
            self.player.x = new_x
            self.player.y = new_y
            return True
        return False

    def render_viewport(self, cam_x: int, cam_y: int, width: int, height: int) -> List[str]:
        """渲染视口范围内的地图"""
        rows = []
        for vy in range(height):
            row_chars = []
            for vx in range(width):
                gx = cam_x + vx
                gy = cam_y + vy
                if self.player and (gx, gy) == (self.player.x, self.player.y):
                    row_chars.append(TileType.PLAYER.value)
                else:
                    row_chars.append(self.get_tile(gx, gy).value)
            rows.append(" " + " ".join(row_chars))
        return rows

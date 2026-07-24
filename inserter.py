"""机械臂（Inserter）- 工厂物流核心，在建筑/传送带/箱子之间搬运物品"""

from typing import Optional, Tuple, TYPE_CHECKING
from building.base import BuildingBase

if TYPE_CHECKING:
    from map_grid import MapGrid


DIR_NAMES = ["↑上", "→右", "↓下", "←左"]
DIR_VECTORS = [(0, -1), (1, 0), (0, 1), (-1, 0)]


class Inserter(BuildingBase):
    """机械臂 - 从 pickup_pos 抓取 → 投放到 dropoff_pos"""

    def __init__(self, x: int, y: int, template: dict):
        super().__init__(x, y, template)
        self.reach: int = template.get("reach", 1)
        self.speed: int = template.get("inserter_speed", 30)
        self.stack_size: int = template.get("stack_size", 1)
        self.filter_items: list = list(template.get("filter", []))
        self.uses_fuel: bool = template.get("uses_fuel", False)
        self.fuel: int = 0
        self.fuel_max: int = template.get("fuel_max", 0)
        self.direction: int = 0
        self.arm_state: int = 0
        self.arm_progress: float = 0.0
        self.held_item: Optional[str] = None
        self.held_count: int = 0
        self.game_map: Optional["MapGrid"] = None  # 由 MapGrid 在 add_building 时注入

    def rotate(self):
        self.direction = (self.direction + 1) % 4

    @property
    def pickup_pos(self):
        dx, dy = DIR_VECTORS[(self.direction + 2) % 4]
        return self.x + dx, self.y + dy

    @property
    def dropoff_pos(self):
        dx, dy = DIR_VECTORS[self.direction]
        return self.x + dx, self.y + dy

    @property
    def direction_name(self):
        return DIR_NAMES[self.direction]

    def add_fuel(self, item_id: str) -> bool:
        if not self.uses_fuel:
            return False
        fuel_values = {"coal": 20, "wood": 10}
        val = fuel_values.get(item_id, 0)
        if val > 0:
            self.fuel = min(self.fuel_max, self.fuel + val)
            return True
        return False

    @property
    def has_fuel(self):
        return True if not self.uses_fuel else self.fuel > 0

    def is_allowed(self, item_id: str) -> bool:
        if not self.filter_items:
            return True
        return item_id in self.filter_items

    # ── tick ──

    def tick(self, inventory) -> dict:
        events = {}
        if self.uses_fuel and self.fuel > 0 and self.arm_state != 0:
            self.fuel = max(0, self.fuel - 1)

        if self.arm_state == 0:
            if self.has_fuel and self._can_pickup():
                self.arm_state = 1
                self.arm_progress = 0.0
        else:
            self.arm_progress += 1.0 / self.speed
            if self.arm_progress >= 1.0:
                self.arm_progress = 0.0
                self._advance_state()
                if self.arm_state == 0:
                    events["transfer"] = True
        return events

    def _can_pickup(self) -> bool:
        """pickup_pos 上有可抓取的物品"""
        if self.held_item is not None:
            return False
        gm = self.game_map
        if not gm:
            return False
        px, py = self.pickup_pos

        # 1. 检查传送带
        for b in gm.buildings:
            if b.x == px and b.y == py and hasattr(b, 'lanes'):
                for ln in ("left", "right"):
                    for item in b.lanes.get(ln, []):
                        if self.is_allowed(item["id"]):
                            return True

        # 2. 检查建筑输出缓冲（简化：检查建筑的 output_buffer）
        for b in gm.buildings:
            if b.x == px and b.y == py and hasattr(b, 'output_buffer'):
                for iid, cnt in b.output_buffer.items():
                    if cnt > 0 and self.is_allowed(iid):
                        return True

        return False

    def _advance_state(self):
        if self.arm_state == 1:
            self._do_grab()
            self.arm_state = 2
        elif self.arm_state == 2:
            self._do_drop()
            self.arm_state = 3
        elif self.arm_state == 3:
            self.arm_state = 0

    def _do_grab(self):
        """从 pickup_pos 的传送带/建筑取物品"""
        gm = self.game_map
        if not gm:
            return
        px, py = self.pickup_pos

        # 1. 优先从传送带取
        for b in gm.buildings:
            if b.x == px and b.y == py and hasattr(b, 'lanes'):
                for ln in ("left", "right"):
                    lane = b.lanes.get(ln, [])
                    for i, item in enumerate(lane):
                        if self.is_allowed(item["id"]):
                            taken = lane.pop(i)
                            self.held_item = taken["id"]
                            self.held_count = 1
                            return

        # 2. 从建筑输出缓冲取
        for b in gm.buildings:
            if b.x == px and b.y == py and hasattr(b, 'output_buffer'):
                for iid, cnt in list(b.output_buffer.items()):
                    if cnt > 0 and self.is_allowed(iid):
                        take = min(cnt, self.stack_size)
                        b.output_buffer[iid] -= take
                        self.held_item = iid
                        self.held_count = take
                        return

    def _do_drop(self):
        """投放到 dropoff_pos 的传送带/建筑"""
        gm = self.game_map
        if not gm or not self.held_item:
            self.held_item = None
            self.held_count = 0
            return
        px, py = self.dropoff_pos

        # 1. 放到传送带（近侧车道 = 远离机械臂一侧）
        for b in gm.buildings:
            if b.x == px and b.y == py and hasattr(b, 'lanes'):
                # 机械臂远侧原则: 机械臂方向的反向远离侧
                dx = self.x - px
                dy = self.y - py
                # 判断哪条车道离机械臂更远
                if b.direction in (0, 2):  # 上下方向
                    target_lane = "right" if dx < 0 else "left"
                else:
                    target_lane = "right" if dy < 0 else "left"
                if b.add_item(self.held_item, target_lane):
                    self.held_item = None
                    self.held_count = 0
                return

            # 2. 放到建筑输入缓冲
            if b.x == px and b.y == py and hasattr(b, 'input_buffer'):
                b.input_buffer[self.held_item] = b.input_buffer.get(self.held_item, 0) + self.held_count
                self.held_item = None
                self.held_count = 0
                return

        # 3. 无接收者 -> 物品丢失（简化处理）
        self.held_item = None
        self.held_count = 0

    def render_popup(self, screen, rect, mx, my, inventory, tech_unlocked, font_small, anim_frame):
        import pygame
        C = self._popup_colors()
        C["border"] = (200, 160, 60)
        C["title_bg"] = (35, 28, 18)
        pr = rect
        s = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA)
        s.fill(C["bg"]); screen.blit(s, pr)
        pygame.draw.rect(screen, C["border"], pr, 2, border_radius=8)
        title_bar = pygame.Rect(pr.x+4, pr.y+4, pr.w-8, 28)
        pygame.draw.rect(screen, C["title_bg"], title_bar, border_radius=4)
        screen.blit(font_small.render(f"Inserter {self.name}  {self.direction_name}", True, C["title_text"]), (pr.x+14, pr.y+8))
        close_r = pygame.Rect(pr.right-28, pr.top+6, 20, 18)
        cc = (255,80,80) if close_r.collidepoint(mx,my) else (120,130,150)
        pygame.draw.rect(screen, cc, close_r, border_radius=3)
        screen.blit(font_small.render("×", True, (255,255,255)), (close_r.x+5, close_r.y+1))
        yy = pr.y+40; lx = pr.x+14
        lines = [f"Dir: {self.direction_name}",
                 f"Pickup: ({self.pickup_pos[0]},{self.pickup_pos[1]})",
                 f"Drop: ({self.dropoff_pos[0]},{self.dropoff_pos[1]})",
                 f"Speed: {self.speed}f/cycle  Reach: {self.reach}",
                 f"Stack: {self.stack_size}"]
        if self.uses_fuel: lines.append(f"Fuel: {self.fuel}/{self.fuel_max}")
        if self.filter_items: lines.append(f"Filter: {','.join(self.filter_items)}")
        for line in lines:
            screen.blit(font_small.render(line, True, C["text"]), (lx, yy)); yy += 18
        screen.blit(font_small.render("R to rotate", True, C["dim"]), (lx, yy))

    def __repr__(self):
        return f"<Inserter {self.name} ({self.x},{self.y}) dir={self.direction_name}>"

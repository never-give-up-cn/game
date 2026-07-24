"""传送带系统 - 队列模型 (尾→头, 车尾→车头)"""

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from building.base import BuildingBase

if TYPE_CHECKING:
    from map_grid import MapGrid

BELT_SPECS = {1: {"speed": 7.5/60, "cap": 4}, 2: {"speed": 15/60, "cap": 4},
              3: {"speed": 22.5/60, "cap": 4}, 4: {"speed": 30/60, "cap": 4}}
UG_DIST = {1: 4, 2: 6, 3: 8, 4: 10}
DIR_VEC = [(0, -1), (1, 0), (0, 1), (-1, 0)]


class ConveyorBelt(BuildingBase):
    """传送带 - 队列模型: lane[List], index 0=车尾, last=车头"""

    def __init__(self, x, y, template):
        super().__init__(x, y, template)
        self.direction = 0
        self.tier = template.get("belt_tier", 1)
        s = BELT_SPECS.get(self.tier, BELT_SPECS[1])
        self.belt_speed = s["speed"]
        self.capacity = s["cap"]
        self.lanes: Dict[str, List[dict]] = {"left": [], "right": []}
        self.game_map: Optional["MapGrid"] = None

    def rotate(self):
        self.direction = (self.direction + 1) % 4

    @property
    def front_pos(self):
        dx, dy = DIR_VEC[self.direction]
        return self.x + dx, self.y + dy

    def add_item(self, item_id: str, lane: str = "left") -> bool:
        """从车尾(index 0)加入物品"""
        if lane not in self.lanes:
            lane = "left"
        if len(self.lanes[lane]) >= self.capacity:
            return False
        self.lanes[lane].insert(0, {"id": item_id})
        return True

    def _find_next(self):
        fx, fy = self.front_pos
        if not self.game_map:
            return None
        for b in self.game_map.buildings:
            if b.x == fx and b.y == fy and isinstance(b, ConveyorBelt):
                return b
        return None

    def _target_lane(self, my_lane, my_dir, next_dir):
        """计算车道映射 (直连/转弯)"""
        if my_dir == next_dir:
            return my_lane
        turn_right = (my_dir + 1) % 4 == next_dir
        turn_left = (my_dir - 1) % 4 == next_dir
        if turn_right:
            return "left" if my_lane == "left" else "right"
        if turn_left:
            return "right" if my_lane == "left" else "left"
        return my_lane

    def tick(self, inventory) -> dict:
        """每帧: 从车头(last)→车尾(0)处理"""
        for ln in ("left", "right"):
            lane = self.lanes[ln]
            if not lane:
                continue
            # 车头 = last index
            head = lane[-1]
            next_belt = self._find_next()
            transferred = False
            if next_belt:
                tl = self._target_lane(ln, self.direction, next_belt.direction)
                if len(next_belt.lanes.get(tl, [])) < next_belt.capacity:
                    next_belt.lanes[tl].insert(0, head)  # 到下游车尾
                    lane.pop()
                    transferred = True
            # 没转移时, 车头不动, 后方都堵住
            # 但物品还是要按速度推进 (用帧计数器也可以)
            # 简化: 每帧推进内部间距 (用 belt_speed 控制视觉移动)
        return {}

    def __repr__(self):
        return f"<Belt T{self.tier} ({len(self.lanes['left'])}/{len(self.lanes['right'])})>"


class UndergroundBelt(BuildingBase):
    def __init__(self, x, y, template):
        super().__init__(x, y, template)
        self.direction = 0
        self.tier = template.get("belt_tier", 1)
        self.max_dist = UG_DIST.get(self.tier, 4)
        self.is_entry = True
        self.paired = False

    def rotate(self):
        self.direction = (self.direction + 1) % 4

    def render_popup(self, screen, rect, mx, my, inventory, tech_unlocked, font_small, anim_frame):
        import pygame
        C = self._popup_colors()
        pr = rect
        s = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA)
        s.fill(C["bg"]); screen.blit(s, pr)
        pygame.draw.rect(screen, (60,160,200), pr, 2, border_radius=8)
        tb = pygame.Rect(pr.x+4, pr.y+4, pr.w-8, 28)
        pygame.draw.rect(screen, C["title_bg"], tb, border_radius=4)
        role = "IN →" if self.is_entry else "← OUT"
        screen.blit(font_small.render(f"Underground {role}  T{self.tier}", True, C["title_text"]), (pr.x+14, pr.y+8))
        cr = pygame.Rect(pr.right-28, pr.top+6, 20, 18)
        cc = (255,80,80) if cr.collidepoint(mx,my) else (120,130,150)
        pygame.draw.rect(screen, cc, cr, border_radius=3)
        screen.blit(font_small.render("×", True, (255,255,255)), (cr.x+5, cr.y+1))
        y = pr.y+40; x = pr.x+14
        for l in [f"Max span: {self.max_dist} tiles", f"Paired: {self.paired}", "R to rotate"]:
            screen.blit(font_small.render(l, True, C["text"]), (x, y)); y += 18

    def __repr__(self):
        return f"<Underground T{self.tier} {'IN' if self.is_entry else 'OUT'}>"


class Splitter(BuildingBase):
    def __init__(self, x, y, template):
        super().__init__(x, y, template)
        self.tier = template.get("belt_tier", 1)
        self.priority = "none"
        self.filter_items: List[str] = []
        self.input_buf: Dict[str, List] = {"left": [], "right": []}
        self.output_buf: Dict[str, List] = {"left": [], "right": []}
        self.toggle = 0

    def tick(self, inventory) -> dict:
        for lane in ("left", "right"):
            if self.input_buf[lane]:
                item = self.input_buf[lane].pop(0)
                if self.filter_items and item["id"] not in self.filter_items:
                    out = "right" if lane == "left" else "left"
                elif self.priority == "left":
                    out = "left"
                elif self.priority == "right":
                    out = "right"
                else:
                    out = "left" if self.toggle % 2 == 0 else "right"
                    self.toggle += 1
                self.output_buf[out].append(item)
        return {}

    def render_popup(self, screen, rect, mx, my, inventory, tech_unlocked, font_small, anim_frame):
        import pygame
        C = self._popup_colors()
        pr = rect
        s = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA)
        s.fill(C["bg"]); screen.blit(s, pr)
        pygame.draw.rect(screen, (60,200,160), pr, 2, border_radius=8)
        tb = pygame.Rect(pr.x+4, pr.y+4, pr.w-8, 28)
        pygame.draw.rect(screen, C["title_bg"], tb, border_radius=4)
        screen.blit(font_small.render(f"Splitter T{self.tier}", True, C["title_text"]), (pr.x+14, pr.y+8))
        cr = pygame.Rect(pr.right-28, pr.top+6, 20, 18)
        cc = (255,80,80) if cr.collidepoint(mx,my) else (120,130,150)
        pygame.draw.rect(screen, cc, cr, border_radius=3)
        screen.blit(font_small.render("×", True, (255,255,255)), (cr.x+5, cr.y+1))
        y = pr.y+40; x = pr.x+14
        pri = {"none":"Off","left":"Left","right":"Right"}
        flt = ",".join(self.filter_items) if self.filter_items else "None"
        for l in [f"Priority: {pri[self.priority]}", f"Filter: {flt}", "Lane: L→L R→R"]:
            screen.blit(font_small.render(l, True, C["text"]), (x, y)); y += 18

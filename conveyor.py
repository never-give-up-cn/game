"""传送带系统 - progress 推进模型"""

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from building.base import BuildingBase

if TYPE_CHECKING:
    from map_grid import MapGrid

BELT_SPECS = {1: 7.5/60, 2: 15/60, 3: 22.5/60, 4: 30/60}  # 每帧移动量
UG_DIST = {1: 4, 2: 6, 3: 8, 4: 10}
DIR_VEC = [(0, -1), (1, 0), (0, 1), (-1, 0)]


class ConveyorBelt(BuildingBase):
    """传送带 - progress 推进 + 首尾直连"""

    def __init__(self, x, y, template):
        super().__init__(x, y, template)
        self.direction = 0
        self.tier = template.get("belt_tier", 1)
        self.belt_speed = BELT_SPECS.get(self.tier, 7.5/60)
        self.capacity = 4
        self.lanes: Dict[str, List[dict]] = {"left": [], "right": []}
        self.game_map: Optional["MapGrid"] = None

    def rotate(self):
        self.direction = (self.direction + 1) % 4

    @property
    def front_pos(self):
        dx, dy = DIR_VEC[self.direction]
        return self.x + dx, self.y + dy

    def add_item(self, item_id: str, lane: str = "left") -> bool:
        if lane not in self.lanes:
            lane = "left"
        if len(self.lanes[lane]) >= self.capacity:
            return False
        self.lanes[lane].insert(0, {"id": item_id, "p": 0.0})  # p=progress 0~1
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
        if my_dir == next_dir:
            return my_lane
        turn_r = (my_dir + 1) % 4 == next_dir
        turn_l = (my_dir - 1) % 4 == next_dir
        if turn_r:
            return "left" if my_lane == "left" else "right"
        if turn_l:
            return "right" if my_lane == "left" else "left"
        return my_lane

    def tick(self, inventory) -> dict:
        spd = self.belt_speed
        for ln in ("left", "right"):
            lane = self.lanes[ln]
            if not lane:
                continue

            # 1. 所有物品推进
            for item in lane:
                item["p"] += spd

            # 2. 车头(progress最高)尝试转移
            head = lane[-1]
            if head["p"] >= 1.0:
                next_belt = self._find_next()
                if next_belt:
                    tl = self._target_lane(ln, self.direction, next_belt.direction)
                    tgt = next_belt.lanes.get(tl, [])
                    if len(tgt) < next_belt.capacity:
                        head["p"] = 0.0  # 重置进度
                        tgt.insert(0, head)
                        lane.pop()
                    else:
                        head["p"] = 1.0  # 堵住不动
                else:
                    head["p"] = 1.0  # 断头排队

            # 3. 移除溢出 (安全)
            while len(lane) > self.capacity:
                lane.pop(0)
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
        self.capacity = 4
        self.priority = "none"
        self.filter_items: List[str] = []
        self.input_buf: Dict[str, List] = {"left": [], "right": []}
        self.output_buf: Dict[str, List] = {"left": [], "right": []}
        self.toggle_l = 0  # 左车道独立 toggle
        self.toggle_r = 0

    def tick(self, inventory) -> dict:
        for lane in ("left", "right"):
            if not self.input_buf[lane]:
                continue
            item = self.input_buf[lane][0]  # peek
            # 过滤
            if self.filter_items and item["id"] not in self.filter_items:
                out = "right" if lane == "left" else "left"
            elif self.priority == "left":
                out = "left"
            elif self.priority == "right":
                out = "right"
            else:
                tog = self.toggle_l if lane == "left" else self.toggle_r
                out = "left" if tog % 2 == 0 else "right"
                if lane == "left": self.toggle_l += 1
                else: self.toggle_r += 1
            # 检查输出容量
            if len(self.output_buf[out]) < self.capacity:
                self.output_buf[out].append(self.input_buf[lane].pop(0))
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

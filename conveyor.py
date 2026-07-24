"""传送带+分流器 - 车头→车尾遍历 + 容量预判 + 输出推送"""

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from building.base import BuildingBase

if TYPE_CHECKING:
    from map_grid import MapGrid

BELT_SPECS = {1: 7.5/60, 2: 15/60, 3: 22.5/60, 4: 30/60}
UG_DIST = {1: 4, 2: 6, 3: 8, 4: 10}
DIR_VEC = [(0, -1), (1, 0), (0, 1), (-1, 0)]


class ConveyorBelt(BuildingBase):
    """传送带 - progress推进 + 车头→车尾遍历 + 首尾直连"""

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
        if lane not in self.lanes: lane = "left"
        if len(self.lanes[lane]) >= self.capacity: return False
        self.lanes[lane].insert(0, {"id": item_id, "p": 0.0})
        return True

    def _find_next(self):
        """仅返回首尾正对的下游传送带（侧向不互通）"""
        fx, fy = self.front_pos
        if not self.game_map: return None
        for b in self.game_map.buildings:
            if not isinstance(b, ConveyorBelt): continue
            if b.x == fx and b.y == fy:
                # 校验：下游的入口方向必须朝向本传送带
                dx, dy = DIR_VEC[b.direction]
                entry_x = b.x + dx
                entry_y = b.y + dy
                if entry_x == self.x and entry_y == self.y:
                    return b
        return None

    def _target_lane(self, my_lane, my_dir, next_dir):
        """车道映射: 直连L→L, 右转L→内侧, 左转L→外侧"""
        if my_dir == next_dir: return my_lane
        turn_r = (my_dir + 1) % 4 == next_dir
        turn_l = (my_dir - 1) % 4 == next_dir
        if turn_r: return "left" if my_lane == "left" else "right"
        if turn_l: return "right" if my_lane == "left" else "left"
        return my_lane

    def tick(self, inventory) -> dict:
        spd = self.belt_speed
        for ln in ("left", "right"):
            lane = self.lanes[ln]
            if not lane: continue

            # 1. 先推进所有物品的 progress
            for item in lane:
                item["p"] += spd

            # 2. 从车头(last)→车尾(0)遍历, 尝试转移
            next_belt = self._find_next()
            i = len(lane) - 1
            while i >= 0:
                item = lane[i]
                if item["p"] >= 1.0:
                    if next_belt:
                        tl = self._target_lane(ln, self.direction, next_belt.direction)
                        tgt = next_belt.lanes.get(tl, [])
                        if len(tgt) < next_belt.capacity:
                            item["p"] = 0.0
                            tgt.insert(0, item)
                            lane.pop(i)
                        else:
                            item["p"] = 1.0  # 下游满, 堵住
                    else:
                        item["p"] = 1.0  # 断头排队
                i -= 1

            # 3. 超限安全清理 (理论上不会触发)
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
        self.is_entry = True; self.paired = False

    def rotate(self):
        self.direction = (self.direction + 1) % 4

    def render_popup(self, screen, rect, mx, my, inventory, tech_unlocked, font_small, anim_frame):
        import pygame
        C = self._popup_colors(); pr = rect
        s = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA); s.fill(C["bg"]); screen.blit(s, pr)
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
        for l in [f"Max: {self.max_dist}t", f"Paired: {self.paired}", "R rotate"]:
            screen.blit(font_small.render(l, True, C["text"]), (x, y)); y += 18


class Splitter(BuildingBase):
    """分流器 - 容量预判 + 车道独立 + 输出推送"""

    def __init__(self, x, y, template):
        super().__init__(x, y, template)
        self.tier = template.get("belt_tier", 1)
        self.capacity = 4
        self.priority = "none"
        self.filter_items: List[str] = []
        self.input_buf: Dict[str, List] = {"left": [], "right": []}
        self.output_buf: Dict[str, List] = {"left": [], "right": []}
        self.toggle_l = 0; self.toggle_r = 0
        self.direction = 0  # 输出方向 (与传送带匹配)
        self.game_map: Optional["MapGrid"] = None

    def _find_output_belt(self, lane):
        """查找输出方向的下游传送带"""
        out_dir = self.direction  # 分流器方向即输出方向
        dx, dy = DIR_VEC[out_dir]
        fx, fy = self.x + dx, self.y + dy
        if not self.game_map: return None
        for b in self.game_map.buildings:
            if isinstance(b, ConveyorBelt) and b.x == fx and b.y == fy:
                return b, lane  # 车道映射 L→L R→R
        return None

    def tick(self, inventory) -> dict:
        # 1. 输入→输出 (先判定容量, 再pop)
        for lane in ("left", "right"):
            ib = self.input_buf.get(lane, [])
            if not ib: continue
            item = ib[0]  # peek
            # 计算输出车道
            if self.filter_items and item["id"] not in self.filter_items:
                out = "right" if lane == "left" else "left"
            elif self.priority == "left": out = "left"
            elif self.priority == "right": out = "right"
            else:
                tog = self.toggle_l if lane == "left" else self.toggle_r
                out = "left" if tog % 2 == 0 else "right"
                if lane == "left": self.toggle_l += 1
                else: self.toggle_r += 1
            # 先检查容量再pop!
            if len(self.output_buf[out]) < self.capacity:
                self.output_buf[out].append(ib.pop(0))

        # 2. 输出→下游传送带
        for lane in ("left", "right"):
            ob = self.output_buf.get(lane, [])
            if not ob: continue
            res = self._find_output_belt(lane)
            if res:
                next_belt, _ = res
                tl = lane
                if len(next_belt.lanes.get(tl, [])) < next_belt.capacity:
                    item = ob.pop(0)
                    item["p"] = 0.0  # 重置进度
                    next_belt.lanes[tl].insert(0, item)
        return {}

    def render_popup(self, screen, rect, mx, my, inventory, tech_unlocked, font_small, anim_frame):
        import pygame
        C = self._popup_colors(); pr = rect
        s = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA); s.fill(C["bg"]); screen.blit(s, pr)
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

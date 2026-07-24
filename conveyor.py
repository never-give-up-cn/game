"""传送带+分流器 - 转弯车道映射 + 标准化API + 去耦合"""

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from building.base import BuildingBase

if TYPE_CHECKING:
    from map_grid import MapGrid

BELT_SPECS = {1: 7.5/60, 2: 15/60, 3: 22.5/60, 4: 30/60}
UG_DIST = {1: 4, 2: 6, 3: 8, 4: 10}
DIR_VEC = [(0, -1), (1, 0), (0, 1), (-1, 0)]


class ConveyorBelt(BuildingBase):
    """传送带 - 双向车道 + 转弯映射 + 首尾直连"""

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

    # ── 标准化 API ──

    def add_item(self, item_id: str, lane: str = "left") -> bool:
        """从车尾放入物品"""
        if lane not in self.lanes: lane = "left"
        if len(self.lanes[lane]) >= self.capacity: return False
        self.lanes[lane].insert(0, {"id": item_id, "p": 0.0})
        return True

    def take_front_item(self, lane: str) -> Optional[dict]:
        """从车头取出物品 (供机械臂/玩家拾取)"""
        ln = self.lanes.get(lane)
        if not ln: return None
        return ln.pop(-1) if ln else None

    def put_back_item(self, item_id: str, lane: str = "left") -> bool:
        """同 add_item, 语义更清晰"""
        return self.add_item(item_id, lane)

    # ── 对接检测 ──

    def _find_next(self):
        """查找首尾正对的下游传送带 (校验入口方向)"""
        fx, fy = self.front_pos
        if not self.game_map: return None
        for b in self.game_map.buildings:
            if not isinstance(b, ConveyorBelt): continue
            if (b.x, b.y) != (fx, fy): continue
            # 下游的入口必须指向自己
            bfx, bfy = b.front_pos
            if (bfx, bfy) == (self.x, self.y):
                return b
        return None

    # ── 转弯车道映射 ──

    def _target_lane(self, my_lane: str, my_dir: int, next_dir: int) -> str:
        """计算车道在转弯时的映射:
        直连: L→L, R→R
        右转: L→L(内轨), R→R(外轨) — 车道不变
        左转: L→R, R→L — 车道互换
        """
        if my_dir == next_dir:
            return my_lane
        turn_r = (my_dir + 1) % 4 == next_dir
        if turn_r:
            return my_lane  # 右转: 车道不变
        # 左转: 车道互换
        return "right" if my_lane == "left" else "left"

    # ── Tick ──

    def tick(self, inventory) -> dict:
        spd = self.belt_speed
        for ln in ("left", "right"):
            lane = self.lanes[ln]
            if not lane: continue
            for item in lane:
                item["p"] += spd
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
                            item["p"] = 1.0
                    else:
                        item["p"] = 1.0
                i -= 1
            while len(lane) > self.capacity:
                lane.pop(0)
        return {}

    def __repr__(self):
        return f"<Belt T{self.tier} ({len(self.lanes['left'])}/{len(self.lanes['right'])})>"


class UndergroundBelt(BuildingBase):
    """地下传送带 - TODO: 隧道传输逻辑"""
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
        screen.blit(font_small.render(f"Underground {role} T{self.tier}", True, C["title_text"]), (pr.x+14, pr.y+8))
        cr = pygame.Rect(pr.right-28, pr.top+6, 20, 18)
        cc = (255,80,80) if cr.collidepoint(mx,my) else (120,130,150)
        pygame.draw.rect(screen, cc, cr, border_radius=3)
        screen.blit(font_small.render("×", True, (255,255,255)), (cr.x+5, cr.y+1))
        y = pr.y+40; x = pr.x+14
        for l in [f"Max: {self.max_dist}t", f"Paired: {self.paired}", "R rotate"]:
            screen.blit(font_small.render(l, True, C["text"]), (x, y)); y += 18


class Splitter(BuildingBase):
    """分流器 - 容量预判 + 车道映射 + 输出推送"""

    def __init__(self, x, y, template):
        super().__init__(x, y, template)
        self.tier = template.get("belt_tier", 1)
        self.capacity = 4
        self.priority = "none"
        self.filter_items: List[str] = []
        self.input_buf: Dict[str, List] = {"left": [], "right": []}
        self.output_buf: Dict[str, List] = {"left": [], "right": []}
        self.toggle_l = 0; self.toggle_r = 0
        self.direction = 0
        self.game_map: Optional["MapGrid"] = None

    def _find_output_belt(self):
        """仅返回下游传送带, 车道映射由外层处理"""
        dx, dy = DIR_VEC[self.direction]
        fx, fy = self.x + dx, self.y + dy
        if not self.game_map: return None
        for b in self.game_map.buildings:
            if isinstance(b, ConveyorBelt) and b.x == fx and b.y == fy:
                return b
        return None

    def tick(self, inventory) -> dict:
        # 1. 输入→输出 (先peek再pop)
        for lane in ("left", "right"):
            ib = self.input_buf.get(lane, [])
            if not ib: continue
            item = ib[0]
            if self.filter_items and item["id"] not in self.filter_items:
                out = "right" if lane == "left" else "left"
            elif self.priority == "left": out = "left"
            elif self.priority == "right": out = "right"
            else:
                tog = self.toggle_l if lane == "left" else self.toggle_r
                out = "left" if tog % 2 == 0 else "right"
                if lane == "left": self.toggle_l += 1
                else: self.toggle_r += 1
            if len(self.output_buf[out]) < self.capacity:
                self.output_buf[out].append(ib.pop(0))

        # 2. 输出→下游传送带 (使用 _target_lane 转弯映射)
        for lane in ("left", "right"):
            ob = self.output_buf.get(lane, [])
            if not ob: continue
            next_belt = self._find_output_belt()
            if not next_belt: continue
            tl = next_belt._target_lane(lane, self.direction, next_belt.direction)
            if len(next_belt.lanes.get(tl, [])) < next_belt.capacity:
                item = ob.pop(0)
                item["p"] = 0.0
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

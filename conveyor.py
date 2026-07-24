"""传送带系统 - 双车道物理引擎 (首尾直连 + 车道保留)"""

from typing import Dict, List, Optional, Tuple

# 运行时才导入 BuildingBase (避免循环引用)
from building.base import BuildingBase

# 传送带速度 (每帧移动量)
BELT_SPECS = {
    1: {"speed": 7.5/60, "capacity": 4},
    2: {"speed": 15.0/60, "capacity": 4},
    3: {"speed": 22.5/60, "capacity": 4},
    4: {"speed": 30.0/60, "capacity": 4},
}

UG_DIST = {1: 4, 2: 6, 3: 8, 4: 10}
DIR_VEC = [(0, -1), (1, 0), (0, 1), (-1, 0)]  # 0=up, 1=right, 2=down, 3=left


class ConveyorBelt(BuildingBase):
    """传送带 - 首尾直连 + 双车道保留"""

    def __init__(self, x: int, y: int, template: dict):
        super().__init__(x, y, template)
        self.direction: int = 0
        self.tier: int = template.get("belt_tier", 1)
        spec = BELT_SPECS.get(self.tier, BELT_SPECS[1])
        self.belt_speed = spec["speed"]
        self.capacity = spec["capacity"]
        self.lanes: Dict[str, List[dict]] = {"left": [], "right": []}
        self.game_map: Optional["MapGrid"] = None

    def rotate(self):
        self.direction = (self.direction + 1) % 4

    @property
    def front_pos(self) -> Tuple[int, int]:
        """车头前方一格 (物品出口方向)"""
        dx, dy = DIR_VEC[self.direction]
        return self.x + dx, self.y + dy

    def add_item(self, item_id: str, lane: str = "left") -> bool:
        """向指定车道添加物品 (从尾部pos=1.0进入)"""
        if lane not in self.lanes:
            lane = "left"
        if len(self.lanes[lane]) >= self.capacity:
            return False
        self.lanes[lane].append({"id": item_id, "pos": 1.0})
        return True

    def _find_next_belt(self) -> Optional["ConveyorBelt"]:
        """查找车头正前方相邻的传送带"""
        fx, fy = self.front_pos
        if not self.game_map:
            return None
        for b in self.game_map.buildings:
            if b.x == fx and b.y == fy and isinstance(b, ConveyorBelt):
                return b
        return None

    def _transfer_front_item(self, lane: str):
        """尝试将某车道车头物品转移到下一格传送带对应车道"""
        lane_items = self.lanes[lane]
        if not lane_items:
            return
        front = lane_items[0]
        if front["pos"] > 0.01:  # 还没到车头位置
            return

        next_belt = self._find_next_belt()
        if not next_belt:
            return  # 前方无传送带, 物品排队等待

        # 车道映射: 直连 L→L, R→R
        # 转弯: 内→内, 外→外 (需要根据方向计算)
        target_lane = lane
        my_dir = self.direction
        next_dir = next_belt.direction

        if my_dir == next_dir:
            # 直连
            target_lane = lane
        elif (my_dir + 1) % 4 == next_dir:
            # 右转弯: 左→内侧, 右→外侧 (内侧=left lane of next belt going right)
            target_lane = "left" if lane == "left" else "right"
        elif (my_dir - 1) % 4 == next_dir:
            # 左转弯: 左→外侧, 右→内侧
            target_lane = "right" if lane == "left" else "left"

        if len(next_belt.lanes.get(target_lane, [])) >= next_belt.capacity:
            return  # 下游车道满了

        # 转移物品 (拷贝, 非引用)
        item = {"id": front["id"], "pos": 1.0}
        next_belt.lanes[target_lane].append(item)
        lane_items.pop(0)

    def tick(self, inventory) -> dict:
        """每帧推进: 从车头→车尾处理, 首尾直连传递"""
        for lane_name in ("left", "right"):
            lane = self.lanes[lane_name]
            if not lane:
                continue

            # 1. 车头物品尝试转移到下一格
            self._transfer_front_item(lane_name)

            # 2. 从车头→车尾推进 (已移除已转移的物品)
            for item in lane:
                item["pos"] -= self.belt_speed
                if item["pos"] < 0.01:
                    item["pos"] = 0.01  # 保留在车头等待

            # 3. 移除 pos < 0 (理论上不会触发, 安全清理)
            self.lanes[lane_name] = [it for it in lane if it["pos"] > -0.01]

        return {}

    def __repr__(self):
        li = len(self.lanes["left"]); ri = len(self.lanes["right"])
        return f"<Belt T{self.tier} dir={self.direction} ({li}/{ri})>"


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

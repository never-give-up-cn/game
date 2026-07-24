"""传送带系统 - 双车道物理引擎"""

from typing import Dict, List, Optional, Tuple
from building.base import BuildingBase


# 传送带速度（单向件/秒, 双向件/秒）
BELT_SPECS = {
    1: {"speed": 7.5/60, "max_per_lane": 4},   # 黄带 7.5/s
    2: {"speed": 15.0/60, "max_per_lane": 4},  # 红带 15/s
    3: {"speed": 22.5/60, "max_per_lane": 4},  # 蓝带 22.5/s
    4: {"speed": 30.0/60, "max_per_lane": 4},  # 涡轮 30/s
}

# 地下传送带最大跨越格数
UG_DIST = {1: 4, 2: 6, 3: 8, 4: 10}


class ConveyorBelt(BuildingBase):
    """传送带 - 双车道物理系统"""

    def __init__(self, x: int, y: int, template: dict):
        super().__init__(x, y, template)
        self.direction: int = 0
        self.tier: int = template.get("belt_tier", 1)
        spec = BELT_SPECS.get(self.tier, BELT_SPECS[1])
        self.belt_speed: float = spec["speed"]     # 每帧移动量
        self.max_per_lane: int = spec["max_per_lane"]
        # 车道: {lane: [{"id": item_id, "pos": float, "progress": float}]}
        self.lanes: Dict[str, List[dict]] = {"left": [], "right": []}

    def rotate(self):
        self.direction = (self.direction + 1) % 4

    def _lane_items(self, lane: str) -> int:
        """某车道物品数"""
        return len(self.lanes.get(lane, []))

    @property
    def total_items(self) -> int:
        return self._lane_items("left") + self._lane_items("right")

    def is_lane_full(self, lane: str) -> bool:
        return self._lane_items(lane) >= self.max_per_lane

    def add_item(self, item_id: str, lane: str = "left") -> bool:
        """向指定车道添加物品，返回是否成功"""
        if lane not in self.lanes:
            lane = "left"
        if self.is_lane_full(lane):
            return False
        # 新物品从末尾(pos=1.0)进入，排队等待
        self.lanes[lane].append({"id": item_id, "pos": 1.0, "progress": 0.0})
        return True

    def tick(self, inventory) -> dict:
        """每帧推进物品，同车道阻塞隔离"""
        for lane_name in ("left", "right"):
            lane = self.lanes[lane_name]
            if not lane:
                continue

            # 从前往后(高pos→低pos)推进
            # 前方(高pos)物品决定后方(低pos)能否移动
            for i in range(len(lane) - 1, -1, -1):
                item = lane[i]
                # 最前方的物品(pos最大)自由移动直到离开
                if i == len(lane) - 1:
                    item["pos"] -= self.belt_speed
                    item["progress"] = 1.0 - item["pos"]
                else:
                    # 检查前方物品位置
                    front = lane[i + 1]
                    gap = front["pos"] - item["pos"]
                    min_gap = 1.0 / self.max_per_lane  # 物品间最小间距
                    if gap > min_gap + self.belt_speed:
                        item["pos"] += self.belt_speed
                    elif gap > min_gap:
                        item["pos"] += gap - min_gap
                    # 否则原地排队
                    item["progress"] = 1.0 - item["pos"]

            # 移除离开传送带的物品(pos <= 0)
            self.lanes[lane_name] = [it for it in lane if it["pos"] > 0]

        return {}

    def can_accept(self, lane: str) -> bool:
        """某车道是否可接收新物品（至少有一个空位）"""
        return self._lane_items(lane) < self.max_per_lane

    def __repr__(self):
        li = len(self.lanes["left"])
        ri = len(self.lanes["right"])
        return f"<Belt T{self.tier} ({li}/{ri}) dir={self.direction}>"


class UndergroundBelt(BuildingBase):
    """地下传送带"""

    def __init__(self, x: int, y: int, template: dict):
        super().__init__(x, y, template)
        self.direction: int = 0
        self.tier: int = template.get("belt_tier", 1)
        self.max_dist: int = UG_DIST.get(self.tier, 4)
        self.is_entry: bool = True
        self.paired: bool = False

    def rotate(self):
        self.direction = (self.direction + 1) % 4

    def render_popup(self, screen, rect, mx, my, inventory, tech_unlocked, font_small, anim_frame):
        import pygame
        C = self._popup_colors()
        pr = rect
        s = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA)
        s.fill(C["bg"])
        screen.blit(s, pr)
        pygame.draw.rect(screen, (60, 160, 200), pr, 2, border_radius=8)
        title_bar = pygame.Rect(pr.x + 4, pr.y + 4, pr.w - 8, 28)
        pygame.draw.rect(screen, C["title_bg"], title_bar, border_radius=4)
        role = "入口 →" if self.is_entry else "← 出口"
        screen.blit(font_small.render(f"Underground {role}", True, C["title_text"]), (pr.x + 14, pr.y + 8))
        close_r = pygame.Rect(pr.right - 28, pr.top + 6, 20, 18)
        cc = (255,80,80) if close_r.collidepoint(mx,my) else (120,130,150)
        pygame.draw.rect(screen, cc, close_r, border_radius=3)
        screen.blit(font_small.render("×", True, (255,255,255)), (close_r.x+5, close_r.y+1))
        yy = pr.y+40; lx = pr.x+14
        for line in [f"Tier {self.tier}  Max span: {self.max_dist} tiles",
                     f"Connected: {'Yes' if self.paired else 'No'}",
                     "Pair required | R to rotate"]:
            screen.blit(font_small.render(line, True, C["text"]), (lx, yy)); yy += 18


class Splitter(BuildingBase):
    """分流器 - 均分/优先/过滤"""

    def __init__(self, x: int, y: int, template: dict):
        super().__init__(x, y, template)
        self.tier: int = template.get("belt_tier", 1)
        self.priority: str = "none"
        self.filter_items: List[str] = []
        self.input_buf: Dict[str, List] = {"left": [], "right": []}
        self.output_buf: Dict[str, List] = {"left": [], "right": []}
        self.toggle: int = 0  # 交替输出用

    def tick(self, inventory) -> dict:
        """分流器: 均分/优先/过滤"""
        for lane in ("left", "right"):
            if self.input_buf[lane]:
                item = self.input_buf[lane].pop(0)
                # 检查过滤
                if self.filter_items and item["id"] not in self.filter_items:
                    # 不匹配走另一输出
                    out_lane = "right" if lane == "left" else "left"
                elif self.priority == "left":
                    out_lane = "left"
                elif self.priority == "right":
                    out_lane = "right"
                else:
                    # 均分: 交替输出
                    out_lane = "left" if self.toggle % 2 == 0 else "right"
                    self.toggle += 1
                self.output_buf[out_lane].append(item)
        return {}

    def render_popup(self, screen, rect, mx, my, inventory, tech_unlocked, font_small, anim_frame):
        import pygame
        C = self._popup_colors()
        pr = rect
        s = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA)
        s.fill(C["bg"]); screen.blit(s, pr)
        pygame.draw.rect(screen, (60,200,160), pr, 2, border_radius=8)
        title_bar = pygame.Rect(pr.x+4, pr.y+4, pr.w-8, 28)
        pygame.draw.rect(screen, C["title_bg"], title_bar, border_radius=4)
        screen.blit(font_small.render(f"Splitter T{self.tier}", True, C["title_text"]), (pr.x+14, pr.y+8))
        close_r = pygame.Rect(pr.right-28, pr.top+6, 20,18)
        cc = (255,80,80) if close_r.collidepoint(mx,my) else (120,130,150)
        pygame.draw.rect(screen, cc, close_r, border_radius=3)
        screen.blit(font_small.render("×", True, (255,255,255)), (close_r.x+5, close_r.y+1))
        yy = pr.y+40; lx = pr.x+14
        pri = {"none":"Off","left":"Left","right":"Right"}
        lines = [
            f"Priority: {pri.get(self.priority,'Off')}",
            f"Filter: {','.join(self.filter_items) if self.filter_items else 'None'}",
            f"Lane: L→L  R→R  |  R to toggle priority",
        ]
        for line in lines:
            screen.blit(font_small.render(line, True, C["text"]), (lx, yy)); yy += 18

"""传送带系统 - 传送带 / 地下传送带 / 分流器"""

from typing import Dict, List, Optional, Tuple
from building.base import BuildingBase


# ── 传送带速度（件/秒）──
BELT_SPEEDS = {1: 15, 2: 30, 3: 45}


class ConveyorBelt(BuildingBase):
    """传送带 - 双车道物流基础"""

    def __init__(self, x: int, y: int, template: dict):
        super().__init__(x, y, template)
        self.direction: int = 0  # 0=上, 1=右, 2=下, 3=左
        self.tier: int = template.get("belt_tier", 1)
        self.speed: float = BELT_SPEEDS.get(self.tier, 15)
        # 车道物品 {lane: [(item_id, progress)]}  progress 0.0~1.0
        self.lanes: Dict[str, List[Tuple[str, float]]] = {"left": [], "right": []}

    def rotate(self):
        self.direction = (self.direction + 1) % 4

    def tick(self, inventory) -> dict:
        """推进物品在传送带上移动"""
        for lane in ("left", "right"):
            moved = []
            for item_id, progress in self.lanes[lane]:
                np = progress + self.speed / 60 / 10
                if np < 1.0:
                    moved.append((item_id, np))
            self.lanes[lane] = moved
        return {}

    def add_item(self, item_id: str, lane: str = "left"):
        """向传送带放置物品"""
        if lane in self.lanes and len(self.lanes[lane]) < 5:
            self.lanes[lane].append((item_id, 0.0))

    def render_popup(self, screen, rect, mx, my, inventory, tech_unlocked, font_small, anim_frame):
        import pygame
        C = self._popup_colors()
        C["border"] = [(200, 180, 60), (200, 80, 60), (60, 140, 220)][self.tier - 1]
        pr = rect
        s = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA)
        s.fill(C["bg"])
        screen.blit(s, pr)
        pygame.draw.rect(screen, C["border"], pr, 2, border_radius=8)

        title_bar = pygame.Rect(pr.x + 4, pr.y + 4, pr.w - 8, 28)
        pygame.draw.rect(screen, C["title_bg"], title_bar, border_radius=4)
        tier_name = ["基础", "高速", "极速"][self.tier - 1]
        label = f"📦 {tier_name}传送带  {self.tier*15}件/秒"
        screen.blit(font_small.render(label, True, C["title_text"]), (pr.x + 14, pr.y + 8))

        close_r = pygame.Rect(pr.right - 28, pr.top + 6, 20, 18)
        cc = (255, 80, 80) if close_r.collidepoint(mx, my) else (120, 130, 150)
        pygame.draw.rect(screen, cc, close_r, border_radius=3)
        screen.blit(font_small.render("×", True, (255, 255, 255)), (close_r.x + 5, close_r.y + 1))

        yy = pr.y + 40
        lx = pr.x + 14
        for line in [
            f"速度: {self.speed}件/秒  车道: 2",
            f"左车道: {len(self.lanes['left'])}件",
            f"右车道: {len(self.lanes['right'])}件",
            "R 旋转 | 无耗电",
        ]:
            screen.blit(font_small.render(line, True, C["text"]), (lx, yy)); yy += 18


class UndergroundBelt(BuildingBase):
    """地下传送带 - 成对使用跨越障碍"""

    def __init__(self, x: int, y: int, template: dict):
        super().__init__(x, y, template)
        self.direction: int = 0
        self.tier: int = template.get("belt_tier", 1)
        self.max_dist: int = {1: 4, 2: 6, 3: 8}[self.tier]
        self.is_entry: bool = True  # True=入口 False=出口
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
        screen.blit(font_small.render(f"🕳 地下传送带 {role}", True, C["title_text"]), (pr.x + 14, pr.y + 8))

        close_r = pygame.Rect(pr.right - 28, pr.top + 6, 20, 18)
        cc = (255, 80, 80) if close_r.collidepoint(mx, my) else (120, 130, 150)
        pygame.draw.rect(screen, cc, close_r, border_radius=3)
        screen.blit(font_small.render("×", True, (255, 255, 255)), (close_r.x + 5, close_r.y + 1))

        yy = pr.y + 40; lx = pr.x + 14
        for line in [
            f"等级: T{self.tier}  最大跨越: {self.max_dist}格",
            f"连接: {'已配对' if self.paired else '未配对'}",
            "需成对放置 | R 旋转",
        ]:
            screen.blit(font_small.render(line, True, C["text"]), (lx, yy)); yy += 18


class Splitter(BuildingBase):
    """分流器 - 均分/优先/过滤"""

    def __init__(self, x: int, y: int, template: dict):
        super().__init__(x, y, template)
        self.tier: int = template.get("belt_tier", 1)
        self.priority: str = "none"  # "none", "left", "right"
        self.filter_items: List[str] = []
        self.input_lanes: Dict[str, List] = {"left": [], "right": []}
        self.output_lanes: Dict[str, List] = {"left": [], "right": []}

    def render_popup(self, screen, rect, mx, my, inventory, tech_unlocked, font_small, anim_frame):
        import pygame
        C = self._popup_colors()
        pr = rect
        s = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA)
        s.fill(C["bg"])
        screen.blit(s, pr)
        pygame.draw.rect(screen, (60, 200, 160), pr, 2, border_radius=8)
        title_bar = pygame.Rect(pr.x + 4, pr.y + 4, pr.w - 8, 28)
        pygame.draw.rect(screen, C["title_bg"], title_bar, border_radius=4)
        screen.blit(font_small.render(f"🔀 分流器 T{self.tier}", True, C["title_text"]), (pr.x + 14, pr.y + 8))

        close_r = pygame.Rect(pr.right - 28, pr.top + 6, 20, 18)
        cc = (255, 80, 80) if close_r.collidepoint(mx, my) else (120, 130, 150)
        pygame.draw.rect(screen, cc, close_r, border_radius=3)
        screen.blit(font_small.render("×", True, (255, 255, 255)), (close_r.x + 5, close_r.y + 1))

        yy = pr.y + 40; lx = pr.x + 14
        pri_txt = {"none": "关闭", "left": "左优先", "right": "右优先"}
        lines = [
            f"优先: {pri_txt.get(self.priority, '关闭')}",
            f"过滤: {','.join(self.filter_items) if self.filter_items else '无'}",
            f"车道保留: 左→左  右→右",
            "R 切换优先 | 车道自动均分",
        ]
        for line in lines:
            screen.blit(font_small.render(line, True, C["text"]), (lx, yy)); yy += 18

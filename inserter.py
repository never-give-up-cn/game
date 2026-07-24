"""机械臂（Inserter）- 工厂物流核心，在建筑/传送带/箱子之间搬运物品"""

from typing import Optional, Tuple
from building.base import BuildingBase


# ── 方向常量 ──
UP, RIGHT, DOWN, LEFT = 0, 1, 2, 3
DIR_NAMES = ["↑上", "→右", "↓下", "←左"]
DIR_VECTORS = [(0, -1), (1, 0), (0, 1), (-1, 0)]


class Inserter(BuildingBase):
    """机械臂 - 自动在两点之间搬运物品"""

    def __init__(self, x: int, y: int, template: dict):
        super().__init__(x, y, template)

        # 核心属性（从模板读取）
        self.reach: int = template.get("reach", 1)          # 抓取距离
        self.speed: int = template.get("inserter_speed", 30) # 周期帧数
        self.stack_size: int = template.get("stack_size", 1) # 一次抓取数量
        self.filter_items: list = list(template.get("filter", []))  # 白名单
        self.uses_fuel: bool = template.get("uses_fuel", False)
        self.fuel: int = 0           # 当前燃料量
        self.fuel_max: int = template.get("fuel_max", 0)

        # 方向
        self.direction: int = UP  # 0=上 1=右 2=下 3=左

        # 动作状态
        self.arm_state: int = 0   # 0=待机 1=伸出抓取 2=缩回投放 3=归位
        self.arm_progress: float = 0.0  # 0.0~1.0
        self.held_item: Optional[str] = None  # 当前抓取的物品
        self.held_count: int = 0

    # ── 方向 ──

    def rotate(self):
        """顺时针旋转 90°"""
        self.direction = (self.direction + 1) % 4

    @property
    def pickup_pos(self) -> Tuple[int, int]:
        """抓取位置（后方一格）"""
        dx, dy = DIR_VECTORS[(self.direction + 2) % 4]
        return self.x + dx, self.y + dy

    @property
    def dropoff_pos(self) -> Tuple[int, int]:
        """投放位置（前方一格）"""
        dx, dy = DIR_VECTORS[self.direction]
        return self.x + dx, self.y + dy

    @property
    def direction_name(self) -> str:
        return DIR_NAMES[self.direction]

    # ── 燃料 ──

    def add_fuel(self, item_id: str) -> bool:
        """添加燃料，返回是否成功"""
        if not self.uses_fuel:
            return False
        fuel_values = {"coal": 20, "wood": 10}
        val = fuel_values.get(item_id, 0)
        if val > 0:
            self.fuel = min(self.fuel_max, self.fuel + val)
            return True
        return False

    @property
    def has_fuel(self) -> bool:
        if not self.uses_fuel:
            return True  # 电力机械臂无需燃料
        return self.fuel > 0

    # ── 过滤 ──

    def is_allowed(self, item_id: str) -> bool:
        """检查物品是否被允许抓取"""
        if not self.filter_items:
            return True  # 无过滤
        return item_id in self.filter_items

    # ── 生产 tick（自动搬运）──

    def tick(self, inventory) -> dict:
        events = {}

        # 燃料消耗
        if self.uses_fuel and self.fuel > 0:
            if self.arm_state != 0:  # 工作中才消耗
                self.fuel = max(0, self.fuel - 1)

        # 动作循环
        if self.arm_state == 0:  # 待机 → 尝试伸出
            if self.has_fuel and self._can_pickup(inventory):
                self.arm_state = 1
                self.arm_progress = 0.0
        else:
            self.arm_progress += 1.0 / self.speed
            if self.arm_progress >= 1.0:
                self.arm_progress = 0.0
                self._advance_state(inventory)
                if self.arm_state == 0:
                    events["transfer"] = True

        return events

    def _can_pickup(self, inventory) -> bool:
        """检查是否可以抓取"""
        # 找 pickup_pos 上的建筑
        return self.held_item is None and self.has_fuel

    def _advance_state(self, inventory):
        """推进一个动作阶段"""
        if self.arm_state == 1:  # 伸出抓取结束 → 抓取物品
            self._do_grab(inventory)
            self.arm_state = 2
        elif self.arm_state == 2:  # 缩回投放结束 → 放置物品
            self._do_drop(inventory)
            self.arm_state = 3
        elif self.arm_state == 3:  # 归位结束 → 待机
            self.arm_state = 0

    def _do_grab(self, inventory):
        """从抓取位置取物品"""
        if not inventory:
            return
        # 从玩家背包取（简化版）
        for iid in list(inventory.slots):
            if not iid:
                continue
            from item import ITEM_TEMPLATES as _it
            s = _it.get(iid)
            if not s:
                continue
            # 检查过滤
            if self.filter_items and iid not in self.filter_items:
                continue
            taken = inventory.remove_item(iid, self.stack_size)
            if taken > 0:
                self.held_item = iid
                self.held_count = taken
                break

    def _do_drop(self, inventory):
        """向投放位置放物品"""
        if self.held_item and inventory:
            inventory.add_item(self.held_item, self.held_count)
        self.held_item = None
        self.held_count = 0

    # ── 弹窗 ──

    def render_popup(self, screen, rect, mx, my, inventory, tech_unlocked, font_small, anim_frame):
        """机械臂信息弹窗"""
        import pygame
        C = self._popup_colors()
        C["border"] = (200, 160, 60)  # 机械臂黄铜色
        C["title_bg"] = (35, 28, 18)

        pr = rect
        s = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA)
        s.fill(C["bg"])
        screen.blit(s, pr)
        pygame.draw.rect(screen, C["border"], pr, 2, border_radius=8)

        # 标题
        title_bar = pygame.Rect(pr.x + 4, pr.y + 4, pr.w - 8, 28)
        pygame.draw.rect(screen, C["title_bg"], title_bar, border_radius=4)
        label = f"🤖 {self.name}  {self.direction_name}"
        screen.blit(font_small.render(label, True, C["title_text"]), (pr.x + 14, pr.y + 8))

        # 关闭
        close_r = pygame.Rect(pr.right - 28, pr.top + 6, 20, 18)
        cc = (255, 80, 80) if close_r.collidepoint(mx, my) else (120, 130, 150)
        pygame.draw.rect(screen, cc, close_r, border_radius=3)
        screen.blit(font_small.render("×", True, (255, 255, 255)), (close_r.x + 5, close_r.y + 1))

        yy = pr.y + 40
        lx = pr.x + 14

        # 信息
        lines = [
            f"方向: {self.direction_name}",
            f"抓取: 从({self.pickup_pos[0]},{self.pickup_pos[1]})",
            f"投放: 到({self.dropoff_pos[0]},{self.dropoff_pos[1]})",
            f"速度: {self.speed}f/周期  距离: {self.reach}格",
            f"堆叠: {self.stack_size}个",
        ]
        if self.uses_fuel:
            lines.append(f"燃料: {self.fuel}/{self.fuel_max}")
        if self.filter_items:
            lines.append(f"过滤: {','.join(self.filter_items)}")

        for line in lines:
            screen.blit(font_small.render(line, True, C["text"]), (lx, yy))
            yy += 18

        screen.blit(font_small.render("R 键旋转方向", True, C["dim"]), (lx, yy))

    def __repr__(self):
        return f"<Inserter {self.name} ({self.x},{self.y}) dir={self.direction_name}>"

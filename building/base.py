"""建筑基类 - 所有建筑的共用属性和方法"""

from typing import Dict, List, Optional, Tuple


class BuildingBase:
    """建筑基类，所有建筑继承此类的属性和方法"""

    def __init__(self, x: int, y: int, template: dict):
        # ========== 基础属性 ==========
        self.x = x
        self.y = y
        self.w = template["width"]
        self.h = template["height"]
        self.name = template["name"]
        self.color = template.get("color", "gray")
        self.description = template.get("description", "")

        # ========== 生命值 ==========
        self.max_hp: int = template.get("max_hp", 100)
        self.hp: int = self.max_hp

        # ========== 生产属性 ==========
        self.power_consumption: float = template.get("power_consumption", 0)
        self.speed: float = template.get("speed", 1.0)
        self.efficiency: float = template.get("efficiency", 1.0)
        self.quality: float = template.get("quality", 1.0)

        # ========== 环境 ==========
        self.pollution: float = template.get("pollution", 0)
        self.freshness: float = template.get("freshness", 1.0)
        self.weight: float = template.get("weight", 100)

        # ========== 插件 ==========
        self.plugin_slots: int = template.get("plugin_slots", 0)
        self.plugins: List[str] = []

        # ========== 建造材料 ==========
        self.construction_materials: Dict[str, int] = {}
        self.construction_materials.update(template.get("construction_materials", {}))

        # ========== 输入/输出 ==========
        self.inputs: Dict[str, int] = {}
        self.inputs.update(template.get("inputs", {}))

        self.outputs: Dict[str, int] = {}
        self.outputs.update(template.get("outputs", {}))

        # 生产缓存
        self.input_buffer: Dict[str, int] = {}
        self.output_buffer: Dict[str, int] = {}
        self.production_progress: float = 0.0  # 0.0 ~ 1.0

        # ========== 移动属性（车辆等） ==========
        self.move_speed: float = template.get("move_speed", 0)

    # ──────────── 格子属性 ────────────

    @property
    def occupied_cells(self) -> List[Tuple[int, int]]:
        """返回建筑占用的所有格子"""
        return [(self.x + dx, self.y + dy)
                for dx in range(self.w) for dy in range(self.h)]

    @property
    def center(self) -> Tuple[int, int]:
        """建筑中心坐标"""
        return (self.x + self.w // 2, self.y + self.h // 2)

    # ──────────── 生命值 ────────────

    def take_damage(self, amount: int):
        self.hp = max(0, self.hp - amount)

    def repair(self, amount: int):
        self.hp = min(self.max_hp, self.hp + amount)

    @property
    def is_destroyed(self) -> bool:
        return self.hp <= 0

    @property
    def hp_ratio(self) -> float:
        return self.hp / self.max_hp if self.max_hp > 0 else 0

    # ──────────── 生产系统 ────────────

    def can_produce(self, inventory) -> bool:
        """检查是否可以开始一轮生产（有无足够输入）"""
        for item_id, amount in self.inputs.items():
            if inventory.count(item_id) < amount:
                return False
        return True

    def produce(self, inventory) -> bool:
        """执行一轮生产：消耗输入 → 产生输出。成功返回 True"""
        if not self.can_produce(inventory):
            return False

        # 消耗输入
        for item_id, amount in self.inputs.items():
            inventory.remove_item(item_id, amount)
            self.input_buffer[item_id] = self.input_buffer.get(item_id, 0) + amount

        # 产生输出（受效率/速度/质量修正）
        for item_id, base_amount in self.outputs.items():
            actual = max(1, int(base_amount * self.efficiency * self.speed))
            inventory.add_item(item_id, actual)
            self.output_buffer[item_id] = self.output_buffer.get(item_id, 0) + actual

        self.production_progress = 0.0
        return True

    def tick(self, inventory) -> dict:
        """每帧更新，返回本次 tick 的事件日志"""
        events = {}

        # 新鲜度衰减
        if self.freshness > 0:
            self.freshness = max(0, self.freshness - 0.0001)

        # 生产进度推进
        if self.inputs and self.outputs:
            self.production_progress += 0.01 * self.speed
            if self.production_progress >= 1.0:
                if self.can_produce(inventory):
                    self.produce(inventory)
                    events["produced"] = self.name

        return events

    @property
    def production_summary(self) -> str:
        """一行生产信息"""
        parts = []
        if self.inputs:
            inp = ",".join(f"{n}x{v}" for n, v in self.inputs.items())
            parts.append(f"输入:{inp}")
        if self.outputs:
            out = ",".join(f"{n}x{v}" for n, v in self.outputs.items())
            parts.append(f"输出:{out}")
        if self.power_consumption:
            parts.append(f"耗电:{self.power_consumption}")
        if self.pollution:
            parts.append(f"污染:{self.pollution}")
        return " ".join(parts)

    # ──────────── 插件 ────────────

    def has_plugin_slot(self, max_tech_tier: int = 99) -> bool:
        return len(self.plugins) < min(self.plugin_slots, max_tech_tier)

    def add_plugin(self, plugin_id: str, max_tech_tier: int = 99) -> bool:
        if self.has_plugin_slot(max_tech_tier):
            self.plugins.append(plugin_id)
            return True
        return False

    def remove_plugin(self, plugin_id: str) -> bool:
        if plugin_id in self.plugins:
            self.plugins.remove(plugin_id)
            return True
        return False

    # ──────────── 序列化 ────────────

    def to_dict(self) -> dict:
        return {
            "x": self.x, "y": self.y,
            "name": self.name,
            "hp": self.hp,
            "freshness": self.freshness,
            "plugins": list(self.plugins),
            "production_progress": self.production_progress,
        }

    # ──────────── 弹窗渲染（可被子类覆盖） ────────────

    def render_popup(self, screen, rect, mx, my, inventory, tech_unlocked, font_small, anim_frame):
        """默认弹窗渲染 - 左输入+插件 | 右生产+状态
        子类可覆盖此方法实现自定义弹窗"""
        import pygame
        from item import ITEM_TEMPLATES as _it
        from tech_tree import get_building_bonuses

        b = self
        bonuses = get_building_bonuses(tech_unlocked)

        has_in = bool(b.inputs)
        has_out = bool(b.outputs)
        has_mats = has_in and all(inventory.count(iid) >= amt for iid, amt in b.inputs.items())
        out_full = has_out and any(inventory.count(oid) >= 20 for oid in b.outputs)

        if not has_in and not has_out:
            status_text, status_c = "⏸ 已暂停", (140, 150, 160)
        elif out_full:
            status_text, status_c = "📦 产出堆满", (220, 200, 60)
        elif has_in and has_mats:
            status_text, status_c = "⚡ 运行中", (80, 220, 120)
        elif has_in and not has_mats:
            status_text, status_c = "⏸ 原料不足", (255, 170, 60)
        else:
            status_text, status_c = "⏸ 待机", (140, 150, 160)

        C = self._popup_colors()
        pr = rect
        s = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA)
        s.fill(C["bg"])
        screen.blit(s, pr)
        pygame.draw.rect(screen, C["border"], pr, 2, border_radius=8)

        # 标题栏
        title_bar = pygame.Rect(pr.x + 4, pr.y + 4, pr.w - 8, 28)
        pygame.draw.rect(screen, C["title_bg"], title_bar, border_radius=4)
        screen.blit(font_small.render(f"□ {b.name}", True, C["title_text"]), (pr.x + 14, pr.y + 8))

        # 关闭×
        close_r = pygame.Rect(pr.right - 28, pr.top + 6, 20, 18)
        cc = (255, 80, 80) if close_r.collidepoint(mx, my) else (120, 130, 150)
        pygame.draw.rect(screen, cc, close_r, border_radius=3)
        screen.blit(font_small.render("×", True, (255, 255, 255)), (close_r.x + 5, close_r.y + 1))

        if title_bar.collidepoint(mx, my) and not close_r.collidepoint(mx, my):
            hint = font_small.render("拖动移动", True, (100, 140, 180))
            screen.blit(hint, (pr.x + pr.w // 2 - hint.get_width() // 2, pr.y + 8))

        # 内部区域
        inner_x = pr.x + 12
        inner_w = pr.w - 24
        col_w = (inner_w - 12) // 2
        lx, rx = inner_x, inner_x + col_w + 12
        yy = pr.y + 40

        def sec(text, color):
            return font_small.render(f"【{text}】", True, color)

        def div(y):
            pygame.draw.line(screen, C["divider"], (lx, y), (lx + col_w - 4, y), 1)
            return y + 4

        # 左: 原料输入
        screen.blit(sec("原料输入", C["sec_input"]), (lx, yy))
        yy += 20; yy = div(yy)
        if b.inputs:
            for iid, amt in b.inputs.items():
                tmpl = _it.get(iid)
                icon = tmpl.icon if tmpl else "?"
                mn = tmpl.name if tmpl else iid
                hv = inventory.count(iid)
                c = C["text"] if hv >= amt else C["warn"]
                screen.blit(font_small.render(f"{icon} {mn}  {hv}/{amt}", True, c), (lx + 4, yy))
                yy += 18
        else:
            screen.blit(font_small.render("  无需原料", True, C["dim"]), (lx + 4, yy)); yy += 18
        yy += 6

        # 左: 插件插槽
        screen.blit(sec("插件插槽", C["sec_plugin"]), (lx, yy))
        yy += 20; yy = div(yy)
        slot_w = col_w - 12
        for i in range(b.plugin_slots):
            sr = pygame.Rect(lx + 4, yy, slot_w, 26)
            sh = sr.collidepoint(mx, my)
            if i < len(b.plugins):
                pygame.draw.rect(screen, (30, 55, 40), sr, border_radius=4)
                pygame.draw.rect(screen, (80, 180, 80), sr, 1, border_radius=4)
                screen.blit(font_small.render(f"  ● {b.plugins[i]}", True, C["green"]), (lx + 8, yy + 4))
            else:
                bg = C["slot_bg"] if not sh else (30, 40, 60)
                pygame.draw.rect(screen, bg, sr, border_radius=4)
                for dx in range(2, slot_w - 4, 8):
                    pygame.draw.rect(screen, C["slot_border"], (lx + 6 + dx, yy + 2, 4, sr.h - 4))
                bc2 = (80, 100, 130) if sh else C["slot_border"]
                pygame.draw.rect(screen, bc2, sr, 1, border_radius=4)
                txt = "  放入插件" if sh else "  空"
                tc = (120, 180, 220) if sh else C["dim"]
                screen.blit(font_small.render(txt, True, tc), (lx + 8, yy + 4))
            yy += 30

        # 右半部分交给子类可覆盖的方法
        self._render_popup_right(screen, pr, rx, yy, font_small, _it,
                                 inventory, bonuses, status_text, status_c,
                                 has_in, has_out, has_mats, C)

    def _render_popup_right(self, screen, pr, rx, yy, font_small, _it,
                            inventory, bonuses, status_text, status_c,
                            has_in, has_out, has_mats, C):
        """弹窗右侧 - 产出+库存+进度+状态（子类可重写）"""
        import pygame
        b = self
        col_w = (pr.w - 24 - 12) // 2

        screen.blit(font_small.render("【生产信息】", True, C["sec_output"]), (rx, pr.y + 40))
        yy2 = pr.y + 60
        pygame.draw.line(screen, C["divider"], (rx, yy2), (rx + col_w - 4, yy2), 1); yy2 += 6

        if b.outputs:
            for iid, amt in b.outputs.items():
                tmpl = _it.get(iid)
                icon = tmpl.icon if tmpl else "?"
                mn = tmpl.name if tmpl else iid
                actual = max(1, int(amt * (1 + bonuses['efficiency']) * (1 + bonuses['speed'])))
                screen.blit(font_small.render(f"产出：{icon} {mn}  ×{actual}/周期", True, C["text"]), (rx + 4, yy2))
                yy2 += 18
        else:
            screen.blit(font_small.render("  无产出", True, C["dim"]), (rx + 4, yy2)); yy2 += 18

        if b.outputs and any(inventory.count(oid) > 0 for oid in b.outputs):
            for iid, _ in b.outputs.items():
                tmpl = _it.get(iid)
                icon = tmpl.icon if tmpl else "?"
                mn = tmpl.name if tmpl else iid
                hv = inventory.count(iid)
                screen.blit(font_small.render(f"当前库存：{icon} {mn}  ×{hv}", True, C["dim"]), (rx + 4, yy2))
                yy2 += 18
        else:
            screen.blit(font_small.render("  无库存", True, C["dim"]), (rx + 4, yy2)); yy2 += 18
        yy2 += 6

        screen.blit(font_small.render("【运行进度】", True, C["sec_progress"]), (rx, yy2))
        yy2 += 20
        pygame.draw.line(screen, C["divider"], (rx, yy2), (rx + col_w - 4, yy2), 1); yy2 += 6

        if has_in and has_out:
            bw = col_w - 8; bh = 10; bx = rx + 4
            progress = b.production_progress
            pygame.draw.rect(screen, (18, 22, 34), (bx, yy2, bw, bh), border_radius=5)
            if progress > 0:
                fill = int(bw * progress)
                for i in range(fill):
                    ratio = i / max(fill, 1)
                    r2 = int(60 + 180 * ratio); g2 = int(200 - 120 * ratio); b2 = int(255 - 80 * ratio)
                    pygame.draw.rect(screen, (r2, g2, b2), (bx + i, yy2 + 1, 1, bh - 2))
            fg = status_c if has_mats else (80, 70, 60)
            pygame.draw.rect(screen, fg, (bx, yy2, bw, bh), 1, border_radius=5)
            screen.blit(font_small.render(f"生产进度 {int(progress * 100)}%", True, (180, 200, 220)), (bx + 4, yy2 - 1))
        else:
            screen.blit(font_small.render("  无需生产", True, C["dim"]), (rx + 4, yy2))
        yy2 += 18
        screen.blit(font_small.render(f"状态：{status_text}", True, status_c), (rx + 4, yy2))

    def _popup_colors(self):
        """弹窗配色方案（子类可覆盖）"""
        return {
            "bg": (12, 14, 24, 245), "border": (60, 160, 255),
            "title_bg": (16, 22, 40), "title_text": (140, 220, 255),
            "text": (220, 220, 220), "dim": (140, 140, 140),
            "warn": (255, 170, 60), "green": (150, 255, 150),
            "divider": (30, 40, 55), "slot_bg": (22, 28, 42),
            "slot_border": (50, 60, 75),
            "sec_input": (120, 180, 220), "sec_plugin": (140, 180, 200),
            "sec_output": (100, 220, 150), "sec_progress": (200, 180, 120),
        }

    def __repr__(self):
        return f"<{self.name} ({self.x},{self.y}) {self.w}x{self.h}>"

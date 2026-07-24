"""苹果工厂 - 建筑自定义弹窗示例"""

from .base import BuildingBase


class AppleFactory(BuildingBase):
    """苹果工厂：消耗煤炭生产苹果，自定义弹窗风格"""

    def render_popup(self, screen, rect, mx, my, inventory, tech_unlocked, font_small, anim_frame):
        """苹果主题自定义弹窗"""
        import pygame
        from item import ITEM_TEMPLATES as _it

        b = self
        C = self._popup_colors()
        # 苹果主题色
        C["border"] = (180, 80, 60)
        C["title_bg"] = (40, 20, 18)
        C["title_text"] = (255, 200, 180)
        C["sec_input"] = (220, 160, 140)
        C["sec_output"] = (200, 220, 140)
        C["sec_progress"] = (220, 180, 140)

        pr = rect
        s = pygame.Surface((pr.w, pr.h), pygame.SRCALPHA)
        s.fill(C["bg"])
        screen.blit(s, pr)
        pygame.draw.rect(screen, C["border"], pr, 2, border_radius=8)

        # 标题（苹果图标）
        title_bar = pygame.Rect(pr.x + 4, pr.y + 4, pr.w - 8, 28)
        pygame.draw.rect(screen, C["title_bg"], title_bar, border_radius=4)
        screen.blit(font_small.render(f"🍎 {b.name}", True, C["title_text"]), (pr.x + 14, pr.y + 8))

        # 关闭
        close_r = pygame.Rect(pr.right - 28, pr.top + 6, 20, 18)
        cc = (255, 80, 80) if close_r.collidepoint(mx, my) else (150, 100, 100)
        pygame.draw.rect(screen, cc, close_r, border_radius=3)
        screen.blit(font_small.render("×", True, (255, 255, 255)), (close_r.x + 5, close_r.y + 1))

        # 内容：输入 → 输出（双栏）
        lx = pr.x + 14
        yy = pr.y + 42
        col_w = (pr.w - 40) // 2
        rx = lx + col_w + 12

        # 左侧：输入
        screen.blit(font_small.render("【原料】", True, C["sec_input"]), (lx, yy))
        yy += 20
        for iid, amt in b.inputs.items():
            tmpl = _it.get(iid)
            icon = tmpl.icon if tmpl else "?"
            mn = tmpl.name if tmpl else iid
            hv = inventory.count(iid)
            c = C["text"] if hv >= amt else C["warn"]
            screen.blit(font_small.render(f"  {icon} {mn}  {hv}/{amt}", True, c), (lx + 4, yy))
            yy += 22

        # 右侧：产出 + 进度
        yy = pr.y + 42
        screen.blit(font_small.render("【产出】", True, C["sec_output"]), (rx, yy))
        yy += 20
        for iid, amt in b.outputs.items():
            tmpl = _it.get(iid)
            icon = tmpl.icon if tmpl else "?"
            mn = tmpl.name if tmpl else iid
            hv = inventory.count(iid)
            screen.blit(font_small.render(f"  {icon} {mn}  ×{amt}/周期", True, C["text"]), (rx + 4, yy))
            yy += 20
            screen.blit(font_small.render(f"  库存 ×{hv}", True, C["dim"]), (rx + 4, yy))
            yy += 22

        # 进度条（底部全宽）
        by = pr.bottom - 24
        bw = pr.w - 24
        bh = 10
        bx = pr.x + 12
        progress = b.production_progress
        pygame.draw.rect(screen, (30, 20, 18), (bx, by, bw, bh), border_radius=5)
        if progress > 0:
            fill = int(bw * progress)
            for i in range(fill):
                r2 = int(200 - 80 * (i / max(fill, 1)))
                g2 = int(120 + 80 * (i / max(fill, 1)))
                pygame.draw.rect(screen, (r2, g2, 60), (bx + i, by + 1, 1, bh - 2))
        pygame.draw.rect(screen, (200, 120, 80), (bx, by, bw, bh), 1, border_radius=5)
        pct = font_small.render(f"🍎准备中 {int(progress * 100)}%", True, (255, 200, 160))
        screen.blit(pct, (bx + 4, by - 1))

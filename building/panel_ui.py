"""建筑交互面板 - 全屏双栏：背包 | 建筑内部"""

import pygame
from typing import List, Tuple

from item import ITEM_TEMPLATES as _it
from backpack.ui import draw_inventory_panel, C as UC
from tech_tree import get_building_bonuses, max_plugin_tier

# 配色（复用背包 UI 配色 + 扩展）
C = dict(UC)
C.update({
    "bld_bg": (14, 18, 28),
    "bld_border": (35, 50, 70),
    "slot_in": (25, 40, 55),
    "slot_in_border": (50, 80, 110),
    "slot_out": (30, 50, 35),
    "slot_out_border": (60, 120, 60),
    "slot_empty": (20, 24, 35),
})


def draw_building_interaction(screen, font, font_small, font_large,
                               building, inventory, tech_unlocked,
                               mouse_pos, anim_frame, transfer_actions: list):
    """全屏双栏：左侧玩家背包 | 右侧建筑交互"""
    w, h = screen.get_size()
    mx, my = mouse_pos
    transfer_actions.clear()

    # ── 全屏半透明背景 ──
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    overlay.fill(C["bg"])
    screen.blit(overlay, (0, 0))

    # ── 标题栏 ──
    title_bar = pygame.Rect(0, 0, w, 36)
    pygame.draw.rect(screen, C["title_bg"], title_bar)
    pygame.draw.line(screen, C["divider"], (0, 36), (w, 36), 1)

    bonuses = get_building_bonuses(tech_unlocked)
    ptier = max_plugin_tier(tech_unlocked)
    status_text = _get_status(building, inventory)
    title = f"□ {building.name}  ({building.x},{building.y})  |  {status_text}  |  [ESC 关闭]"
    screen.blit(font.render(title, True, C["title"]), (16, 8))

    # ── 左右双栏 ──
    gap = 8
    col_w = (w - 20 - gap) // 2
    top = 44
    col_h = h - top - 12

    left_x = 8
    right_x = left_x + col_w + gap

    # 左: 玩家背包（和独立背包界面保持一致）
    draw_inventory_panel(screen, font, font_small, inventory,
                         left_x, top, col_w, col_h, mx, my, anim_frame)

    # 右: 建筑内部
    _draw_building_container(screen, font, font_small, font_large,
                             building, inventory, bonuses, ptier,
                             right_x, top, col_w, col_h, mx, my,
                             anim_frame, transfer_actions)


def _get_status(b, inv):
    """返回建筑状态简写"""
    has_in = bool(b.inputs)
    has_out = bool(b.outputs)
    if not has_in and not has_out:
        return "⏸ 待机"
    has_mats = has_in and all(inv.count(iid) >= amt for iid, amt in b.inputs.items())
    out_full = has_out and any(inv.count(oid) >= 20 for oid in b.outputs)
    if out_full:
        return "📦 堆满"
    if has_in and has_mats:
        return "⚡ 运行中"
    if has_in and not has_mats:
        return "⏸ 缺原料"
    return "⏸ 待机"


def _draw_building_container(screen, font, font_small, font_large,
                              b, inv, bonuses, ptier,
                              px, py, pw, ph, mx, my,
                              anim_frame, transfer_actions):
    """右侧：建筑容器面板"""
    # 面板背景
    pygame.draw.rect(screen, C["bld_bg"], (px, py, pw, ph), border_radius=6)
    pygame.draw.rect(screen, C["bld_border"], (px, py, pw, ph), 1, border_radius=6)

    yy = py + 12

    # ── 标题行 ──
    screen.blit(font.render(f"📦 {b.name}  内部", True, C["title"]), (px + 12, yy))
    yy += 30

    # 状态行
    status = _get_status(b, inv)
    hp_str = f"HP: {b.hp}/{b.max_hp}"
    info = font_small.render(f"{status}  |  {hp_str}  |  效率:{1+bonuses['efficiency']:.1f}  速度:{1+bonuses['speed']:.1f}",
                             True, C["dim"])
    screen.blit(info, (px + 12, yy))
    yy += 24

    # ── 输入槽 ──
    if b.inputs:
        screen.blit(font_small.render("▶ 输入缓冲区", True, C["accent"]), (px + 12, yy))
        yy += 22
        pygame.draw.line(screen, C["divider"], (px + 12, yy), (px + pw - 12, yy), 1)
        yy += 6

        slot_size = 42
        gap = 6
        cols = max(1, (pw - 24 - gap) // (slot_size + gap))

        for idx, (iid, amt) in enumerate(b.inputs.items()):
            row = idx // cols
            col = idx % cols
            sx = px + 12 + col * (slot_size + gap)
            sy = yy + row * (slot_size + gap + 20)

            tmpl = _it.get(iid)
            icon = tmpl.icon if tmpl else "?"
            mn = tmpl.name if tmpl else iid
            hv = inv.count(iid)
            enough = hv >= amt

            slot_r = pygame.Rect(sx, sy, slot_size, slot_size)
            hover = slot_r.collidepoint(mx, my)

            # 槽背景
            bg = C["slot_in"] if not hover else (35, 55, 75)
            pygame.draw.rect(screen, bg, slot_r, border_radius=4)
            bc = C["accent"] if enough else C["warn"]
            pygame.draw.rect(screen, bc if hover else C["slot_in_border"], slot_r, 1, border_radius=4)

            # 图标
            screen.blit(font_small.render(icon, True, C["text"]), (sx + 8, sy + 4))
            c = C["text"] if enough else C["warn"]
            screen.blit(font_small.render(f"{hv}/{amt}", True, c), (sx + 2, sy + 24))

            # 物品名
            screen.blit(font_small.render(mn, True, C["dim"]), (sx, sy + slot_size + 2))

            # Shift+左键提示
            if hover:
                tip = font_small.render("左键放入", True, (150, 200, 255))
                screen.blit(tip, (sx + slot_size + 4, sy + 6))
                transfer_actions.append(('input', slot_r, iid, amt))

        yy += ((len(b.inputs) + cols - 1) // cols) * (slot_size + gap + 22) + 8
    else:
        screen.blit(font_small.render("  无需原料", True, C["dim"]), (px + 14, yy))
        yy += 22

    yy += 6

    # ── 输出槽 ──
    if b.outputs:
        screen.blit(font_small.render("▶ 输出缓冲区", True, (100, 220, 150)), (px + 12, yy))
        yy += 22
        pygame.draw.line(screen, C["divider"], (px + 12, yy), (px + pw - 12, yy), 1)
        yy += 6

        slot_size = 42
        gap = 6
        cols = max(1, (pw - 24 - gap) // (slot_size + gap))

        for idx, (iid, amt) in enumerate(b.outputs.items()):
            row = idx // cols
            col = idx % cols
            sx = px + 12 + col * (slot_size + gap)
            sy = yy + row * (slot_size + gap + 20)

            tmpl = _it.get(iid)
            icon = tmpl.icon if tmpl else "?"
            mn = tmpl.name if tmpl else iid
            actual = max(1, int(amt * (1 + bonuses['efficiency']) * (1 + bonuses['speed'])))
            hv = inv.count(iid)

            slot_r = pygame.Rect(sx, sy, slot_size, slot_size)
            hover = slot_r.collidepoint(mx, my)

            pygame.draw.rect(screen, C["slot_out"] if not hover else (45, 70, 50), slot_r, border_radius=4)
            bc = C["green"] if hover else C["slot_out_border"]
            pygame.draw.rect(screen, bc, slot_r, 1, border_radius=4)

            screen.blit(font_small.render(icon, True, C["text"]), (sx + 8, sy + 4))
            screen.blit(font_small.render(f"×{actual}/周期", True, C["dim"]), (sx + 2, sy + 24))
            screen.blit(font_small.render(mn, True, C["dim"]), (sx, sy + slot_size + 2))

            if hover:
                tip = font_small.render(f"库存 ×{hv}  左键取出", True, (150, 220, 180))
                screen.blit(tip, (sx + slot_size + 4, sy + 6))
                transfer_actions.append(('output', slot_r, iid, hv))

        yy += ((len(b.outputs) + cols - 1) // cols) * (slot_size + gap + 22) + 8
    else:
        screen.blit(font_small.render("  无产出", True, C["dim"]), (px + 14, yy))
        yy += 22

    yy += 6

    # ── 插件槽 ──
    if b.plugin_slots > 0:
        screen.blit(font_small.render("▶ 插件", True, (140, 180, 200)), (px + 12, yy))
        yy += 22
        pygame.draw.line(screen, C["divider"], (px + 12, yy), (px + pw - 12, yy), 1)
        yy += 4

        ms = min(b.plugin_slots, ptier)
        for i in range(ms):
            sr = pygame.Rect(px + 12 + i * 34, yy, 30, 30)
            if i < len(b.plugins):
                pygame.draw.rect(screen, (30, 55, 40), sr, border_radius=4)
                pygame.draw.rect(screen, (80, 180, 80), sr, 1, border_radius=4)
            else:
                pygame.draw.rect(screen, C["slot_empty"], sr, border_radius=4)
                pygame.draw.rect(screen, C["slot_border"], sr, 1, border_radius=4)
                screen.blit(font_small.render("+", True, C["dim"]), (sr.x + 8, sr.y + 4))
        yy += 36

    # ── 生产进度条（底部） ──
    if b.inputs and b.outputs:
        by = py + ph - 30
        bw = pw - 24
        bh = 12
        bx = px + 12
        progress = b.production_progress

        pygame.draw.rect(screen, (18, 22, 34), (bx, by, bw, bh), border_radius=6)
        if progress > 0:
            fill = int(bw * progress)
            for i in range(fill):
                ratio = i / max(fill, 1)
                r2 = int(60 + 180 * ratio); g2 = int(200 - 120 * ratio); b2 = int(255 - 80 * ratio)
                pygame.draw.rect(screen, (r2, g2, b2), (bx + i, by + 1, 1, bh - 2))
        pygame.draw.rect(screen, (60, 120, 200), (bx, by, bw, bh), 1, border_radius=6)
        pct = font_small.render(f"生产进度 {int(progress * 100)}%", True, (180, 200, 220))
        screen.blit(pct, (bx + 4, by - 1))

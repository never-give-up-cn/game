"""背包全屏界面 - 三栏横向：背包 | 物流 | 制作台"""

import pygame
from typing import List, Tuple, Optional

from item import ITEM_TEMPLATES
from backpack.inventory import Inventory
from backpack.logistics import Logistics
from crafting import MANUAL_RECIPES, get_craftable_manual, Recipe


# ── 配色 ──
C = {
    "bg": (10, 12, 20, 245),
    "panel": (16, 18, 28),
    "panel_border": (40, 50, 65),
    "title": (140, 200, 240),
    "title_bg": (20, 25, 38),
    "text": (220, 220, 220),
    "dim": (130, 140, 150),
    "slot": (22, 26, 38),
    "slot_hover": (35, 45, 65),
    "slot_border": (40, 50, 60),
    "accent": (100, 180, 255),
    "green": (80, 200, 100),
    "red": (200, 70, 70),
    "warn": (255, 170, 60),
    "trash_bg": (35, 22, 22),
    "trash_border": (80, 40, 40),
    "craft_ok": (35, 55, 35),
    "craft_missing": (45, 30, 30),
    "divider": (30, 38, 50),
    "logistics_bg": (18, 22, 32),
}


def draw_backpack_ui(screen, font, font_small, font_large,
                     inv: Inventory, logistics: Logistics,
                     mouse_pos, anim_frame, craft_buttons: list,
                     selected_item=None):
    """绘制三栏背包界面"""
    w, h = screen.get_size()
    mx, my = mouse_pos
    craft_buttons.clear()

    # 全屏半透明背景
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    overlay.fill(C["bg"])
    screen.blit(overlay, (0, 0))

    # ── 标题栏 ──
    title_bar = pygame.Rect(0, 0, w, 36)
    pygame.draw.rect(screen, C["title_bg"], title_bar)
    pygame.draw.line(screen, C["divider"], (0, 36), (w, 36), 1)
    screen.blit(font.render("背包管理系统  [ESC 关闭]", True, C["title"]), (16, 8))

    # 搜索按钮（右上角）
    search_r = pygame.Rect(w - 80, 6, 70, 24)
    pygame.draw.rect(screen, (30, 35, 50), search_r, border_radius=4)
    screen.blit(font_small.render("🔍 搜索", True, C["dim"]), (search_r.x + 8, search_r.y + 4))

    # ── 三栏布局 ──
    panel_gap = 8
    col_w = (w - 20 - panel_gap * 2) // 3
    top = 44
    col_h = h - top - 12

    left_x = 8
    mid_x = left_x + col_w + panel_gap
    right_x = mid_x + col_w + panel_gap

    # 绘制三个面板
    _draw_inventory_panel(screen, font, font_small, inv, left_x, top, col_w, col_h, mx, my, anim_frame)
    _draw_logistics_panel(screen, font, font_small, logistics, inv, mid_x, top, col_w, col_h, mx, my)
    _draw_crafting_panel(screen, font, font_small, inv, right_x, top, col_w, col_h, mx, my, craft_buttons)


# ════════════════════════════════════════
# 左: 背包网格
# ════════════════════════════════════════

def _draw_inventory_panel(screen, font, font_small, inv: Inventory,
                          px, py, pw, ph, mx, my, anim_frame):
    # 面板背景
    pygame.draw.rect(screen, C["panel"], (px, py, pw, ph), border_radius=6)
    pygame.draw.rect(screen, C["panel_border"], (px, py, pw, ph), 1, border_radius=6)
    screen.blit(font.render("🎒 背包", True, C["title"]), (px + 12, py + 8))

    # 装备栏（顶部预留）
    eq_y = py + 34
    eq_slots = 4
    eq_w = (pw - 24 - (eq_slots - 1) * 4) // eq_slots
    for i in range(eq_slots):
        er = pygame.Rect(px + 12 + i * (eq_w + 4), eq_y, eq_w, 30)
        pygame.draw.rect(screen, (18, 20, 30), er, border_radius=4)
        pygame.draw.rect(screen, C["slot_border"], er, 1, border_radius=4)
        if i == 0:
            screen.blit(font_small.render("护甲", True, C["dim"]), (er.x + 6, er.y + 6))

    # 物品网格
    grid_y = eq_y + 38
    slot_size = 36
    gap = 4
    cols = max(1, (pw - 20 - gap) // (slot_size + gap))
    rows = (Inventory.MAX_SLOTS + cols - 1) // cols

    for idx in range(Inventory.MAX_SLOTS):
        row = idx // cols
        col = idx % cols
        sx = px + 10 + col * (slot_size + gap)
        sy = grid_y + row * (slot_size + gap)
        slot_r = pygame.Rect(sx, sy, slot_size, slot_size)
        stack = inv.slots[idx] if idx < len(inv.slots) else None
        hover = slot_r.collidepoint(mx, my)

        # 选中高亮
        if idx == inv.selected:
            pygame.draw.rect(screen, C["accent"], slot_r.inflate(4, 4), border_radius=4)
        elif hover and stack:
            pygame.draw.rect(screen, C["slot_hover"], slot_r, border_radius=4)
        else:
            pygame.draw.rect(screen, C["slot"], slot_r, border_radius=4)
        pygame.draw.rect(screen, C["slot_border"], slot_r, 1, border_radius=4)

        if stack:
            # 图标
            try:
                icon = font.render(stack.item.icon, True, C["text"])
            except Exception:
                icon = font.render("?", True, C["text"])
            screen.blit(icon, (sx + 2, sy + 2))
            # 数量右下角
            if stack.quantity > 1:
                qty = font_small.render(str(stack.quantity), True, C["accent"])
                screen.blit(qty, (sx + slot_size - qty.get_width() - 2,
                                  sy + slot_size - qty.get_height() - 2))

    # 垃圾槽（底部）
    trash_y = py + ph - 50
    pygame.draw.line(screen, C["divider"], (px + 10, trash_y - 4), (px + pw - 10, trash_y - 4), 1)
    screen.blit(font_small.render("🗑 垃圾槽", True, C["dim"]), (px + 12, trash_y + 2))
    for i in range(4):
        tr = pygame.Rect(px + 12 + i * (38 + 4), trash_y + 20, 36, 36)
        pygame.draw.rect(screen, C["trash_bg"], tr, border_radius=4)
        pygame.draw.rect(screen, C["trash_border"], tr, 1, border_radius=4)
        # 闪烁骷髅标记
        if (anim_frame // 30) % 2 == 0:
            screen.blit(font_small.render("💀", True, (150, 50, 50)), (tr.x + 6, tr.y + 6))


# ════════════════════════════════════════
# 中: 物流 - 无人机补给
# ════════════════════════════════════════

def _draw_logistics_panel(screen, font, font_small,
                          logistics: Logistics, inv: Inventory,
                          px, py, pw, ph, mx, my):
    pygame.draw.rect(screen, C["logistics_bg"], (px, py, pw, ph), border_radius=6)
    pygame.draw.rect(screen, C["panel_border"], (px, py, pw, ph), 1, border_radius=6)

    # 标题 + 自动丢弃开关
    screen.blit(font.render("📦 无人机物流", True, C["title"]), (px + 12, py + 8))
    auto_r = pygame.Rect(px + pw - 110, py + 8, 98, 22)
    auto_bg = (60, 40, 30) if logistics.auto_discard else (30, 35, 40)
    auto_txt = "丢弃未请求" if logistics.auto_discard else "自动管理关"
    pygame.draw.rect(screen, auto_bg, auto_r, border_radius=4)
    screen.blit(font_small.render(auto_txt, True, C["warn"] if logistics.auto_discard else C["dim"]),
                (auto_r.x + 6, auto_r.y + 3))
    if auto_r.collidepoint(mx, my):
        screen.blit(font_small.render("点击切换", True, C["dim"]), (auto_r.x + auto_r.w + 4, auto_r.y + 3))

    # 请求列表
    list_y = py + 38
    screen.blit(font_small.render("物资需求清单", True, C["accent"]), (px + 12, list_y))
    list_y += 20

    reqs = logistics.get_requests_sorted()
    if reqs:
        for req in reqs:
            current = inv.count(req.item_id)
            enough = current >= req.target_quantity
            bar_r = pygame.Rect(px + 12, list_y, pw - 24, 22)
            hover = bar_r.collidepoint(mx, my)

            bg = (30, 38, 50) if hover else (22, 28, 40)
            pygame.draw.rect(screen, bg, bar_r, border_radius=4)

            # 需求进度条
            ratio = min(1.0, current / max(req.target_quantity, 1))
            fill_w = int((pw - 24) * ratio)
            fc = C["green"] if enough else C["warn"]
            pygame.draw.rect(screen, fc, (px + 12, list_y, fill_w, 22), border_radius=4)
            # 半透明覆盖
            s2 = pygame.Surface((fill_w, 22), pygame.SRCALPHA)
            s2.fill((*fc[:3], 30))
            screen.blit(s2, (px + 12, list_y))

            text = f"{req.icon} {req.name}  {current}/{req.target_quantity}"
            c = C["text"] if enough else C["warn"]
            screen.blit(font_small.render(text, True, c), (px + 16, list_y + 3))
            list_y += 26
    else:
        screen.blit(font_small.render("  暂无需求，点击下方添加", True, C["dim"]), (px + 14, list_y))
        list_y += 26

    # 添加请求按钮 [+]
    add_y = list_y + 4
    add_r = pygame.Rect(px + 12, add_y, pw - 24, 26)
    hover_add = add_r.collidepoint(mx, my)
    pygame.draw.rect(screen, (30, 45, 55) if hover_add else (22, 35, 45), add_r, border_radius=4)
    pygame.draw.rect(screen, C["accent"], add_r, 1, border_radius=4)
    screen.blit(font_small.render("+ 添加物资需求", True, C["accent"]), (add_r.x + 8, add_r.y + 4))

    # 底部状态摘要
    summary_y = py + ph - 32
    total_req = len(reqs)
    total_items = sum(inv.count(r.item_id) for r in reqs)
    screen.blit(
        font_small.render(f"监控中: {total_req} 种物资  |  背包: {len(inv.list_items())} 格",
                          True, C["dim"]),
        (px + 12, summary_y))


# ════════════════════════════════════════
# 右: 制作台
# ════════════════════════════════════════

def _draw_crafting_panel(screen, font, font_small,
                         inv: Inventory,
                         px, py, pw, ph, mx, my,
                         craft_buttons: list):
    pygame.draw.rect(screen, C["panel"], (px, py, pw, ph), border_radius=6)
    pygame.draw.rect(screen, C["panel_border"], (px, py, pw, ph), 1, border_radius=6)

    screen.blit(font.render("🔧 制作台", True, C["title"]), (px + 12, py + 8))

    # 常用/最近配方（顶部快捷栏）
    fav_y = py + 34
    recipes = list(MANUAL_RECIPES.values())
    if recipes:
        fav_w = (pw - 20 - 3 * 4) // 4
        for i in range(min(4, len(recipes))):
            r = recipes[i]
            fr = pygame.Rect(px + 10 + i * (fav_w + 4), fav_y, fav_w, 32)
            can = r.can_craft(inv)
            bg = C["craft_ok"] if can else C["craft_missing"]
            hover = fr.collidepoint(mx, my)
            if hover and can:
                bg = (45, 70, 45)
            pygame.draw.rect(screen, bg, fr, border_radius=4)
            pygame.draw.rect(screen, C["slot_border"], fr, 1, border_radius=4)
            screen.blit(font_small.render(r.name, True, C["text"] if can else C["dim"]),
                        (fr.x + 4, fr.y + 6))
    else:
        screen.blit(font_small.render("无可用配方", True, C["dim"]), (px + 14, fav_y))

    # 全部配方网格
    grid_y = fav_y + 40
    screen.blit(font_small.render("全部配方", True, C["accent"]), (px + 12, grid_y))
    grid_y += 20

    slot_size = 42
    gap = 4
    cols = max(1, (pw - 20 - gap) // (slot_size + gap))

    for idx, recipe in enumerate(recipes):
        row = idx // cols
        col = idx % cols
        sx = px + 10 + col * (slot_size + gap)
        sy = grid_y + row * (slot_size + gap)

        # 检查是否超出面板高度
        if sy + slot_size > py + ph - 40:
            break

        can_craft = recipe.can_craft(inv)
        slot_r = pygame.Rect(sx, sy, slot_size, slot_size)
        hover = slot_r.collidepoint(mx, my)

        bg = C["craft_ok"] if can_craft else C["craft_missing"]
        if hover and can_craft:
            bg = (50, 80, 50)
        elif hover and not can_craft:
            bg = (60, 35, 35)

        pygame.draw.rect(screen, bg, slot_r, border_radius=4)
        pygame.draw.rect(screen, C["slot_border"], slot_r, 1, border_radius=4)

        # 产出图标
        from item import ITEM_TEMPLATES as _it
        tmpl = _it.get(recipe.item_id)
        icon = tmpl.icon if tmpl else "?"
        screen.blit(font_small.render(icon, True, C["text"]), (sx + 6, sy + 4))
        # 短名
        screen.blit(font_small.render(recipe.name[:2], True, C["dim"]), (sx + 4, sy + 22))

        if can_craft:
            craft_buttons.append((slot_r, recipe))

"""Pygame 图形窗口版 - 网格地图游戏"""

import sys
from typing import Dict, Tuple, List

import pygame

from map_grid import MapGrid, TileType
from building import Building, BUILDING_TEMPLATES
from crafting import MANUAL_RECIPES, get_craftable_manual
from tech_tree import TECH_NODES, get_available, max_plugin_tier, get_building_bonuses
from player import Player


# ========== 常量 ==========

TILE_SIZE = 40
MAP_COLS, MAP_ROWS = 20, 12
SIDEBAR_WIDTH = 200

WIN_WIDTH = MAP_COLS * TILE_SIZE + SIDEBAR_WIDTH
MAP_HEIGHT = MAP_ROWS * TILE_SIZE
HOTBAR_HEIGHT = 110  # 底部背包栏高度
WIN_HEIGHT = MAP_HEIGHT + HOTBAR_HEIGHT

FPS = 60
INFO_HEIGHT = 60
MOVE_DELAY = 7  # 每 7 帧移动一格（约 8.5 格/秒）
MOVE_INITIAL_DELAY = 4  # 首次移动更快响应

# 颜色
COLOR_BG = (30, 30, 35)
COLOR_GRID = (50, 50, 55)
COLOR_EMPTY = (40, 40, 48)
COLOR_PLAYER = (255, 200, 50)
COLOR_PLAYER_OUTLINE = (200, 160, 30)
COLOR_SIDEBAR = (25, 25, 30)
COLOR_TEXT = (220, 220, 220)
COLOR_TEXT_DIM = (140, 140, 140)
COLOR_HIGHLIGHT = (255, 220, 80)

# 背包栏颜色
COLOR_HOTBAR_BG = (20, 20, 28)
COLOR_HOTBAR_BORDER = (60, 60, 70)
COLOR_SLOT = (35, 35, 45)
COLOR_SLOT_HOVER = (55, 55, 70)
COLOR_SLOT_SELECTED = (100, 180, 255)
COLOR_SLOT_SELECTED_BG = (50, 80, 120)

BUILDING_COLORS: Dict[str, Tuple[int, int, int]] = {
    "工厂":   (70, 130, 200),
    "住宅":   (80, 180, 80),
    "仓库":   (200, 180, 60),
    "研究所": (60, 200, 200),
    "城墙":   (140, 140, 150),
}
BUILDING_ACCENT: Dict[str, Tuple[int, int, int]] = {
    "工厂":   (100, 170, 240),
    "住宅":   (110, 220, 110),
    "仓库":   (240, 220, 90),
    "研究所": (90, 240, 240),
    "城墙":   (170, 170, 180),
}
BUILDING_NAMES = list(BUILDING_TEMPLATES.keys())

# 物品 -> 建筑映射（选中该物品时左键点击地图放置对应建筑）
ITEM_TO_BUILDING = {
    "wood": "住宅",
    "stone": "城墙",
    "iron": "工厂",
    "steel": "研究所",
    "coal": "仓库",
}

DEMOLISH_TIME = FPS * 2  # 按住右键 2 秒拆除


class GameWindow:
    """图形窗口游戏"""

    def __init__(self):
        pygame.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
        pygame.display.set_caption("工厂建造者")
        self.clock = pygame.time.Clock()
        self.font = self._make_font(16)
        self.font_small = self._make_font(13)
        self.font_large = self._make_font(20)

        # 游戏数据
        self.game_map = MapGrid(MAP_COLS, MAP_ROWS)
        self._init_demo_buildings()
        self.player = Player(10, 6, "工程师")
        self.game_map.set_player(self.player)
        # 演示背包物品
        inv = self.player.inventory
        inv.add_item("wood", 12)
        inv.add_item("stone", 8)
        inv.add_item("iron", 5)
        inv.add_item("bread", 3)
        inv.add_item("apple", 2)
        inv.add_item("key", 1)
        inv.add_item("gold", 50)

        # 移动计时
        self.move_timer = 0
        self.move_initial = True  # 是否首次按下

        # 按键状态
        self.keys_down: Dict[int, bool] = {}

        # 放置模式
        self.placing = False
        self.place_idx = 0
        self.px, self.py = 0, 0

        # 消息
        self.messages: List[Tuple[str, int]] = []
        self._msg("WASD 移动 | 左键放置 | 右键拆除 | H 帮助")

        self.show_help = False
        self.show_backpack = False   # E 键背包界面
        self.show_building_panel = False  # 建筑面板
        self.show_tech_tree = False       # 科技树
        self.panel_building = None        # 当前打开的建筑
        self.tech_unlocked: set = set()   # 已解锁科技 ID 集合

        # 拆除状态（长按展示进度条）
        self.demolish_target = None  # 正在拆除的建筑
        self.demolish_frames = 0  # 已按住多少帧
        self.right_held = False  # 右键是否按住

        # 鼠标状态
        self.mouse_grid_pos: Tuple[int, int] = (-1, -1)  # 鼠标所在的格子
        self.mouse_in_map = False
        self.hover_slot_idx = -1  # 悬浮在哪个背包格子上

    def _make_font(self, size: int):
        """从系统字体文件加载中文字体"""
        # 直接加载字体文件路径（避免 SysFont 在 pygame 2.6.1 下的 bug）
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",     # 黑体
            "C:/Windows/Fonts/simsun.ttc",     # 宋体
            "C:/Windows/Fonts/dengl.ttf",      # 等线
            "C:/Windows/Fonts/msyhbd.ttc",     # 微软雅黑粗体
        ]
        for path in font_paths:
            try:
                return pygame.font.Font(path, size)
            except Exception:
                continue
        return pygame.font.Font(None, size)

    def _init_demo_buildings(self):
        for args in [
            (1, 1, "工厂"), (5, 1, "仓库"), (5, 3, "住宅"),
            (8, 1, "研究所"), (1, 5, "住宅"), (3, 5, "城墙"),
        ]:
            try:
                self.game_map.add_building(Building(*args))
            except ValueError:
                pass

    def _msg(self, text: str):
        self.messages.append((text, FPS * 4))

    # ========== 输入 ==========

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit()
            elif event.type == pygame.KEYDOWN:
                self.keys_down[event.key] = True
                self._on_keydown(event.key)
            elif event.type == pygame.KEYUP:
                self.keys_down[event.key] = False
            elif event.type == pygame.MOUSEMOTION:
                self._on_mouse_move(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:     # 左键
                    self._on_left_click(event.pos)
                elif event.button == 3:   # 右键按下 -> 开始拆除
                    self.right_held = True
                    self._on_right_down(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3:     # 右键松开 -> 取消拆除
                    self.right_held = False
                    self._cancel_demolish()

    def _on_keydown(self, key: int):
        if key == pygame.K_q:
            self._quit()
        elif key == pygame.K_h:
            self.show_help = not self.show_help
        elif key == pygame.K_e:
            self.show_backpack = not self.show_backpack
            self.show_building_panel = False
        elif key == pygame.K_t:
            self.show_tech_tree = not self.show_tech_tree
        elif key == pygame.K_ESCAPE:
            self.placing = False
            self.show_help = False
            self.show_backpack = False
            self.show_building_panel = False
            self.show_tech_tree = False
        elif key == pygame.K_b:
            if not self.placing:
                self.placing = True
                self.place_idx = 0
                self.px, self.py = 0, 0
            else:
                self._confirm_place()
        elif self.placing:
            self._place_key(key)
        elif key in (pygame.K_w, pygame.K_UP, pygame.K_s, pygame.K_DOWN,
                     pygame.K_a, pygame.K_LEFT, pygame.K_d, pygame.K_RIGHT):
            # 按键即时移动一步（只朝该方向）
            dx = dy = 0
            if key in (pygame.K_w, pygame.K_UP):
                dy = -1
            elif key in (pygame.K_s, pygame.K_DOWN):
                dy = 1
            elif key in (pygame.K_a, pygame.K_LEFT):
                dx = -1
            elif key in (pygame.K_d, pygame.K_RIGHT):
                dx = 1
            if dx != 0 or dy != 0:
                self.game_map.move_player(dx, dy)
            # 启用长按连续移动
            self.move_initial = True
            self.move_timer = 0
        elif pygame.K_1 <= key <= pygame.K_8:
            # 数字键选择背包栏位 (1-8)
            idx = key - pygame.K_1
            inv = self.player.inventory
            if idx < len(inv.slots):
                inv.selected = idx

    def _on_mouse_move(self, pos: Tuple[int, int]):
        """更新鼠标所在的格子坐标和悬浮索引"""
        mx, my = pos
        # 地图格子
        if 0 <= mx < MAP_COLS * TILE_SIZE and 0 <= my < MAP_HEIGHT:
            gx = mx // TILE_SIZE
            gy = my // TILE_SIZE
            self.mouse_grid_pos = (gx, gy)
            self.mouse_in_map = True
        else:
            self.mouse_in_map = False
        # 背包格子
        self.hover_slot_idx = self._get_clicked_slot(pos)

    def _get_clicked_slot(self, pos: Tuple[int, int]) -> int:
        """检测鼠标点击了哪个背包格子，返回索引 (-1 = 未命中)"""
        mx, my = pos
        bar_rect = pygame.Rect(0, MAP_HEIGHT, MAP_COLS * TILE_SIZE, HOTBAR_HEIGHT)
        if not bar_rect.collidepoint(mx, my):
            return -1
        # 计算格子参数 (与 _draw_hotbar 保持一致)
        slots_per_row = 8
        slot_rows = 2
        cell_w = 56
        cell_h = 44
        gap = 6
        total_w = slots_per_row * (cell_w + gap) - gap
        bar_x0 = bar_rect.x + (bar_rect.width - total_w) // 2
        bar_y0 = bar_rect.y + 6

        for idx in range(slots_per_row * slot_rows):
            row = idx // slots_per_row
            col = idx % slots_per_row
            cx = bar_x0 + col * (cell_w + gap)
            cy = bar_y0 + row * (cell_h + gap)
            if cx <= mx <= cx + cell_w and cy <= my <= cy + cell_h:
                return idx
        return -1

    def _on_left_click(self, pos: Tuple[int, int]):
        """鼠标左键：选中背包 / 放置建筑 / 合成 / 打开建筑面板 / 科技树"""
        # 建筑面板：插件/科技树按钮
        if self.show_building_panel:
            self._click_building_panel(pos)
            return
        # 科技树：解锁节点
        if self.show_tech_tree:
            self._click_tech_tree(pos)
            return
        # 背包界面：合成
        if self.show_backpack:
            for rect, recipe in getattr(self, '_craft_buttons', []):
                if rect.collidepoint(pos):
                    inv = self.player.inventory
                    if recipe.craft(inv):
                        self._msg(f"合成 {recipe.name} x{recipe.quantity}")
                    else:
                        self._msg(f"材料不足，无法合成 {recipe.name}")
                    return
            return

        # 点击背包栏选中物品
        slot = self._get_clicked_slot(pos)
        if slot >= 0:
            inv = self.player.inventory
            if slot < len(inv.slots) and inv.slots[slot] is not None:
                inv.selected = slot
                return

        # 点击地图
        mx, my = pos
        if 0 <= mx < MAP_COLS * TILE_SIZE and 0 <= my < MAP_HEIGHT:
            gx = mx // TILE_SIZE
            gy = my // TILE_SIZE
            # 有选中的建造材料 → 放置建筑
            sel = self.player.selected_slot
            if sel and sel.item_id in ITEM_TO_BUILDING:
                self._place_with_selected(gx, gy)
            else:
                # 无建造材料 → 打开建筑面板
                bld = self._building_at(gx, gy)
                if bld:
                    self.panel_building = bld
                    self.show_building_panel = True

    def _building_at(self, gx: int, gy: int):
        """返回 (gx,gy) 处的建筑，没有则返回 None"""
        for b in self.game_map.buildings:
            if b.x <= gx < b.x + b.w and b.y <= gy < b.y + b.h:
                return b
        return None

    def _on_right_down(self, pos: Tuple[int, int]):
        """右键按下：开始拆除建筑"""
        mx, my = pos
        if 0 <= mx < MAP_COLS * TILE_SIZE and 0 <= my < MAP_HEIGHT:
            gx, gy = mx // TILE_SIZE, my // TILE_SIZE
            bld = self._building_at(gx, gy)
            if bld:
                self.demolish_target = bld
                self.demolish_frames = 0

    def _click_building_panel(self, pos):
        """建筑面板点击 - 打开科技树"""
        mx, my = pos
        if self.panel_building:
            # 底部按钮区域
            if WIN_HEIGHT - 60 <= my <= WIN_HEIGHT - 20:
                self.show_building_panel = False
                self.show_tech_tree = True

    def _click_tech_tree(self, pos):
        """科技树点击 - 解锁节点"""
        mx, my = pos
        for rect, node in getattr(self, '_tech_buttons', []):
            if rect.collidepoint(pos):
                inv = self.player.inventory
                if node.can_unlock(inv, self.tech_unlocked):
                    node.unlock(inv)
                    self.tech_unlocked.add(node.node_id)
                    self._msg(f"解锁: {node.name}")
                else:
                    self._msg(f"材料不足或前置未解锁")
                return

    def _cancel_demolish(self):
        """取消拆除（松开右键或移开鼠标）"""
        self.demolish_target = None
        self.demolish_frames = 0

    def _place_with_selected(self, gx: int, gy: int):
        """根据选中的背包物品放置对应建筑"""
        sel = self.player.selected_slot
        if not sel:
            self._msg("请先选择背包中的物品")
            return
        bld_name = ITEM_TO_BUILDING.get(sel.item_id)
        if not bld_name:
            self._msg(f"{sel.name} 不能用于建造")
            return
        try:
            b = Building(gx, gy, bld_name)
            self.game_map.add_building(b)
            self._msg(f"放置 {b.name} 于 ({b.x},{b.y})")
        except ValueError as e:
            self._msg(f"放置失败: {e}")

    def _place_key(self, key: int):
        if key == pygame.K_TAB:
            self.place_idx = (self.place_idx + 1) % len(BUILDING_NAMES)
        elif key == pygame.K_w:
            self.py = max(0, self.py - 1)
        elif key == pygame.K_s:
            self.py = min(MAP_ROWS - 1, self.py + 1)
        elif key == pygame.K_a:
            self.px = max(0, self.px - 1)
        elif key == pygame.K_d:
            self.px = min(MAP_COLS - 1, self.px + 1)

    def _confirm_place(self):
        name = BUILDING_NAMES[self.place_idx]
        try:
            b = Building(self.px, self.py, name)
            self.game_map.add_building(b)
            self._msg(f"放置 {b.name} 于 ({b.x},{b.y})")
            self.placing = False
        except ValueError as e:
            self._msg(f"失败: {e}")

    def _tick_demolish(self):
        """每帧推进拆除进度（按住右键时）"""
        if not self.right_held or self.demolish_target is None:
            return
        # 检查鼠标是否还在同一个建筑上
        mx, my = pygame.mouse.get_pos()
        if not (0 <= mx < MAP_COLS * TILE_SIZE and 0 <= my < MAP_HEIGHT):
            self._cancel_demolish()
            return
        gx, gy = mx // TILE_SIZE, my // TILE_SIZE
        if self._building_at(gx, gy) is not self.demolish_target:
            self._cancel_demolish()
            return
        self.demolish_frames += 1
        if self.demolish_frames >= DEMOLISH_TIME:
            bld = self.demolish_target
            self._msg(f"拆除 {bld.name}")
            self.game_map.remove_building(bld)
            self._cancel_demolish()
            self.right_held = False

    def _update_movement(self):
        """每帧根据持续按住的键移动（支持斜向）"""
        self._tick_demolish()
        if self.placing or self.show_help or self.show_backpack or self.show_building_panel or self.show_tech_tree:
            return

        dx, dy = 0, 0
        if self.keys_down.get(pygame.K_w) or self.keys_down.get(pygame.K_UP):
            dy -= 1
        if self.keys_down.get(pygame.K_s) or self.keys_down.get(pygame.K_DOWN):
            dy += 1
        if self.keys_down.get(pygame.K_a) or self.keys_down.get(pygame.K_LEFT):
            dx -= 1
        if self.keys_down.get(pygame.K_d) or self.keys_down.get(pygame.K_RIGHT):
            dx += 1

        if dx == 0 and dy == 0:
            self.move_timer = 0
            self.move_initial = True
            return

        delay = MOVE_INITIAL_DELAY if self.move_initial else MOVE_DELAY
        self.move_timer += 1
        if self.move_timer >= delay:
            self.move_timer = 0
            self.move_initial = False
            self.game_map.move_player(dx, dy)

    # ========== 渲染 ==========

    def _draw_grid(self):
        for y in range(MAP_ROWS):
            for x in range(MAP_COLS):
                rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                tile = self.game_map.get_tile(x, y)
                if tile == TileType.EMPTY:
                    pygame.draw.rect(self.screen, COLOR_EMPTY, rect)
                elif tile == TileType.BUILDING:
                    self._draw_building_cell(x, y, rect)
                pygame.draw.rect(self.screen, COLOR_GRID, rect, 1)

    def _draw_building_cell(self, gx: int, gy: int, rect: pygame.Rect):
        color = (100, 100, 120)
        accent = (150, 150, 150)
        for b in self.game_map.buildings:
            if b.x <= gx < b.x + b.w and b.y <= gy < b.y + b.h:
                color = BUILDING_COLORS.get(b.name, color)
                accent = BUILDING_ACCENT.get(b.name, accent)
                break
        pygame.draw.rect(self.screen, color, rect)
        inner = rect.inflate(-6, -6)
        pygame.draw.rect(self.screen, accent, inner, 1)

    def _draw_player(self):
        cx = self.player.x * TILE_SIZE + TILE_SIZE // 2
        cy = self.player.y * TILE_SIZE + TILE_SIZE // 2
        r = TILE_SIZE // 2 - 4
        # 光晕
        for i in range(3):
            sr = r + i * 3
            s = pygame.Surface((sr * 2, sr * 2), pygame.SRCALPHA)
            alpha = 50 - i * 15
            pygame.draw.circle(s, (255, 200, 50, alpha), (sr, sr), sr)
            self.screen.blit(s, (cx - sr, cy - sr))
        # 身体
        pygame.draw.circle(self.screen, COLOR_PLAYER_OUTLINE, (cx, cy), r + 1)
        pygame.draw.circle(self.screen, COLOR_PLAYER, (cx, cy), r)
        # 眼睛
        off = r // 3
        for ex, ey in [(-off, -off), (off, -off)]:
            pygame.draw.circle(self.screen, (0, 0, 0), (cx + ex, cy + ey), 3)
        # 表情（微笑）
        pygame.draw.arc(self.screen, (0, 0, 0),
                        (cx - off, cy - 1, off * 2, off + 2), 0, 3.14, 2)

    def _draw_sidebar(self):
        x0 = MAP_COLS * TILE_SIZE
        pygame.draw.rect(self.screen, COLOR_SIDEBAR, (x0, 0, SIDEBAR_WIDTH, WIN_HEIGHT))
        pygame.draw.line(self.screen, COLOR_GRID, (x0, 0), (x0, WIN_HEIGHT), 2)

        x = x0 + 12
        y = 16
        title = self.font_large.render("----", True, COLOR_HIGHLIGHT)
        self.screen.blit(title, (x, y))
        y += 32

        for line in [
            f"-: {self.player.name}",
            f"-: Lv.{self.player.level}",
            f"-: {self.player.hp}/{self.player.max_hp}",
            f"坐标: ({self.player.x}, {self.player.y})",
        ]:
            self.screen.blit(self.font.render(line, True, COLOR_TEXT), (x, y))
            y += 22

        y += 12
        self.screen.blit(
            self.font.render(f"建筑 ({len(self.game_map.buildings)})", True, COLOR_HIGHLIGHT), (x, y))
        y += 24
        for b in self.game_map.buildings[:7]:
            self.screen.blit(
                self.font_small.render(f"  {b.name} ({b.x},{b.y})", True, COLOR_TEXT_DIM), (x, y))
            y += 18
        if len(self.game_map.buildings) > 7:
            self.screen.blit(
                self.font_small.render(f"  ... +{len(self.game_map.buildings)-7}", True, COLOR_TEXT_DIM), (x, y))

        # 背包摘要
        y += 8
        self.screen.blit(
            self.font.render("背包", True, COLOR_HIGHLIGHT), (x, y))
        y += 24
        inv = self.player.inventory
        items = inv.list_items()
        if items:
            for s in items[:5]:
                self.screen.blit(
                    self.font_small.render(f"  {s.icon} {s.name} x{s.quantity}", True, COLOR_TEXT_DIM), (x, y))
                y += 18
            if len(items) > 5:
                self.screen.blit(
                    self.font_small.render(f"  ... +{len(items)-5}", True, COLOR_TEXT_DIM), (x, y))
        else:
            self.screen.blit(
                self.font_small.render("  (空)", True, COLOR_TEXT_DIM), (x, y))

    def _draw_placement(self):
        if not self.placing:
            return

        name = BUILDING_NAMES[self.place_idx]
        tmpl = BUILDING_TEMPLATES[name]
        w, h = tmpl["width"], tmpl["height"]
        valid = self.game_map.area_free(self.px, self.py, w, h)
        color = (0, 200, 0, 80) if valid else (200, 0, 0, 80)

        for dx in range(w):
            for dy in range(h):
                rect = pygame.Rect((self.px + dx) * TILE_SIZE, (self.py + dy) * TILE_SIZE,
                                   TILE_SIZE, TILE_SIZE)
                s = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                s.fill(color)
                self.screen.blit(s, rect)

        # 底部提示栏 (地图区域底部, 非热栏)
        panel = pygame.Surface((420, INFO_HEIGHT), pygame.SRCALPHA)
        panel.fill((20, 20, 25, 220))
        self.screen.blit(panel, (10, MAP_HEIGHT - INFO_HEIGHT - 10))

        lines = [
            f"放置: {name} ({w}x{h})   {'' if valid else '区域被占用!'}",
            "WASD 移动光标 | TAB 切换 | B 确认 | ESC 取消",
        ]
        for i, line in enumerate(lines):
            c = COLOR_HIGHLIGHT if valid else (255, 80, 80)
            self.screen.blit(self.font.render(line, True, c), (18, MAP_HEIGHT - INFO_HEIGHT - 6 + i * 22))

    def _draw_mouse_ghost(self):
        """在地图上绘制建筑预览虚影（跟随鼠标）"""
        if not self.mouse_in_map or self.placing:
            return
        sel = self.player.selected_slot
        if not sel:
            return
        bld_name = ITEM_TO_BUILDING.get(sel.item_id)
        if not bld_name:
            return

        gx, gy = self.mouse_grid_pos
        tmpl = BUILDING_TEMPLATES[bld_name]
        w, h = tmpl["width"], tmpl["height"]
        valid = self.game_map.area_free(gx, gy, w, h)
        color = (0, 220, 0, 60) if valid else (220, 0, 0, 60)
        border_color = (0, 255, 0) if valid else (255, 0, 0)

        for dx in range(w):
            for dy in range(h):
                rect = pygame.Rect((gx + dx) * TILE_SIZE, (gy + dy) * TILE_SIZE,
                                   TILE_SIZE, TILE_SIZE)
                s = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                s.fill(color)
                self.screen.blit(s, rect)
                pygame.draw.rect(self.screen, border_color, rect, 2)

    def _draw_demolish_bar(self):
        """绘制正在拆除的建筑上的进度条"""
        if self.demolish_target is None or self.demolish_frames <= 0:
            return
        b = self.demolish_target
        progress = self.demolish_frames / DEMOLISH_TIME
        bar_w = b.w * TILE_SIZE - 4
        bar_h = 5
        bar_x = b.x * TILE_SIZE + 2
        bar_y = b.y * TILE_SIZE - 8

        # 背景（暗红）
        pygame.draw.rect(self.screen, (50, 15, 15), (bar_x, bar_y, bar_w, bar_h))
        # 进度（亮红）
        fill = int(bar_w * progress)
        if fill > 0:
            pygame.draw.rect(self.screen, (255, 50, 50), (bar_x, bar_y, fill, bar_h))
        # 边框
        pygame.draw.rect(self.screen, (180, 30, 30), (bar_x, bar_y, bar_w, bar_h), 1)

    def _draw_messages(self):
        y = MAP_HEIGHT - 30
        keep = []
        for text, remain in self.messages:
            if remain > 0:
                keep.append((text, remain - 1))
                self.screen.blit(self.font.render(text, True, COLOR_HIGHLIGHT), (10, y))
                y -= 22
        self.messages = keep

    # ========== 背包 ==========

    def _draw_hotbar(self):
        """底部背包物品栏"""
        inv = self.player.inventory
        slots_per_row = 8
        slot_rows = 2
        cell_w = 56
        cell_h = 44
        gap = 6

        total_w = slots_per_row * (cell_w + gap) - gap
        bar_rect = pygame.Rect(0, MAP_HEIGHT, MAP_COLS * TILE_SIZE, HOTBAR_HEIGHT)
        pygame.draw.rect(self.screen, COLOR_HOTBAR_BG, bar_rect)
        pygame.draw.line(self.screen, COLOR_HOTBAR_BORDER,
                         (0, MAP_HEIGHT), (MAP_COLS * TILE_SIZE, MAP_HEIGHT), 3)

        for idx in range(slots_per_row * slot_rows):
            row = idx // slots_per_row
            col = idx % slots_per_row
            cx = bar_rect.x + (bar_rect.width - total_w) // 2 + col * (cell_w + gap)
            cy = bar_rect.y + 6 + row * (cell_h + gap)

            slot_rect = pygame.Rect(cx, cy, cell_w, cell_h)
            stack = inv.slots[idx] if idx < len(inv.slots) else None
            is_selected = (idx == inv.selected and stack is not None)
            is_hover = (idx == self.hover_slot_idx and not is_selected)

            if is_selected:
                pygame.draw.rect(self.screen, COLOR_SLOT_SELECTED_BG, slot_rect)
                pygame.draw.rect(self.screen, COLOR_SLOT_SELECTED, slot_rect, 2)
            elif is_hover and stack:
                pygame.draw.rect(self.screen, (70, 100, 140), slot_rect)
                pygame.draw.rect(self.screen, COLOR_HIGHLIGHT, slot_rect, 2)
            elif stack:
                pygame.draw.rect(self.screen, COLOR_SLOT_HOVER, slot_rect)
                pygame.draw.rect(self.screen, COLOR_HOTBAR_BORDER, slot_rect, 1)
            else:
                pygame.draw.rect(self.screen, COLOR_SLOT, slot_rect)
                pygame.draw.rect(self.screen, COLOR_HOTBAR_BORDER, slot_rect, 1)

            if stack:
                # 图标
                try:
                    icon = self.font_large.render(stack.item.icon, True, COLOR_TEXT)
                except Exception:
                    icon = self.font_large.render("?", True, COLOR_TEXT)
                ix = cx + (cell_w - icon.get_width()) // 2
                self.screen.blit(icon, (ix, cy + 2))
                # 数量
                if stack.quantity > 1:
                    qty = self.font_small.render(str(stack.quantity), True, COLOR_HIGHLIGHT)
                    self.screen.blit(qty, (cx + cell_w - qty.get_width() - 3,
                                           cy + cell_h - qty.get_height() - 2))

            # 编号
            if row == 0:
                num = self.font_small.render(str(col + 1), True, COLOR_TEXT_DIM)
                self.screen.blit(num, (cx + 3, cy + 2))

        # 选中物品名称
        sel = inv.slots[inv.selected] if inv.selected < len(inv.slots) else None
        if sel:
            label = f"{sel.name}  ({sel.item.description})"
            surf = self.font_small.render(label, True, COLOR_TEXT_DIM)
            self.screen.blit(surf, (bar_rect.x + 10, MAP_HEIGHT + HOTBAR_HEIGHT - 20))

    # ========== 背包界面 ==========

    def _draw_backpack_ui(self):
        """背包界面 (E键) - 左背包 / 右合成"""
        if not self.show_backpack:
            return

        inv = self.player.inventory
        recipes = list(MANUAL_RECIPES.values())
        craftable_ids = {r.recipe_id for r in get_craftable_manual(inv)}

        # 半透明背景
        overlay = pygame.Surface((WIN_WIDTH, WIN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 15, 230))
        self.screen.blit(overlay, (0, 0))

        mx, my = pygame.mouse.get_pos()
        panel_pad = 30

        # ===== 左栏: 物品列表 =====
        left_w = MAP_COLS * TILE_SIZE // 2 - panel_pad
        left_x = panel_pad
        left_y = 50
        left_h = WIN_HEIGHT - 100

        # 标题
        title = self.font_large.render("我的物品", True, COLOR_HIGHLIGHT)
        self.screen.blit(title, (left_x, left_y - 28))

        items = inv.list_items()
        if items:
            cell_sz = 38
            gap = 4
            cols = max(1, left_w // (cell_sz + gap))
            for idx, stack in enumerate(items):
                row = idx // cols
                col = idx % cols
                ix = left_x + col * (cell_sz + gap)
                iy = left_y + row * (cell_sz + gap)
                rect = pygame.Rect(ix, iy, cell_sz, cell_sz)
                pygame.draw.rect(self.screen, COLOR_SLOT_HOVER, rect)
                pygame.draw.rect(self.screen, COLOR_HOTBAR_BORDER, rect, 1)
                # 图标
                try:
                    icon = self.font.render(stack.item.icon, True, COLOR_TEXT)
                except Exception:
                    icon = self.font.render("?", True, COLOR_TEXT)
                self.screen.blit(icon, (ix + 2, iy + 2))
                # 数量
                if stack.quantity > 1:
                    qty = self.font_small.render(str(stack.quantity), True, COLOR_HIGHLIGHT)
                    self.screen.blit(qty, (ix + cell_sz - qty.get_width() - 2,
                                           iy + cell_sz - qty.get_height() - 2))
        else:
            empty = self.font.render("  (空)", True, COLOR_TEXT_DIM)
            self.screen.blit(empty, (left_x, left_y))

        # ===== 右栏: 合成列表 =====
        right_x = MAP_COLS * TILE_SIZE // 2 + panel_pad
        right_w = MAP_COLS * TILE_SIZE // 2 - panel_pad * 2
        right_y = 50

        title2 = self.font_large.render("手动合成", True, COLOR_HIGHLIGHT)
        self.screen.blit(title2, (right_x, right_y - 28))

        if not recipes:
            none = self.font.render("  无可合成的物品", True, COLOR_TEXT_DIM)
            self.screen.blit(none, (right_x, right_y))
        else:
            self._craft_buttons = []  # [(rect, recipe), ...] 用于点击检测
            ry = right_y
            for recipe in recipes:
                can_craft = recipe.recipe_id in craftable_ids
                row_h = 44
                if ry + row_h > WIN_HEIGHT - 30:
                    break

                # 背景
                row_rect = pygame.Rect(right_x, ry, right_w, row_h)
                if can_craft:
                    if row_rect.collidepoint(mx, my):
                        pygame.draw.rect(self.screen, (50, 80, 100), row_rect)
                        pygame.draw.rect(self.screen, COLOR_SLOT_SELECTED, row_rect, 1)
                    else:
                        pygame.draw.rect(self.screen, (30, 45, 55), row_rect)
                else:
                    pygame.draw.rect(self.screen, (20, 25, 30), row_rect)

                color = COLOR_TEXT if can_craft else COLOR_TEXT_DIM

                # 配方名
                name = self.font.render(recipe.name, True, color)
                if can_craft and row_rect.collidepoint(mx, my):
                    name = self.font.render(recipe.name, True, COLOR_HIGHLIGHT)
                self.screen.blit(name, (right_x + 8, ry + 3))

                # 材料明细
                mat_parts = []
                for mid, amt in recipe.materials.items():
                    from item import ITEM_TEMPLATES
                    tmpl = ITEM_TEMPLATES.get(mid)
                    mname = tmpl.name if tmpl else mid
                    have = inv.count(mid)
                    has_enough = have >= amt
                    mcolor = COLOR_TEXT if has_enough else (255, 80, 80)
                    mat_parts.append(f"{mname}")
                mat_str = " + ".join(mat_parts) if mat_parts else "(无材料)"
                mat_str += f" → x{recipe.quantity}"
                mat = self.font_small.render(mat_str, True, COLOR_TEXT_DIM)
                self.screen.blit(mat, (right_x + 8, ry + 24))

                # 材料数量（右上角显示拥有/需要）
                x_off = right_x + right_w - 8
                for mid, amt in recipe.materials.items():
                    have = inv.count(mid)
                    amt_str = self.font_small.render(f"{have}/{amt}", True,
                                                     COLOR_TEXT if have >= amt else (255, 80, 80))
                    x_off -= amt_str.get_width() + 4
                    self.screen.blit(amt_str, (x_off, ry + 3))

                if can_craft:
                    self._craft_buttons.append((row_rect, recipe))

                ry += row_h + 2

        # 底部提示
        hint = self.font_small.render("ESC 关闭  |  点击合成配方制作物品", True, COLOR_TEXT_DIM)
        self.screen.blit(hint, (panel_pad, WIN_HEIGHT - 30))

    # ========== 建筑面板 ==========

    def _draw_building_panel(self):
        if not self.show_building_panel or not self.panel_building:
            return
        b = self.panel_building
        inv = self.player.inventory

        overlay = pygame.Surface((WIN_WIDTH, WIN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 15, 230))
        self.screen.blit(overlay, (0, 0))

        cx = WIN_WIDTH // 2
        y = 60

        title = self.font_large.render(f"{b.name}  ({b.x},{b.y})", True, COLOR_HIGHLIGHT)
        self.screen.blit(title, (cx - title.get_width() // 2, y))
        y += 35

        ptier = max_plugin_tier(self.tech_unlocked)
        bonuses = get_building_bonuses(self.tech_unlocked)
        info = (f"HP: {b.hp}/{b.max_hp}  "
                f"效率: {1+bonuses['efficiency']:.1f}  "
                f"速度: {1+bonuses['speed']:.1f}  "
                f"插件: {len(b.plugins)}/{min(b.plugin_slots, ptier)}")
        line = self.font.render(info, True, COLOR_TEXT_DIM)
        self.screen.blit(line, (cx - line.get_width() // 2, y))
        y += 30

        from item import ITEM_TEMPLATES as _it

        # 左: 输入
        lx = cx - 200
        self.screen.blit(self.font.render("输入", True, COLOR_HIGHLIGHT), (lx, y))
        y2 = y + 25
        if b.inputs:
            for iid, amt in b.inputs.items():
                t = _it.get(iid)
                n = t.name if t else iid
                hv = inv.count(iid)
                self.screen.blit(self.font.render(f"  {n} x{amt}  (有{hv})", True, COLOR_TEXT), (lx, y2))
                y2 += 22
        else:
            self.screen.blit(self.font.render("  (无)", True, COLOR_TEXT_DIM), (lx, y2))

        # 右: 输出
        rx = cx + 20
        self.screen.blit(self.font.render("输出", True, COLOR_HIGHLIGHT), (rx, y))
        y2 = y + 25
        if b.outputs:
            for iid, amt in b.outputs.items():
                t = _it.get(iid)
                n = t.name if t else iid
                a = max(1, int(amt * (1+bonuses['efficiency']) * (1+bonuses['speed'])))
                self.screen.blit(self.font.render(f"  {n} x{a}", True, COLOR_TEXT), (rx, y2))
                y2 += 22
        else:
            self.screen.blit(self.font.render("  (无)", True, COLOR_TEXT_DIM), (rx, y2))

        y += max(len(b.inputs or []), len(b.outputs or []), 1) * 24 + 10

        # 进度条
        if b.inputs and b.outputs:
            bw, bh = 300, 12
            bx = cx - bw // 2
            pr = b.production_progress
            pygame.draw.rect(self.screen, (40,40,50), (bx, y, bw, bh))
            if pr > 0:
                pygame.draw.rect(self.screen, (80,180,255), (bx, y, int(bw*pr), bh))
            pygame.draw.rect(self.screen, (100,100,120), (bx, y, bw, bh), 1)
            pct = self.font_small.render(f"{int(pr*100)}%", True, COLOR_TEXT)
            self.screen.blit(pct, (cx - pct.get_width()//2, y+bh+4))
            y += bh + 25
        else:
            self.screen.blit(self.font_small.render("(无需生产)", True, COLOR_TEXT_DIM), (cx-50, y))
            y += 25

        # 插件槽
        plug = self.font.render(f"插件槽  (科技{ptier}级)", True, COLOR_HIGHLIGHT)
        self.screen.blit(plug, (cx - plug.get_width()//2, y))
        y += 25
        ms = min(b.plugin_slots, ptier)
        ss, sg = 36, 8
        tw = ms * (ss + sg) - sg
        sx0 = cx - tw // 2
        for i in range(ms):
            sx = sx0 + i * (ss + sg)
            if i < len(b.plugins):
                pygame.draw.rect(self.screen, (60,120,60), (sx, y, ss, ss))
                pygame.draw.rect(self.screen, (100,200,100), (sx, y, ss, ss), 1)
                self.screen.blit(self.font_small.render("P", True, COLOR_HIGHLIGHT), (sx+10, y+8))
            else:
                pygame.draw.rect(self.screen, (40,40,50), (sx, y, ss, ss))
                pygame.draw.rect(self.screen, COLOR_HOTBAR_BORDER, (sx, y, ss, ss), 1)
                self.screen.blit(self.font_small.render("+", True, COLOR_TEXT_DIM), (sx+12, y+8))

        self.screen.blit(self.font.render("T 科技树", True, COLOR_HIGHLIGHT), (20, WIN_HEIGHT-45))
        self.screen.blit(self.font_small.render("ESC 关闭", True, COLOR_TEXT_DIM), (WIN_WIDTH-120, WIN_HEIGHT-45))

    # ========== 科技树 ==========

    def _draw_tech_tree(self):
        if not self.show_tech_tree:
            return
        inv = self.player.inventory
        mx, my = pygame.mouse.get_pos()

        # 半透明背景
        overlay = pygame.Surface((WIN_WIDTH, WIN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 15, 240))
        self.screen.blit(overlay, (0, 0))

        title = self.font_large.render("科 技 树", True, COLOR_HIGHLIGHT)
        self.screen.blit(title, (WIN_WIDTH//2 - title.get_width()//2, 25))

        # ── 树形布局计算 ──
        NODE_W, NODE_H = 170, 62
        TIER_GAP = 100
        COL_SPACING = NODE_W + 40

        # 按 tier 分组
        tiers: Dict[int, List] = {}
        for n in TECH_NODES.values():
            tiers.setdefault(n.tier, []).append(n)

        # 计算每个节点的 (col, row) 位置
        # col: 水平偏移(整型), row: tier-1
        layout = {}  # node_id -> (col, row)

        # 根节点 (T1) 放在 col=0
        for n in tiers.get(1, []):
            layout[n.node_id] = (0, 0)

        # 逐层向下分配子节点列位置
        for tier in range(2, 6):
            for node in tiers.get(tier, []):
                # 获取所有已布局的父节点列
                parent_cols = []
                for pid in node.parent_ids:
                    if pid in layout:
                        parent_cols.append(layout[pid][0])
                if parent_cols:
                    # 子节点放在父节点平均列（可处理双父合并）
                    avg_col = sum(parent_cols) / len(parent_cols)
                    col = int(avg_col)
                    # 如果平均列不是整数，保留半列偏移以便居中
                    if avg_col % 1 != 0:
                        col = avg_col  # 允许半列
                else:
                    # 无父节点(通常不会发生)，顺序排列
                    siblings = tiers.get(tier, [])
                    idx = siblings.index(node)
                    total = len(siblings)
                    col = idx - (total - 1) / 2
                layout[node.node_id] = (col, tier - 1)

        # 计算屏幕坐标
        def node_pos(node_id):
            col, row = layout.get(node_id, (0, 0))
            cx = WIN_WIDTH // 2 + int(col * COL_SPACING)
            cy = 70 + row * TIER_GAP
            return cx, cy

        # ── 绘制连线 ──
        for node in TECH_NODES.values():
            cx, cy = node_pos(node.node_id)
            # 从子节点向父节点画线
            for pid in node.parent_ids:
                if pid not in layout:
                    continue
                px, py = node_pos(pid)
                # 父节点底部 → 子节点顶部
                start = (px, py + NODE_H // 2)
                end = (cx, cy - NODE_H // 2)
                mid_y = (start[1] + end[1]) // 2
                color = (80, 120, 80) if pid in self.tech_unlocked else (50, 50, 55)
                # 先垂直线、再水平、再垂直线（阶梯线）
                pygame.draw.line(self.screen, color, start, (start[0], mid_y), 2)
                pygame.draw.line(self.screen, color, (start[0], mid_y), (end[0], mid_y), 2)
                pygame.draw.line(self.screen, color, (end[0], mid_y), end, 2)

        # ── 绘制节点卡片 ──
        self._tech_buttons = []
        for node in TECH_NODES.values():
            cx, cy = node_pos(node.node_id)
            rx, ry = cx - NODE_W // 2, cy - NODE_H // 2
            rect = pygame.Rect(rx, ry, NODE_W, NODE_H)

            unlocked = node.node_id in self.tech_unlocked
            can = node.can_unlock(inv, self.tech_unlocked)
            parents_ok = all(p in self.tech_unlocked for p in node.parent_ids)
            hover = rect.collidepoint(mx, my)

            # 背景色
            if unlocked:
                bg = (35, 65, 35)
                border = (80, 160, 80)
            elif can:
                bg = (55, 70, 40) if hover else (40, 55, 35)
                border = (120, 200, 80) if hover else (70, 120, 50)
            elif parents_ok:
                bg = (40, 30, 25) if hover else (30, 25, 20)
                border = (80, 60, 40)
            else:
                bg = (25, 25, 30)
                border = COLOR_HOTBAR_BORDER

            pygame.draw.rect(self.screen, bg, rect, border_radius=6)
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=6)

            # 状态图标 + 名称
            st = "✓" if unlocked else ("▶" if can else "🔒")
            sc = COLOR_HIGHLIGHT if unlocked else ((150, 255, 150) if can else COLOR_TEXT_DIM)
            label = f"{st} {node.name}"
            name_surf = self.font.render(label, True, sc)
            self.screen.blit(name_surf, (rx + 8, ry + 6))

            # 描述
            desc = self.font_small.render(node.description, True, COLOR_TEXT_DIM)
            self.screen.blit(desc, (rx + 8, ry + 28))

            # 材料需求（右侧）
            if not unlocked:
                xo = rect.right - 8
                for mid, amt in node.requirements.items():
                    from item import ITEM_TEMPLATES as _it2
                    tmpl = _it2.get(mid)
                    mn = tmpl.name if tmpl else mid
                    hv = inv.count(mid)
                    c = COLOR_TEXT if hv >= amt else (255, 80, 80)
                    m = self.font_small.render(f"{mn} {hv}/{amt}", True, c)
                    xo -= m.get_width() + 6
                    self.screen.blit(m, (xo, ry + 6))

            if can:
                self._tech_buttons.append((rect, node))

        # 底部提示
        if self._tech_buttons:
            hint = self.font_small.render("🖱 点击绿色节点解锁  |  ESC 关闭", True, COLOR_TEXT_DIM)
        else:
            hint = self.font_small.render("无可用解锁项目  |  ESC 关闭", True, COLOR_TEXT_DIM)
        self.screen.blit(hint, (60, WIN_HEIGHT - 30))

    def _draw_help(self):
        if not self.show_help:
            return
        s = pygame.Surface((WIN_WIDTH, WIN_HEIGHT), pygame.SRCALPHA)
        s.fill((0, 0, 0, 200))
        self.screen.blit(s, (0, 0))

        lines = [
            "操作帮助", "",
            "W / ↑         向上",
            "S / ↓         向下",
            "A / ←         向左",
            "D / →         向右",
            "W + A         左上 (斜向)",
            "W + D         右上 (斜向)",
            "S + A         左下 (斜向)",
            "S + D         右下 (斜向)", "",
            "E             打开背包 / 合成界面",
            "T             科技树",
            "左键建筑      打开建筑面板",
            "1 ~ 8         选择背包物品",
            "左键背包格    选中物品",
            "左键地图      放置建筑（需选中建造材料）",
            "右键地图      拆除建筑（2秒冷却）",
            "B             打开 / 确认放置建筑",
            "TAB            切换建筑类型",
            "ESC            取消 / 关闭帮助",
            "H             帮助开关",
            "Q             退出游戏",
        ]
        cx = WIN_WIDTH // 2
        cy = WIN_HEIGHT // 2 - len(lines) * 13
        for line in lines:
            if line and line[0].isupper():
                surf = self.font_large.render(line, True, COLOR_HIGHLIGHT)
            else:
                surf = self.font.render(line, True, COLOR_TEXT)
            self.screen.blit(surf, (cx - surf.get_width() // 2, cy))
            cy += 26

    def _quit(self):
        pygame.quit()
        sys.exit()

    # ========== 主循环 ==========

    def run(self):
        while True:
            self.clock.tick(FPS)
            self._handle_events()
            self._update_movement()

            self.screen.fill(COLOR_BG)
            self._draw_grid()
            self._draw_player()
            self._draw_sidebar()
            self._draw_hotbar()
            self._draw_placement()
            self._draw_mouse_ghost()
            self._draw_demolish_bar()
            self._draw_messages()
            self._draw_building_panel()
            self._draw_tech_tree()
            self._draw_backpack_ui()
            self._draw_help()
            pygame.display.flip()


def main():
    GameWindow().run()


if __name__ == "__main__":
    main()

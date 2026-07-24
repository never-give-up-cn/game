"""Pygame 图形窗口版 - 网格地图游戏"""

import math
import sys
from typing import Dict, Tuple, List

import pygame

from map_grid import MapGrid, TileType
from building import Building, BUILDING_TEMPLATES, register_building
from building.apple_factory import AppleFactory
register_building("苹果工厂", AppleFactory)
from crafting import MANUAL_RECIPES, get_craftable_manual
from backpack.ui import draw_backpack_ui
from building.panel_ui import draw_building_interaction
from tech_tree import TECH_NODES, get_available, max_plugin_tier, get_building_bonuses
from player import Player


# ========== 常量 ==========

TILE_SIZE = 40
MAP_COLS, MAP_ROWS = 20, 12
SIDEBAR_WIDTH = 160
SIDEBAR_COLLAPSED = 24

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
        # 演示物流需求
        logi = self.player.logistics
        logi.set_request("wood", 10)
        logi.set_request("stone", 5)
        logi.set_request("iron", 10)
        logi.set_request("bread", 3)

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
        self._msg("WASD 移动 | 左键建筑查看 | 右键拆除 | H 操作指南")

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

        # 侧栏折叠
        self.sidebar_collapsed = False

        # 选中建筑 + 动画帧
        self.selected_building = None
        self._transfer_actions = []
        self.anim_frame = 0

        # 鼠标状态
        self.mouse_grid_pos: Tuple[int, int] = (-1, -1)
        self.mouse_in_map = False
        self.hover_slot_idx = -1

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
                if event.button == 1:
                    # 检测侧栏折叠/展开点击
                    mx, my = event.pos
                    sw = SIDEBAR_COLLAPSED if self.sidebar_collapsed else SIDEBAR_WIDTH
                    x0 = MAP_COLS * TILE_SIZE
                    if x0 <= mx <= x0 + sw and 0 <= my <= MAP_HEIGHT:
                        self.sidebar_collapsed = not self.sidebar_collapsed
                    else:
                        self._on_left_click(event.pos)
                elif event.button == 3:
                    self.right_held = True
                    self._on_right_down(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3:   # 右键松开 -> 取消拆除
                    self.right_held = False
                    self._cancel_demolish()

    def _on_keydown(self, key: int):
        if key == pygame.K_q:
            # Q: 空手（取消选中 + 取消放置）
            self.player.inventory.selected = -1
            self.placing = False
            self.selected_building = None
            self.show_building_panel = False
        elif key == pygame.K_ESCAPE:
            self._quit()
        elif key == pygame.K_h:
            self.show_help = not self.show_help
        elif key == pygame.K_e:
            self.show_backpack = not self.show_backpack
            self.show_building_panel = False
        elif key == pygame.K_t:
            self.show_tech_tree = not self.show_tech_tree
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
        # 地图格子 + 建筑悬浮检测
        if 0 <= mx < MAP_COLS * TILE_SIZE and 0 <= my < MAP_HEIGHT:
            gx = mx // TILE_SIZE
            gy = my // TILE_SIZE
            self.mouse_grid_pos = (gx, gy)
            self.mouse_in_map = True
            # 悬浮在建筑上 -> 侧栏显示信息
            bld = self._building_at(gx, gy)
            if bld:
                self.selected_building = bld
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
        """鼠标左键：建筑面板 / 合成 / 选中 / 放置 / 科技树"""
        mx, my = pos

        if self.show_building_panel:
            self._click_building_panel(pos)
            return
        # 科技树：解锁节点
        if self.show_tech_tree:
            self._click_tech_tree(pos)
            return
        # 背包界面：合成 + 物流交互
        if self.show_backpack:
            for rect, recipe in getattr(self, '_craft_buttons', []):
                if rect.collidepoint(pos):
                    inv = self.player.inventory
                    if recipe.craft(inv):
                        self._msg(f"合成 {recipe.name} x{recipe.quantity}")
                    else:
                        self._msg(f"材料不足，无法合成 {recipe.name}")
                    return
            return  # 背包打开时屏蔽其他点击

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
            # 先检查是否点击到建筑 → 弹窗
            bld = self._building_at(gx, gy)
            if bld:
                self.panel_building = bld
                self.selected_building = bld
                self.show_building_panel = True
            elif self.player.selected_slot and self.player.selected_slot.item_id in ITEM_TO_BUILDING:
                # 无建筑 + 有建造材料 → 放置
                self._place_with_selected(gx, gy)
            else:
                self.selected_building = None

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
        self.anim_frame += 1
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
        bld = None
        for b in self.game_map.buildings:
            if b.x <= gx < b.x + b.w and b.y <= gy < b.y + b.h:
                color = BUILDING_COLORS.get(b.name, color)
                accent = BUILDING_ACCENT.get(b.name, accent)
                bld = b
                break

        is_selected = (bld is not None and bld is self.selected_building)
        inv = self.player.inventory

        # 判断建筑状态
        border_color = COLOR_GRID
        show_glow = False
        show_flash = False
        show_full = False

        if bld and bld.inputs:
            has_mats = all(inv.count(iid) >= amt for iid, amt in bld.inputs.items())
            if has_mats:
                show_glow = True  # 正常生产中
            else:
                show_flash = True  # 停工（缺材料）

        if bld and bld.outputs:
            for oid, _ in bld.outputs.items():
                if inv.count(oid) >= 20:
                    show_full = True  # 堆满

        # 绘制底色
        pygame.draw.rect(self.screen, color, rect)

        # 内部纹理
        inner = rect.inflate(-6, -6)
        pygame.draw.rect(self.screen, accent, inner, 1)

        # 选中高亮外框
        if is_selected:
            pygame.draw.rect(self.screen, COLOR_HIGHLIGHT, rect, 3)

        # 呼吸光效（正常生产）
        if show_glow:
            glow = int(60 + 40 * abs(math.sin(self.anim_frame * 0.05)))
            gs = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            gs.fill((*accent, glow))
            self.screen.blit(gs, rect)

        # 橙黄闪烁（停工/故障）
        if show_flash:
            if (self.anim_frame // 15) % 2 == 0:
                pygame.draw.rect(self.screen, (255, 160, 40), rect, 3)
            else:
                pygame.draw.rect(self.screen, (200, 100, 20), rect, 2)

        # 堆满标识（右上角小三角）
        if show_full:
            tri = [(rect.right, rect.top), (rect.right - 12, rect.top), (rect.right, rect.top + 12)]
            pygame.draw.polygon(self.screen, (255, 200, 50), tri)
            exc = self.font_small.render("!", True, (30, 30, 35))
            self.screen.blit(exc, (rect.right - 10, rect.top + 1))

    def _draw_player(self):
        cx = self.player.x * TILE_SIZE + TILE_SIZE // 2
        cy = self.player.y * TILE_SIZE + TILE_SIZE // 2
        r = TILE_SIZE // 2 - 4

        # 呼吸光圈（整个格子大小的脉冲光晕）
        pulse = abs(math.sin(self.anim_frame * 0.04))  # 0~1 呼吸
        glow_r = TILE_SIZE
        for i in range(4):
            sr = glow_r + i * 6
            alpha = int(35 * pulse) - i * 6
            if alpha <= 0:
                continue
            s = pygame.Surface((sr * 2, sr * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 200, 50, max(0, alpha)), (sr, sr), sr)
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
        inv = self.player.inventory

        if self.sidebar_collapsed:
            # 折叠态：仅窄条 + 展开箭头
            pygame.draw.rect(self.screen, COLOR_SIDEBAR, (x0, 0, SIDEBAR_COLLAPSED, WIN_HEIGHT))
            pygame.draw.line(self.screen, COLOR_GRID, (x0, 0), (x0, WIN_HEIGHT), 2)
            arrow = self.font.render("<", True, COLOR_TEXT_DIM)
            self.screen.blit(arrow, (x0 + 6, WIN_HEIGHT // 2 - 10))
            return

        # 展开态
        sw = SIDEBAR_WIDTH
        pygame.draw.rect(self.screen, COLOR_SIDEBAR, (x0, 0, sw, WIN_HEIGHT))
        pygame.draw.line(self.screen, COLOR_GRID, (x0, 0), (x0, WIN_HEIGHT), 2)

        # 折叠按钮（右上角）
        fold = self.font.render(">", True, COLOR_TEXT_DIM)
        fold_rect = fold.get_rect(topright=(x0 + sw - 6, 10))
        self.screen.blit(fold, fold_rect)

        x = x0 + 10
        y = 16

        # 标题
        title = self.font_large.render("信息", True, COLOR_HIGHLIGHT)
        self.screen.blit(title, (x, y))
        y += 28

        # 玩家信息（紧凑）
        info_lines = [
            f"{self.player.name}  Lv.{self.player.level}",
            f"HP: {self.player.hp}/{self.player.max_hp}  ({self.player.x},{self.player.y})",
        ]
        for line in info_lines:
            self.screen.blit(self.font_small.render(line, True, COLOR_TEXT), (x, y))
            y += 17
        y += 4

        # 选中物品详情（热栏中的物品）
        sel_slot = self.player.selected_slot
        if sel_slot:
            from item import ITEM_TEMPLATES as _it
            item = sel_slot.item
            self.screen.blit(
                self.font_small.render(f"{item.icon} {item.name}  {item.category}", True, COLOR_HIGHLIGHT), (x, y))
            y += 18
            self.screen.blit(
                self.font_small.render(f"  {item.description}", True, COLOR_TEXT_DIM), (x, y))
            y += 16
            bld = ITEM_TO_BUILDING.get(item.item_id)
            if bld:
                self.screen.blit(
                    self.font_small.render(f"  -> 建造: {bld}", True, (150, 255, 150)), (x, y))
                y += 16
            y += 4

        # 选中建筑详情（紧凑格式，同玩家信息）
        if self.selected_building:
            b = self.selected_building
            self.screen.blit(
                self.font_small.render(f"{b.name}  {b.w}x{b.h}  ({b.x},{b.y})", True, COLOR_HIGHLIGHT), (x, y))
            y += 18
            self.screen.blit(
                self.font_small.render(f"HP: {b.hp}/{b.max_hp}", True, COLOR_TEXT), (x, y))
            y += 17
            summary = b.production_summary
            if summary:
                self.screen.blit(
                    self.font_small.render(f"  {summary}", True, COLOR_TEXT_DIM), (x, y))
                y += 17
            if b.inputs:
                for iid, amt in b.inputs.items():
                    from item import ITEM_TEMPLATES as _it
                    tmpl = _it.get(iid)
                    mn = tmpl.name if tmpl else iid
                    hv = inv.count(iid)
                    c = COLOR_TEXT if hv >= amt else (255, 80, 80)
                    self.screen.blit(
                        self.font_small.render(f"  {mn} {hv}/{amt}", True, c), (x, y))
                    y += 16
            y += 4
        else:
            self.screen.blit(
                self.font_small.render(f"建筑 ({len(self.game_map.buildings)})", True, COLOR_HIGHLIGHT), (x, y))
            y += 18
            for b in self.game_map.buildings[:5]:
                self.screen.blit(
                    self.font_small.render(f"  {b.name} ({b.x},{b.y})", True, COLOR_TEXT_DIM), (x, y))
                y += 15
            if len(self.game_map.buildings) > 5:
                self.screen.blit(
                    self.font_small.render(f"  ... +{len(self.game_map.buildings)-5}", True, COLOR_TEXT_DIM), (x, y))
            y += 4

        # 背包摘要（紧凑）
        self.screen.blit(self.font_small.render("背包", True, COLOR_HIGHLIGHT), (x, y))
        y += 18
        items = inv.list_items()
        if items:
            for s in items[:4]:
                self.screen.blit(
                    self.font_small.render(f"  {s.icon} {s.name} x{s.quantity}", True, COLOR_TEXT_DIM), (x, y))
                y += 15
            if len(items) > 4:
                self.screen.blit(
                    self.font_small.render(f"  ... +{len(items)-4}", True, COLOR_TEXT_DIM), (x, y))
        else:
            self.screen.blit(self.font_small.render("  (空)", True, COLOR_TEXT_DIM), (x, y))

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

        # 选中物品名称（-1=空手）
        sel_idx = inv.selected
        sel = inv.slots[sel_idx] if 0 <= sel_idx < len(inv.slots) else None
        if sel:
            label = f"{sel.name}  ({sel.item.description})"
            surf = self.font_small.render(label, True, COLOR_TEXT_DIM)
            self.screen.blit(surf, (bar_rect.x + 10, MAP_HEIGHT + HOTBAR_HEIGHT - 20))

    # ========== 背包界面 ==========

    def _draw_backpack_ui(self):
        """背包界面委托给 backpack.ui"""
        if not self.show_backpack:
            return
        self._craft_buttons = []
        draw_backpack_ui(
            screen=self.screen,
            font=self.font,
            font_small=self.font_small,
            font_large=self.font_large,
            inv=self.player.inventory,
            logistics=self.player.logistics,
            mouse_pos=pygame.mouse.get_pos(),
            anim_frame=self.anim_frame,
            craft_buttons=self._craft_buttons,
        )

    # ========== 建筑面板 ==========

    def _draw_building_panel(self):
        if not self.show_building_panel or not self.panel_building:
            return
        draw_building_interaction(
            screen=self.screen,
            font=self.font,
            font_small=self.font_small,
            font_large=self.font_large,
            building=self.panel_building,
            inventory=self.player.inventory,
            tech_unlocked=self.tech_unlocked,
            mouse_pos=pygame.mouse.get_pos(),
            anim_frame=self.anim_frame,
            transfer_actions=self._transfer_actions,
        )

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
        NODE_W = 190
        TIER_GAP = 120
        COL_SPACING = NODE_W + 30

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

        # ── 计算每个节点的动态高度（依赖资源行数）──
        node_heights = {}
        for node in TECH_NODES.values():
            n_req = len(node.requirements)
            node_heights[node.node_id] = 56 + n_req * 18 + 4

        # ── 绘制连线（使用动态节点高度）──
        for node in TECH_NODES.values():
            cx, cy = node_pos(node.node_id)
            nh = node_heights.get(node.node_id, 62)
            for pid in node.parent_ids:
                if pid not in layout:
                    continue
                px, py = node_pos(pid)
                ph = node_heights.get(pid, 62)
                start = (px, py + ph // 2)
                end = (cx, cy - nh // 2)
                mid_y = (start[1] + end[1]) // 2
                color = (80, 120, 80) if pid in self.tech_unlocked else (50, 50, 55)
                pygame.draw.line(self.screen, color, start, (start[0], mid_y), 2)
                pygame.draw.line(self.screen, color, (start[0], mid_y), (end[0], mid_y), 2)
                pygame.draw.line(self.screen, color, (end[0], mid_y), end, 2)

        # ── 绘制节点卡片（文字堆叠：名称 → 效果 → 资源 xN）──
        self._tech_buttons = []
        for node in TECH_NODES.values():
            cx, cy = node_pos(node.node_id)
            nh = node_heights.get(node.node_id, 62)
            rx, ry = cx - NODE_W // 2, cy - nh // 2
            rect = pygame.Rect(rx, ry, NODE_W, nh)

            unlocked = node.node_id in self.tech_unlocked
            can = node.can_unlock(inv, self.tech_unlocked)
            parents_ok = all(p in self.tech_unlocked for p in node.parent_ids)
            hover = rect.collidepoint(mx, my)
            reqs = list(node.requirements.items())

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

            y_off = ry + 6

            # 行 1: 状态 + 名称 + 等级标签
            st = "✓" if unlocked else ("▶" if can else "🔒")
            sc = COLOR_HIGHLIGHT if unlocked else ((150, 255, 150) if can else COLOR_TEXT_DIM)
            name_surf = self.font.render(f"{st} {node.name}", True, sc)
            self.screen.blit(name_surf, (rx + 8, y_off))
            # tier 标签（右上角）
            tier_tag = self.font_small.render(f"T{node.tier}", True, COLOR_TEXT_DIM)
            self.screen.blit(tier_tag, (rect.right - tier_tag.get_width() - 8, y_off + 2))
            y_off += 22

            # 行 2: 效果描述
            desc = self.font_small.render(node.description, True, COLOR_TEXT_DIM)
            self.screen.blit(desc, (rx + 8, y_off))
            y_off += 18

            # 行 3+: 资源存量 / 需求（逐行扫视）
            if not unlocked:
                for mid, amt in reqs:
                    from item import ITEM_TEMPLATES as _it2
                    tmpl = _it2.get(mid)
                    mn = tmpl.name if tmpl else mid
                    hv = inv.count(mid)
                    enough = hv >= amt
                    color = COLOR_TEXT if enough else (255, 80, 80)

                    # 文字: "资源名  存量/需求"
                    line = self.font_small.render(f"{mn}  {hv}/{amt}", True, color)
                    self.screen.blit(line, (rx + 12, y_off))

                    # 微型进度条（视觉辅助）
                    bar_w = 40
                    bar_h = 4
                    bar_x = rect.right - bar_w - 10
                    bar_y = y_off + 4
                    ratio = min(1.0, hv / max(amt, 1))
                    pygame.draw.rect(self.screen, (40, 30, 30), (bar_x, bar_y, bar_w, bar_h))
                    if ratio > 0:
                        bc = (80, 200, 80) if enough else (200, 60, 60)
                        pygame.draw.rect(self.screen, bc, (bar_x, bar_y, int(bar_w * ratio), bar_h))
                    y_off += 18

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
        s.fill((0, 0, 0, 210))
        self.screen.blit(s, (0, 0))

        title = self.font_large.render("操 作 指 南", True, COLOR_HIGHLIGHT)
        self.screen.blit(title, (WIN_WIDTH // 2 - title.get_width() // 2, 28))

        # 左中右三栏
        col_x = [60, WIN_WIDTH // 2 - 50, WIN_WIDTH - 230]
        col_w = 200

        sections = [
            ("移动", [
                ("W / ↑",   "向上移动一格"),
                ("S / ↓",   "向下移动一格"),
                ("A / ←",   "向左移动一格"),
                ("D / →",   "向右移动一格"),
                ("W+A 等",  "同时按两个键斜向移动"),
            ]),
            ("采集与建造", [
                ("左键地图",  "选中建造材料时放置建筑"),
                ("左键建筑",  "打开建筑面板查看详情"),
                ("右键建筑",  "按住 2 秒拆除（进度条）"),
                ("B 键",     "键盘放置模式 / 确认"),
                ("TAB",      "切换建筑类型"),
            ]),
            ("背包与合成", [
                ("E 键",     "打开背包 / 合成界面"),
                ("左键背包格", "选中该物品"),
                ("1~8 数字键", "快速选择物品格"),
                ("左键配方",  "消耗材料合成物品"),
                ("Q 键",     "空手（取消选中）"),
                ("T 键",     "科技树（消耗物品解锁）"),
            ]),
            ("视觉提示", [
                ("呼吸光圈",  "角色所在格，脉冲光效"),
                ("绿光边框",  "建筑正常生产中"),
                ("橙光闪烁",  "建筑材料不足，停工"),
                ("黄色三角!", "产品堆满，需要清理"),
                ("黄色边框",  "当前选中的建筑"),
            ]),
            ("界面说明", [
                ("右侧面板",  "点击边缘 > 折叠/展开"),
                ("底部热栏",  "背包物品快捷栏"),
                ("侧栏详情",  "选中建筑后显示生产信息"),
                ("ESC",      "退出游戏"),
                ("H 键",     "开关本指南"),
            ]),
        ]

        for si, (title_text, items) in enumerate(sections):
            cx = col_x[si % 3]
            cy = 65 + (si // 3) * 220

            sec_title = self.font.render(title_text, True, COLOR_HIGHLIGHT)
            self.screen.blit(sec_title, (cx, cy))
            cy += 24

            for key, desc in items:
                key_surf = self.font_small.render(key, True, (180, 200, 255))
                self.screen.blit(key_surf, (cx, cy))
                desc_surf = self.font_small.render(desc, True, COLOR_TEXT)
                self.screen.blit(desc_surf, (cx + key_surf.get_width() + 8, cy))
                cy += 20

        # 底部退出提示
        hint = self.font_small.render("H 键关闭指南", True, COLOR_TEXT_DIM)
        self.screen.blit(hint, (WIN_WIDTH // 2 - hint.get_width() // 2, WIN_HEIGHT - 30))

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

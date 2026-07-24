"""Pygame 图形窗口版 - 网格地图游戏"""

import math
import sys
from typing import Dict, Tuple, List, Optional

import pygame

from map_grid import MapGrid, TileType
from building import Building, BUILDING_TEMPLATES, register_building
from building.apple_factory import AppleFactory
register_building("苹果工厂", AppleFactory)
from crafting import MANUAL_RECIPES, get_craftable_manual
from backpack.ui import draw_backpack_ui
from building.panel_ui import draw_building_interaction
from tech_tree import TECH_NODES, get_available, max_plugin_tier, get_building_bonuses, ResearchQueue
from player import Player
from item import ItemStack


# ========== 常量 ==========

TILE_SIZE = 40
VIEWPORT_COLS, VIEWPORT_ROWS = 20, 12
SIDEBAR_WIDTH = 160
SIDEBAR_COLLAPSED = 24

WIN_WIDTH = VIEWPORT_COLS * TILE_SIZE + SIDEBAR_WIDTH
MAP_HEIGHT = VIEWPORT_ROWS * TILE_SIZE
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
    "belt_item": "基础传送带",
    "inserter_item": "电力机械臂",
}

# 机械臂类名列表（用于方向箭头渲染）
_INSERTER_NAMES = [n for n in BUILDING_NAMES if "机械臂" in n]

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
        self.game_map = MapGrid()
        self.camera_x = 0  # 相机世界坐标
        self.camera_y = 0
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
        # 初始建筑物资
        inv.add_item("belt_item", 5)      # 5 条传送带
        inv.add_item("inserter_item", 2)  # 2 个机械臂
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
        self.cursor_item: Optional[str] = None  # 光标持有的物品ID
        self.cursor_count: int = 0
        self.research_queue = ResearchQueue()

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
        self.hovered_tile = None  # 悬浮的地图物体 {type, name, icon, details, pct}

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
                    x0 = VIEWPORT_COLS * TILE_SIZE
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
            # Q: 光标物品放回背包（不清空，背包满则保留光标）
            if self.cursor_item and self.cursor_count > 0:
                placed = self.player.inventory.add_item(self.cursor_item, self.cursor_count)
                if placed >= self.cursor_count:
                    self.cursor_item = None
                    self.cursor_count = 0
                else:
                    self.cursor_count -= placed
                self._msg(f"Q↑ 放回背包 ({placed}个)")
            self.player.inventory.selected = -1
            self.placing = False
            self.selected_building = None
            self.show_building_panel = False
        elif key == pygame.K_z:
            # Z: 从光标放1个到地图/传送带
            self._drop_from_cursor()
        elif key == pygame.K_f:
            # F: 拾取脚下/附近物品
            self._pickup_to_cursor()
        elif key == pygame.K_ESCAPE:
            self._quit()
        elif key == pygame.K_h:
            self.show_help = not self.show_help
        elif key == pygame.K_e:
            self.show_backpack = not self.show_backpack
            self.show_building_panel = False
        elif key == pygame.K_t:
            self.show_tech_tree = not self.show_tech_tree
        elif key == pygame.K_r:
            # R: 旋转选中的机械臂
            if self.selected_building and hasattr(self.selected_building, 'rotate'):
                self.selected_building.rotate()
                self._msg(f"{self.selected_building.name} 方向: {self.selected_building.direction_name}")
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
        if 0 <= mx < VIEWPORT_COLS * TILE_SIZE and 0 <= my < MAP_HEIGHT:
            gx = mx // TILE_SIZE + self.camera_x
            gy = my // TILE_SIZE + self.camera_y
            self.mouse_grid_pos = (gx, gy)
            self.mouse_in_map = True
            # 悬浮检测: 建筑 > 资源 > 地形
            bld = self._building_at(gx, gy)
            if bld:
                self.selected_building = bld
                self.hovered_tile = None
                return
            self.selected_building = None

            from resource_gen import get_planet_at
            tile = self.game_map.get_tile(gx, gy)
            info = {"planet": get_planet_at(gx, gy), "gx": gx, "gy": gy}

            if tile == TileType.ORE:
                ore_id = self.game_map.get_ore(gx, gy)
                node = self.game_map.resource_mgr.get_node_at(gx, gy)
                if node:
                    from item import ITEM_TEMPLATES as _it
                    t = _it.get(ore_id)
                    info.update({"type": "矿脉", "name": t.name if t else ore_id,
                                 "icon": t.icon if t else "?",
                                 "pct": node.amount / max(node.max_amount, 1),
                                 "detail": f"储量: {node.amount:.0f}/{node.max_amount:.0f}"})
            elif tile == TileType.FLUID:
                ore_id = self.game_map.get_ore(gx, gy)
                node = self.game_map.resource_mgr.get_node_at(gx, gy)
                if node:
                    from item import ITEM_TEMPLATES as _it
                    t = _it.get(ore_id)
                    info.update({"type": "流体", "name": t.name if t else "流体",
                                 "icon": t.icon if t else "~",
                                 "pct": node.amount / max(node.max_amount, 1),
                                 "detail": f"储量: {node.amount:.0f}/{node.max_amount:.0f}"})
                else:
                    info.update({"type": "流体", "name": "熔岩/流体", "icon": "~",
                                 "pct": 1.0, "detail": "无限资源"})
            elif tile == TileType.BIO:
                info.update({"type": "生物", "name": "真菌/植物", "icon": "%",
                             "pct": 1.0, "detail": "Gleba 生物质"})
            elif tile == TileType.TREE:
                info.update({"type": "树木", "name": "树木", "icon": "t",
                             "pct": 1.0, "detail": "可砍伐获得木材"})
            elif tile == TileType.WATER:
                info.update({"type": "水域", "name": "水", "icon": "w",
                             "pct": 1.0, "detail": "可抽取无限水源"})
            elif tile == TileType.WALL:
                info.update({"type": "地形", "name": "废墟/岩石", "icon": "X",
                             "pct": 1.0, "detail": "不可通行"})
            elif tile == TileType.EMPTY:
                info.update({"type": "空地", "name": f"{info['planet'].upper()}地表",
                             "icon": ".", "pct": 1.0, "detail": "可建造"})
            self.hovered_tile = info if len(info) > 2 else None
        else:
            self.mouse_in_map = False
        # 背包格子
        self.hover_slot_idx = self._get_clicked_slot(pos)

    def _get_clicked_slot(self, pos: Tuple[int, int]) -> int:
        """检测鼠标点击了哪个背包格子，返回索引 (-1 = 未命中)"""
        mx, my = pos
        bar_rect = pygame.Rect(0, MAP_HEIGHT, VIEWPORT_COLS * TILE_SIZE, HOTBAR_HEIGHT)
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
            sx = bar_x0 + col * (cell_w + gap)
            sy = bar_y0 + row * (cell_h + gap)
            if sx <= mx <= sx + cell_w and sy <= my <= sy + cell_h:
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

        # 点击背包栏 -> 光标交互（拿起/放下）
        slot = self._get_clicked_slot(pos)
        if slot >= 0:
            inv = self.player.inventory
            if slot < len(inv.slots):
                stack = inv.slots[slot]
                if self.cursor_item and self.cursor_count > 0:
                    if stack and stack.item_id == self.cursor_item:
                        can = stack.item.max_stack - stack.quantity
                        add = min(can, self.cursor_count)
                        stack.add(add); self.cursor_count -= add
                        if self.cursor_count <= 0: self.cursor_item = None
                    elif stack is None:
                        n = ItemStack(self.cursor_item, 0)
                        n.add(self.cursor_count)
                        inv.slots[slot] = n
                        self.cursor_item = None; self.cursor_count = 0
                    else:
                        old_id, old_q = stack.item_id, stack.quantity
                        inv.slots[slot] = ItemStack(self.cursor_item, self.cursor_count)
                        self.cursor_item = old_id; self.cursor_count = old_q
                elif stack:
                    self.cursor_item = stack.item_id
                    self.cursor_count = stack.quantity
                    inv.slots[slot] = None
                inv.selected = slot
                return

        # 点击地图
        mx, my = pos
        if 0 <= mx < VIEWPORT_COLS * TILE_SIZE and 0 <= my < MAP_HEIGHT:
            gx = mx // TILE_SIZE + self.camera_x
            gy = my // TILE_SIZE + self.camera_y
            # 先检查是否点击到建筑
            bld = self._building_at(gx, gy)
            if bld:
                self.selected_building = bld
                # 传送带/分流器等纯物流建筑不弹窗
                if hasattr(bld, 'lanes') or hasattr(bld, 'input_buf'):
                    self.panel_building = None
                    self.show_building_panel = False
                else:
                    self.panel_building = bld
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
        if 0 <= mx < VIEWPORT_COLS * TILE_SIZE and 0 <= my < MAP_HEIGHT:
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


    def _cancel_demolish(self):
        """取消拆除（松开右键或移开鼠标）"""
        self.demolish_target = None
        self.demolish_frames = 0

    def _near_lane(self, belt) -> str:
        """传送带靠近玩家一侧的车道"""
        dx = self.player.x - belt.x
        dy = self.player.y - belt.y
        if belt.direction == 0:
            return "left" if dx < 0 else "right"
        elif belt.direction == 1:
            return "left" if dy < 0 else "right"
        elif belt.direction == 2:
            return "right" if dx < 0 else "left"
        else:
            return "right" if dy < 0 else "left"

    def _drop_from_cursor(self):
        """Z: 从光标放1个物品到传送带/地面"""
        if not self.cursor_item or self.cursor_count <= 0:
            self._msg("光标没有物品")
            return
        if not self.mouse_in_map:
            self._msg("鼠标不在游戏地图上")
            return
        gx, gy = self.mouse_grid_pos
        bld = self._building_at(gx, gy)
        if bld and hasattr(bld, 'lanes'):
            lane = self._near_lane(bld)
            if bld.add_item(self.cursor_item, lane):
                self.cursor_count -= 1
                if self.cursor_count <= 0:
                    self.cursor_item = None; self.cursor_count = 0
                self._msg(f"Z↓ {self.cursor_item} → {lane}")
            else:
                self._msg("该车道已满")
        else:
            if not hasattr(self, '_ground_items'):
                self._ground_items = {}
            key = (gx, gy)
            self._ground_items.setdefault(key, {})
            self._ground_items[key][self.cursor_item] = self._ground_items[key].get(self.cursor_item, 0) + 1
            self.cursor_count -= 1
            if self.cursor_count <= 0:
                self.cursor_item = None; self.cursor_count = 0
            self._msg(f"Z↓ {self.cursor_item} 到地面")

    def _pickup_to_cursor(self):
        """F: 拾取脚下物品（玩家所在格）"""
        gx, gy = self.player.x, self.player.y
        bld = self._building_at(gx, gy)
        if bld and hasattr(bld, 'lanes'):
            for ln in ("left", "right"):
                lane = bld.lanes.get(ln, [])
                if lane:
                    item = lane.pop(0)
                    if self.cursor_item == item["id"]:
                        self.cursor_count += 1
                    elif not self.cursor_item:
                        self.cursor_item = item["id"]; self.cursor_count = 1
                    else:
                        self.player.inventory.add_item(item["id"], 1)
                    self._msg(f"F↑ {item['id']}"); return
        if hasattr(self, '_ground_items'):
            key = (gx, gy)
            if key in self._ground_items and self._ground_items[key]:
                iid, cnt = next(iter(self._ground_items[key].items()))
                del self._ground_items[key][iid]
                if not self._ground_items[key]: del self._ground_items[key]
                if self.cursor_item == iid:
                    self.cursor_count += cnt
                elif not self.cursor_item:
                    self.cursor_item = iid; self.cursor_count = cnt
                else:
                    self.player.inventory.add_item(iid, cnt)
                self._msg(f"F↑ {iid} x{cnt}"); return

        # 矿脉开采 (F on ore)
        ore_id = self.game_map.get_ore(gx, gy)
        if ore_id:
            mined_id, mined_amt = self.game_map.resource_mgr.mine_at(gx, gy, 1)
            if mined_id and mined_amt > 0:
                self.player.inventory.add_item(mined_id, int(mined_amt))
                self._msg(f"开采: {mined_id}")

    def _place_with_selected(self, gx: int, gy: int):
        """根据选中的背包物品放置对应建筑（消耗物品）"""
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
            # 消耗一个建筑物品
            self.player.inventory.remove_item(sel.item_id, 1)
            self._msg(f"放置 {b.name} 于 ({b.x},{b.y}) (剩余{self.player.inventory.count(sel.item_id)})")
        except ValueError as e:
            self._msg(f"放置失败: {e}")

    def _place_key(self, key: int):
        if key == pygame.K_TAB:
            self.place_idx = (self.place_idx + 1) % len(BUILDING_NAMES)
        elif key == pygame.K_w:
            self.py = max(0, self.py - 1)
        elif key == pygame.K_s:
            self.py = min(VIEWPORT_ROWS - 1, self.py + 1)
        elif key == pygame.K_a:
            self.px = max(0, self.px - 1)
        elif key == pygame.K_d:
            self.px = min(VIEWPORT_COLS - 1, self.px + 1)

    def _confirm_place(self):
        name = BUILDING_NAMES[self.place_idx]
        try:
            b = Building(self.px, self.py, name)
            self.game_map.add_building(b)
            self._msg(f"放置 {b.name} 于 ({b.x},{b.y})")
            self.placing = False
        except ValueError as e:
            self._msg(f"失败: {e}")

    def _tick_buildings(self):
        inv = self.player.inventory
        for b in self.game_map.buildings[:]:
            b.tick(inv)

    def _tick_research(self):
        """每帧推进研究进度"""
        rq = self.research_queue
        if not rq.current_node:
            rq.start_next()
            return
        node = rq.current_node
        if not node:
            rq.current = None
            return
        inv = self.player.inventory
        if self.anim_frame % 60 == 0:
            if node.consume_science(inv):
                rq.progress += 0.1
            elif node.requirements:
                for iid, amt in node.requirements.items():
                    if inv.count(iid) >= amt:
                        inv.remove_item(iid, amt)
                        rq.progress += 0.05
                        break
        if rq.progress >= 1.0:
            if node.can_unlock(inv, self.tech_unlocked):
                node.unlock(inv)
                self.tech_unlocked.add(node.node_id)
                self._msg(f"研究完成: {node.name}")
            rq.current = None
            rq.progress = 0.0
            rq.start_next()

    def _tick_demolish(self):
        """每帧推进拆除进度（按住右键时）"""
        if not self.right_held or self.demolish_target is None:
            return
        # 检查鼠标是否还在同一个建筑上
        mx, my = pygame.mouse.get_pos()
        if not (0 <= mx < VIEWPORT_COLS * TILE_SIZE and 0 <= my < MAP_HEIGHT):
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
            if not hasattr(self, '_ground_items'):
                self._ground_items = {}
            for mat_id, mat_amt in bld.construction_materials.items():
                key = (bld.x, bld.y)
                self._ground_items.setdefault(key, {})
                refund = max(1, mat_amt // 2)
                self._ground_items[key][mat_id] = self._ground_items[key].get(mat_id, 0) + refund
            self.game_map.remove_building(bld)
            self._cancel_demolish()
            self.right_held = False

    def _update_camera(self):
        """相机跟随玩家，居中显示"""
        self.camera_x = self.player.x - VIEWPORT_COLS // 2
        self.camera_y = self.player.y - VIEWPORT_ROWS // 2

    def _update_movement(self):
        """每帧更新移动 + 相机跟随"""
        self.anim_frame += 1
        self._tick_buildings()
        self._tick_research()
        self._tick_demolish()
        self._update_camera()
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
        for vy in range(VIEWPORT_ROWS):
            for vx in range(VIEWPORT_COLS):
                wx = self.camera_x + vx
                wy = self.camera_y + vy
                rect = pygame.Rect(vx * TILE_SIZE, vy * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                tile = self.game_map.get_tile(wx, wy)
                # 资源矿脉着色
                ore_color = None
                if tile == TileType.ORE:
                    ore_color = (120, 100, 60)
                    # 根据矿石类型微调色
                    o = self.game_map.get_ore(wx, wy)
                    if o:
                        ore_shades = {
                            'iron_ore': (140, 120, 100), 'copper_ore': (160, 100, 80),
                            'tungsten_ore': (100, 120, 140), 'holmium_ore': (120, 80, 140),
                            'uranium_ore': (100, 200, 100),
                        }
                        ore_color = ore_shades.get(o, (120, 100, 60))
                    pygame.draw.rect(self.screen, ore_color, rect)
                    # 矿脉标记
                    pygame.draw.circle(self.screen, (180, 160, 100), rect.center, 8)
                elif tile == TileType.FLUID:
                    pygame.draw.rect(self.screen, (60, 100, 140), rect)
                elif tile == TileType.BIO:
                    pygame.draw.rect(self.screen, (60, 120, 60), rect)
                elif tile == TileType.WATER:
                    pygame.draw.rect(self.screen, (40, 80, 120), rect)
                elif tile == TileType.TREE:
                    pygame.draw.rect(self.screen, (50, 100, 50), rect)
                elif tile == TileType.EMPTY:
                    pygame.draw.rect(self.screen, COLOR_EMPTY, rect)
                elif tile == TileType.BUILDING:
                    self._draw_building_cell(wx, wy, rect)
                pygame.draw.rect(self.screen, COLOR_GRID, rect, 1)

                # 地面物品渲染
                if hasattr(self, '_ground_items'):
                    gkey = (wx, wy)
                    if gkey in self._ground_items and self._ground_items[gkey]:
                        items_at = list(self._ground_items[gkey].items())
                        if items_at:
                            iid, cnt = items_at[0]
                            from item import ITEM_TEMPLATES as _git
                            t = _git.get(iid)
                            ic = t.icon if t else "?"
                            try:
                                isurf = self.font_small.render(ic, True, COLOR_HIGHLIGHT)
                            except:
                                isurf = self.font_small.render("?", True, COLOR_HIGHLIGHT)
                            self.screen.blit(isurf, (rect.x + 2, rect.y + 2))
                            if cnt > 1:
                                csurf = self.font_small.render(str(cnt), True, COLOR_HIGHLIGHT)
                                self.screen.blit(csurf, (rect.right - csurf.get_width() - 2, rect.bottom - csurf.get_height() - 2))

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

        # 方向箭头（机械臂 / 传送带 / 地下）
        if bld and hasattr(bld, 'direction'):
            sx2 = rect.centerx
            sy2 = rect.centery
            dir_angle = bld.direction * 90
            import math as m2
            rad = m2.radians(dir_angle)
            # 颜色：机械臂=金色 传送带=按等级
            if hasattr(bld, 'belt_tier'):
                tier_colors = [(220, 200, 60), (220, 100, 60), (60, 160, 240)]
                arrow_c = tier_colors[min(bld.belt_tier, 3) - 1]
            else:
                arrow_c = (255, 220, 80)  # 机械臂金色
            end_x = sx2 + int(12 * m2.sin(rad))
            end_y = sy2 - int(12 * m2.cos(rad))
            pygame.draw.line(self.screen, arrow_c, (sx2, sy2), (end_x, end_y), 3)
            tip_size = 5
            for a in (dir_angle + 150, dir_angle - 150):
                tx = end_x + int(tip_size * m2.sin(m2.radians(a)))
                ty = end_y - int(tip_size * m2.cos(m2.radians(a)))
                pygame.draw.line(self.screen, arrow_c, (end_x, end_y), (tx, ty), 2)

        # 传送带物品渲染（双车道，物品缩小到 1/3 宽度）
        if bld and hasattr(bld, 'lanes'):
            from item import ITEM_TEMPLATES as _belt_it
            dir_angle = bld.direction * 90
            rad = math.radians(dir_angle)
            cx2 = rect.centerx
            cy2 = rect.centery
            for lane_name, off in [("left", -6), ("right", 6)]:
                lane = bld.lanes.get(lane_name, [])
                for item in lane:
                    progress = 1.0 - item["pos"]
                    px = cx2 + int((progress - 0.5) * 16 * math.sin(rad))
                    py = cy2 - int((progress - 0.5) * 16 * math.cos(rad))
                    lx = px + int(off * math.cos(rad))
                    ly = py + int(off * math.sin(rad))
                    shades = {"iron": (140,140,160), "steel": (180,200,220),
                              "coal": (60,60,60), "stone": (140,130,120),
                              "iron_ore": (160,120,80), "copper_ore": (180,100,60)}
                    ic = shades.get(item["id"], (200,160,60))
                    pygame.draw.circle(self.screen, ic, (int(lx), int(ly)), 5)

    def _draw_player(self):
        # 世界坐标 → 屏幕坐标（相机偏移）
        sx = (self.player.x - self.camera_x) * TILE_SIZE + TILE_SIZE // 2
        sy = (self.player.y - self.camera_y) * TILE_SIZE + TILE_SIZE // 2
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
            self.screen.blit(s, (sx - sr, sy - sr))

        # 身体
        pygame.draw.circle(self.screen, COLOR_PLAYER_OUTLINE, (sx, sy), r + 1)
        pygame.draw.circle(self.screen, COLOR_PLAYER, (sx, sy), r)
        # 眼睛
        off = r // 3
        for ex, ey in [(-off, -off), (off, -off)]:
            pygame.draw.circle(self.screen, (0, 0, 0), (sx + ex, sy + ey), 3)
        # 表情（微笑）
        pygame.draw.arc(self.screen, (0, 0, 0),
                        (sx - off, sy - 1, off * 2, off + 2), 0, 3.14, 2)

    def _draw_sidebar(self):
        x0 = VIEWPORT_COLS * TILE_SIZE
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
        from resource_gen import get_planet_at
        _planet = get_planet_at(self.player.x, self.player.y)
        title = self.font_small.render(f"[{_planet.upper()}] 信息", True, COLOR_HIGHLIGHT)
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

        # 悬浮地图物体详情
        if self.hovered_tile:
            h = self.hovered_tile
            self.screen.blit(
                self.font_small.render(f"{h['icon']} {h['name']}  [{h['type']}]", True, COLOR_HIGHLIGHT), (x, y))
            y += 18
            self.screen.blit(
                self.font_small.render(f"  {h['detail']}", True, COLOR_TEXT), (x, y))
            y += 16
            # 储量进度条（仅矿脉/流体有）
            pct = h.get('pct', 1.0)
            if pct < 1.0:
                bw, bh = 80, 4
                pygame.draw.rect(self.screen, (30, 25, 20), (x + 10, y, bw, bh))
                c = (80, 200, 80) if pct > 0.3 else (200, 160, 60) if pct > 0.1 else (200, 60, 60)
                pygame.draw.rect(self.screen, c, (x + 10, y, int(bw * pct), bh))
                y += 10
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
        bar_rect = pygame.Rect(0, MAP_HEIGHT, VIEWPORT_COLS * TILE_SIZE, HOTBAR_HEIGHT)
        pygame.draw.rect(self.screen, COLOR_HOTBAR_BG, bar_rect)
        pygame.draw.line(self.screen, COLOR_HOTBAR_BORDER,
                         (0, MAP_HEIGHT), (VIEWPORT_COLS * TILE_SIZE, MAP_HEIGHT), 3)

        for idx in range(slots_per_row * slot_rows):
            row = idx // slots_per_row
            col = idx % slots_per_row
            sx = bar_rect.x + (bar_rect.width - total_w) // 2 + col * (cell_w + gap)
            sy = bar_rect.y + 6 + row * (cell_h + gap)

            slot_rect = pygame.Rect(sx, sy, cell_w, cell_h)
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
                ix = sx + (cell_w - icon.get_width()) // 2
                self.screen.blit(icon, (ix, sy + 2))
                # 数量
                if stack.quantity > 1:
                    qty = self.font_small.render(str(stack.quantity), True, COLOR_HIGHLIGHT)
                    self.screen.blit(qty, (sx + cell_w - qty.get_width() - 3,
                                           sy + cell_h - qty.get_height() - 2))

            # 编号
            if row == 0:
                num = self.font_small.render(str(col + 1), True, COLOR_TEXT_DIM)
                self.screen.blit(num, (sx + 3, sy + 2))

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

    # ========== 研究窗口（三栏） ==========

    def _draw_tech_tree(self):
        if not self.show_tech_tree:
            return
        inv = self.player.inventory
        mx, my = pygame.mouse.get_pos()
        overlay = pygame.Surface((WIN_WIDTH, WIN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 15, 240))
        self.screen.blit(overlay, (0, 0))
        title = self.font_large.render("研 究 窗 口  [T 关闭]", True, COLOR_HIGHLIGHT)
        self.screen.blit(title, (WIN_WIDTH//2 - title.get_width()//2, 20))
        self._tech_buttons = []
        lw = 210
        self._draw_research_info(inv, mx, my, 6, 48, lw-6, 190)
        self._draw_tech_list(inv, mx, my, 6, 242, lw-6, WIN_HEIGHT-256)
        self._draw_tree_view(inv, mx, my, lw+8, 48, WIN_WIDTH-lw-14, WIN_HEIGHT-60)

    def _draw_research_info(self, inv, mx, my, px, py, pw, ph):
        pygame.draw.rect(self.screen, (16,18,28), (px,py,pw,ph), border_radius=6)
        pygame.draw.rect(self.screen, (40,50,65), (px,py,pw,ph), 1, border_radius=6)
        self.screen.blit(self.font_small.render("\U0001f4d6 当前研究", True, COLOR_HIGHLIGHT), (px+10, py+6))
        rq = self.research_queue; yy = py + 26
        if rq.current_node:
            n = rq.current_node
            self.screen.blit(self.font_small.render(n.name, True, COLOR_HIGHLIGHT), (px+12, yy)); yy+=20
            for sid, cnt in n.science_packs.items():
                from item import ITEM_TEMPLATES as _it2
                t = _it2.get(sid); ic = t.icon if t else "?"; mn = t.name if t else sid
                hv = inv.count(sid); c = COLOR_TEXT if hv>=cnt else (255,170,60)
                self.screen.blit(self.font_small.render(f"{ic} {mn} {hv}/{cnt}", True, c), (px+14, yy)); yy+=16
            bw, bh = pw-16, 8; bx = px+8; prog = rq.progress
            pygame.draw.rect(self.screen, (20,24,35), (bx,yy,bw,bh), border_radius=4)
            if prog>0:
                pygame.draw.rect(self.screen, (80,200,120), (bx,yy,int(bw*prog),bh), border_radius=4)
            pygame.draw.rect(self.screen, (50,60,75), (bx,yy,bw,bh), 1, border_radius=4)
            pct = self.font_small.render(f"{int(prog*100)}%", True, COLOR_TEXT_DIM)
            self.screen.blit(pct, (bx+bw-pct.get_width()-2, yy-1)); yy+=bh+6
            if n.rewards:
                self.screen.blit(self.font_small.render(f"\U0001f3c6 {n.rewards}", True, COLOR_TEXT_DIM), (px+12, yy))
        else:
            self.screen.blit(self.font_small.render("  未开始研究", True, COLOR_TEXT_DIM), (px+14, yy)); yy+=18
            self.screen.blit(self.font_small.render("  点击科技树节点添加到队列", True, COLOR_TEXT_DIM), (px+14, yy))
        yy = max(yy+8, py+ph-80)
        self.screen.blit(self.font_small.render(f"队列 ({len(rq.queue)}/6)", True, COLOR_HIGHLIGHT), (px+10, yy)); yy+=18
        for i, tid in enumerate(rq.queue[:6]):
            n2 = TECH_NODES.get(tid)
            if n2:
                self.screen.blit(self.font_small.render(f"  {i+1}. {n2.name}", True, COLOR_TEXT_DIM), (px+12, yy)); yy+=16
        if not rq.queue:
            self.screen.blit(self.font_small.render("  (空)", True, COLOR_TEXT_DIM), (px+14, yy))

    def _draw_tech_list(self, inv, mx, my, px, py, pw, ph):
        pygame.draw.rect(self.screen, (16,18,28), (px,py,pw,ph), border_radius=6)
        pygame.draw.rect(self.screen, (40,50,65), (px,py,pw,ph), 1, border_radius=6)
        self.screen.blit(self.font_small.render("\U0001f52c 全部科技", True, COLOR_HIGHLIGHT), (px+8, py+6))
        ss, gp = 34, 3; cols = 5
        for idx, node in enumerate(TECH_NODES.values()):
            sx = px+5+(idx%cols)*(ss+gp); sy = py+26+(idx//cols)*(ss+gp)
            sr = pygame.Rect(sx, sy, ss, ss)
            unlocked = node.node_id in self.tech_unlocked
            can = node.can_unlock(inv, self.tech_unlocked)
            bg = (30,60,30) if unlocked else ((50,60,40) if can else (25,25,30))
            bd = (80,180,80) if unlocked else ((120,200,80) if can else (40,40,50))
            pygame.draw.rect(self.screen, bg, sr, border_radius=4)
            pygame.draw.rect(self.screen, bd, sr, 1, border_radius=4)
            txt = self.font_small.render(node.name[:2], True, COLOR_TEXT if unlocked or can else COLOR_TEXT_DIM)
            self.screen.blit(txt, (sx+4, sy+6))
            if can:
                self._tech_buttons.append((sr, node, 'list'))

    def _draw_tree_view(self, inv, mx, my, px, py, pw, ph):
        pygame.draw.rect(self.screen, (12,14,22), (px,py,pw,ph), border_radius=6)
        pygame.draw.rect(self.screen, (30,40,55), (px,py,pw,ph), 1, border_radius=6)
        self.screen.blit(self.font_small.render("\U0001f9ec 科技树", True, COLOR_HIGHLIGHT), (px+12, py+8))
        NW, TG = 160, 100; CS = NW+25
        tiers = {}
        for n in TECH_NODES.values(): tiers.setdefault(n.tier, []).append(n)
        layout = {}
        for n in tiers.get(1,[]): layout[n.node_id] = (0,0)
        for t in range(2,6):
            for node in tiers.get(t,[]):
                pc = [layout[pid][0] for pid in node.parent_ids if pid in layout]
                if pc: a = sum(pc)/len(pc); col = int(a) if a%1==0 else a
                else: sib = tiers.get(t,[]); i = sib.index(node); col = i-(len(sib)-1)/2
                layout[node.node_id] = (col, t-1)
        ox, oy = px+pw//2, py+50
        def np(nid): c,r = layout.get(nid,(0,0)); return int(ox+c*CS), int(oy+r*TG)
        for node in TECH_NODES.values():
            sx,sy = np(node.node_id)
            for pid in node.parent_ids:
                if pid not in layout: continue
                px2,py2 = np(pid); col = (80,120,80) if pid in self.tech_unlocked else (50,50,55)
                my2 = (py2+25+sy-25)//2
                pygame.draw.line(self.screen, col, (px2,py2+25),(px2,my2),2)
                pygame.draw.line(self.screen, col, (px2,my2),(sx,my2),2)
                pygame.draw.line(self.screen, col, (sx,my2),(sx,sy-25),2)
        for node in TECH_NODES.values():
            sx,sy = np(node.node_id); nh = 50+len(node.science_packs)*16
            rx,ry = sx-NW//2, sy-nh//2; rect = pygame.Rect(rx,ry,NW,nh)
            unlocked = node.node_id in self.tech_unlocked
            can = node.can_unlock(inv, self.tech_unlocked)
            parents_ok = all(p in self.tech_unlocked for p in node.parent_ids)
            hover = rect.collidepoint(mx,my)
            is_cur = self.research_queue.current == node.node_id
            if unlocked: bg,bd = (35,65,35),(80,160,80)
            elif is_cur: bg,bd = (55,55,30),(200,200,60)
            elif can: bg = (55,60,40) if hover else (40,50,35); bd = (120,200,80) if hover else (70,120,50)
            elif parents_ok: bg = (40,30,25) if hover else (30,25,20); bd = (80,60,40)
            else: bg,bd = (25,25,30),(40,40,50)
            pygame.draw.rect(self.screen, bg, rect, border_radius=6)
            pygame.draw.rect(self.screen, bd, rect, 2, border_radius=6)
            st = "✓" if unlocked else ("▶" if can else "\U0001f512")
            sc = COLOR_HIGHLIGHT if unlocked else ((150,255,150) if can else COLOR_TEXT_DIM)
            self.screen.blit(self.font.render(f"{st} {node.name}", True, sc), (rx+8, ry+4))
            self.screen.blit(self.font_small.render(f"T{node.tier}", True, COLOR_TEXT_DIM), (rx+NW-24, ry+6))
            yy = ry+24
            for sid, cnt in node.science_packs.items():
                from item import ITEM_TEMPLATES as _it2
                t = _it2.get(sid); ic = t.icon if t else "?"; mn = t.name if t else sid
                hv = inv.count(sid); c = COLOR_TEXT if hv>=cnt else (255,170,60)
                self.screen.blit(self.font_small.render(f"{ic} {hv}/{cnt}", True, c), (rx+10, yy)); yy+=16
            if can and not is_cur: self._tech_buttons.append((rect, node, 'tree'))

    def _click_tech_tree(self, pos):
        """添加到研究队列"""
        for rect, node, source in getattr(self, '_tech_buttons', []):
            if rect.collidepoint(pos):
                if node.node_id in self.tech_unlocked:
                    self._msg(f"{node.name} 已完成"); return
                if not all(p in self.tech_unlocked for p in node.parent_ids):
                    self._msg("前置科技未完成"); return
                rq = self.research_queue
                if rq.current is None:
                    rq.current = node.node_id; rq.progress = 0.0
                    self._msg(f"开始研究: {node.name}")
                elif len(rq.queue) < 6:
                    rq.add(node.node_id)
                    self._msg(f"加入队列: {node.name} ({len(rq.queue)}/6)")
                else:
                    self._msg("队列已满 (最多6个)")
                return


    def _draw_cursor(self):
        if self.cursor_item and self.cursor_count > 0:
            mx, my = pygame.mouse.get_pos()
            from item import ITEM_TEMPLATES as _it
            t = _it.get(self.cursor_item)
            icon = t.icon if t else "?"
            lbl = self.font.render(f"{icon} {self.cursor_count}", True, COLOR_HIGHLIGHT)
            bg = pygame.Surface((lbl.get_width()+6, lbl.get_height()+4), pygame.SRCALPHA)
            bg.fill((10, 10, 15, 180))
            self.screen.blit(bg, (mx+16, my-10))
            self.screen.blit(lbl, (mx+19, my-8))

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
            sx = col_x[si % 3]
            sy = 65 + (si // 3) * 220

            sec_title = self.font.render(title_text, True, COLOR_HIGHLIGHT)
            self.screen.blit(sec_title, (sx, sy))
            sy += 24

            for key, desc in items:
                key_surf = self.font_small.render(key, True, (180, 200, 255))
                self.screen.blit(key_surf, (sx, sy))
                desc_surf = self.font_small.render(desc, True, COLOR_TEXT)
                self.screen.blit(desc_surf, (sx + key_surf.get_width() + 8, sy))
                sy += 20

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
            self._draw_cursor()
            pygame.display.flip()


def main():
    GameWindow().run()


if __name__ == "__main__":
    main()

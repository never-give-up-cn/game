"""游戏主循环 - 终端交互"""

import io
import os
import sys

# 确保 stdout 使用 UTF-8 编码（兼容 Windows 终端中文显示）
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from map_grid import MapGrid
from building import Building
from player import Player


def clear_screen():
    """清屏"""
    os.system("cls" if os.name == "nt" else "clear")


def safe_print(text: str):
    """安全打印（兼容 GBK 终端）"""
    try:
        print(text)
    except UnicodeEncodeError:
        # 移除或替换无法编码的字符
        cleaned = text.encode("gbk", errors="replace").decode("gbk")
        print(cleaned)


def print_help():
    print("""
  ┌─ 操作帮助 ─────────────────────────────┐
  │  WASD / 方向键   移动                   │
  │  B               放置建筑               │
  │  L               列出所有建筑           │
  │  Q               退出游戏               │
  │  H               帮助                   │
  └────────────────────────────────────────┘
    """)


def game_loop(game_map: MapGrid):
    """主游戏循环"""
    player = game_map.player
    assert player is not None

    while True:
        clear_screen()
        # 显示地图
        print(game_map.render_with_info())
        print()
        # 显示玩家状态
        print(player.status_line())
        print()

        # 处理输入
        cmd = input("  > ").strip().lower()

        moved = False
        if cmd in ("w", "key_up"):
            moved = game_map.move_player(0, -1)
        elif cmd in ("s", "key_down"):
            moved = game_map.move_player(0, 1)
        elif cmd in ("a", "key_left"):
            moved = game_map.move_player(-1, 0)
        elif cmd in ("d", "key_right"):
            moved = game_map.move_player(1, 0)
        elif cmd == "b":
            place_building_ui(game_map, player)
        elif cmd == "l":
            list_buildings(game_map)
            input("  按回车继续...")
        elif cmd == "h":
            print_help()
            input("  按回车继续...")
        elif cmd == "q":
            print("  感谢游玩！")
            sys.exit(0)

        if not moved and cmd in ("w", "s", "a", "d", "key_up", "key_down", "key_left", "key_right"):
            print("  XX 无法移动到那里！(超出地图或被建筑阻挡)")
            input("  按回车继续...")


def place_building_ui(game_map: MapGrid, player: Player):
    """放置建筑的用户交互"""
    clear_screen()
    print("  ┌─ 放置建筑 ──────────┐")
    templates = Building.list_templates()
    names = list(templates.keys())

    for i, name in enumerate(names, 1):
        print(f"  {i}. {name} - {templates[name]}")

    print(f"  {len(names)+1}. 取消")
    print("  └─────────────────────┘")
    print()

    try:
        choice = input("  请选择建筑编号: ").strip()
        idx = int(choice) - 1
        if idx < 0 or idx >= len(names):
            return
        template_name = names[idx]
    except (ValueError, IndexError):
        return

    print(f"\n  选择: {template_name}")
    print(f"  请输入放置坐标 (参考地图坐标轴):")

    try:
        x = int(input("    x = ").strip())
        y = int(input("    y = ").strip())
    except ValueError:
        print("  XX 无效坐标")
        input("  按回车继续...")
        return

    try:
        building = Building(x, y, template_name)
        game_map.add_building(building)
        print(f"  [OK] {building.name} 已放置于 ({x},{y})，占地 {building.w}×{building.h}")
    except ValueError as e:
        print(f"  XX {e}")
    input("  按回车继续...")


def list_buildings(game_map: MapGrid):
    """列出地图上所有建筑"""
    if not game_map.buildings:
        print("  (空) 地图上还没有建筑")
        return
    print(f"   地图上的建筑 ({len(game_map.buildings)}):")
    for i, b in enumerate(game_map.buildings, 1):
        print(f"    {i}. {b}")


def main():
    """入口函数"""
    clear_screen()

    print("""
  +==============================+
  |      [F] 工厂建造者          |
  |   2D 网格地图游戏            |
  +==============================+
    """)

    # 创建地图 (20x12)
    width, height = 20, 12
    game_map = MapGrid(width, height)

    # 放置一些预置建筑
    demo_buildings = [
        Building(1, 1, "工厂"),     # 2x2
        Building(5, 1, "仓库"),     # 2x1
        Building(5, 3, "住宅"),     # 1x1
        Building(8, 1, "研究所"),   # 2x2
        Building(1, 5, "住宅"),     # 1x1
        Building(3, 5, "城墙"),     # 3x1
    ]
    for b in demo_buildings:
        try:
            game_map.add_building(b)
        except ValueError:
            pass  # 跳过失败的放置

    # 创建玩家
    player = Player(10, 6, "工程师")
    game_map.set_player(player)

    print_help()
    input("  按回车开始游戏...")

    # 开始游戏循环
    game_loop(game_map)


if __name__ == "__main__":
    main()

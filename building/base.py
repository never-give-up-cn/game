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

    def has_plugin_slot(self) -> bool:
        return len(self.plugins) < self.plugin_slots

    def add_plugin(self, plugin_id: str) -> bool:
        if self.has_plugin_slot():
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

    def __repr__(self):
        return f"<{self.name} ({self.x},{self.y}) {self.w}x{self.h}>"

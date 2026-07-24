"""个人物流系统 - 无人机自动补给"""

from typing import Dict, List, Optional
from item import ITEM_TEMPLATES


class LogisticsRequest:
    """物流请求 - 玩家希望保持的库存"""

    def __init__(self, item_id: str, target_quantity: int):
        self.item_id = item_id
        self.target_quantity = target_quantity

    @property
    def name(self) -> str:
        t = ITEM_TEMPLATES.get(self.item_id)
        return t.name if t else self.item_id

    @property
    def icon(self) -> str:
        t = ITEM_TEMPLATES.get(self.item_id)
        return t.icon if t else "?"

    def __repr__(self):
        return f"<请求 {self.name} x{self.target_quantity}>"


class Logistics:
    """个人无人机物流系统"""

    def __init__(self):
        # 需求列表: item_id -> 目标数量
        self.requests: Dict[str, LogisticsRequest] = {}
        # 垃圾槽（拖入的物品标记为丢弃）
        self.trash_slots: List[Optional[str]] = [None] * 4
        # 自动丢弃未请求物品开关
        self.auto_discard: bool = False

    def set_request(self, item_id: str, quantity: int):
        """设置某物品的物流需求"""
        if quantity <= 0:
            self.requests.pop(item_id, None)
        else:
            self.requests[item_id] = LogisticsRequest(item_id, quantity)

    def remove_request(self, item_id: str):
        self.requests.pop(item_id, None)

    def get_requests_sorted(self) -> List[LogisticsRequest]:
        """按添加顺序返回请求列表"""
        return list(self.requests.values())

    # ── 垃圾槽 ──

    def add_trash(self, item_id: str) -> bool:
        """将物品放入垃圾槽，返回是否成功"""
        for i in range(len(self.trash_slots)):
            if self.trash_slots[i] is None:
                self.trash_slots[i] = item_id
                return True
        return False

    def remove_trash(self, slot_idx: int):
        if 0 <= slot_idx < len(self.trash_slots):
            self.trash_slots[slot_idx] = None

    # ── 无人机逻辑 ──

    def check_inventory(self, inventory) -> Dict[str, int]:
        """检查背包状态，返回需要补充和需要移除的物品
        返回: {item_id: delta}, delta>0需要补充, delta<0需要运走
        """
        actions = {}
        for item_id, req in self.requests.items():
            current = inventory.count(item_id)
            deficit = req.target_quantity - current
            if deficit > 0:
                actions[item_id] = deficit  # 需要补充

        if self.auto_discard:
            # 找出背包中不在请求列表且不是垃圾的物品
            for s in inventory.slots:
                if s and s.item_id not in self.requests:
                    actions[s.item_id] = -s.quantity  # 需要运走

        return actions

    def to_dict(self) -> dict:
        return {
            "requests": {k: v.target_quantity for k, v in self.requests.items()},
            "trash": [s for s in self.trash_slots if s],
            "auto_discard": self.auto_discard,
        }

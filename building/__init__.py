"""建筑系统包"""

from typing import Dict, Any, List, Type

from .base import BuildingBase
from .templates import BUILDING_TEMPLATES, BUILDING_NAMES
from inserter import Inserter
from conveyor import ConveyorBelt, UndergroundBelt, Splitter


_BUILDING_CLASSES: Dict[str, Type[BuildingBase]] = {}


def register_building(template_name: str, cls: Type[BuildingBase]):
    _BUILDING_CLASSES[template_name] = cls


# 自动注册
for _name in BUILDING_NAMES:
    if "机械臂" in _name:
        _BUILDING_CLASSES[_name] = Inserter
    elif "地下传送带" in _name:
        _BUILDING_CLASSES[_name] = UndergroundBelt
    elif "传送带" in _name:
        _BUILDING_CLASSES[_name] = ConveyorBelt
    elif "分流器" in _name:
        _BUILDING_CLASSES[_name] = Splitter


def Building(x: int, y: int, template_name: str) -> BuildingBase:
    """工厂函数：根据模板名创建建筑实例"""
    tmpl = BUILDING_TEMPLATES.get(template_name)
    if not tmpl:
        raise ValueError(f"未知建筑模板: {template_name}")
    cls = _BUILDING_CLASSES.get(template_name, BuildingBase)
    return cls(x, y, tmpl)


def list_templates() -> Dict[str, str]:
    return {
        name: f"{t['description']} ({t['width']}x{t['height']})"
        for name, t in BUILDING_TEMPLATES.items()
    }

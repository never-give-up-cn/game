"""建筑系统包"""

from typing import Dict, Any, List, Type

from .base import BuildingBase
from .templates import BUILDING_TEMPLATES, BUILDING_NAMES


_BUILDING_CLASSES: Dict[str, Type[BuildingBase]] = {}


def register_building(template_name: str, cls: Type[BuildingBase]):
    _BUILDING_CLASSES[template_name] = cls


def Building(x: int, y: int, template_name: str) -> BuildingBase:
    tmpl = BUILDING_TEMPLATES.get(template_name)
    if not tmpl:
        raise ValueError(f"未知建筑模板: {template_name}")
    cls = _BUILDING_CLASSES.get(template_name)
    if cls is None:
        # 延迟导入 + 自动注册
        if "机械臂" in template_name:
            from inserter import Inserter as _c
            _BUILDING_CLASSES[template_name] = _c; cls = _c
        elif "地下传送带" in template_name:
            from conveyor import UndergroundBelt as _c
            _BUILDING_CLASSES[template_name] = _c; cls = _c
        elif "传送带" in template_name:
            from conveyor import ConveyorBelt as _c
            _BUILDING_CLASSES[template_name] = _c; cls = _c
        elif "分流器" in template_name:
            from conveyor import Splitter as _c
            _BUILDING_CLASSES[template_name] = _c; cls = _c
        else:
            cls = BuildingBase
    return cls(x, y, tmpl)


def list_templates() -> Dict[str, str]:
    return {
        name: f"{t['description']} ({t['width']}x{t['height']})"
        for name, t in BUILDING_TEMPLATES.items()
    }

"""建筑系统包"""

from typing import Dict, Any, List, Type

from .base import BuildingBase
from .templates import BUILDING_TEMPLATES, BUILDING_NAMES


# 建筑类注册表：模板名 -> Python 类
# 自定义弹窗的建筑注册在这里，默认使用 BuildingBase
_BUILDING_CLASSES: Dict[str, Type[BuildingBase]] = {}


def register_building(template_name: str, cls: Type[BuildingBase]):
    """注册自定义建筑类（用于自定义弹窗等）"""
    _BUILDING_CLASSES[template_name] = cls


def Building(x: int, y: int, template_name: str) -> BuildingBase:
    """工厂函数：根据模板名创建建筑实例"""
    tmpl = BUILDING_TEMPLATES.get(template_name)
    if not tmpl:
        raise ValueError(f"未知建筑模板: {template_name}")
    cls = _BUILDING_CLASSES.get(template_name, BuildingBase)
    return cls(x, y, tmpl)


def list_templates() -> Dict[str, str]:
    """列出所有建筑模板"""
    return {
        name: f"{t['description']} ({t['width']}x{t['height']})"
        for name, t in BUILDING_TEMPLATES.items()
    }

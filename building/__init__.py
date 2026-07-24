"""建筑系统包"""

from typing import Dict, Any, List

from .base import BuildingBase
from .templates import BUILDING_TEMPLATES, BUILDING_NAMES


def Building(x: int, y: int, template_name: str) -> BuildingBase:
    """工厂函数：根据模板名创建建筑（兼容旧代码 Building(x,y,name) 语法）"""
    tmpl = BUILDING_TEMPLATES.get(template_name)
    if not tmpl:
        raise ValueError(f"未知建筑模板: {template_name}")
    return BuildingBase(x, y, tmpl)


def list_templates() -> Dict[str, str]:
    """列出所有建筑模板（兼容旧代码）"""
    return {
        name: f"{t['description']} ({t['width']}x{t['height']})"
        for name, t in BUILDING_TEMPLATES.items()
    }

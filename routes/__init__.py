#!/usr/bin/env python3
"""
路由模块
"""

from routes.admin import admin_bp
from routes.jetbrains import jetbrains_bp
from routes.jrebel import jrebel_bp
from routes.web import web_bp

__all__ = ['web_bp', 'jrebel_bp', 'jetbrains_bp', 'admin_bp']


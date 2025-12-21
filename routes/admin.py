#!/usr/bin/env python3
"""
后台管理 API 路由
"""

from flask import Blueprint, request, render_template, jsonify

from database import get_usage_records, get_usage_stats
from routes.utils import admin_required

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
def admin_page():
    """后台管理页面"""
    return render_template('admin.html')


@admin_bp.route('/api/admin/stats')
@admin_required
def admin_stats():
    """获取统计数据"""
    return jsonify(get_usage_stats())


@admin_bp.route('/api/admin/records')
@admin_required
def admin_records():
    """获取使用记录"""
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    search = request.args.get('search', '').strip()

    return jsonify(get_usage_records(page, page_size, search if search else None))


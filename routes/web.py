#!/usr/bin/env python3
"""
Web 界面路由
"""

import uuid

from flask import Blueprint, request, render_template, jsonify

from services import jrebel_signer, jetbrains_signer

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
def index():
    """首页 - Web 界面"""
    host = request.host
    scheme = request.scheme
    base_url = f"{scheme}://{host}"

    # 生成示例 GUID
    example_guid = str(uuid.uuid4())

    return render_template('index.html',
                           base_url=base_url,
                           example_guid=example_guid)


@web_bp.route('/generate', methods=['POST'])
def generate_url():
    """生成激活 URL"""
    data = request.get_json() or request.form

    product = data.get('product', 'jrebel')
    custom_guid = data.get('guid', '').strip()

    # 生成或使用自定义 GUID
    guid = custom_guid if custom_guid else str(uuid.uuid4())

    host = request.host
    scheme = request.scheme
    base_url = f"{scheme}://{host}"

    if product == 'jrebel':
        activation_url = f"{base_url}/{guid}"
    else:
        activation_url = f"{base_url}/"

    return jsonify({
        'success': True,
        'product': product,
        'guid': guid,
        'activation_url': activation_url,
        'email': '任意邮箱'
    })


@web_bp.route('/api/status')
def api_status():
    """API 状态检查"""
    return jsonify({
        'status': 'running',
        'version': '1.0.0',
        'jrebel_signer': jrebel_signer.private_key is not None,
        'jetbrains_signer': jetbrains_signer.private_key is not None
    })


@web_bp.route('/<path:guid>', methods=['GET'])
def handle_guid_path(guid):
    """处理 GUID 路径访问 (用于 JRebel 激活页面)"""
    # 如果是静态文件请求或管理页面，跳过
    if guid.startswith('static/') or guid.startswith('api/') or guid == 'admin':
        return '', 404

    # 返回激活信息页面
    host = request.host
    scheme = request.scheme
    base_url = f"{scheme}://{host}"

    return render_template('activation.html',
                           guid=guid,
                           base_url=base_url,
                           activation_url=f"{base_url}/{guid}")


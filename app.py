#!/usr/bin/env python3
"""
JRebel & JetBrains License Server
支持 Web 界面生成激活 URL

参考: https://github.com/Ahaochan/JrebelLicenseServerforJava
"""

import logging
import os

from flask import Flask

from config import SECRET_KEY
from routes import web_bp, jrebel_bp, jetbrains_bp, admin_bp

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    """创建 Flask 应用"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY

    # 注册蓝图
    app.register_blueprint(web_bp)
    app.register_blueprint(jrebel_bp)
    app.register_blueprint(jetbrains_bp)
    app.register_blueprint(admin_bp)

    return app


# 创建应用实例
app = create_app()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 58080))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    
    print("=" * 70)
    print("🚀 JRebel & JetBrains License Server")
    print("=" * 70)
    print(f"Web 界面: http://localhost:{port}")
    print(f"JRebel 激活: http://localhost:{port}/{{GUID}}")
    print(f"JetBrains 激活: http://localhost:{port}/")
    print("=" * 70)
    
    app.run(host='0.0.0.0', port=port, debug=debug)
#!/usr/bin/env python3
"""
JRebel & JetBrains License Server
支持 Web 界面生成激活 URL

参考: https://github.com/Ahaochan/JrebelLicenseServerforJava
"""

import os
import base64
import json
import time
import uuid
import hashlib
import logging
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for
from functools import wraps

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'jrebel-license-server-secret')

# 远程配置服务
CONFIG_SERVER_URL = os.environ.get('CONFIG_SERVER_URL', 'http://43.143.21.219:5000')
CONFIG_SERVER_TOKEN = os.environ.get('CONFIG_SERVER_TOKEN', 'u2InTXnmFF0Um6Sd')

# 使用记录存储 (内存存储，生产环境建议使用数据库)
usage_records = []
MAX_RECORDS = 10000  # 最大记录数

# ==================== JRebel 私钥 ====================
JREBEL_PRIVATE_KEY_BASE64 = (
    "MIICXAIBAAKBgQDQ93CP6SjEneDizCF1P/MaBGf582voNNFcu8oMhgdTZ/N6qa6O"
    "7XJDr1FSCyaDdKSsPCdxPK7Y4Usq/fOPas2kCgYcRS/iebrtPEFZ/7TLfk39HLuT"
    "Ejzo0/CNvjVsgWeh9BYznFaxFDLx7fLKqCQ6w1OKScnsdqwjpaXwXqiulwIDAQAB"
    "AoGATOQvvBSMVsTNQkbgrNcqKdGjPNrwQtJkk13aO/95ZJxkgCc9vwPqPrOdFbZa"
    "ppZeHa5IyScOI2nLEfe+DnC7V80K2dBtaIQjOeZQt5HoTRG4EHQaWoDh27BWuJoi"
    "p5WMrOd+1qfkOtZoRjNcHl86LIAh/+3vxYyebkug4UHNGPkCQQD+N4ZUkhKNQW7m"
    "pxX6eecitmOdN7Yt0YH9UmxPiW1LyCEbLwduMR2tfyGfrbZALiGzlKJize38shGC"
    "1qYSMvZFAkEA0m6psWWiTUWtaOKMxkTkcUdigalZ9xFSEl6jXFB94AD+dlPS3J5g"
    "NzTEmbPLc14VIWJFkO+UOrpl77w5uF2dKwJAaMpslhnsicvKMkv31FtBut5iK6GW"
    "eEafhdPfD94/bnidpP362yJl8Gmya4cI1GXvwH3pfj8S9hJVA5EFvgTB3QJBAJP1"
    "O1uAGp46X7Nfl5vQ1M7RYnHIoXkWtJ417Kb78YWPLVwFlD2LHhuy/okT4fk8LZ9L"
    "eZ5u1cp1RTdLIUqAiAECQC46OwOm87L35yaVfpUIjqg/1gsNwNsj8HvtXdF/9d30"
    "JIM3GwdytCvNRLqP35Ciogb9AO8ke8L6zY83nxPbClM="
)

# JetBrains 私钥
JETBRAINS_PRIVATE_KEY_BASE64 = (
    "MIIBOgIBAAJBALecq3BwAI4YJZwhJ+snnDFj3lF3DMqNPorV6y5ZKXCiCMqj8OeO"
    "mxk4YZW9aaV9ckl/zlAOI0mpB3pDT+Xlj2sCAwEAAQJAW6/aVD05qbsZHMvZuS2A"
    "a5FpNNj0BDlf38hOtkhDzz/hkYb+EBYLLvldhgsD0OvRNy8yhz7EjaUqLCB0juIN"
    "4QIhAOeCQp+NXxfBmfdG/S+XbRUAdv8iHBl+F6O2wr5fA2jzAiEAywlDfGIl6acn"
    "akPrmJE0IL8qvuO3FtsHBrpkUuOnXakCIQCqdr+XvADI/UThTuQepuErFayJMBSA"
    "sNe3NFsw0cUxAQIgGA5n7ZPfdBi3BdM4VeJWb87WrLlkVxPqeDSbcGrCyMkCIFSs"
    "5JyXvFTreWt7IQjDssrKDRIPmALdNjvfETwlNJyY"
)

# 固定的服务器随机数
SERVER_RANDOMNESS = "H2ulzLlh7E0="


class JRebelSigner:
    """JRebel 签名器"""
    
    def __init__(self):
        self.private_key = None
        self._load_private_key()
    
    def _load_private_key(self):
        """加载私钥"""
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend
            
            key_bytes = base64.b64decode(JREBEL_PRIVATE_KEY_BASE64)
            self.private_key = serialization.load_der_private_key(
                key_bytes,
                password=None,
                backend=default_backend()
            )
            logger.info("JRebel 私钥加载成功")
        except Exception as e:
            logger.error(f"加载私钥失败: {e}")
            self.private_key = None
    
    def sign(self, data: str) -> str:
        """SHA1withRSA 签名"""
        if self.private_key is None:
            return ""
        
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            
            signature = self.private_key.sign(
                data.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA1()
            )
            return base64.b64encode(signature).decode()
        except Exception as e:
            logger.error(f"签名失败: {e}")
            return ""
    
    def create_lease_signature(self, client_randomness: str, guid: str, 
                                offline: bool, valid_from: str = "null", 
                                valid_until: str = "null") -> str:
        """创建 JRebel lease 签名"""
        if offline:
            sign_data = f"{client_randomness};{SERVER_RANDOMNESS};{guid};true;{valid_from};{valid_until}"
        else:
            sign_data = f"{client_randomness};{SERVER_RANDOMNESS};{guid};false"
        
        logger.info(f"签名数据: {sign_data}")
        return self.sign(sign_data)


class JetBrainsSigner:
    """JetBrains 签名器"""
    
    def __init__(self):
        self.private_key = None
        self._load_private_key()
    
    def _load_private_key(self):
        """加载私钥"""
        try:
            from cryptography.hazmat.primitives.serialization import load_der_private_key
            from cryptography.hazmat.backends import default_backend
            
            key_bytes = base64.b64decode(JETBRAINS_PRIVATE_KEY_BASE64)
            try:
                self.private_key = load_der_private_key(
                    key_bytes,
                    password=None,
                    backend=default_backend()
                )
                logger.info("JetBrains 私钥加载成功")
            except:
                self.private_key = None
                logger.warning("JetBrains 私钥格式不兼容")
        except Exception as e:
            logger.error(f"加载 JetBrains 私钥失败: {e}")
            self.private_key = None
    
    def sign(self, content: str) -> str:
        """MD5withRSA 签名"""
        if self.private_key is None:
            return hashlib.md5(content.encode()).hexdigest()
        
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            
            signature = self.private_key.sign(
                content.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.MD5()
            )
            return signature.hex()
        except Exception as e:
            logger.error(f"JetBrains 签名失败: {e}")
            return hashlib.md5(content.encode()).hexdigest()


# 全局签名器
jrebel_signer = JRebelSigner()
jetbrains_signer = JetBrainsSigner()


# ==================== 辅助函数 ====================

def get_client_ip():
    """获取客户端真实 IP"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr


def add_usage_record(product: str, action: str, guid: str = None, username: str = None):
    """添加使用记录"""
    global usage_records
    
    record = {
        'timestamp': datetime.now().isoformat(),
        'product': product,
        'action': action,
        'guid': guid,
        'username': username,
        'ip': get_client_ip(),
        'user_agent': request.headers.get('User-Agent', '')[:200]
    }
    
    usage_records.insert(0, record)
    
    # 限制记录数量
    if len(usage_records) > MAX_RECORDS:
        usage_records = usage_records[:MAX_RECORDS]
    
    logger.info(f"Usage: {product} - {action} - {guid} - {username} - {get_client_ip()}")


def verify_admin_token():
    """验证管理员 token"""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return False
    
    token = auth_header[7:]
    return token == CONFIG_SERVER_TOKEN


def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not verify_admin_token():
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ==================== Web 界面路由 ====================

@app.route('/')
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


@app.route('/generate', methods=['POST'])
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


@app.route('/api/status')
def api_status():
    """API 状态检查"""
    return jsonify({
        'status': 'running',
        'version': '1.0.0',
        'jrebel_signer': jrebel_signer.private_key is not None,
        'jetbrains_signer': jetbrains_signer.private_key is not None
    })


# ==================== JRebel License Server 路由 ====================

@app.route('/jrebel/leases', methods=['GET', 'POST'])
@app.route('/agent/leases', methods=['GET', 'POST'])
def jrebel_leases():
    """JRebel lease 请求"""
    params = {**request.args, **request.form}
    if request.is_json:
        params.update(request.get_json() or {})
    
    client_randomness = params.get('randomness', '')
    username = params.get('username', '')
    guid = params.get('guid', '')
    offline = str(params.get('offline', 'false')).lower() == 'true'
    
    logger.info(f"JRebel Lease - User: {username}, GUID: {guid}, Offline: {offline}")
    
    if not client_randomness or not username or not guid:
        return '', 403
    
    # 记录使用
    add_usage_record('jrebel', 'lease', guid, username)
    
    valid_from = None
    valid_until = None
    
    if offline:
        client_time = params.get('clientTime', str(int(time.time() * 1000)))
        valid_until_ts = int(client_time) + 180 * 24 * 60 * 60 * 1000
        valid_from = int(client_time)
        valid_until = valid_until_ts
        signature = jrebel_signer.create_lease_signature(
            client_randomness, guid, True, str(valid_from), str(valid_until)
        )
    else:
        signature = jrebel_signer.create_lease_signature(
            client_randomness, guid, False
        )
    
    response = {
        "serverVersion": "3.2.4",
        "serverProtocolVersion": "1.1",
        "serverGuid": "a1b4aea8-b031-4302-b602-670a990272cb",
        "groupType": "managed",
        "id": 1,
        "licenseType": 1,
        "evaluationLicense": False,
        "signature": signature,
        "serverRandomness": SERVER_RANDOMNESS,
        "seatPoolType": "standalone",
        "statusCode": "SUCCESS",
        "offline": offline,
        "validFrom": valid_from,
        "validUntil": valid_until,
        "company": username,
        "orderId": "",
        "zeroIds": [],
        "licenseValidFrom": 1490544001000,
        "licenseValidUntil": 1691839999000,
    }
    
    return jsonify(response)


@app.route('/jrebel/leases/1', methods=['GET', 'POST', 'DELETE'])
@app.route('/agent/leases/1', methods=['GET', 'POST', 'DELETE'])
def jrebel_leases_1():
    """JRebel lease 释放"""
    params = {**request.args, **request.form}
    username = params.get('username', 'Administrator')
    
    response = {
        "serverVersion": "3.2.4",
        "serverProtocolVersion": "1.1",
        "serverGuid": "a1b4aea8-b031-4302-b602-670a990272cb",
        "groupType": "managed",
        "statusCode": "SUCCESS",
        "msg": None,
        "statusMessage": None,
        "company": username,
    }
    
    return jsonify(response)


@app.route('/jrebel/validate-connection', methods=['GET', 'POST'])
def jrebel_validate():
    """JRebel 验证连接"""
    response = {
        "serverVersion": "3.2.4",
        "serverProtocolVersion": "1.1",
        "serverGuid": "a1b4aea8-b031-4302-b602-670a990272cb",
        "groupType": "managed",
        "statusCode": "SUCCESS",
        "company": "Administrator",
        "canGetLease": True,
        "licenseType": 1,
        "evaluationLicense": False,
        "seatPoolType": "standalone",
    }
    
    return jsonify(response)


# ==================== JetBrains License Server 路由 ====================

@app.route('/rpc/ping.action', methods=['GET', 'POST'])
def jetbrains_ping():
    """JetBrains ping"""
    params = {**request.args, **request.form}
    salt = params.get('salt', '')
    
    if not salt:
        return '', 403
    
    xml_content = f"<PingResponse><message></message><responseCode>OK</responseCode><salt>{salt}</salt></PingResponse>"
    signature = jetbrains_signer.sign(xml_content)
    
    return f"<!-- {signature} -->\n{xml_content}", 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/rpc/obtainTicket.action', methods=['GET', 'POST'])
def jetbrains_obtain_ticket():
    """JetBrains 获取票据"""
    params = {**request.args, **request.form}
    salt = params.get('salt', '')
    username = params.get('userName', 'Administrator')
    
    if not salt or not username:
        return '', 403
    
    # 记录使用
    add_usage_record('jetbrains', 'obtainTicket', None, username)
    
    prolongation_period = "607875500"
    xml_content = (
        f"<ObtainTicketResponse><message></message>"
        f"<prolongationPeriod>{prolongation_period}</prolongationPeriod>"
        f"<responseCode>OK</responseCode><salt>{salt}</salt>"
        f"<ticketId>1</ticketId>"
        f"<ticketProperties>licensee={username}\tlicenseType=0\t</ticketProperties>"
        f"</ObtainTicketResponse>"
    )
    signature = jetbrains_signer.sign(xml_content)
    
    return f"<!-- {signature} -->\n{xml_content}", 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/rpc/releaseTicket.action', methods=['GET', 'POST'])
def jetbrains_release_ticket():
    """JetBrains 释放票据"""
    params = {**request.args, **request.form}
    salt = params.get('salt', '')
    
    if not salt:
        return '', 403
    
    xml_content = f"<ReleaseTicketResponse><message></message><responseCode>OK</responseCode><salt>{salt}</salt></ReleaseTicketResponse>"
    signature = jetbrains_signer.sign(xml_content)
    
    return f"<!-- {signature} -->\n{xml_content}", 200, {'Content-Type': 'text/html; charset=utf-8'}


# ==================== 后台管理 API ====================

@app.route('/admin')
def admin_page():
    """后台管理页面"""
    return render_template('admin.html')


@app.route('/api/admin/stats')
@admin_required
def admin_stats():
    """获取统计数据"""
    today = datetime.now().date()
    today_str = today.isoformat()
    
    total = len(usage_records)
    today_count = sum(1 for r in usage_records if r['timestamp'].startswith(today_str))
    jrebel_count = sum(1 for r in usage_records if r['product'] == 'jrebel')
    jetbrains_count = sum(1 for r in usage_records if r['product'] == 'jetbrains')
    
    return jsonify({
        'total': total,
        'today': today_count,
        'jrebel': jrebel_count,
        'jetbrains': jetbrains_count
    })


@app.route('/api/admin/records')
@admin_required
def admin_records():
    """获取使用记录"""
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    search = request.args.get('search', '').strip().lower()
    
    # 过滤记录
    if search:
        filtered = [
            r for r in usage_records 
            if search in (r.get('guid') or '').lower() 
            or search in (r.get('ip') or '').lower()
            or search in (r.get('username') or '').lower()
        ]
    else:
        filtered = usage_records
    
    # 分页
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    records = filtered[start:end]
    
    return jsonify({
        'total': total,
        'page': page,
        'page_size': page_size,
        'records': records
    })


# ==================== 通配路由 (处理 GUID 路径) ====================

@app.route('/<path:guid>', methods=['GET'])
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
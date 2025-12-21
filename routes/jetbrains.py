#!/usr/bin/env python3
"""
JetBrains License Server 路由
"""

from flask import Blueprint, request

from database import add_usage_record
from routes.utils import get_client_ip
from services import jetbrains_signer

jetbrains_bp = Blueprint('jetbrains', __name__)


@jetbrains_bp.route('/rpc/ping.action', methods=['GET', 'POST'])
def jetbrains_ping():
    """JetBrains ping"""
    params = {**request.args, **request.form}
    salt = params.get('salt', '')

    if not salt:
        return '', 403

    xml_content = f"<PingResponse><message></message><responseCode>OK</responseCode><salt>{salt}</salt></PingResponse>"
    signature = jetbrains_signer.sign(xml_content)

    return f"<!-- {signature} -->\n{xml_content}", 200, {'Content-Type': 'text/html; charset=utf-8'}


@jetbrains_bp.route('/rpc/obtainTicket.action', methods=['GET', 'POST'])
def jetbrains_obtain_ticket():
    """JetBrains 获取票据"""
    params = {**request.args, **request.form}
    salt = params.get('salt', '')
    username = params.get('userName', 'Administrator')

    if not salt or not username:
        return '', 403

    # 记录使用
    ip = get_client_ip()
    user_agent = request.headers.get('User-Agent', '')[:500]
    add_usage_record('jetbrains', 'obtainTicket', None, username, ip, user_agent)

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


@jetbrains_bp.route('/rpc/releaseTicket.action', methods=['GET', 'POST'])
def jetbrains_release_ticket():
    """JetBrains 释放票据"""
    params = {**request.args, **request.form}
    salt = params.get('salt', '')

    if not salt:
        return '', 403

    xml_content = f"<ReleaseTicketResponse><message></message><responseCode>OK</responseCode><salt>{salt}</salt></ReleaseTicketResponse>"
    signature = jetbrains_signer.sign(xml_content)

    return f"<!-- {signature} -->\n{xml_content}", 200, {'Content-Type': 'text/html; charset=utf-8'}


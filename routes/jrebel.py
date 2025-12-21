#!/usr/bin/env python3
"""
JRebel License Server 路由
"""

import time

from flask import Blueprint, request, jsonify

from database import add_usage_record
from routes.utils import get_client_ip
from services import jrebel_signer, SERVER_RANDOMNESS

jrebel_bp = Blueprint('jrebel', __name__)


@jrebel_bp.route('/jrebel/leases', methods=['GET', 'POST'])
@jrebel_bp.route('/agent/leases', methods=['GET', 'POST'])
def jrebel_leases():
    """JRebel lease 请求"""
    params = {**request.args, **request.form}
    if request.is_json:
        params.update(request.get_json() or {})

    client_randomness = params.get('randomness', '')
    username = params.get('username', '')
    guid = params.get('guid', '')
    offline = str(params.get('offline', 'false')).lower() == 'true'

    if not client_randomness or not username or not guid:
        return '', 403

    # 记录使用
    ip = get_client_ip()
    user_agent = request.headers.get('User-Agent', '')[:500]
    add_usage_record('jrebel', 'lease', guid, username, ip, user_agent)

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


@jrebel_bp.route('/jrebel/leases/1', methods=['GET', 'POST', 'DELETE'])
@jrebel_bp.route('/agent/leases/1', methods=['GET', 'POST', 'DELETE'])
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


@jrebel_bp.route('/jrebel/validate-connection', methods=['GET', 'POST'])
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


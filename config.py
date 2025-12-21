#!/usr/bin/env python3
"""
配置管理模块
负责从远程配置服务或环境变量获取配置
"""

import json
import logging
import os

from kengerkit import KengerClient

logger = logging.getLogger(__name__)

# 远程配置服务
CONFIG_SERVER_URL = os.environ.get('CONFIG_SERVER_URL', 'http://43.143.21.219:5000')
CONFIG_SERVER_TOKEN = os.environ.get('CONFIG_SERVER_TOKEN', 'u2InTXnmFF0Um6Sd')

# 初始化 KengerClient
kenger_client = None
try:
    kenger_client = KengerClient(
        base_url=CONFIG_SERVER_URL,
        token=CONFIG_SERVER_TOKEN
    )
    logger.info("KengerClient 初始化成功")
except Exception as e:
    logger.warning(f"KengerClient 初始化失败: {e}，将使用环境变量配置")


def get_config_value(key: str, default: str = None) -> str:
    """从远程配置服务获取配置值，失败时返回默认值"""
    if kenger_client:
        try:
            value = kenger_client.config.get(key)
            if value is not None:
                logger.info(f"从远程配置获取 {key} 成功")
                return value
        except Exception as e:
            logger.warning(f"从远程配置获取 {key} 失败: {e}")
    return default


def get_mysql_config() -> dict:
    """从远程配置或环境变量获取 MySQL 配置"""
    # 优先从远程配置获取
    if kenger_client:
        try:
            mysql_config_str = kenger_client.config.get('mysql.config')
            if mysql_config_str:
                # 如果是字符串，尝试解析 JSON
                if isinstance(mysql_config_str, str):
                    mysql_config = json.loads(mysql_config_str)
                else:
                    mysql_config = mysql_config_str
                logger.info("从远程配置获取 MySQL 配置成功")
                return mysql_config
        except Exception as e:
            logger.warning(f"从远程配置获取 MySQL 配置失败: {e}")

    # 从环境变量获取
    env_config = {
        'host': os.environ.get('MYSQL_HOST'),
        'port': os.environ.get('MYSQL_PORT'),
        'db': os.environ.get('MYSQL_DB'),
        'user': os.environ.get('MYSQL_USER'),
        'password': os.environ.get('MYSQL_PASSWORD')
    }

    # 检查环境变量是否完整
    if all(env_config.values()):
        env_config['port'] = int(env_config['port'])
        logger.info("从环境变量获取 MySQL 配置成功")
        return env_config

    # 配置不完整，返回 None
    logger.warning("MySQL 配置不完整，请配置远程配置服务或设置环境变量: MYSQL_HOST, MYSQL_PORT, MYSQL_DB, MYSQL_USER, MYSQL_PASSWORD")
    return None


# 配置常量
SECRET_KEY = os.environ.get('SECRET_KEY', 'jrebel-license-server-secret')
ADMIN_TOKEN = get_config_value('api_tokens', CONFIG_SERVER_TOKEN)
MYSQL_CONFIG = get_mysql_config()


#!/usr/bin/env python3
"""
数据层模块
负责数据库连接和数据操作
"""

import logging
from contextlib import contextmanager
from datetime import datetime

import pymysql

from config import MYSQL_CONFIG

logger = logging.getLogger(__name__)

# 内存存储作为备用 (当数据库不可用时使用)
_usage_records_memory = []
_MAX_RECORDS_MEMORY = 10000


@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器"""
    if not MYSQL_CONFIG:
        yield None
        return

    conn = None
    try:
        conn = pymysql.connect(
            host=MYSQL_CONFIG['host'],
            port=int(MYSQL_CONFIG['port']),
            user=MYSQL_CONFIG['user'],
            password=MYSQL_CONFIG['password'],
            database=MYSQL_CONFIG['db'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )
        yield conn
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        yield None
    finally:
        if conn:
            conn.close()


def init_database() -> bool:
    """初始化数据库表"""
    if not MYSQL_CONFIG:
        logger.warning("MySQL 配置未设置，跳过数据库初始化")
        return False

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS `jrebel_usage_records` (
        `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
        `timestamp` DATETIME NOT NULL COMMENT '记录时间',
        `product` VARCHAR(50) NOT NULL COMMENT '产品类型: jrebel/jetbrains',
        `action` VARCHAR(50) NOT NULL COMMENT '操作类型: lease/obtainTicket等',
        `guid` VARCHAR(100) DEFAULT NULL COMMENT '客户端GUID',
        `username` VARCHAR(200) DEFAULT NULL COMMENT '用户名',
        `ip` VARCHAR(50) DEFAULT NULL COMMENT '客户端IP',
        `user_agent` VARCHAR(500) DEFAULT NULL COMMENT '用户代理',
        `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
        PRIMARY KEY (`id`),
        INDEX `idx_timestamp` (`timestamp`),
        INDEX `idx_product` (`product`),
        INDEX `idx_guid` (`guid`),
        INDEX `idx_ip` (`ip`),
        INDEX `idx_created_at` (`created_at`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='JRebel License Server 使用记录表';
    """

    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(create_table_sql)
                logger.info("数据库表初始化成功")
                return True
            except Exception as e:
                logger.error(f"数据库表初始化失败: {e}")
                return False
    return False


# 初始化数据库
DB_INITIALIZED = init_database()
if not DB_INITIALIZED:
    logger.warning("数据库初始化失败，将使用内存存储作为备用")


def add_usage_record(product: str, action: str, guid: str = None,
                     username: str = None, ip: str = None, user_agent: str = None):
    """添加使用记录到数据库"""
    global _usage_records_memory

    now = datetime.now()

    # 尝试写入数据库
    if DB_INITIALIZED:
        with get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cursor:
                        sql = """
                        INSERT INTO jrebel_usage_records
                        (timestamp, product, action, guid, username, ip, user_agent)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(sql, (now, product, action, guid, username, ip, user_agent))
                    logger.info(f"Usage saved to DB: {product} - {action} - {guid} - {username} - {ip}")
                    return
                except Exception as e:
                    logger.error(f"写入数据库失败: {e}")

    # 数据库不可用时，使用内存存储作为备用
    record = {
        'timestamp': now.isoformat(),
        'product': product,
        'action': action,
        'guid': guid,
        'username': username,
        'ip': ip,
        'user_agent': user_agent
    }

    _usage_records_memory.insert(0, record)

    # 限制内存记录数量
    if len(_usage_records_memory) > _MAX_RECORDS_MEMORY:
        _usage_records_memory = _usage_records_memory[:_MAX_RECORDS_MEMORY]

    logger.info(f"Usage saved to memory: {product} - {action} - {guid} - {username} - {ip}")


def get_usage_records(page: int = 1, page_size: int = 20, search: str = None) -> dict:
    """从数据库获取使用记录"""
    if DB_INITIALIZED:
        with get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cursor:
                        # 构建查询条件
                        where_clause = ""
                        params = []

                        if search:
                            where_clause = "WHERE guid LIKE %s OR ip LIKE %s OR username LIKE %s"
                            search_pattern = f"%{search}%"
                            params = [search_pattern, search_pattern, search_pattern]

                        # 获取总数
                        count_sql = f"SELECT COUNT(*) as total FROM jrebel_usage_records {where_clause}"
                        cursor.execute(count_sql, params)
                        total = cursor.fetchone()['total']

                        # 获取分页数据
                        offset = (page - 1) * page_size
                        data_sql = f"""
                        SELECT id, timestamp, product, action, guid, username, ip, user_agent, created_at
                        FROM jrebel_usage_records
                        {where_clause}
                        ORDER BY timestamp DESC
                        LIMIT %s OFFSET %s
                        """
                        cursor.execute(data_sql, params + [page_size, offset])
                        records = cursor.fetchall()

                        # 转换 datetime 为字符串
                        for record in records:
                            if record.get('timestamp'):
                                record['timestamp'] = record['timestamp'].isoformat()
                            if record.get('created_at'):
                                record['created_at'] = record['created_at'].isoformat()

                        return {
                            'total': total,
                            'page': page,
                            'page_size': page_size,
                            'records': records
                        }
                except Exception as e:
                    logger.error(f"查询数据库失败: {e}")

    # 数据库不可用时，使用内存数据
    if search:
        search_lower = search.lower()
        filtered = [
            r for r in _usage_records_memory
            if search_lower in (r.get('guid') or '').lower()
            or search_lower in (r.get('ip') or '').lower()
            or search_lower in (r.get('username') or '').lower()
        ]
    else:
        filtered = _usage_records_memory

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    records = filtered[start:end]

    return {
        'total': total,
        'page': page,
        'page_size': page_size,
        'records': records
    }


def get_usage_stats() -> dict:
    """获取使用统计数据"""
    today = datetime.now().date()
    today_str = today.isoformat()

    if DB_INITIALIZED:
        with get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cursor:
                        # 总数
                        cursor.execute("SELECT COUNT(*) as total FROM jrebel_usage_records")
                        total = cursor.fetchone()['total']

                        # 今日数量
                        cursor.execute(
                            "SELECT COUNT(*) as today FROM jrebel_usage_records WHERE DATE(timestamp) = %s",
                            (today_str,)
                        )
                        today_count = cursor.fetchone()['today']

                        # JRebel 数量
                        cursor.execute(
                            "SELECT COUNT(*) as jrebel FROM jrebel_usage_records WHERE product = 'jrebel'"
                        )
                        jrebel_count = cursor.fetchone()['jrebel']

                        # JetBrains 数量
                        cursor.execute(
                            "SELECT COUNT(*) as jetbrains FROM jrebel_usage_records WHERE product = 'jetbrains'"
                        )
                        jetbrains_count = cursor.fetchone()['jetbrains']

                        return {
                            'total': total,
                            'today': today_count,
                            'jrebel': jrebel_count,
                            'jetbrains': jetbrains_count
                        }
                except Exception as e:
                    logger.error(f"获取统计数据失败: {e}")

    # 数据库不可用时，使用内存数据
    total = len(_usage_records_memory)
    today_count = sum(1 for r in _usage_records_memory if r['timestamp'].startswith(today_str))
    jrebel_count = sum(1 for r in _usage_records_memory if r['product'] == 'jrebel')
    jetbrains_count = sum(1 for r in _usage_records_memory if r['product'] == 'jetbrains')

    return {
        'total': total,
        'today': today_count,
        'jrebel': jrebel_count,
        'jetbrains': jetbrains_count
    }


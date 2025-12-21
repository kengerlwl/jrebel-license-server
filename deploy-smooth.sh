#!/bin/bash

# JRebel License Server 平滑发布脚本 V2
# 基于 OpenResty 动态 upstream（多租户版本）实现零停机部署
#
# 发布流程：
# 1. 启动新版本容器（使用不同端口）
# 2. 等待新容器健康检查通过
# 3. 将新容器注册到 OpenResty（指定 namespace）
# 4. 逐步降低旧容器权重（流量切换）
# 5. 从 OpenResty 注销旧容器
# 6. 停止并删除旧容器

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================
# 配置区域（根据实际情况修改）
# ============================================
PROJECT_NAME="jrebel-license-server"
NAMESPACE="jrebel"                    # OpenResty namespace
OPENRESTY_ADMIN="http://127.0.0.1:8081"
HEALTH_CHECK_PATH="/api/status"
HEALTH_CHECK_TIMEOUT=60               # 健康检查超时（秒）
WEIGHT_STEP=20                        # 每次权重调整步长
WEIGHT_INTERVAL=5                     # 权重调整间隔（秒）

# 端口配置（交替使用）
PORT_A=58081
PORT_B=58082

# 容器内部端口
CONTAINER_PORT=58080

# ============================================
# 以下为脚本逻辑，一般不需要修改
# ============================================

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%H:%M:%S') $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%H:%M:%S') $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%H:%M:%S') $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $(date '+%H:%M:%S') $1"
}

# 获取当前运行的容器信息
get_current_container() {
    local container_a="${PROJECT_NAME}-a"
    local container_b="${PROJECT_NAME}-b"

    if docker ps --format '{{.Names}}' | grep -q "^${container_a}$"; then
        echo "a"
    elif docker ps --format '{{.Names}}' | grep -q "^${container_b}$"; then
        echo "b"
    else
        echo "none"
    fi
}

# 获取下一个容器配置
get_next_config() {
    local current=$1
    if [ "$current" = "a" ]; then
        echo "b ${PORT_B}"
    else
        echo "a ${PORT_A}"
    fi
}

# 健康检查
wait_for_healthy() {
    local host=$1
    local port=$2
    local timeout=$3
    local start_time=$(date +%s)

    log_info "等待服务健康检查通过: ${host}:${port}${HEALTH_CHECK_PATH}"

    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [ $elapsed -ge $timeout ]; then
            log_error "健康检查超时（${timeout}秒）"
            return 1
        fi

        if curl -sf "http://${host}:${port}${HEALTH_CHECK_PATH}" > /dev/null 2>&1; then
            echo ""
            log_info "健康检查通过！耗时 ${elapsed} 秒"
            return 0
        fi

        echo -n "."
        sleep 2
    done
}

# 注册服务到 OpenResty（V2 带 namespace）
register_service() {
    local host=$1
    local port=$2
    local weight=${3:-100}

    log_info "注册服务到 OpenResty: ns=${NAMESPACE} ${host}:${port} (weight=${weight})"

    local url="${OPENRESTY_ADMIN}/register?ns=${NAMESPACE}&host=${host}&port=${port}&weight=${weight}&health_path=${HEALTH_CHECK_PATH}"
    local response=$(curl -sf "$url" 2>&1)
    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        log_info "注册成功: $response"
        return 0
    else
        log_error "注册失败: $response"
        return 1
    fi
}

# 从 OpenResty 注销服务（V2 带 namespace）
deregister_service() {
    local host=$1
    local port=$2

    log_info "从 OpenResty 注销服务: ns=${NAMESPACE} ${host}:${port}"

    local url="${OPENRESTY_ADMIN}/deregister?ns=${NAMESPACE}&host=${host}&port=${port}"
    local response=$(curl -sf "$url" 2>&1)

    if [ $? -eq 0 ]; then
        log_info "注销成功: $response"
        return 0
    else
        log_warn "注销失败（可能节点不存在）: $response"
        return 0  # 不影响流程
    fi
}

# 调整服务权重（V2 带 namespace）
set_weight() {
    local host=$1
    local port=$2
    local weight=$3

    local url="${OPENRESTY_ADMIN}/weight?ns=${NAMESPACE}&host=${host}&port=${port}&weight=${weight}"
    curl -sf "$url" > /dev/null 2>&1
}

# 逐步切换流量
gradual_traffic_shift() {
    local old_host=$1
    local old_port=$2
    local new_host=$3
    local new_port=$4

    log_step "开始逐步切换流量..."

    local old_weight=100
    local new_weight=0

    while [ $old_weight -gt 0 ]; do
        old_weight=$((old_weight - WEIGHT_STEP))
        new_weight=$((new_weight + WEIGHT_STEP))

        if [ $old_weight -lt 0 ]; then
            old_weight=0
            new_weight=100
        fi

        set_weight "$old_host" "$old_port" "$old_weight"
        set_weight "$new_host" "$new_port" "$new_weight"

        log_info "流量分配: 旧节点=${old_weight}% 新节点=${new_weight}%"

        if [ $old_weight -gt 0 ]; then
            sleep $WEIGHT_INTERVAL
        fi
    done

    log_info "流量切换完成！"
}

# 构建新镜像
build_image() {
    log_step "构建新镜像: ${PROJECT_NAME}:latest"
    docker build -t ${PROJECT_NAME}:latest . --no-cache
    log_info "镜像构建完成"
}

# 启动新容器
start_new_container() {
    local suffix=$1
    local port=$2
    local container_name="${PROJECT_NAME}-${suffix}"

    log_step "启动新容器: ${container_name} (端口: ${port})"

    # 删除可能存在的同名容器
    docker rm -f ${container_name} 2>/dev/null || true

    docker run -d \
        --name ${container_name} \
        --restart unless-stopped \
        -p ${port}:${CONTAINER_PORT} \
        -e PORT=${CONTAINER_PORT} \
        -e SECRET_KEY="${SECRET_KEY:-your-secret-key}" \
        -e DEBUG=false \
        ${PROJECT_NAME}:latest

    log_info "容器 ${container_name} 启动完成"
}

# 停止旧容器
stop_old_container() {
    local suffix=$1
    local container_name="${PROJECT_NAME}-${suffix}"

    log_step "停止旧容器: ${container_name}"

    if docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        docker stop ${container_name}
        docker rm ${container_name}
        log_info "旧容器 ${container_name} 已停止并删除"
    else
        log_info "旧容器 ${container_name} 不存在，跳过"
    fi
}

# 查看当前节点状态
show_nodes() {
    echo ""
    log_info "当前 OpenResty 节点状态 (namespace: ${NAMESPACE}):"
    echo ""
    curl -sf "${OPENRESTY_ADMIN}/nodes?ns=${NAMESPACE}" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "无法获取节点状态"
}

# 查看所有 namespace
show_all_nodes() {
    echo ""
    log_info "所有 OpenResty 节点状态:"
    echo ""
    curl -sf "${OPENRESTY_ADMIN}/nodes" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "无法获取节点状态"
}

# 查看健康状态
show_health() {
    echo ""
    log_info "健康检查状态 (namespace: ${NAMESPACE}):"
    echo ""
    curl -sf "${OPENRESTY_ADMIN}/health?ns=${NAMESPACE}" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "无法获取健康状态"
}

# 主函数 - 执行部署
main() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     JRebel License Server 平滑发布脚本 V2                  ║${NC}"
    echo -e "${GREEN}║     Namespace: ${NAMESPACE}                                         ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # 检查 Docker 是否可用
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装或不可用"
        exit 1
    fi

    # 检查 OpenResty 管理接口是否可用
    log_info "检查 OpenResty 管理接口..."
    if ! curl -sf "${OPENRESTY_ADMIN}/nodes" > /dev/null 2>&1; then
        log_error "无法连接 OpenResty 管理接口: ${OPENRESTY_ADMIN}"
        log_error "请确保 OpenResty 已启动并配置正确"
        exit 1
    fi
    log_info "OpenResty 管理接口正常"

    # 获取当前运行状态
    local current=$(get_current_container)
    log_info "当前运行容器: ${current}"

    # 获取下一个配置
    local next_config=$(get_next_config "$current")
    local next_suffix=$(echo $next_config | cut -d' ' -f1)
    local next_port=$(echo $next_config | cut -d' ' -f2)

    log_info "新容器配置: suffix=${next_suffix}, port=${next_port}"
    echo ""

    # 1. 构建新镜像
    build_image
    echo ""

    # 2. 启动新容器
    start_new_container "$next_suffix" "$next_port"
    echo ""

    # 3. 等待健康检查
    if ! wait_for_healthy "127.0.0.1" "$next_port" "$HEALTH_CHECK_TIMEOUT"; then
        log_error "新容器健康检查失败，执行回滚..."
        docker rm -f "${PROJECT_NAME}-${next_suffix}" 2>/dev/null || true
        exit 1
    fi
    echo ""

    # 4. 注册新服务到 OpenResty（初始权重为 0）
    register_service "127.0.0.1" "$next_port" 0
    echo ""

    # 5. 逐步切换流量（如果有旧容器）
    if [ "$current" != "none" ]; then
        local old_port
        if [ "$current" = "a" ]; then
            old_port=$PORT_A
        else
            old_port=$PORT_B
        fi

        gradual_traffic_shift "127.0.0.1" "$old_port" "127.0.0.1" "$next_port"
        echo ""

        # 6. 注销旧服务
        deregister_service "127.0.0.1" "$old_port"
        echo ""

        # 7. 停止旧容器
        stop_old_container "$current"
    else
        # 首次部署，直接设置权重为 100
        log_info "首次部署，设置权重为 100"
        set_weight "127.0.0.1" "$next_port" 100
    fi

    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    平滑发布完成！                          ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"

    show_nodes

    echo ""
    log_info "服务地址: http://localhost (通过 OpenResty)"
    log_info "直接访问: http://localhost:${next_port}"
    echo ""
}

# 回滚到上一个版本
rollback() {
    echo ""
    log_step "执行回滚操作..."

    local current=$(get_current_container)

    if [ "$current" = "none" ]; then
        log_error "没有运行中的容器，无法回滚"
        exit 1
    fi

    local old_suffix
    local old_port
    local new_suffix
    local new_port

    if [ "$current" = "a" ]; then
        new_suffix="a"
        new_port=$PORT_A
        old_suffix="b"
        old_port=$PORT_B
    else
        new_suffix="b"
        new_port=$PORT_B
        old_suffix="a"
        old_port=$PORT_A
    fi

    # 检查旧容器是否存在
    local old_container="${PROJECT_NAME}-${old_suffix}"
    if ! docker ps -a --format '{{.Names}}' | grep -q "^${old_container}$"; then
        log_error "旧容器 ${old_container} 不存在，无法回滚"
        exit 1
    fi

    # 启动旧容器（如果已停止）
    if ! docker ps --format '{{.Names}}' | grep -q "^${old_container}$"; then
        log_info "启动旧容器 ${old_container}..."
        docker start ${old_container}

        # 等待健康检查
        if ! wait_for_healthy "127.0.0.1" "$old_port" "$HEALTH_CHECK_TIMEOUT"; then
            log_error "旧容器健康检查失败"
            exit 1
        fi
    fi

    # 注册旧节点
    register_service "127.0.0.1" "$old_port" 0

    # 切换流量
    gradual_traffic_shift "127.0.0.1" "$new_port" "127.0.0.1" "$old_port"

    # 注销新节点
    deregister_service "127.0.0.1" "$new_port"

    # 停止新容器
    stop_old_container "$new_suffix"

    log_info "回滚完成！"
    show_nodes
}

# 快速注册当前容器（用于首次配置）
quick_register() {
    local port=${1:-58080}

    log_info "快速注册服务: 127.0.0.1:${port}"
    register_service "127.0.0.1" "$port" 100
    show_nodes
}

# 帮助信息
show_help() {
    echo ""
    echo "用法: $0 [命令] [参数]"
    echo ""
    echo "命令:"
    echo "  deploy          执行平滑发布（默认）"
    echo "  rollback        回滚到上一个版本"
    echo "  status          查看当前 namespace 节点状态"
    echo "  status-all      查看所有 namespace 节点状态"
    echo "  health          查看健康检查状态"
    echo "  register [port] 快速注册节点（默认端口 58080）"
    echo "  help            显示帮助信息"
    echo ""
    echo "配置:"
    echo "  PROJECT_NAME    = ${PROJECT_NAME}"
    echo "  NAMESPACE       = ${NAMESPACE}"
    echo "  PORT_A          = ${PORT_A}"
    echo "  PORT_B          = ${PORT_B}"
    echo "  OPENRESTY_ADMIN = ${OPENRESTY_ADMIN}"
    echo ""
    echo "环境变量:"
    echo "  SECRET_KEY      Flask 密钥"
    echo ""
    echo "示例:"
    echo "  $0 deploy              # 执行平滑发布"
    echo "  $0 status              # 查看节点状态"
    echo "  $0 register 58080      # 注册现有服务"
    echo "  $0 rollback            # 回滚到上一版本"
    echo ""
}

# 命令处理
case "${1:-deploy}" in
    deploy)
        main
        ;;
    rollback)
        rollback
        ;;
    status)
        show_nodes
        ;;
    status-all)
        show_all_nodes
        ;;
    health)
        show_health
        ;;
    register)
        quick_register "${2:-58080}"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "未知命令: $1"
        show_help
        exit 1
        ;;
esac


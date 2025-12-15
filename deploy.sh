#!/bin/bash

# JRebel License Server 一键部署脚本
# 功能：清除旧容器和镜像，重新构建并部署

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目名称
PROJECT_NAME="jrebel-license-server"
CONTAINER_NAME="jrebel-license-server"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  JRebel License Server 一键部署脚本  ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 1. 停止并删除旧容器
echo -e "${YELLOW}[1/4] 停止并删除旧容器...${NC}"
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker stop ${CONTAINER_NAME} 2>/dev/null || true
    docker rm ${CONTAINER_NAME} 2>/dev/null || true
    echo -e "${GREEN}  ✓ 旧容器已删除${NC}"
else
    echo -e "${GREEN}  ✓ 没有发现旧容器${NC}"
fi

# 2. 删除旧镜像
echo -e "${YELLOW}[2/4] 删除旧镜像...${NC}"
OLD_IMAGE=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep "${PROJECT_NAME}" | head -1)
if [ -n "$OLD_IMAGE" ]; then
    docker rmi ${OLD_IMAGE} 2>/dev/null || true
    echo -e "${GREEN}  ✓ 旧镜像已删除${NC}"
else
    echo -e "${GREEN}  ✓ 没有发现旧镜像${NC}"
fi

# 清理悬空镜像
docker image prune -f 2>/dev/null || true

# 3. 构建新镜像
echo -e "${YELLOW}[3/4] 构建新镜像...${NC}"
docker-compose build --no-cache
echo -e "${GREEN}  ✓ 新镜像构建完成${NC}"

# 4. 启动容器
echo -e "${YELLOW}[4/4] 启动容器...${NC}"
docker-compose up -d
echo -e "${GREEN}  ✓ 容器启动完成${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 显示容器状态
echo -e "${YELLOW}容器状态：${NC}"
docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo -e "${GREEN}服务地址: http://localhost:58080${NC}"
echo -e "${GREEN}状态检查: http://localhost:58080/api/status${NC}"
echo ""

# 显示日志（最后10行）
echo -e "${YELLOW}最近日志：${NC}"
sleep 2
docker logs --tail 10 ${CONTAINER_NAME} 2>/dev/null || echo "等待容器启动..."
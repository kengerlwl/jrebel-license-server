-- upstream_manager_v2.lua
-- 多租户动态 upstream 管理模块
-- 支持多个 namespace，每个网站可以有独立的后端节点池

local _M = {}

local cjson = require "cjson"

-- 共享内存
local upstream_nodes = ngx.shared.upstream_nodes
local healthcheck = ngx.shared.healthcheck

-- 常量
local DEFAULT_NS = "default"
local HEALTH_CHECK_PATH = "/api/status"
local HEALTH_CHECK_TIMEOUT = 2000  -- 2秒

-- 获取 namespace 的 key
local function get_ns_key(ns)
    return "ns:" .. (ns or DEFAULT_NS)
end

-- 初始化
function _M.init()
    ngx.log(ngx.INFO, "upstream_manager_v2 initialized (multi-tenant mode)")
end

-- 获取指定 namespace 的所有节点
function _M.get_all_nodes(ns)
    local ns_key = get_ns_key(ns)
    local nodes_json = upstream_nodes:get(ns_key)
    if not nodes_json then
        return {}
    end

    local ok, nodes = pcall(cjson.decode, nodes_json)
    if not ok then
        ngx.log(ngx.ERR, "failed to decode nodes for ", ns_key, ": ", nodes)
        return {}
    end

    -- 添加健康状态
    for _, node in ipairs(nodes) do
        local key = ns_key .. ":" .. node.host .. ":" .. node.port
        local health = healthcheck:get(key)
        node.healthy = (health ~= "unhealthy")
    end

    return nodes
end

-- 获取所有 namespace 及其节点
function _M.get_all_namespaces()
    local keys = upstream_nodes:get_keys(100)  -- 最多获取 100 个
    local result = {}

    for _, key in ipairs(keys) do
        if key:sub(1, 3) == "ns:" then
            local ns = key:sub(4)
            result[ns] = _M.get_all_nodes(ns)
        end
    end

    return result
end

-- 保存节点列表
local function save_nodes(ns, nodes)
    local ns_key = get_ns_key(ns)
    local ok, json = pcall(cjson.encode, nodes)
    if not ok then
        return false, "failed to encode nodes"
    end

    local ok, err = upstream_nodes:set(ns_key, json)
    if not ok then
        return false, err
    end

    return true
end

-- 注册节点
function _M.register(ns, host, port, weight, health_path)
    local nodes = _M.get_all_nodes(ns)

    -- 检查是否已存在
    for i, node in ipairs(nodes) do
        if node.host == host and node.port == port then
            -- 更新
            nodes[i].weight = weight
            nodes[i].health_path = health_path or HEALTH_CHECK_PATH
            nodes[i].updated_at = ngx.time()
            return save_nodes(ns, nodes)
        end
    end

    -- 添加新节点
    table.insert(nodes, {
        host = host,
        port = port,
        weight = weight,
        health_path = health_path or HEALTH_CHECK_PATH,
        created_at = ngx.time(),
        updated_at = ngx.time()
    })

    ngx.log(ngx.INFO, "registered node: ns=", ns or DEFAULT_NS, " ", host, ":", port, " weight=", weight)
    return save_nodes(ns, nodes)
end

-- 注销节点
function _M.deregister(ns, host, port)
    local nodes = _M.get_all_nodes(ns)
    local new_nodes = {}
    local found = false

    for _, node in ipairs(nodes) do
        if node.host == host and node.port == port then
            found = true
            ngx.log(ngx.INFO, "deregistered node: ns=", ns or DEFAULT_NS, " ", host, ":", port)
        else
            table.insert(new_nodes, node)
        end
    end

    if not found then
        return false, "node not found"
    end

    return save_nodes(ns, new_nodes)
end

-- 设置权重
function _M.set_weight(ns, host, port, weight)
    local nodes = _M.get_all_nodes(ns)

    for i, node in ipairs(nodes) do
        if node.host == host and node.port == port then
            nodes[i].weight = weight
            nodes[i].updated_at = ngx.time()
            ngx.log(ngx.INFO, "updated weight: ns=", ns or DEFAULT_NS, " ", host, ":", port, " -> ", weight)
            return save_nodes(ns, nodes)
        end
    end

    return false, "node not found"
end

-- 加权随机选择算法
local function weighted_random_select(ns, nodes)
    local ns_key = get_ns_key(ns)
    local total_weight = 0
    local available_nodes = {}

    -- 只选择健康且权重大于0的节点
    for _, node in ipairs(nodes) do
        local key = ns_key .. ":" .. node.host .. ":" .. node.port
        local health = healthcheck:get(key)

        if health ~= "unhealthy" and node.weight > 0 then
            total_weight = total_weight + node.weight
            table.insert(available_nodes, node)
        end
    end

    if #available_nodes == 0 then
        return nil
    end

    if #available_nodes == 1 then
        return available_nodes[1]
    end

    -- 加权随机选择
    local rand = math.random(1, total_weight)
    local cumulative = 0

    for _, node in ipairs(available_nodes) do
        cumulative = cumulative + node.weight
        if rand <= cumulative then
            return node
        end
    end

    return available_nodes[1]
end

-- 获取后端地址（指定 namespace）
function _M.get_backend(ns)
    local nodes = _M.get_all_nodes(ns)

    if #nodes == 0 then
        ngx.log(ngx.WARN, "no nodes available for ns=", ns or DEFAULT_NS)
        return nil
    end

    local node = weighted_random_select(ns, nodes)
    if not node then
        ngx.log(ngx.WARN, "no healthy nodes available for ns=", ns or DEFAULT_NS)
        return nil
    end

    return node.host .. ":" .. node.port
end

-- 健康检查（检查所有 namespace 的节点）
function _M.health_check()
    local all_ns = _M.get_all_namespaces()

    for ns, nodes in pairs(all_ns) do
        local ns_key = get_ns_key(ns)

        for _, node in ipairs(nodes) do
            local key = ns_key .. ":" .. node.host .. ":" .. node.port
            local health_path = node.health_path or HEALTH_CHECK_PATH

            local sock = ngx.socket.tcp()
            sock:settimeout(HEALTH_CHECK_TIMEOUT)

            local ok, err = sock:connect(node.host, node.port)
            if ok then
                local req = "GET " .. health_path .. " HTTP/1.0\r\nHost: " .. node.host .. ":" .. node.port .. "\r\n\r\n"
                sock:send(req)

                local line, err = sock:receive("*l")
                if line and line:match("200") then
                    healthcheck:set(key, "healthy", 30)
                    ngx.log(ngx.DEBUG, "health check passed: ", key)
                else
                    healthcheck:set(key, "unhealthy", 30)
                    ngx.log(ngx.WARN, "health check failed: ", key, " - ", err or "non-200")
                end

                sock:close()
            else
                healthcheck:set(key, "unhealthy", 30)
                ngx.log(ngx.WARN, "health check failed: ", key, " - ", err)
            end
        end
    end
end

-- 获取健康状态
function _M.get_health_status(ns)
    local nodes
    if ns then
        nodes = _M.get_all_nodes(ns)
    else
        -- 返回所有 namespace 的状态
        return _M.get_all_namespaces()
    end

    local ns_key = get_ns_key(ns)
    local result = {
        namespace = ns or DEFAULT_NS,
        total = #nodes,
        healthy = 0,
        unhealthy = 0,
        nodes = {}
    }

    for _, node in ipairs(nodes) do
        local key = ns_key .. ":" .. node.host .. ":" .. node.port
        local health = healthcheck:get(key)
        local is_healthy = (health ~= "unhealthy")

        if is_healthy then
            result.healthy = result.healthy + 1
        else
            result.unhealthy = result.unhealthy + 1
        end

        table.insert(result.nodes, {
            address = node.host .. ":" .. node.port,
            weight = node.weight,
            healthy = is_healthy,
            health_path = node.health_path
        })
    end

    return result
end

return _M


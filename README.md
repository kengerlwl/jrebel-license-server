# JRebel & JetBrains License Server

🚀 一个支持 JRebel 和 JetBrains IDE 的本地 License Server，提供 Web 界面生成激活 URL。

## ✨ 功能特性

- 🔥 **JRebel 激活** - 支持 JRebel 7.1+ 和 2018.1+ 版本
- 💡 **JetBrains IDE 激活** - 支持旧版本 IDE（新版本需配合 ja-netfilter）
- 🌐 **Web 界面** - 美观的 Web 界面，一键生成激活 URL
- 🐳 **Docker 部署** - 支持 Docker 一键部署
- 🔒 **自托管** - 完全自托管，数据安全

## 📸 截图

Web 界面提供：
- 产品选择（JRebel / JetBrains）
- 自动生成 GUID
- 一键复制激活 URL
- 详细使用说明

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

```bash
# 克隆项目
git clone https://github.com/xiaoyu-ai/jrebel-license-server.git
cd jrebel-license-server

# 启动服务
docker-compose up -d

# 访问 Web 界面
open http://localhost:8080
```

### 方式二：Docker 单命令运行

```bash
docker run -d -p 8080:8080 --name jrebel-server \
  ghcr.io/xiaoyu-ai/jrebel-license-server:latest
```

### 方式三：本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python app.py

# 或使用 gunicorn
gunicorn --bind 0.0.0.0:8080 app:app
```

## 📖 使用方法

### JRebel 激活

1. 访问 Web 界面 `http://localhost:8080`
2. 选择 **JRebel** 产品
3. 点击 **生成激活 URL**
4. 复制生成的激活 URL
5. 在 JRebel 激活界面选择 **Team URL**
6. 粘贴激活 URL
7. 邮箱填写任意邮箱
8. 点击 **Activate**

### JetBrains IDE 激活

> ⚠️ 新版本 JetBrains IDE（2021.3+）需要配合 [ja-netfilter](https://gitee.com/ja-netfilter/ja-netfilter) 使用

1. 下载并配置 ja-netfilter
2. 访问 Web 界面生成激活 URL
3. 在 IDE 中使用 License Server 方式激活

## 🔧 配置

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PORT` | 服务端口 | `8080` |
| `SECRET_KEY` | Flask 密钥 | 随机生成 |
| `DEBUG` | 调试模式 | `false` |

### Docker Compose 配置

```yaml
version: '3.8'

services:
  license-server:
    build: .
    ports:
      - "8080:8080"
    environment:
      - PORT=8080
      - SECRET_KEY=your-secret-key
    restart: unless-stopped
```

## 🌐 API 接口

### 状态检查

```
GET /api/status
```

响应：
```json
{
  "status": "running",
  "version": "1.0.0",
  "jrebel_signer": true,
  "jetbrains_signer": true
}
```

### 生成激活 URL

```
POST /generate
Content-Type: application/json

{
  "product": "jrebel",
  "guid": "optional-custom-guid"
}
```

响应：
```json
{
  "success": true,
  "product": "jrebel",
  "guid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "activation_url": "http://localhost:8080/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "email": "任意邮箱"
}
```

### JRebel Lease 接口

```
POST /jrebel/leases
```

### JetBrains 接口

```
GET/POST /rpc/ping.action
GET/POST /rpc/obtainTicket.action
GET/POST /rpc/releaseTicket.action
```

## 🏗️ 项目结构

```
jrebel-license-server/
├── app.py                 # 主应用
├── requirements.txt       # Python 依赖
├── Dockerfile            # Docker 构建文件
├── docker-compose.yml    # Docker Compose 配置
├── templates/            # HTML 模板
│   ├── index.html       # 首页
│   └── activation.html  # 激活信息页
└── README.md            # 说明文档
```

## 🔐 安全说明

- 本项目仅供学习研究使用
- 请支持正版软件
- 建议在内网环境部署
- 不要将服务暴露到公网

## 📝 技术原理

### JRebel 激活机制

1. 客户端发送 `randomness`（客户端随机数）和 `guid`
2. 服务器返回 `serverRandomness` + `signature`
3. 签名数据格式：`clientRandomness;serverRandomness;guid;offline`
4. 签名算法：SHA1withRSA
5. 客户端使用内置公钥验证签名

### JetBrains 激活机制

1. 客户端发送 `salt` 参数
2. 服务器返回 XML 响应 + 签名注释
3. 签名算法：MD5withRSA

## 🙏 致谢

- [JrebelLicenseServerforJava](https://github.com/Ahaochan/JrebelLicenseServerforJava) - 原始 Java 实现
- [ja-netfilter](https://gitee.com/ja-netfilter/ja-netfilter) - JetBrains 激活工具

## 📄 License

MIT License

---

⭐ 如果这个项目对你有帮助，请给个 Star！
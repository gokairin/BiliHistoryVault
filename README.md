# BiliHistoryVault

B 站对非官方视频（无官方认证标识）的浏览记录仅保留最近 1000 条，超出部分会被自动删除。本项目定时将你的完整观看历史同步保存到 Excel，通过 GitHub Actions 自动运行，无需手动操作。

输出的 Excel 包含以下信息：观看时间（UTC）、视频标题、BV 号、UP 主、分区、视频时长。

## 工作原理

1. 通过 B 站 API `x/web-interface/history/cursor` 获取观看历史
2. 与已有的 Excel 对比，只追加新记录，累积保存
3. 每 4 小时自动同步一次，也可手动触发

## 前置准备

### 1. 获取 SESSDATA

SESSDATA 是 B 站的登录凭证，用于 API 鉴权。

**方法一：扫码登录（推荐）**

本地安装 Python 依赖后运行：

```bash
pip install -r requirements.txt
python scripts/refresh_sessdata.py
```

用 B 站 APP 扫码后，脚本会自动获取 SESSDATA 并尝试更新 GitHub Secret（需要安装 gh CLI），否则会在终端打印出 SESSDATA 值。

**方法二：手动从浏览器获取**

1. 打开浏览器，登录 [bilibili.com](https://www.bilibili.com)
2. 按 `F12` 打开开发者工具
3. 切换到 **Application（应用）** 标签页
4. 左侧找到 **Cookies → https://www.bilibili.com**
5. 找到名为 `SESSDATA` 的条目，复制其 Value

### 2. 配置 GitHub Secrets

在仓库 **Settings → Secrets and variables → Actions** 中添加：

| Secret | 必填 | 说明 |
|--------|------|------|
| `SESSDATA` | 是 | B 站登录凭证 |
| `MAIL_SERVER` | 否 | SMTP 服务器地址（如 `smtp.163.com`） |
| `MAIL_PORT` | 否 | SMTP 端口（如 `465`） |
| `MAIL_USERNAME` | 否 | 邮箱地址 |
| `MAIL_PASSWORD` | 否 | 邮箱授权码 |
| `MAIL_RECIPIENT` | 否 | 收件人邮箱 |

> 邮件配置为可选项。未配置时，同步失败不会发送邮件通知，不影响同步功能。

## 运行方式

### GitHub Actions（自动）

每 4 小时自动执行一次（cron: `0 */4 * * *`），也可在 Actions 页面手动触发。

### 本地运行

```bash
# 克隆仓库
git clone https://github.com/gokairin/BiliHistoryVault.git
cd BiliHistoryVault

# 安装依赖
pip install -r requirements.txt

# 设置 SESSDATA 环境变量
set SESSDATA=你的值

# 运行同步
python src/sync.py
```

本地模式下会自动执行：
1. 从 GitHub 拉取最新 Excel
2. 同步 B 站数据
3. 上传更新后的 Excel 到 GitHub
4. 拉取一次确保本地状态同步

> GitHub 连接失败时会直接报错退出。上传失败时数据会保留在本地 `output/BilibiliHistory.xlsx`。

## 同步间隔

修改 `.github/workflows/sync.yml` 中的 `cron` 即可调整同步频率：

```yaml
on:
  schedule:
    - cron: '0 */4 * * *'   # 每 4 小时
    # - cron: '0 */2 * * *'  # 每 2 小时
    # - cron: '0 6 * * *'    # 每天早上 6 点
```

> GitHub Actions cron 最小间隔为每小时一次。

## 数据说明

- **不自动去重**：同一视频在多个同步间隔内重复观看，会多次记录。去重逻辑仅依赖 B 站 API 返回的新旧时间戳对比，不校验视频 ID 是否已存在。
- **时间为 UTC**：Excel 中「观看时间」列存储为 UTC 时间，非本地时区。

## 项目结构

```
BiliHistoryVault/
├── .github/workflows/sync.yml    # GitHub Actions 工作流
├── src/sync.py                    # 主同步脚本
├── scripts/refresh_sessdata.py    # SESSDATA 刷新工具
├── output/BilibiliHistory.xlsx    # 同步生成的 Excel 文件
├── requirements.txt               # Python 依赖
└── README.md
```

## 同步失败通知

当 B 站 API 返回异常时（SESSDATA 失效、网络错误等）：

1. 同步脚本以非零状态退出
2. GitHub Actions 标记本次运行为失败
3. 如已配置邮件 Secrets，自动发送失败通知邮件到收件箱
4. 邮件中包含 SESSDATA 的获取与设置步骤

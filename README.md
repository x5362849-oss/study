# 📚 天体物理文献每日推送 — 部署指南

为高能天体物理探测器方向定制：中国空间站 **HERD-TRD**、**Polar-2** 量能器、**eXTP GPD**、**LACT SiPM 相机**。

每天早上 8:30 左右，自动从 arXiv 抓取 astro-ph.HE / astro-ph.IM 新论文，按课题关键词筛选出最相关的 ≤3 篇，用大模型生成中文导读（一句话总结 / 创新点 / 核心问题 / 对我们的启发 / 可信度提示），末尾附导师式提问 1-2 个，推送到你的微信。

---

## 一、需要注册的账号（全部免费，共 3 个）

| # | 平台 | 网址 | 用途 | 注册方式 |
|---|------|------|------|---------|
| 1 | **GitHub** | github.com | 存放本项目 + 提供免费定时运行（Actions） | 邮箱注册 |
| 2 | **Server酱** | sct.ftqq.com | 把结果推送到微信 | 微信扫码登录 GitHub 账号即可 |
| 3 | **智谱开放平台** | open.bigmodel.cn | 提供大模型 API（glm-4-flash 免费） | 手机号注册 |

> 💡 预算约 0 元：glm-4-flash 是免费模型；Server酱免费档每天可推 5 条；GitHub Actions 公开仓库免费。

## 二、获取 3 个密钥（约 10 分钟）

1. **Server酱 SendKey** → 登录 [sct.ftqq.com](https://sct.ftqq.com) 后，首页"SendKey"处复制（形如 `SCT12345...`）。页面同时提示你微信关注"方糖"服务号，**这一步就是绑定微信**，不关注收不到消息
2. **智谱 API Key** → 登录 [open.bigmodel.cn](https://open.bigmodel.cn) → 右上角头像 → "API 密钥" → 新建并复制
3. GitHub 的密钥**不用现在复制**，下一步配置时填

## 三、部署到 GitHub（约 15 分钟）

### 方法 A：网页操作（手机也能完成）

1. 登录 GitHub → 右上角 **+** → **Import repository**
   - 旧仓库 URL 填：本压缩包解压后上传到自己新建的空仓库，或直接网页上传文件
   - （更简单的方法：新建仓库 `astro-literature-scout`，在网页端把压缩包里的所有文件/文件夹逐一上传，注意保持目录结构）
2. 配置密钥：仓库页面 → **Settings** → **Secrets and variables** → **Actions**
   - **Secrets** 标签 → New repository secret，添加两条：
     - Name: `SENDKEY`，Value: 你的 Server酱 SendKey
     - Name: `LLM_API_KEY`，Value: 你的智谱 API Key
3. 手动测试：仓库 **Actions** 标签 → 左侧 `daily-literature` → **Run workflow** → Run
   - 运行成功后，微信应收到一条"📚 天体物理文献日报"
4. 完成。之后每天 8:30 左右自动推送

### 方法 B：命令行（电脑操作，略快）

```bash
# 在 GitHub 网页新建空仓库 astro-literature-scout 后:
unzip astro-literature-scout.zip && cd astro-literature-scout
git init && git add -A && git commit -m "init"
git remote add origin https://github.com/<你的用户名>/astro-literature-scout.git
git push -u origin main
# 密钥配置同方法 A 第 2 步 (或用 gh secret set SENDKEY)
```

## 四、本地测试（可选，电脑）

```bash
pip install requests pyyaml
python scripts/main.py --dry-run          # 只抓取筛选, 无需任何密钥
export SENDKEY=SCT12345... LLM_API_KEY=你的key
python scripts/main.py --no-push          # 生成导读存到 scripts/output/, 不推送
python scripts/main.py                    # 完整推送
```

## 五、日常调整（改 scripts/config.yaml）

- **关键词**：`topics` 下按项目分组，命中标题 3 分、摘要 1 分，想收得更宽就多加泛化词（如 `cosmic ray`、`gamma-ray astronomy`）
- **每天推几篇**：`top_n`
- **回看几天**：`days_back`（如果只在工作日运行，周末的论文会漏掉，建议保持 3）
- **换大模型**：改仓库 Variables `LLM_BASE_URL`（OpenAI 兼容地址）和 `LLM_MODEL`，任何 OpenAI 兼容服务都可用

## 六、目录结构

```
astro-literature-scout/
├── README.md                     ← 本文件
├── skill/SKILL.md                ← 导读规范 (AI 的"操作手册", 想改输出格式就编辑它)
├── scripts/
│   ├── main.py                   ← 主脚本: 抓取→筛选→AI标注→推送
│   ├── config.yaml               ← 课题关键词与参数
│   └── output/                   ← 本地运行时的结果 (git 可忽略)
└── .github/workflows/daily.yml   ← GitHub Actions 每日定时任务
```

## 七、常见问题

- **GitHub 定时不准时？** Actions 定时有 ±15 分钟到偶发 1 小时延迟，属正常；也可在手机浏览器打开仓库 Actions 页手动 Run
- **微信收不到消息？** 检查是否已用微信关注"方糖"服务号；Server酱免费版每天 5 条上限
- **60 天不活跃的仓库定时任务会被 GitHub 自动停用**，收到停用邮件后去 Actions 页重新 Enable 即可（也可偶尔手动跑一次保活）
- **想加 NASA ADS 数据源？** ADS 覆盖更全但需要额外注册 ADS 账号申请 API token，初版先用 arXiv 已够日常使用

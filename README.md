# 血糖客户汇总自动审查工具

## 当前目标：智能表格

`run_live.py` 已切换至 https://docs.qq.com/smartsheet/DVEFWWHprU0ZRa1Za ，工作表为“客户回访台账”（`1uYjAx`）。下文普通在线表格说明为迁移前记录。

2026-09-29 本地实际同步验证通过：服务器 12 位客户、监测期内 3 位，更新 1 位、无变化 2 位、新增 0 位，智能表共 12 行。服务器发布使用 `server_ledger_ops.py` 创建完整的新 release，并由 `/opt/tencent-doc-automation/current` 指向最新版本；定时任务仍为每天 08:00 和 17:00。

每次写入前读取实际字段类型：首次佩戴日期及四个回访字段均按北京时间零点的毫秒时间戳写入日期字段；其余受管字段按文本写入。2026-09-29 已确认用户将“取机器回访”从单选改为日期，显示格式为中文年月日，脚本自动适配并保留该显示格式。保留 15 列，按“客户姓名＋首次佩戴日期”匹配，更新已有客户并新增监测期内新客户，回读验证写入及历史内容保留。

智能表不会调用普通在线表格的字体、行高、行移动或条件格式接口。

经用户同意，已增加日期字段“最近同步变更时间”（`fQfOTP`）。只有客户新增或业务字段实际变化时，脚本才在同一批写入中记录北京时间对应的毫秒时间戳；无变化记录和重复运行不刷新时间，序号差异也不触发。此字段用于降序排列，使当天更新记录排在历史记录之前。写后校验保留毫秒精度。19 项测试已通过，本地实际同步已确认只给 1 条变化记录标记时间，2 条无变化记录未刷新。

**服务器进展（2026-10-02）：** 已获用户批准，将更新时间记录版本部署到服务器并实际执行成功：更新 2 位、无变化 2 位，今日取机回访 2 条。定时计划保持 08:00 和 17:00。已从服务器 6 对同步前后快照恢复 4 位客户真实的历史更新时间；旧代码备份在 `/opt/tencent-doc-automation/shared/target-switch-20261002104126`。

**显示设置已完成（2026-10-02 11:09）：** 已在可见、已登录的 Edge 中设置当前视图按“最近同步变更时间”降序自动排序，并隐藏辅助字段。四个回访字段均新增“等于今天”的红色背景规则，保留 15 条蓝色表头规则。官方 API 回读验证了排序、隐藏及四条动态日期规则；网页刷新确认序号 10、13、11、12 排在前四行，只有两条当天取机器回访单元格呈红色背景。这里是红色背景提醒，不是红色字体。

腾讯网页客户端把空日期排在有值日期之前（与接口返回顺序不同）。已用 `initialize_smart_sort.py --apply` 为 9 条缺少历史更新时间的记录设置隐藏排序占位值 `1`（Unix 毫秒，代表未知历史更新时间，**不代表实际发生过同步变更**）。原有真实时间、所有业务字段保持不变，操作前后备份并完整回读校验；再次运行不会重复写入。以后新增或实际变化记录由 `smart_sync.py` 写入真实时间，无需每次运行此修复。服务器同步使用 Token，不需要服务器浏览器或每天登录；视图规则已保存到腾讯文档，后续新增记录沿用。详见 [智能表显示规则设置](docs/智能表显示规则设置.md)。

## 历史普通表格说明（迁移前）

以下为迁移前普通在线表格的实施记录。当前正式入口仍为 `run_live.py`，但目标已切换为上文智能表格。默认 `main.py` 配置保留离线模式。

```powershell
$env:TENCENT_DOCS_TOKEN = [Environment]::GetEnvironmentVariable('TENCENT_DOCS_TOKEN', 'User')
.\.venv\Scripts\python.exe run_live.py
```

本机运行时程序使用现有 SSH 凭据连接生产服务器，在业务容器中执行只读 SQL，无需将数据库连接密码复制到本机。凭据文件位置由 `run_live.py` 中的 `credential_file` 配置。服务器运行时 `server_run.py` 从服务器既有的 `/opt/teyi/production.env` 和 `/root/.config/tencent-docs/env` 读取凭据，通过本机 `127.0.0.1:5432` 查询数据库，不在项目中保存密码或 Token。

普通表按“客户姓名＋首次佩戴日期”匹配，仅同步 14 天内的客户；缺失的新客户追加一行。姓名或首次佩戴日期被人工修改后匹配键会变化，可能新增为另一条记录，因此此两列应与服务器保持一致。当天有变化的行整行移到表头下方，人工字段和行格式随行保留。本地 `output/live/sync_state.json` 保存当天更新标记，不占用表格列。回访列 H:K 设置文本日期等于 `TEXT(TODAY(),"yyyy-mm-dd")` 时红字的条件格式。

`output/live/` 保存同步前后读取快照及条件格式 ID，包含客户数据，已由 `.gitignore` 排除。后续运行应保留此目录。2026-09-29 首次真实执行：服务器 12 位客户，3 位监测中，更新 2 行、新增 1 行、置顶 3 行，9 位到期客户保持原值；写后回读校验通过。

生产部署在 `/opt/tencent-doc-automation/current`，`output/` 和 `logs/` 使用 `/opt/tencent-doc-automation/shared` 持久目录。`tencent-ledger.timer` 按服务器北京时间每天 08:00 和 17:00 触发 `tencent-ledger.service`；服务用 `flock` 防止重叠运行。手动执行及检查可使用：

```bash
systemctl start tencent-ledger.service
systemctl show tencent-ledger.service -p Result -p ExecMainStatus
journalctl -u tencent-ledger.service -n 35 --no-pager
systemctl list-timers tencent-ledger.timer --all --no-pager
```

`server_ledger_ops.py` 在本机使用现有服务器凭据部署、运行和检查；`verify_live_write.py` 在服务器对目标智能表格的一条已有客户记录执行“客户姓名”原值写入并回读，用于验证写入权限而不改变台账业务数据。

回访列 H:K 的普通字体为黑色，只有“文本日期等于当天”的条件格式负责标红。同步时清理完全位于这四列中的其他旧条件格式，避免旧规则把整列日期染红；其他列的条件格式保持不变。

线上字体为微软雅黑 11 号、水平及垂直居中、自动换行。行高目标 42，列宽目标 140；每次正式同步后应用格式并回读全部 15 列及首末行，尺寸未生效会在结果 `formatting.dimension_mismatches` 中明确报告，不影响已成功完成的数据同步。2026-09-29 实测腾讯列宽写入接口及脚本接口均返回成功但回读仍为旧列宽，等宽列尚未完成。保留现有表头底色、字体颜色和回访条件格式。仅调整格式可运行 `.\.venv\Scripts\python.exe sheet_format.py`。

该项目每天从业务数据库只读取得血糖客户汇总数据，校验后与腾讯文档中的既有记录比较，更新变化字段、自动新增监测期内的新客户，并通过企业微信报告结果。首次佩戴日算第 1 天，第 15 天起不再更新该客户。

项目以 `服务器血糖客户汇总_2026-09-22.xlsx` 的现有结构为基准。源工作簿及已补回访日期的版本保存在本地项目输出目录，不随代码仓库发布，以免公开真实客户数据。

## 当前表格结构

工作表名称：`血糖客户汇总`

列顺序固定为：

1. 序号
2. 姓名
3. 性别
4. 电话
5. 是否是糖尿病
6. 是否服药
7. 首次佩戴日期
8. 1小时回访
9. 3天回访
10. 首次周回访
11. 取机器回访
12. 血糖均值
13. 血糖最高值
14. 血糖最低值
15. 14天血糖达标情况

当前源表中实际已有数据的列为：

- 序号
- 姓名
- 首次佩戴日期
- 血糖均值
- 血糖最高值
- 血糖最低值

这 6 列保留原有审查规则，另将电话和四个**计划回访日期**纳入自动同步。客户 ID 匹配建立后，姓名和首次佩戴日期也可在原行更新。电话只取数据库的客户或设备账号电话；数据库缺失时不清空腾讯文档已有电话。四个日期按首次佩戴日期分别加 0、3、9、13 天计算，不代表实际回访已完成。性别、病史、服药及达标情况仍不由此工具覆盖。

本地更新版和 `--dry-run` 预览对四个日期列设置了动态条件格式：日期等于系统当天时显示红字，其他日期保持原格式。脚本也按北京时间统计四类“今日应回访”数量。目标腾讯表格的列已确认均为文本，日期将以 `yyyy-mm-dd` 文本同步；在线红字尚需确认目标产品支持的格式接口或在界面配置规则，不能把本地 Excel 的红字视为已同步到线上。

“姓名”列中即使出现手机号样式或内部编号样式的文本，也按源表现状继续作为姓名/客户标识处理，不会擅自移动到“电话”列。

详细规则见 [docs/表格结构与同步规则.md](docs/表格结构与同步规则.md)。

## 每日执行流程

```text
只读查询业务数据库
→ 校验字段、日期、数值和组合键
→ 跳过首次佩戴已满 14 天的客户
→ 根据首次佩戴日期计算四个计划回访日期
→ 读取腾讯智能表现有记录
→ 优先按客户 UUID 匹配；旧行用“姓名 + 首次佩戴日期”迁移
→ 只比较服务器受管字段
→ 更新变化字段，新增监测期内缺失的客户
→ 给当天有业务字段变动的行写入“最近更新日期”
→ 统计无变化、未匹配和更新记录
→ 写日志并发送企业微信通知
```

默认每天 08:00 和 17:00 运行。

## 同步保护规则

默认同步策略为：

```json
"sync_strategy": "review_existing"
```

该策略具有以下保护：

- 只更新腾讯文档中已经存在、且组合键匹配的记录。
- “客户ID”采用数据库 `customers.id` UUID；旧行可按“姓名＋首次佩戴日期”匹配一次并回填 ID。
- 只更新 `managed_fields` 中的字段；其中电话为服务器值，四个回访日期由脚本计算。
- 服务器空值默认不会覆盖腾讯文档已有值。
- 内容相同的记录不调用更新接口。
- 监测期内服务器新增但腾讯文档不存在的客户默认自动新增。
- 腾讯文档存在但服务器不存在的记录只报告，不自动删除。
- 服务器或腾讯文档存在重复组合键时停止任务，防止更新错行。

服务器新增记录的处理由 `new_record_policy` 控制：

- `skip`：只报告，不新增。
- `add`：默认，自动新增。
- `error`：发现新记录即让任务失败。

## 为什么使用组合键

数据库中 `customers.id` 为稳定 UUID，当前目标表格尚需增加文本列“客户ID”。`序号` 只是展示顺序，不能作为稳定主键。现有无 ID 行迁移时才使用：

```text
姓名 + 首次佩戴日期
```

另需增加文本列“最近更新日期”，以 `yyyy-mm-dd` 记录当天有业务字段变化或新增的行。在腾讯表格中将此列按降序排序，即可让当天更新的行显示在上方；这是视图排序，不会删除或搬动历史记录。该在线规则尚未配置，需先确认目标表格产品类型。

## 数据校验

运行前会检查：

- 客户 UUID、姓名、首次佩戴日期和血糖汇总值是否存在且非空。
- 电话可暂缺；有值时作为文本写入，避免号码被当作数字处理。
- 序号和血糖值是否为非负数值。
- 首次佩戴日期是否为有效日期。
- 是否满足 `血糖最低值 ≤ 血糖均值 ≤ 血糖最高值`。
- 客户 UUID 是否重复；旧行迁移组合键是否冲突。

工具不会自行定义医学正常范围，也不会根据血糖数值自动诊断、分级或生成治疗建议。`14天血糖达标情况` 仍由现有业务流程或明确的医学规则维护。

## 项目结构

```text
腾讯文档自动化工具/
├── main.py
├── config_loader.py
├── remote_data.py
├── database_source.py
├── monitoring.py
├── validation.py
├── followup_schedule.py
├── tencent_doc.py
├── notification.py
├── config.json
├── sample_data.json
├── requirements.txt
├── requirements-dev.txt
├── docs/
│   └── 表格结构与同步规则.md
├── tests/
├── logs/
└── output/
```

## 业务服务器字段映射

配置模板暂定业务服务器返回以下字段：

| 服务器字段 | 腾讯文档列 |
|---|---|
| `sequence` | 序号 |
| `customer_id` | 客户ID（数据库 `customers.id`） |
| `customer_name` | 姓名 |
| `phone` | 电话（可暂缺） |
| `first_wear_date` | 首次佩戴日期 |
| `followup_1h_date` | 1小时回访：首次佩戴当天 |
| `followup_3d_date` | 3天回访：首次佩戴 +3 天 |
| `followup_first_week_date` | 首次周回访：首次佩戴 +9 天 |
| `pickup_followup_date` | 取机器回访：首次佩戴 +13 天 |
| `glucose_mean` | 血糖均值 |
| `glucose_max` | 血糖最高值 |
| `glucose_min` | 血糖最低值 |

默认数据源直接对 PostgreSQL 做只读查询，`GLUCOSE_DATABASE_URL` 需在运行脚本的服务器环境中设置；脚本不记录连接地址或客户明细。四个回访字段由脚本生成，不要求数据库提供。原 HTTP API 取数模式仍保留为可选方案。

业务接口可返回：

```json
{
  "data": {
    "items": [
      {
        "sequence": 1,
        "customer_id": "11111111-1111-4111-8111-111111111111",
        "customer_name": "测试客户",
        "phone": "13800000001",
        "first_wear_date": "2026-09-20",
        "glucose_mean": 6.25,
        "glucose_max": 10.4,
        "glucose_min": 3.8
      }
    ]
  }
}
```

对应配置：

```json
"data_path": "data.items"
```

如果响应本身就是数组，将 `data_path` 设置为空字符串。

## 腾讯文档接入

项目使用腾讯文档官方 Streamable HTTP MCP 服务：

- MCP 地址：`https://docs.qq.com/openapi/mcp`
- 鉴权头：`Authorization: <个人 Token>`
- Token 页面：`https://docs.qq.com/open/auth/mcp.html`
- 读取记录：`smartsheet.list_records`
- 更新记录：`smartsheet.update_records`
- 可选新增：`smartsheet.add_records`

当前用户提供的目标链接为 `/sheet/` 普通在线表格。现有 MCP 按行更新实现不能直接用于该链接；迁移到智能表格或取得普通表格高级写入接口后才可启用线上模式。详见 [docs/腾讯文档接入待确认.md](docs/腾讯文档接入待确认.md)。

普通腾讯在线 Excel 当前公开的 MCP `batch_update_sheet_range` 主要用于末尾追加，不能安全完成本项目所需的“按既有客户记录比较并更新”。因此在普通表格的高级接口未验证前保持 `backend=mock`。

## 配置腾讯智能表格

1. 在腾讯文档建立智能表格，保留原有 15 列并增加“客户ID”“最近更新日期”两个文本列。
2. 确认 Token 所属账号对文档有编辑权限。
3. 获取 `file_id` 和 `sheet_id`。
4. 设置环境变量：

   ```bash
   export TENCENT_DOCS_TOKEN='实际 Token'
   ```

5. 修改 `config.json`：

   ```json
   {
     "backend": "mcp",
     "document_type": "smartsheet",
     "smartsheet": {
       "file_id": "实际 file_id",
       "sheet_id": "实际 sheet_id",
       "sync_strategy": "review_existing"
     }
   }
   ```

## 本地安全演练

安装环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

使用脱敏样例生成预览，不访问服务器、不写腾讯文档、不通知：

```bash
python main.py --config config.json --input-json sample_data.json --dry-run
```

输出文件：

```text
output/tencent_doc_preview.xlsx
```

只检查配置：

```bash
python main.py --config config.json --check-config
```

## 企业微信通知

设置：

```bash
export WECHAT_WORK_WEBHOOK='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=实际值'
```

将 `notification.enabled` 改为 `true`。每日审查成功通知会包含：

- 服务器记录数。
- 已更新记录数。
- 无变化记录数。
- 服务器端未匹配记录数。
- 腾讯文档端未匹配记录数。
- 执行耗时。
- 今日四类应回访数量（只报数量，不含客户信息）。

通知和日志只记录数量，不记录客户姓名、电话或具体血糖值。

## Linux 部署

示例目录：`/opt/tencent-doc-automation`。

```bash
cd /opt/tencent-doc-automation
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py --config config.json --input-json sample_data.json --dry-run
```

把密钥保存在 `runtime.env`，并设置权限：

```bash
chmod 600 /opt/tencent-doc-automation/runtime.env
```

文件内容：

```bash
BUSINESS_API_TOKEN='实际业务 Token'
TENCENT_DOCS_TOKEN='实际腾讯文档 Token'
WECHAT_WORK_WEBHOOK='实际企业微信 Webhook'
```

## crontab

```cron
CRON_TZ=Asia/Shanghai
0 8,17 * * * set -a; . /opt/tencent-doc-automation/runtime.env; set +a; cd /opt/tencent-doc-automation && /opt/tencent-doc-automation/.venv/bin/python main.py --config config.json >> logs/cron.log 2>&1
```

如果系统不支持 `CRON_TZ`，先用 `timedatectl` 确认服务器时区。

## 测试

```bash
python -m pip install -r requirements-dev.txt
pytest -q
```

测试覆盖：

- 业务接口响应提取。
- 必填和数值校验。
- 日期和血糖最小/均值/最大顺序校验。
- 组合键重复检测。
- 完整 15 列 Excel 预览。
- 电话文本及四个回访计划日期计算。
- 数据库客户 UUID 与 14 天监测期判定。
- 旧行 UUID 回填、新客户自动新增、最近更新日期标记。
- 腾讯文档 MCP 初始化和会话传递。
- 只更新变化字段。
- 跳过服务器空值。
- 不覆盖人工维护列。
- 源端和文档端未匹配计数。

## 上线前仍需确认

- 运行环境的只读 PostgreSQL 连接地址 `GLUCOSE_DATABASE_URL`（仅保存在服务器环境中）。
- 腾讯智能表格的 `file_id` 和 `sheet_id`。
- 目标表格增加“客户ID”“最近更新日期”两个文本字段，或确认保留普通在线 Excel 并提供可按原行更新的开放平台接入方式。
- 企业微信 Webhook 和提醒对象。

在这些参数确认前，保持 `backend=mock`。

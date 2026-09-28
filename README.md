# 血糖客户汇总自动审查工具

该项目每天从业务服务器取得血糖客户汇总数据，校验后与腾讯文档中的既有记录进行比较，只更新发生变化的服务器受管字段，并通过企业微信报告结果。

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

这 6 列保留原有审查规则，另将电话和四个**计划回访日期**纳入自动同步。电话只取业务服务器的 `phone` 字段；服务器缺失时不清空腾讯文档已有电话。四个日期按首次佩戴日期分别加 0、3、9、13 天计算，不代表实际回访已完成。性别、病史、服药及达标情况仍不由此工具覆盖。

本地更新版和 `--dry-run` 预览对四个日期列设置了动态条件格式：日期等于系统当天时显示红字，其他日期保持原格式。脚本也按北京时间统计四类“今日应回访”数量，加入运行结果和通知。腾讯智能表格的日期仍按日期类型同步；其界面红字规则需在目标表中单独配置，脚本不会把日期转成文本来模拟红字。

“姓名”列中即使出现手机号样式或内部编号样式的文本，也按源表现状继续作为姓名/客户标识处理，不会擅自移动到“电话”列。

详细规则见 [docs/表格结构与同步规则.md](docs/表格结构与同步规则.md)。

## 每日执行流程

```text
读取业务服务器数据
→ 校验字段、日期、数值和组合键
→ 根据首次佩戴日期计算四个计划回访日期
→ 读取腾讯智能表现有记录
→ 按“姓名 + 首次佩戴日期”匹配
→ 只比较服务器受管字段
→ 仅提交真正发生变化的字段
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
- 主键列“姓名”和“首次佩戴日期”只用于匹配，不自动改写。
- 只更新 `managed_fields` 中的字段；其中电话为服务器值，四个回访日期由脚本计算。
- 服务器空值默认不会覆盖腾讯文档已有值。
- 内容相同的记录不调用更新接口。
- 服务器新增但腾讯文档不存在的记录默认只报告，不自动新增。
- 腾讯文档存在但服务器不存在的记录只报告，不自动删除。
- 服务器或腾讯文档存在重复组合键时停止任务，防止更新错行。

服务器新增记录的处理由 `new_record_policy` 控制：

- `skip`：默认，只报告，不新增。
- `add`：自动新增。
- `error`：发现新记录即让任务失败。

## 为什么使用组合键

当前表格没有服务器客户 ID。`序号` 只是展示顺序，不能作为稳定主键；“姓名”单独使用也可能重复。因此当前使用：

```text
姓名 + 首次佩戴日期
```

如果业务服务器后续能返回稳定的 `customer_id` 或佩戴记录 ID，应在腾讯文档增加对应列，并改用该 ID 作为唯一主键。这样比姓名组合键更可靠。

## 数据校验

运行前会检查：

- 6 个服务器受管字段是否存在且非空。
- 电话可暂缺；有值时作为文本写入，避免号码被当作数字处理。
- 序号和血糖值是否为非负数值。
- 首次佩戴日期是否为有效日期。
- 是否满足 `血糖最低值 ≤ 血糖均值 ≤ 血糖最高值`。
- “姓名 + 首次佩戴日期”是否重复。

工具不会自行定义医学正常范围，也不会根据血糖数值自动诊断、分级或生成治疗建议。`14天血糖达标情况` 仍由现有业务流程或明确的医学规则维护。

## 项目结构

```text
腾讯文档自动化工具/
├── main.py
├── config_loader.py
├── remote_data.py
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

四个回访字段由脚本生成，不要求业务服务器提供；若服务器真实字段名不同，调整取数适配、`config.json` 的 `mapping.fields` 和 `validation` 字段名。

业务接口可返回：

```json
{
  "data": {
    "items": [
      {
        "sequence": 1,
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

正式使用时建议把现有 15 列结构导入或建立为腾讯智能表格。智能表格具有稳定的 `record_id`，适合审查后按行更新。

普通腾讯在线 Excel 当前公开的 `batch_update_sheet_range` 主要用于末尾追加，不能安全完成本项目所需的“按既有客户记录比较并更新”。因此每日审查模式优先使用智能表格。

## 配置腾讯智能表格

1. 在腾讯文档建立智能表格，列标题与本 README 中的 15 列完全一致。
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

使用脱敏样例生成完整 15 列预览，不访问服务器、不写腾讯文档、不通知：

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
- 腾讯文档 MCP 初始化和会话传递。
- 只更新变化字段。
- 跳过服务器空值。
- 不覆盖人工维护列。
- 源端和文档端未匹配计数。

## 上线前仍需确认

- 业务服务器真实 URL、请求方法和响应样例。
- 服务器真实字段名。
- 腾讯智能表格的 `file_id` 和 `sheet_id`。
- 是否允许服务器新记录自动新增；当前默认不新增。
- 是否能提供稳定的客户 ID 或佩戴记录 ID。
- 企业微信 Webhook 和提醒对象。

在这些参数确认前，保持 `backend=mock`。

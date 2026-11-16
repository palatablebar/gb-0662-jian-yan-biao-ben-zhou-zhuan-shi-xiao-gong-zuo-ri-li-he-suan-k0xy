# 检验时效深度登记

规模：中型。使用者：检验科数据专员。核心规则：工作日历与暂停区间均做集合交并，急诊按自然分钟，签发时效依据接收时的项目版本。

## 功能模块
| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 标本采信 | 读取仪器台账并保留物理行号 | `/intake`、`/api/intake` | `app/modules/intake/reader.py` `app/modules/intake/service.py` | `tests/test_intake.py` |
| M2 项目契约 | 匹配项目版本并去重冲突 | `/contract`、`/api/contract` | `app/modules/contract/versions.py` `app/modules/contract/service.py` | `tests/test_contract.py` |
| M3 节假日历 | 合并暂停并扣除非工作时间 | `/model`、`/api/model` | `app/modules/model/calendar.py` `app/modules/model/service.py` | `tests/test_model.py` |
| M4 时效计算 | 分别核算常规与急诊时效 | `/calculate`、`/api/calculate` | `app/modules/calculate/sla.py` `app/modules/calculate/service.py` | `tests/test_calculate.py` |
| M5 异常隔离 | 按原因筛查拒收证据 | `/quarantine`、`/api/quarantine` | `app/modules/quarantine/diagnose.py` `app/modules/quarantine/service.py` | `tests/test_quarantine.py` |
| M6 科室对账 | 核对行数与科室分位数 | `/reconcile`、`/api/reconcile` | `app/modules/reconcile/metrics.py` `app/modules/reconcile/service.py` | `tests/test_reconcile.py` |
| M7 批次复核 | 幂等存档、复核与正式定版 | `/batches`、`/api/batches` | `app/modules/batches/review.py` `app/modules/batches/service.py` `app/modules/batches/formal.py` | `tests/test_batches.py` `tests/test_formal.py` |

## 正式结论定版裁决
- 定版时点：批次复核通过后由数据专员发起 `POST /api/batches/lock`，把“统计截止时点 + 补录窗口”冻结为正式结论。
- 统计截止：默认取本批最新接收时间之后的首个上海零点；可显式传入带偏移时点。接收早于截止的标本进入本版，其余进入下一周期并单独计数。
- 补录窗口：自定版时点起算，默认 24 小时（0–168）。窗口内后到且接收早于截止的标本在下一版自动纳入，记 `late_backfill`；超窗后到的记 `overdue_backfill`，必须显式确认才可定版。
- 同一核算重试：以标本级冻结依据生成摘要，同批次同摘要再次定版复用原修订，不新增正式批次；已定版修订被回滚后再次提交相同依据，恢复原修订。
- 失败回滚：定版在一个 SQLite 事务内切换生效修订，旧修订仅在同一事务中标记被替代；任何失败都不改变生效修订，复核审计行保持可读。
- 恢复：`POST /api/batches/restore` 在版本校验通过时把历史修订恢复为生效，两版证据与审计都保留。


## 陷阱登记
| TRAP | 现象 | 朴素实现会怎样 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | 旧设备编码 | 直接减时间或后写覆盖导致误判 | 按契约保留证据并确定性计算 | `app/modules/intake/reader.py` | `tests/test_intake.py::test_gb18030` |
| TRAP-02 | BOM表头 | 直接减时间或后写覆盖导致误判 | 按契约保留证据并确定性计算 | `app/modules/intake/reader.py` | `tests/test_intake.py::test_bom_header` |
| TRAP-07 | 时间哨兵 | 直接减时间或后写覆盖导致误判 | 按契约保留证据并确定性计算 | `app/modules/contract/service.py` | `tests/test_contract.py::test_missing_isolated` |
| TRAP-08 | 标本前导零 | 直接减时间或后写覆盖导致误判 | 按契约保留证据并确定性计算 | `app/modules/contract/service.py` | `tests/test_contract.py::test_leading_zero` |
| TRAP-11 | 偏移换算 | 直接减时间或后写覆盖导致误判 | 按契约保留证据并确定性计算 | `app/modules/contract/versions.py` | `tests/test_contract.py::test_timezone` |
| TRAP-14 | 标本签发冲突 | 直接减时间或后写覆盖导致误判 | 按契约保留证据并确定性计算 | `app/modules/contract/service.py` | `tests/test_contract.py::test_conflict` |
| TRAP-18 | 三种空态 | 直接减时间或后写覆盖导致误判 | 按契约保留证据并确定性计算 | `app/modules/intake/reader.py` | `tests/test_intake.py::test_empty_tristate` |
| TRAP-23 | 区间端点 | 直接减时间或后写覆盖导致误判 | 按契约保留证据并确定性计算 | `app/modules/model/calendar.py` | `tests/test_model.py::test_half_open_intersection` |
| TRAP-25 | 项目版本重叠 | 直接减时间或后写覆盖导致误判 | 按契约保留证据并确定性计算 | `app/modules/contract/versions.py` | `tests/test_contract.py::test_version_overlap` |
| TRAP-26 | 陈旧复核 | 直接减时间或后写覆盖导致误判 | 按契约保留证据并确定性计算 | `app/modules/batches/service.py` | `tests/test_batches.py::test_stale_version` |
| TRAP-27 | 月末先定版后补录 | 要么漏掉后到标本，要么等补齐错过报表时点 | 截止+补录窗口定版，差异按补录/超窗/下一周期解释 | `app/modules/batches/formal.py` | `tests/test_formal.py::test_late_backfill_is_explained_against_locked_revision` |
| TRAP-28 | 同一核算重复定版 | 每次重试都新增正式批次 | 冻结依据摘要命中即复用修订 | `app/store.py` | `tests/test_formal.py::test_same_calculation_retry_does_not_append` |
| TRAP-29 | 定版中途失败 | 旧结论已被覆盖，无法恢复 | 单事务切换生效修订，失败保留旧版 | `app/store.py` | `tests/test_formal.py::test_failed_lock_keeps_old_conclusion` |

## 对账规则
输入=有效时效+隔离+空行。有效时效=达标+超时，各科室合计必须回到有效数；P50/P95采用最近秩。
正式结论按周期追加一条口径守恒：输入=纳入+隔离+空行+下一周期，纳入=达标+超时，超时名单人数=超时计数。

## 恢复与不变量
同内容、项目版本、日历、暂停与宽限参数的摘要构成批次键；幂等重跑不追加。SQLite事务保存完整计算结果，失败不落半批。复核使用版本乐观锁。每个业务模块可独立以样例运行。暂停先求并集，再与工作段交集；不因重复批准扣两次。

正式结论额外不变量：同一核算摘要只对应一个修订；重建或重试不新增批次；任一时刻仅一个生效修订；替换与恢复只改变生效标记，历史修订的冻结依据与复核审计始终可读；差异桥接的纳入、达标、超时三行必须各自守恒。

## 已知不覆盖
日历固定Asia/Shanghai，不包含跨DST工作区。仅处理31天内已签发标本。无医院系统连接，不诊断医疗结果。
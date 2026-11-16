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
| M7 批次复核 | 幂等存档与乐观版本复核 | `/batches`、`/api/batches` | `app/modules/batches/review.py` `app/modules/batches/service.py` | `tests/test_batches.py` |

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

## 对账规则
输入=有效时效+隔离+空行。有效时效=达标+超时，各科室合计必须回到有效数；P50/P95采用最近秩。

## 恢复与不变量
同内容、项目版本、日历、暂停与宽限参数的摘要构成批次键；幂等重跑不追加。SQLite事务保存完整计算结果，失败不落半批。复核使用版本乐观锁。每个业务模块可独立以样例运行。暂停先求并集，再与工作段交集；不因重复批准扣两次。

## 已知不覆盖
日历固定Asia/Shanghai，不包含跨DST工作区。仅处理31天内已签发标本。无医院系统连接，不诊断医疗结果。
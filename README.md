# 检验标本周转时效与工作日历核算

检验科数据专员核对标本时效的工作台，含标本采信、项目契约、节假日历、时效计算、异常隔离、科室对账、批次复核七模块。常规检验计算工作分钟，急诊计算自然分钟，重叠暂停仅扣一次，项目版本按接收时间匹配。

## 启动与验证

```sh
docker compose up --build -d
docker compose config --quiet
docker compose exec -T app pytest -q
```

访问 http://localhost:18201 ，首次自动装入仪器脏台账。选择标准标本后重新核算可对照干净结果。标本采信页可粘贴CSV和调整宽限分钟；异常隔离页导出来源证据。API文档位于 `/docs`，六个计算模块均支持POST模块API独立使用样例试跑，`POST /api/runs`保存完整运行。

## 演示步骤

1. 先查看000006与000030的暂停扣除。
2. 在节假日历确认11月3日休息。
3. 时效计算页筛选标本或科室，复核净分钟及上限。
4. 查看异常隔离的CONFLICT与REVERSED证据。
5. 科室对账确认输入行数守恒，再在批次复核确认版本。

SQLite使用records命名卷。`docker compose down`停止服务后数据保留；确认只需演示初始数据后可用 `docker compose down -v`删除本项目数据重新启动。数据字段定义见 `docs/DATA-DICTIONARY.md`，边界与测试映射见 `docs/DEPTH.md`。

`app/modules/`按业务划分，`sample_data/`为标准、脏台账及规则，`tests/`包含模块与端到端验证。仅支持31天内已签发标本与上海工作日历，不连接医院系统。

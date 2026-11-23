# CampusEvent · 校园活动报名与管理系统

> 《软件工程》实验二 ｜ 24 计科 2 班 · 242806010214 ｜ 项目代号：CampusEvent
> 状态：🚧 初始版本已实现，**22 条 pytest 全部通过**（2026-11-23）；C1–C10 人工验收已执行，验收发现 D-01～D-04 已修复，待复验与云服务器部署后再打 baseline-v1。
> 设计评审：已由王以欣评审并签署（结论：通过，2026-11-22），见 docs/08-设计评审记录.md。

## 1. 项目概述

校园管理员发布活动，学生浏览活动并报名；支持“直接报名”和“管理员审核”两类规则，报名/审核结果通过站内消息通知。使用固定演示账号，无注册、无复杂权限系统。

## 2. 技术栈

- Python 3.11+（开发验证 3.13.1）
- Flask 3.1 + Jinja2
- SQLite（首次启动自动建库）
- pytest 9

## 3. 演示账号

| 账号 | 密码 | 角色 | 说明 |
|---|---|---|---|
| admin | admin123 | 管理员 | 活动管理、审批、统计 |
| S001 | 123456 | 学生（张三） | 报名、取消、消息 |
| S002 | 123456 | 学生（李四） | 用于名额/重复报名验证 |
| S003 | 123456 | 学生（王五） | 用于名额已满验证 |

## 4. 从零运行

```bash
cd 24计科2班_242806010214_CampusEvent
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
#临时清空当前终端的代理环境变量
set http_proxy=
set https_proxy=
#国内镜像安装，避免网络卡死
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --no-cache-dir

python app.py
```

浏览器打开 <http://127.0.0.1:5000>。

首次启动在 `instance/campusevent.db` 自动建表并写入演示学生；删除该文件可重置。管理员登录后先“新建活动”，再切换学生账号报名。

## 5. 测试

```bash
python -m pytest tests -q
```

当前结果：**22 passed**。覆盖 C1–C10、重复报名、名额超限、审批满员/并发冲突、取消限制（Q-03）、软删除、消息已读、持久化、权限，以及已审核记录页与统计参与详情。

## 6. 目录结构

```text
24计科2班_242806010214_CampusEvent/
├── app.py                     # Flask 入口
├── campus/
│   ├── __init__.py            # app factory
│   ├── schema.sql             # SQLite 建表
│   ├── db.py                  # 连接、初始化、演示学生
│   ├── repositories.py        # 4 个 Repository
│   ├── policies.py            # 策略接口/两实现/PolicyProvider
│   ├── capacity.py            # CapacityChecker
│   ├── events.py              # 事件、发布者、观察者
│   ├── services.py            # Activity/Registration/Message Service
│   ├── routes.py              # 页面与表单
│   ├── templates/             # Jinja2 页面
│   └── static/style.css
├── tests/                     # pytest（20 条）
├── docs/                      # 需求基线、UML、评审记录、设计说明
├── requirements.txt
├── AI_DEV_LOG.md
└── README.md
```

## 7. 设计文档

- 需求基线：[docs/01-需求基线.md](docs/01-需求基线.md)（v1.3）
- 用例图/说明：[docs/uml/use-case-v1.1.drawio](docs/uml/use-case-v1.1.drawio)、[docs/uml/use-case-spec-v1.1.md](docs/uml/use-case-spec-v1.1.md)
- 类图/类模型：[docs/uml/class-diagram-v1.4.drawio](docs/uml/class-diagram-v1.4.drawio)、[docs/uml/class-model-v1.4.md](docs/uml/class-model-v1.4.md)
- 时序图：[docs/uml/sequence-signup-v1.2.drawio](docs/uml/sequence-signup-v1.2.drawio)、[docs/uml/sequence-approval-v1.3.drawio](docs/uml/sequence-approval-v1.3.drawio)、[docs/uml/sequence-cancel-v1.0.drawio](docs/uml/sequence-cancel-v1.0.drawio)
- 设计原则与模式决策：[docs/07-设计原则与模式决策说明.md](docs/07-设计原则与模式决策说明.md)
- 设计评审记录：[docs/08-设计评审记录.md](docs/08-设计评审记录.md)
- 人工验收记录：[docs/验收记录.md](docs/验收记录.md)（C1–C10 待填；截图可放 `docs/evidence/`）

## 8. 已实现功能（P2-F01～F08）

| 编号 | 功能 | 实现 |
|---|---|---|
| P2-F01 | 活动管理 | 管理员创建/编辑/软删除活动 |
| P2-F02 | 活动查看 | 列表、详情、按名称筛选、剩余名额 |
| P2-F03 | 报名/取消 | 报名、取消；唯一有效报名约束 |
| P2-F04 | 报名策略 | 直接报名自动通过；审核型待审核 |
| P2-F05 | 审批 | 管理员批准/拒绝；批准前重查名额 |
| P2-F06 | 状态管理 | PENDING/APPROVED/REJECTED/CANCELLED |
| P2-F07 | 站内通知 | 报名/审核结果写消息；可标记已读 |
| P2-F08 | 统计 | 管理员按活动查看已通过/待审核/剩余 |

> 验收增强（非 C1–C10 必需）：已审核记录页（D-01）、统计页参与详情（D-02）。

## 9. 验收用例与测试对应

| 用例 | 测试 |
|---|---|
| C1 创建直接报名活动 | test_create_activity_c1 |
| C2 直接报名通过并通知 | test_direct_signup_and_message_c2 |
| C3 拒绝重复报名 | test_duplicate_signup_c3 |
| C4 名额满后报名失败 | test_capacity_full_c4 |
| C5 审核型待审核 | test_audit_pending_c5 |
| C6 批准并通知 | test_approve_c6 |
| C7 拒绝并通知 | test_reject_c7 |
| C8 批准时满员失败 | test_approve_full_c8 |
| C9 取消报名/统计同步 | test_cancel_pending_c9 等 |
| C10 重启后数据一致 | test_persistence_c10 |

## 10. 已知限制（如实说明）

1. 演示账号硬编码在 routes.py，无注册、无密码哈希、无 CSRF；仅用于课程演示。
2. 单进程 SQLite；未做高并发压测。审批并发由条件更新 + 唯一约束兜底。
3. Message 表有技术字段 event_key（唯一）用于重复通知防护，类图 v1.4 的领域字段未展开该技术列。
4. confirm_approval 内含容量条件，CapacityChecker 也做前置检查；两处口径需保持一致。
5. 尚未部署云服务器；实验二要求部署，部署后需在 README 补访问地址。
6. 尚未打 baseline-v1；D-01～D-04 已修复，需人工复验、云服务器部署与版本封存后再打。

## 11. AI 协作

见 [AI_DEV_LOG.md](AI_DEV_LOG.md)：关键指令、AI 产出与问题、人工判断（评审意见、版本修订、测试结果）。

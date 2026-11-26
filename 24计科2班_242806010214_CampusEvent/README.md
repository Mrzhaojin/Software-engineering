# CampusEvent · 校园活动报名与管理系统

> 《软件工程》实验二 ｜ 24 计科 2 班 · 242806010214 ｜ 项目代号：CampusEvent
> 状态：🟡 **change-v2 分支**：CR-01（年级限定报名）与 CR-02（模拟邮件通知）已实现，**31 条 pytest 全部通过**（2026-11-26）；线上当前仍是 baseline-v1，待 CR 验收后部署并打 change-v2。
> 在线访问（baseline-v1）：<http://49.233.87.52:5001/>
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
| S003 | 123456 | 学生（王五，大三） | 用于名额已满/年级限定验证 |
| S004 | 123456 | 学生（赵六，大四） | 用于年级限定拒绝验证 |

> 学生年级：S001=大二、S002=大一、S003=大三、S004=大四；均为演示数据。
> 以上账号仅用于课程演示，不是真实凭据；不要用于生产环境。

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

云服务器在线访问：<http://49.233.87.52:5001/>（部署验证 2026-11-23，返回登录页 200）。

首次启动在 `instance/campusevent.db` 自动建表并写入演示学生；删除该文件可重置。管理员登录后先“新建活动”，再切换学生账号报名。

可选：设置环境变量 `CAMPUS_EVENT_SECRET_KEY`；不设置时每次启动随机生成 Flask session 密钥（重启后旧会话失效）。

CR-02 手工验收可设 `CAMPUS_EVENT_EMAIL_FAILURE=1` 后重启，模拟邮件发送失败（报名仍成功、email_logs 记录 FAILED）。

## 5. 测试

```bash
python -m pytest tests -q
```

当前结果：**31 passed**。覆盖 C1–C10、重复报名、名额超限、审批满员/并发冲突、取消限制（Q-03）、软删除、消息已读、持久化、权限、已审核记录/统计参与详情，以及 CR1-01～05、CR2-01～05、baseline 数据库迁移。

## 6. 目录结构

```text
24计科2班_242806010214_CampusEvent/
├── app.py                     # Flask 入口
├── campus/
│   ├── __init__.py            # app factory
│   ├── schema.sql             # SQLite 建表
│   ├── db.py                  # 连接、初始化、演示学生
│   ├── repositories.py        # 5 个 Repository（含 EmailLogRepository）
│   ├── policies.py            # 策略接口/三实现/PolicyProvider
│   ├── capacity.py            # CapacityChecker
│   ├── events.py              # 事件、发布者、观察者、EmailObserver
│   ├── email.py               # MockEmailSender（CR-02）
│   ├── services.py            # Activity/Registration/Message Service
│   ├── routes.py              # 页面与表单
│   ├── templates/             # Jinja2 页面
│   └── static/style.css
├── tests/                     # pytest（31 条，含 CR 测试与迁移测试）
├── docs/                      # 需求基线、UML、评审记录、设计说明
├── requirements.txt
├── AI_DEV_LOG.md
└── README.md
```

## 7. 设计文档

- 需求基线：[docs/01-需求基线.md](docs/01-需求基线.md)（v1.3）
- 用例图/说明：[docs/uml/use-case-v1.1.drawio](docs/uml/use-case-v1.1.drawio)、[docs/uml/use-case-spec-v1.1.md](docs/uml/use-case-spec-v1.1.md)
- 类图/类模型（CR 后 v2.0）：[docs/uml/class-diagram-v2.0.drawio](docs/uml/class-diagram-v2.0.drawio)、[docs/uml/class-model-v2.0.md](docs/uml/class-model-v2.0.md)
- 时序图（CR 后 v2.0）：[docs/uml/sequence-signup-v2.0.drawio](docs/uml/sequence-signup-v2.0.drawio)、[docs/uml/sequence-approval-v2.0.drawio](docs/uml/sequence-approval-v2.0.drawio)、[docs/uml/sequence-cancel-v1.0.drawio](docs/uml/sequence-cancel-v1.0.drawio)
- CR 影响分析/设计：[docs/09-CR影响分析.md](docs/09-CR影响分析.md)、[docs/10-CR设计变更方案.md](docs/10-CR设计变更方案.md)
- 设计原则与模式决策：[docs/07-设计原则与模式决策说明.md](docs/07-设计原则与模式决策说明.md)
- 设计评审记录：[docs/08-设计评审记录.md](docs/08-设计评审记录.md)
- 人工验收记录：[docs/验收记录.md](docs/验收记录.md)（C1–C10、S1–S7、D-01～D-05 已通过）
- CR 验收记录：[docs/11-CR验收记录.md](docs/11-CR验收记录.md)（待学生填写）

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

### CR-01 / CR-02（change-v2 分支）

| 变更 | 实现 |
|---|---|
| CR-01 年级限定直接报名 | Student.grade；Activity.grade_limited；GradeLimitedDirectPolicy（装饰 DirectRegistrationPolicy）；PolicyRejectedError；S004（大四） |
| CR-02 模拟邮件通知 | EmailLog、EmailLogRepository、MockEmailSender、EmailObserver；站内消息仍事务内，邮件失败只记 FAILED、不回滚；event_key 唯一防重复 |

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
| CR1-01/02 大二/大三通过 | test_grade_limited_allows_grade2_and_3 |
| CR1-03/04 大一/大四拒绝 | test_grade_limited_rejects_grade1_and_4 |
| CR1-05 原 C1–C10 回归 | 原 22 条测试 + CR 测试 |
| CR2-01/02 站内+邮件 | test_email_logged_for_direct_signup / test_email_logged_for_approval_and_rejection |
| CR2-03 邮件失败不回滚 | test_email_failure_does_not_rollback_registration |
| CR2-04 不重复发送 | test_email_not_duplicated_for_same_event |
| CR2-05 原功能回归 | 原 22 条测试 + CR 测试 |

## 10. 已知限制（如实说明）

1. 演示账号硬编码在 routes.py，无注册、无密码哈希、无 CSRF；仅用于课程演示。
2. 单进程 SQLite；未做高并发压测。审批并发由条件更新 + 唯一约束兜底。
3. Message/EmailLog 表有技术字段 event_key（唯一）用于重复通知防护，类图 v2.0 的领域字段未展开该技术列。
4. confirm_approval 内含容量条件，CapacityChecker 也做前置检查；两处口径需保持一致。
5. 已部署云服务器：<http://49.233.87.52:5001/>（需保证服务器进程运行；数据库在服务器本地）。
6. baseline-v1 已打（2026-11-23）；CR 实现在 change-v2 分支，待验收后再部署并打 change-v2 标签。
7. CR-02 邮件在报名事务提交前尝试；极端情况下“邮件已发、提交失败”可能不一致，课程 mock 接受，若严格可改 after-commit 分发。
8. 邮件日志只落库，无管理员查看页面（CR 未要求）。

## 11. 安全说明

- 本仓库为公开课程演示仓库；固定演示账号、验收截图仅用于课程，不是真实凭据。
- 不提交 .env、SSH/API 密钥、数据库、虚拟环境；根目录与项目 .gitignore 已覆盖这些路径。
- Flask session 密钥由环境变量 CAMPUS_EVENT_SECRET_KEY 或每次启动的随机值生成，源码不再硬编码。
- 验收截图包含本机浏览器界面与演示姓名；如公开分享，建议裁剪浏览器地址栏/搜索建议后再发布。

## 12. AI 协作

见 [AI_DEV_LOG.md](AI_DEV_LOG.md)：关键指令、AI 产出与问题、人工判断（评审意见、版本修订、测试结果）。

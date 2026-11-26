# CampusEvent 类模型 v2.0（CR-01 + CR-02）

> 版本：v2.0 ｜ 日期：2026-11-26 ｜ 基线：baseline-v1（8accd33）｜ 分支：change-v2
> 对应类图：class-diagram-v2.0.drawio（第 1 页：核心；第 2 页：CR-01 年级限定策略；第 3 页：CR-02 邮件通知）
> 依据：实验二CR.docx（CR-01/CR-02）、需求基线 v1.3、类模型 v1.4
> 设计选择：CR-01 方案 B（grade_limited + GradeLimitedDirectPolicy 装饰器）；CR-02 方案 A（EmailObserver 内部捕获，Service 不改）。

## 1. 类清单（27 个）

### 1.1 核心/报名（22 个）

| 序号 | 类 / 接口 | 类型 | 一句话职责 | 关键属性/操作 |
|---|---|---|---|---|
| 1 | Student | 实体 | 学生身份与年级 | student_id、name、grade（1–4） |
| 2 | Activity | 实体 | 活动信息、容量、报名方式、年级限定与软删除 | activity_id、title、category、start_at、location、capacity、policy_type、grade_limited、deleted_at |
| 3 | Registration | 实体 | 报名记录与状态 | registration_id、activity_id、student_id、status、created_at、updated_at |
| 4 | Message | 实体 | 站内消息 | message_id、student_id、activity_id、content、created_at、is_read、event_key |
| 5 | StudentRepository | 接口 | 学生查询 | find_by_id |
| 6 | ActivityRepository | 接口 | 活动查询/保存/列表/软删除 | find_by_id、save、list_active、soft_delete |
| 7 | RegistrationRepository | 接口 | 报名持久化、统计、审批原子确认、只读查询 | save、find_by_id、find_active、count_approved、count_pending、confirm_approval、list_reviewed、list_by_activity |
| 8 | MessageRepository | 接口 | 站内消息持久化/查询 | save、list_by_student、mark_read |
| 9 | ActivityService | 应用服务 | 活动管理/浏览；校验 grade_limited 只能配 direct | create_activity、update_activity、soft_delete_activity、get_activity、list_activities |
| 10 | RegistrationService | 应用服务 | 报名/审批/取消编排；只把取策略改为 get(activity) | submit、approve、reject、cancel |
| 11 | MessageService | 应用服务 | 消息列表/已读 | list_messages、mark_read |
| 12 | PolicyProvider | 接口 | 按 activity 提供策略 | get(activity): RegistrationPolicy |
| 13 | PolicyRegistry | 实现 | 注册/选择策略；direct+grade_limited 返回年级策略 | register、get(activity) |
| 14 | RegistrationPolicy | 接口 | 报名策略契约 | decide(activity, student): RegistrationStatus |
| 15 | DirectRegistrationPolicy | 策略 | 直接报名：APPROVED | decide |
| 16 | AuditRegistrationPolicy | 策略 | 审核报名：PENDING | decide |
| 17 | GradeLimitedDirectPolicy | 策略 | 先查 grade∈{2,3}，再委托 DirectRegistrationPolicy；不满足抛 PolicyRejectedError | decide |
| 18 | PolicyRejectedError | 异常 | 年级不符等策略拒绝，带原因 | message |
| 19 | CapacityChecker | 领域服务 | 公共名额检查 | ensure_available、remaining |
| 20 | RegistrationEvent | 事件 | 报名/审批事件数据 | event_type、registration_id、student_id、activity_id、result_status |
| 21 | RegistrationEventPublisher | 发布者 | 维护观察者，按顺序发布 | subscribe、publish |
| 22 | RegistrationObserver | 接口 | 观察者契约 | on_registration_event |

### 1.2 通知/邮件（5 个，第 2 页）

| 序号 | 类 / 接口 | 类型 | 一句话职责 | 关键属性/操作 |
|---|---|---|---|---|
| 23 | MessageObserver | 观察者 | 站内消息；事务内，失败抛异常回滚 | on_registration_event |
| 24 | EmailObserver | 观察者 | 对 APPROVED/REJECTED 事件发 mock 邮件；异常捕获并写 FAILED，不抛出 | email_sender、email_repo、on_registration_event |
| 25 | MockEmailSender | 发送器 | 模拟发送；可配置失败；无真实网络；不直接写库 | send(recipient, subject, content) |
| 26 | EmailLogRepository | 接口 | 邮件日志持久化/按 event_key 查重 | save、find_by_event_key、list |
| 27 | EmailLog | 实体 | 邮件日志（收件人/主题/内容/状态/错误/时间） | log_id、registration_id、event_type、recipient、subject、content、status、error、created_at、event_key |

## 2. 关系与依赖（关键变化）

- Student 1—0..* Registration；Activity 1—0..* Registration（不变）。
- GradeLimitedDirectPolicy 实现 RegistrationPolicy，并依赖 DirectRegistrationPolicy（组合/委托）。
- PolicyRegistry 实现 PolicyProvider；get(activity)：direct + grade_limited=1 返回年级策略，其他按 policy_type 返回。
- RegistrationService 依赖 PolicyProvider，调用 get(activity)（比 v1.4 仅改这一行）；公共校验/容量/事件不变。
- PolicyRejectedError 由 GradeLimitedDirectPolicy 抛出，路由捕获 DomainError 显示原因；不进入 Service 的 catch。
- RegistrationEventPublisher 1—0..* RegistrationObserver；观察者顺序：MessageObserver 先，EmailObserver 后。
- EmailObserver 实现 RegistrationObserver；依赖 MockEmailSender 与 EmailLogRepository；EmailLogRepository 依赖 EmailLog。
- Q-04 例外：MessageObserver 失败仍回滚；EmailObserver 失败捕获并写 FAILED，不回滚（CR-02 要求）。

## 3. 状态与数据迁移

- Student.grade：1–4，演示账号 S001=2、S002=1、S003=3、S004=4。
- Activity.grade_limited：0/1；仅当 policy_type=direct 时允许为 1；不修改 activities 的 policy_type CHECK，不重建表。
- EmailLog.event_key：唯一（event_type:registration_id），用于重复发送防护。
- 迁移：students ADD grade；activities ADD grade_limited；新增 email_logs 表；PRAGMA user_version=2；迁移脚本幂等，迁移前备份。

## 4. 行为概要

### 4.1 年级限定报名（CR-01）

1. Service 公共校验（活动未开始/未删除、无重复有效报名）。
2. provider.get(activity) 返回 GradeLimitedDirectPolicy（direct + grade_limited=1）。
3. policy.decide：grade 不是 2/3 → 抛 PolicyRejectedError（“仅限大二、大三学生报名”），报名不创建；grade 符合 → APPROVED。
4. Service 对 APPROVED 执行 CapacityChecker.ensure_available；名额不足仍失败。
5. 创建报名、发布事件；站内消息 + 邮件。

### 4.2 邮件通知（CR-02）

- 事件类型：SIGNUP_APPROVED、APPROVAL_APPROVED、APPROVAL_REJECTED 才发邮件；PENDING 不发。
- EmailObserver：查 event_key 去重 → 生成 recipient=student_id@campus.demo、subject/content → 调用 MockEmailSender → 成功写 SENT，失败写 FAILED（error）→ 不抛出。
- 站内消息仍由 MessageObserver 在事务内处理；邮件不影响报名事务。

## 5. 追踪

| CR | 需求点 | 类/操作 | 测试 |
|---|---|---|---|
| CR-01 | 年级 2/3 通过 | GradeLimitedDirectPolicy.decide + Direct | CR1-01/02 |
| CR-01 | 大一/大四拒绝原因 | PolicyRejectedError + 路由 | CR1-03/04 |
| CR-01 | 公共约束不变 | RegistrationService + CapacityChecker | CR1-05 / C1–C10 |
| CR-02 | 站内+邮件 | Publisher + MessageObserver + EmailObserver | CR2-01/02 |
| CR-02 | 邮件失败不回滚、有日志 | EmailObserver catch + EmailLog(FAILED) | CR2-03 |
| CR-02 | 不重复发送 | EmailLog.event_key 唯一 + 查重 | CR2-04 |
| CR-02 | 原功能回归 | 全量 C1–C10 | CR2-05 |

## 6. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.4 | 2026-11-23 | 验收增强只读查询 |
| v2.0 | 2026-11-26 | CR-01 年级限定策略；CR-02 邮件观察者/日志；Student/Activity 字段；Provider get(activity) |

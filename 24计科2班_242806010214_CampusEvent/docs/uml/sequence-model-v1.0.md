# CampusEvent 时序模型 v1.0（报名 / 审批）

> 版本：v1.0 ｜ 日期：2026-11-22 ｜ 对应图：sequence-signup-v1.0.drawio、sequence-approval-v1.0.drawio ｜ 依据：类图 v1.1、类模型 v1.1、用例说明 v1.1
> 说明：时序图只表达对象协作与消息顺序；事务、去重与异常以图下 note 与本文件为准。

## 1. 参与者（生命线）

| 生命线 | 类型 | 职责 |
|---|---|---|
| Student / Admin | 参与者 | 触发报名 / 审批 |
| RegistrationService | 应用服务 | 编排、事务边界、构造事件 |
| StudentRepository / ActivityRepository / RegistrationRepository | 仓储接口 | 读取学生/活动、保存与统计报名 |
| PolicyRegistry | 注册表 | 按 policy_type 取策略 |
| RegistrationPolicy | 策略接口 | 返回已通过/待审核 |
| CapacityChecker | 领域服务 | 公共名额检查 |
| RegistrationEventPublisher | 发布者 | 发布事件 |
| MessageObserver | 观察者 | 写站内消息 |
| Message | 实体 | 消息记录 |

## 2. 报名时序（UC-03，直接/审核）

| # | 发送方 → 接收方 | 消息 | 说明 |
|---|---|---|---|
| 1 | Student → Service | submit(student_id, activity_id) | 用例入口 |
| 2 | Service → StudentRepository | find_by_id(student_id) | 取学生 |
| 3 | StudentRepository → Service | Student | 返回 |
| 4 | Service → ActivityRepository | find_by_id(activity_id) | 取活动 |
| 5 | ActivityRepository → Service | Activity | 返回 |
| 6 | Service → RegistrationRepository | find_active(student_id, activity_id) | 校验重复有效报名 |
| 7 | RegistrationRepository → Service | None | 无有效报名 |
| 8 | Service → PolicyRegistry | get(policy_type) | 取策略 |
| 9 | PolicyRegistry → Service | policy | 返回接口 |
| 10 | Service → RegistrationPolicy | decide(activity) | 策略决定结果 |
| 11 | RegistrationPolicy → Service | APPROVED / PENDING | 直接型/审核型 |
| 12 | Service → CapacityChecker | ensure_available(activity_id) | 仅 APPROVED 分支 |
| 13 | CapacityChecker → RegistrationRepository | count_approved(activity_id) | 统计已通过 |
| 14 | RegistrationRepository → CapacityChecker | count | 返回 |
| 15 | CapacityChecker → Service | ok（count < capacity） | 满员抛异常 |
| 16 | Service → RegistrationRepository | save(Registration APPROVED) | 直接型 |
| 17 | RegistrationRepository → Service | reg | 返回 |
| 18 | Service → RegistrationRepository | save(Registration PENDING) | 审核型 |
| 19 | RegistrationRepository → Service | reg | 返回 |
| 20 | Service → RegistrationEventPublisher | publish(event) | 事件 |
| 21 | RegistrationEventPublisher → MessageObserver | on_registration_event(event) | 通知 |
| 22 | MessageObserver → Message | create Message | 同一事务内写消息 |
| 23 | Service → Student | Registration（成功） | 返回 |

- 第 1–23 步在 Service 的事务内；第 20–22 步通知写入失败 → 异常抛出 → 整体回滚，报名不生效（Q-04）。
- 第 8–11 步不含具体策略类型判断；第 12 步只在 APPROVED 分支执行，避免 Service 里 if 具体类。
- 重复防护：第 6 步无有效报名 + 唯一约束；消息去重键 (registration_id, event_type)。

## 3. 审批时序（UC-04，批准/拒绝）

| # | 发送方 → 接收方 | 消息 | 说明 |
|---|---|---|---|
| 1 | Admin → Service | approve/reject(registration_id, admin_id) | 用例入口 |
| 2 | Service → RegistrationRepository | find_by_id(registration_id) | 取报名 |
| 3 | RegistrationRepository → Service | Registration(PENDING) | 返回 |
| 4 | Service → ActivityRepository | find_by_id(activity_id) | 取活动 |
| 5 | ActivityRepository → Service | Activity | 返回 |
| 6 | Service → CapacityChecker | ensure_available(activity_id) | 仅批准分支 |
| 7 | CapacityChecker → RegistrationRepository | count_approved(activity_id) | 统计 |
| 8 | RegistrationRepository → CapacityChecker | count | 返回 |
| 9 | CapacityChecker → Service | ok（count < capacity） | 满员抛异常（C8） |
| 10 | Service → RegistrationRepository | save(reg.status=APPROVED) | 条件更新，防并发（Q-05） |
| 11 | RegistrationRepository → Service | ok | 返回 |
| 12 | Service → RegistrationRepository | save(reg.status=REJECTED) | 拒绝分支，不查容量 |
| 13 | RegistrationRepository → Service | ok | 返回 |
| 14 | Service → RegistrationEventPublisher | publish(event) | 事件 |
| 15 | RegistrationEventPublisher → MessageObserver | on_registration_event(event) | 通知 |
| 16 | MessageObserver → Message | create Message | 同一事务内 |
| 17 | Service → Admin | Registration（已通过/已拒绝） | 返回 |

- 第 6 步仅“批准”分支执行；拒绝分支直接第 12 步。
- 第 10 步 save 在 Repository 实现里做条件更新（仅 PENDING 且容量满足时更新），返回 0 行表示已被处理（Q-05）。
- 通知失败 → 第 14–16 步异常 → 整体回滚（Q-04）。

## 4. VOPC 与类图一致性

- 消息均可映射到类图 v1.1 的操作：submit/approve/reject、find_by_id、find_active、count_approved、save、get、decide、ensure_available、publish、on_registration_event。
- 未新增类；save 需要承载“创建 + 条件更新”两种语义，实现时在 Repository 内用事务/条件 SQL 完成（Q-05）；若实现阶段拆成 confirm_approval，类图需升 v1.2。
- RegistrationEvent 作为值对象不在生命线出现（由 Service 构造后传给 Publisher/Observer），类图 v1.1 已有其定义。

## 5. 验收用例覆盖

| 用例 | 对应图 / 分支 |
|---|---|
| C2 直接报名通过并通知 | 报名图 APPROVED 分支 + 通知 |
| C3 重复报名拒绝 | 报名图第 6 步返回已有记录（扩展） |
| C4 满员后报名失败 | 报名图第 12–15 步抛满员 |
| C5 审核型提交待审核 | 报名图 PENDING 分支 |
| C6 批准并通知 | 审批图批准分支 |
| C7 拒绝并通知 | 审批图拒绝分支 |
| C8 批准时满员失败 | 审批图第 6–9 步抛满员 |
| C10 重启后数据一致 | 事务提交 + 持久化（图外） |

## 6. 待确认

- 是否要把“通知失败回滚”画成显式 alt/异常片段（当前用 note 表达）；如需更强可视化可加。
- 拒绝分支是否需要单独一张图（当前合并在审批图的 alt 中）。
- 是否把 RegistrationEvent 也画成生命线（当前作为参数值对象处理）。

## 7. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-11-22 | 首版：报名（直接/审核）、审批（批准/拒绝）两张时序图与消息表 |

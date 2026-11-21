# CampusEvent 时序模型 v1.1（报名 / 审批）

> 版本：v1.1 ｜ 日期：2026-11-22 ｜ 对应图：sequence-signup-v1.1.drawio、sequence-approval-v1.1.drawio ｜ 依据：类图 v1.1、类模型 v1.1、用例说明 v1.1
> 相对 v1.0：alt 由状态命名改为“直接报名型/审核型”；直接报名分支增加 opt [名额不足] 显式异常出口；通知改为 alt [通知成功/通知失败]。v1.0 归档保留。
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
| 12 | Service → CapacityChecker | ensure_available(activity_id) | **直接报名型分支**；审核型分支不执行 |
| 13 | CapacityChecker → RegistrationRepository | count_approved(activity_id) | 统计已通过 |
| 14 | RegistrationRepository → CapacityChecker | count | 返回 |
| 15 | CapacityChecker → Service | ok（count < capacity） | 名额充足 |
| 16 | CapacityChecker → Service | raise 满员 | opt [名额不足] |
| 17 | Service → Student | 报名失败（名额已满） | opt [名额不足]，不保存、不发事件 |
| 18 | Service → RegistrationRepository | save(Registration APPROVED) | 直接型且名额充足 |
| 19 | RegistrationRepository → Service | reg | 返回 |
| 20 | Service → RegistrationRepository | save(Registration PENDING) | 审核型分支 |
| 21 | RegistrationRepository → Service | reg | 返回 |
| 22 | Service → RegistrationEventPublisher | publish(event) | 事件 |
| 23 | RegistrationEventPublisher → MessageObserver | on_registration_event(event) | 通知 |
| 24 | MessageObserver → Message | create Message | alt [通知成功] |
| 25 | Service → Student | Registration（成功） | alt [通知成功] |
| 26 | MessageObserver → Message | create Message（失败） | alt [通知失败] |
| 27 | MessageObserver → Service | throw NotificationError | alt [通知失败] |
| 28 | Service → Student | 报名失败（通知失败，已回滚） | alt [通知失败] |

- 第 12–17 步：名额检查**在直接报名型分支内**，不是公共前置；审核型按 Q-02 满员也允许提交，因此不查。直接型若名额不足，走 opt 异常出口，不保存、不发事件（C4）。
- 第 22–28 步：通知与报名同事务；写消息失败抛异常 → 回滚，报名不生效（Q-04）。
- 去重：第 6 步无有效报名 + 唯一约束；Message 用 (registration_id, event_type) 唯一键，失败不重试。

## 3. 审批时序（UC-04，批准/拒绝）

| # | 发送方 → 接收方 | 消息 | 说明 |
|---|---|---|---|
| 1 | Admin → Service | approve/reject(registration_id, admin_id) | 用例入口 |
| 2 | Service → RegistrationRepository | find_by_id(registration_id) | 取报名 |
| 3 | RegistrationRepository → Service | Registration(PENDING) | 返回 |
| 4 | Service → ActivityRepository | find_by_id(activity_id) | 取活动 |
| 5 | ActivityRepository → Service | Activity | 返回 |
| 6 | Service → CapacityChecker | ensure_available(activity_id) | **批准分支**；拒绝分支不执行 |
| 7 | CapacityChecker → RegistrationRepository | count_approved(activity_id) | 统计 |
| 8 | RegistrationRepository → CapacityChecker | count | 返回 |
| 9 | CapacityChecker → Service | ok（count < capacity） | 名额充足 |
| 10 | CapacityChecker → Service | raise 满员 | opt [名额不足] |
| 11 | Service → Admin | 批准失败（名额已满） | opt [名额不足]，不更新、不发事件（C8） |
| 12 | Service → RegistrationRepository | save(reg.status=APPROVED) | 条件更新（Q-05） |
| 13 | RegistrationRepository → Service | ok | 返回 |
| 14 | Service → RegistrationRepository | save(reg.status=REJECTED) | 拒绝分支，不查容量 |
| 15 | RegistrationRepository → Service | ok | 返回 |
| 16 | Service → RegistrationEventPublisher | publish(event) | 事件 |
| 17 | RegistrationEventPublisher → MessageObserver | on_registration_event(event) | 通知 |
| 18 | MessageObserver → Message | create Message | alt [通知成功] |
| 19 | Service → Admin | Registration（已通过/已拒绝） | alt [通知成功] |
| 20 | MessageObserver → Message | create Message（失败） | alt [通知失败] |
| 21 | MessageObserver → Service | throw NotificationError | alt [通知失败] |
| 22 | Service → Admin | 处理失败（已回滚） | alt [通知失败] |

- 第 6–11 步只在“批准”分支；拒绝分支直接第 14–15 步。
- 第 12 步 save 在 Repository 内做条件更新（仅 PENDING 且容量满足），返回 0 行表示已被处理（Q-05）。
- 通知失败 → 第 16–22 步异常 → 整体回滚（Q-04）。

## 4. VOPC 与类图一致性

- 消息均可映射到类图 v1.1 的操作：submit/approve/reject、find_by_id、find_active、count_approved、save、get、decide、ensure_available、publish、on_registration_event。
- 未新增类；save 承载“创建 + 条件更新”两种语义，实现时在 Repository 内用事务/条件 SQL 完成（Q-05）；若拆分 confirm_approval，类图需升 v1.2。
- RegistrationEvent 作为值对象不在生命线出现（由 Service 构造后传给 Publisher/Observer），类图 v1.1 已有定义。

## 5. 验收用例覆盖

| 用例 | 对应图 / 分支 |
|---|---|
| C2 直接报名通过并通知 | 报名图直接分支 + 通知成功 |
| C3 重复报名拒绝 | 报名图第 6 步返回已有记录（扩展） |
| C4 满员后报名失败 | 报名图 opt [名额不足] |
| C5 审核型提交待审核 | 报名图审核分支 |
| C6 批准并通知 | 审批图批准分支 + 通知成功 |
| C7 拒绝并通知 | 审批图拒绝分支 + 通知成功 |
| C8 批准时满员失败 | 审批图 opt [名额不足] |
| C10 重启后数据一致 | 事务提交 + 持久化（图外） |

## 6. 待确认

- 是否把“通知失败”画成显式 alt 已按本轮要求完成；若还需要把 throw 画成红色粗线或加终止符，可再调。
- 拒绝分支当前合并在审批图 alt 中；如需单独图可另出。

## 7. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-11-22 | 首版：报名（直接/审核）、审批（批准/拒绝） |
| v1.1 | 2026-11-22 | alt 改直接/审核命名；加 opt 名额不足；加 alt 通知成功/失败 |

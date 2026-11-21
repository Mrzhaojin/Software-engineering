# CampusEvent 时序模型 v1.2（报名 / 审批 / 取消）

> 版本：v1.2 ｜ 日期：2026-11-22 ｜ 对应图：sequence-signup-v1.2.drawio、sequence-approval-v1.2.drawio、sequence-cancel-v1.0.drawio ｜ 依据：类图 v1.2、类模型 v1.2、用例说明 v1.1
> 相对 v1.1：报名图补重复报名 alt；名额检查改为 alt [名额充足/不足]（去掉“opt 后继续 save”的矛盾）；审批图补 save 0 行 alt；新增取消时序；生命线事件发布者改为 RegistrationEventPublisher。
> v1.1 及更早版本归档保留。

## 1. 参与者（生命线）

| 生命线 | 类型 | 职责 |
|---|---|---|
| Student / Admin | 参与者 | 触发报名 / 审批 / 取消 |
| RegistrationService | 应用服务 | 编排、事务边界、构造事件 |
| StudentRepository / ActivityRepository / RegistrationRepository | 仓储接口 | 读取、保存、统计 |
| PolicyProvider | 策略提供者接口 | 按 policy_type 提供策略 |
| RegistrationPolicy | 策略接口 | 返回已通过/待审核 |
| CapacityChecker | 领域服务 | 公共名额检查 |
| RegistrationEventPublisher | 发布者 | 发布事件 |
| MessageObserver | 观察者 | 写站内消息 |
| Message | 实体 | 消息记录 |

## 2. 报名时序（UC-03，直接/审核）

| # | 发送方 → 接收方 | 消息 | 说明 |
|---|---|---|---|
| 1 | Student → Service | submit(student_id, activity_id) | 入口 |
| 2 | Service → StudentRepository | find_by_id(student_id) | 取学生 |
| 3 | StudentRepository → Service | Student | 返回 |
| 4 | Service → ActivityRepository | find_by_id(activity_id) | 取活动 |
| 5 | ActivityRepository → Service | Activity | 返回 |
| 6 | Service → RegistrationRepository | find_active(student_id, activity_id) | 查有效报名 |
| 7 | RegistrationRepository → Service | existing / None | 结果 |
| 8 | Service → Student | 报名失败（重复报名） | alt [已存在有效报名] |
| 9 | Service → PolicyProvider | get(policy_type) | 取策略 |
| 10 | PolicyProvider → Service | policy | 返回接口 |
| 11 | Service → RegistrationPolicy | decide(activity, student) | 策略决定结果 |
| 12 | RegistrationPolicy → Service | APPROVED / PENDING | 直接型/审核型 |
| 13 | Service → CapacityChecker | ensure_available(activity_id) | 直接报名型分支 |
| 14 | CapacityChecker → RegistrationRepository | count_approved(activity_id) | 统计 |
| 15 | RegistrationRepository → CapacityChecker | count | 返回 |
| 16 | CapacityChecker → Service | ok（count < capacity） | alt [名额充足] |
| 17 | Service → RegistrationRepository | save(Registration APPROVED) | 充足分支 |
| 18 | RegistrationRepository → Service | reg | 返回 |
| 19 | CapacityChecker → Service | raise 满员 | alt [名额不足] |
| 20 | Service → Student | 报名失败（名额已满） | 不足分支，不保存、不发事件 |
| 21 | Service → RegistrationRepository | save(Registration PENDING) | 审核型分支 |
| 22 | RegistrationRepository → Service | reg | 返回 |
| 23 | Service → RegistrationEventPublisher | publish(event) | 事件 |
| 24 | RegistrationEventPublisher → MessageObserver | on_registration_event(event) | 通知 |
| 25 | MessageObserver → Message | create Message | alt [通知成功] |
| 26 | Service → Student | Registration（成功） | alt [通知成功] |
| 27 | MessageObserver → Message | create Message（失败） | alt [通知失败] |
| 28 | MessageObserver → Service | throw NotificationError | alt [通知失败] |
| 29 | Service → Student | 报名失败（通知失败，已回滚） | alt [通知失败] |

- 重复报名：第 6–8 步的 alt 明确拒绝，不再进入策略/保存。
- 名额检查只在“直接报名型”分支；审核型满员仍可提交（Q-02）。
- 通知与报名同事务；第 27 步失败 → 回滚（Q-04）；消息去重键 (registration_id, event_type)。

## 3. 审批时序（UC-04，批准/拒绝）

| # | 发送方 → 接收方 | 消息 | 说明 |
|---|---|---|---|
| 1 | Admin → Service | approve/reject(registration_id, admin_id) | 入口 |
| 2 | Service → RegistrationRepository | find_by_id(registration_id) | 取报名 |
| 3 | RegistrationRepository → Service | Registration(PENDING) | 返回 |
| 4 | Service → ActivityRepository | find_by_id(activity_id) | 取活动 |
| 5 | ActivityRepository → Service | Activity | 返回 |
| 6 | Service → CapacityChecker | ensure_available(activity_id) | 仅批准分支 |
| 7 | CapacityChecker → RegistrationRepository | count_approved(activity_id) | 统计 |
| 8 | RegistrationRepository → CapacityChecker | count | 返回 |
| 9 | CapacityChecker → Service | ok（count < capacity） | alt [名额充足] |
| 10 | Service → RegistrationRepository | save(reg.status=APPROVED) | alt [更新成功] |
| 11 | RegistrationRepository → Service | 1 row | 返回 |
| 12 | Service → RegistrationRepository | save(reg.status=APPROVED) | alt [0 行]（并发/已处理） |
| 13 | RegistrationRepository → Service | 0 行 | 返回 |
| 14 | Service → Admin | 已被处理，未更新 | 0 行分支 |
| 15 | CapacityChecker → Service | raise 满员 | alt [名额不足] |
| 16 | Service → Admin | 批准失败（名额已满） | 不足分支 |
| 17 | Service → RegistrationRepository | save(reg.status=REJECTED) | 拒绝分支，不查容量 |
| 18 | RegistrationRepository → Service | ok | 返回 |
| 19 | Service → RegistrationEventPublisher | publish(event) | 事件 |
| 20 | RegistrationEventPublisher → MessageObserver | on_registration_event(event) | 通知 |
| 21 | MessageObserver → Message | create Message | alt [通知成功] |
| 22 | Service → Admin | Registration（已通过/已拒绝） | alt [通知成功] |
| 23 | MessageObserver → Message | create Message（失败） | alt [通知失败] |
| 24 | MessageObserver → Service | throw NotificationError | alt [通知失败] |
| 25 | Service → Admin | 处理失败（已回滚） | alt [通知失败] |

- 结构：批准分支内先判断容量（充足/不足），充足后再判断更新结果（1 行/0 行）；拒绝分支不查容量。
- 0 行表示并发下已被其他管理员处理或状态已变化（Q-05）；不生成事件。
- 通知失败 → 回滚（Q-04）。

## 4. 取消时序（UC-05，Q-03）

| # | 发送方 → 接收方 | 消息 | 说明 |
|---|---|---|---|
| 1 | Student → Service | cancel(registration_id, student_id) | 入口 |
| 2 | Service → RegistrationRepository | find_by_id(registration_id) | 取报名 |
| 3 | RegistrationRepository → Service | Registration | 返回 |
| 4 | Service → ActivityRepository | find_by_id(activity_id) | 取活动（判断是否开始） |
| 5 | ActivityRepository → Service | Activity | 返回 |
| 6 | Service → RegistrationRepository | save(reg.status=CANCELLED) | 允许取消 |
| 7 | RegistrationRepository → Service | ok | 返回 |
| 8 | Service → Student | 取消成功 | 返回 |
| 9 | Service → Student | 拒绝：活动已开始且已通过 | 拒绝分支 |

- 允许条件：活动未开始（待审核/已通过都可取消），或活动已开始但状态为待审核；活动已开始且已通过 → 拒绝（Q-03）。
- 取消不生成通知；统计按状态实时查询，不需要额外事件。

## 5. 分支与异常汇总

| 场景 | 图 / 分支 |
|---|---|
| 重复报名 | 报名图 alt [已存在有效报名] |
| 名额不足（报名） | 报名图 alt [名额不足] |
| 名额不足（审批） | 审批图 alt [名额不足] |
| 审批并发/已处理 | 审批图 alt [0 行] |
| 通知失败 | 报名/审批图 alt [通知失败] |
| 取消限制 | 取消图 alt [允许取消 / 拒绝] |

## 6. VOPC 与类图一致性

- 消息均可映射到类图 v1.2 操作：submit/approve/reject/cancel、find_by_id、find_active、count_approved、count_pending（统计 UI 用）、save、get、decide、ensure_available、publish、on_registration_event。
- 未新增类；save 承担“创建 + 条件更新”，0 行语义在审批图中显式表达；若实现时拆 confirm_approval，类图升 v1.3。
- ActivityService / MessageService / MessageRepository 不在这三条时序中（分别覆盖 UC-01/02、UC-06），由用例说明与类模型覆盖。

## 7. 覆盖矩阵

| 用例 | 对应 |
|---|---|
| C2 直接报名通过并通知 | 报名图直接分支 + 通知成功 |
| C3 重复报名拒绝 | 报名图 alt [已存在有效报名] |
| C4 满员报名失败 | 报名图 alt [名额不足] |
| C5 审核型待审核 | 报名图审核分支 |
| C6 批准并通知 | 审批图批准 + 通知成功 |
| C7 拒绝并通知 | 审批图拒绝 + 通知成功 |
| C8 批准满员失败 | 审批图 alt [名额不足] |
| C9 取消并同步统计 | 取消图 |
| C10 重启一致 | 事务提交 + 持久化（图外） |

## 8. 待确认

- 取消是否需要生成通知？当前按 B.2 未要求，不生成；如需要可加事件与观察者。
- 审批图嵌套 alt 较深（批准→容量→更新结果），评审若觉得复杂可拆成两张；目前保留以完整表达边界。
- RegistrationEvent 仍作为值对象，不作为生命线。

## 9. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.1 | 2026-11-22 | 直接/审核命名、名额不足 opt、通知 alt |
| v1.2 | 2026-11-22 | 重复报名 alt、名额充足/不足 alt、审批 0 行 alt、取消时序、事件发布者命名 |

# CampusEvent 类模型 v1.1（方案甲）

> 版本：v1.1 ｜ 日期：2026-11-22 ｜ 对应类图：class-diagram-v1.1.drawio ｜ 需求基线：v1.3
> 设计选择：**方案甲**——名额检查作为公共不变量放在 CapacityChecker；策略只决定报名结果（Q-07 = A）。
> 相对 v1.0：补 ActivityRepository、StudentRepository、PolicyRegistry、RegistrationEvent；操作签名改为 snake_case、以 ID 为参数（分模块 Flask 结构）；补通知重复防护。
> 依据：知识库《UML图速查》2.1 类图、《面向对象分析与设计》2.4 OOD 原则、《设计模式》2.5.9 策略 / 2.5.6 观察者；用例说明 v1.1。

## 1. 类清单（17 个）

| 序号 | 类 / 接口 | 类型 | 一句话职责 | 关键属性 | 关键操作 |
|---|---|---|---|---|---|
| 1 | Student | 实体 | 学生身份与姓名，报名人的唯一标识 | student_id、name | — |
| 2 | Activity | 实体 | 活动信息与容量/报名方式，支持软删除 | activity_id、title、category、start_at、location、capacity、policy_type、deleted_at | is_before_start(now): bool |
| 3 | Registration | 实体 | 一条报名记录及其状态 | registration_id、activity_id、student_id、status、created_at、updated_at | — |
| 4 | Message | 实体 | 站内通知记录 | message_id、student_id、activity_id、content、created_at、is_read | — |
| 5 | StudentRepository | 接口 | 学生查询 | — | find_by_id(id): Student |
| 6 | ActivityRepository | 接口 | 活动查询、保存、列表与软删除 | — | find_by_id、save、list_active(name)、soft_delete(id) |
| 7 | RegistrationRepository | 接口 | 报名持久化、查有效报名、统计已通过数 | — | save、find_by_id、find_active、count_approved |
| 8 | RegistrationService | 应用服务 | 编排提交/审批/取消，控制事务与事件发布 | student_repo、activity_repo、registration_repo、policy_registry、capacity_checker、publisher | submit、approve、reject、cancel |
| 9 | PolicyRegistry | 注册表 | 按 policy_type 返回策略实例 | policies: dict | register、get |
| 10 | RegistrationPolicy | 接口 | 报名策略契约：决定报名结果 | — | decide(activity): RegistrationStatus |
| 11 | DirectRegistrationPolicy | 策略实现 | 直接报名：返回“已通过” | — | decide(activity) |
| 12 | AuditRegistrationPolicy | 策略实现 | 审核型报名：返回“待审核” | — | decide(activity) |
| 13 | CapacityChecker | 领域服务 | 统一名额检查：统计已通过数、判断剩余名额、满员拒绝 | — | ensure_available(activity_id)、remaining(activity_id) |
| 14 | RegistrationEvent | 事件对象 | 报名/审批事件的数据载体 | event_id、event_type、registration_id、student_id、activity_id、result_status、occurred_at | — |
| 15 | RegistrationEventPublisher | 发布者（Subject） | 维护观察者并发布事件 | observers: list | subscribe、publish(event) |
| 16 | RegistrationObserver | 接口 | 观察者契约 | — | on_registration_event(event) |
| 17 | MessageObserver | 观察者实现 | 把事件写成 Message 记录（可扩展第二通知渠道） | — | on_registration_event(event) |

说明：RegistrationStatus 为枚举（PENDING / APPROVED / REJECTED / CANCELLED），不是类。

## 2. 关系与多重性

| 关系 | 源 | 目标 | 类型 | 多重性 / 说明 |
|---|---|---|---|---|
| 报名归属 | Student | Registration | 关联 | 1 — 0..* |
| 报名所属活动 | Activity | Registration | 关联 | 1 — 0..* |
| 策略实现 | DirectRegistrationPolicy | RegistrationPolicy | 实现 | 虚线 + 空心三角 |
| 策略实现 | AuditRegistrationPolicy | RegistrationPolicy | 实现 | 同上 |
| 通知解耦 | RegistrationEventPublisher | RegistrationObserver | 关联 | 1 — 0..* |
| 观察者实现 | MessageObserver | RegistrationObserver | 实现 | 同上 |
| 消息创建 | MessageObserver | Message | 依赖 | 事件触发时创建 |
| 消息归属 | Message | Student / Activity | 关联（属性表示） | * — 1；未画连线，见 note |

## 3. 依赖方向（虚线开放箭头）

| 依赖方 | 被依赖方 | 原因 |
|---|---|---|
| RegistrationService | StudentRepository / ActivityRepository / RegistrationRepository | 读取学生、活动；保存报名 |
| RegistrationService | PolicyRegistry | 按 policy_type 取策略 |
| RegistrationService | RegistrationPolicy | 依赖抽象（DIP） |
| RegistrationService | CapacityChecker | 公共名额检查 |
| RegistrationService | RegistrationEventPublisher | 发布事件 |
| RegistrationService | RegistrationEvent | 构造事件 |
| PolicyRegistry | RegistrationPolicy | 返回策略接口 |
| CapacityChecker | RegistrationRepository | count_approved 统计已通过 |
| RegistrationEventPublisher | RegistrationEvent | 发布事件对象 |
| RegistrationObserver | RegistrationEvent | 接收事件对象 |
| MessageObserver | Message | 写站内消息 |
| **策略实现** | **CapacityChecker** | **无依赖**（方案甲关键检查点） |

## 4. 关键设计决策

1. **Q-07 = A**：名额检查集中在 CapacityChecker；策略只回答“已通过/待审核”。RegistrationService 根据策略返回状态决定是否调用 CapacityChecker（返回“已通过”才检查），不判断具体策略类型。
2. **提交**：Service 校验（活动未开始、无重复有效报名）→ registry.get(policy_type) → decide → 若“已通过”则 ensure_available → 创建 Registration → 构造 RegistrationEvent → publish。
3. **审批**：Service 校验待审核 → ensure_available → 条件更新（Q-05）→ 构造事件 → publish。
4. **事务与通知（Q-04）**：Service 持有事务；MessageObserver 在同一事务内写 Message；写入失败抛异常，事务回滚，报名不生效；失败日志在事务外记录。
5. **避免重复通知（3.3-C）**：
   - 每次成功状态迁移只发布 1 个事件；
   - Message 增加去重键（registration_id + event_type）唯一索引，MessageObserver 重复收到同一事件时跳过；
   - 审批使用条件更新（Q-05），避免并发重复批准产生两个事件；
   - 报名使用“同一学生同一活动仅一条有效报名”的唯一约束，避免重复提交产生两个报名；
   - 通知失败按 Q-04 整体回滚，不做“重试通知”，因此不会产生重复消息。
6. **软删除（Q-06）**：Activity.deleted_at 非空表示已下线；列表/详情/统计过滤；报名与消息保留。
7. **观察者（B.3-3）**：Publisher 依赖 Observer 接口；第二通知渠道只需新增观察者并注册。
8. **分模块结构**：models、repositories、services、policies、events 分层；本类图的操作签名按该结构（ID 入参、snake_case）。

## 5. 状态枚举

| 状态 | 含义 | 迁移 |
|---|---|---|
| PENDING | 审核型报名已提交 | → APPROVED / REJECTED / CANCELLED |
| APPROVED | 报名成功，占用名额 | → CANCELLED |
| REJECTED | 审批拒绝，保留历史 | 终态；可重新申请（新建记录） |
| CANCELLED | 学生取消，保留历史 | 终态；可重新申请（新建记录） |

## 6. 持久类清单（供后续 ERD）

Student、Activity、Registration、Message 四个实体持久化；其余为服务/策略/仓储接口/事件类，不建表。

## 7. UC → 类 / 操作追踪

| UC | 主要类 / 操作 |
|---|---|
| UC-01 管理活动 | RegistrationService（活动校验）、ActivityRepository、Activity |
| UC-02 浏览活动 | ActivityRepository.list_active、RegistrationRepository.count_approved（剩余名额） |
| UC-03 报名活动 | RegistrationService.submit、PolicyRegistry.get、RegistrationPolicy.decide、CapacityChecker.ensure_available、RegistrationRepository、Publisher |
| UC-04 审批报名 | RegistrationService.approve/reject、CapacityChecker、RegistrationRepository、Publisher |
| UC-05 取消报名 | RegistrationService.cancel、RegistrationRepository |
| UC-06 查看站内消息 | Message、MessageObserver |
| UC-07 查看活动统计 | RegistrationRepository.count_approved、ActivityRepository |

## 8. 自检与待办

- 17 个类/接口，每个有职责与至少一个属性或操作；无孤立类。
- 关联多重性明确；依赖方向符合 DIP。
- 策略实现不依赖 CapacityChecker（方案甲检查点）。
- 观察者链完整：Publisher → Observer ← MessageObserver → Message；事件对象贯穿。
- 已完成：2 张时序图 v1.0（直接/审核报名、审批）；消息可映射到现有操作，未新增类；save 在 Repository 内承担条件更新（Q-05）。
- 待办：设计原则说明（SRP/OCP/DIP）与评审签名（3.3-D）。

## 9. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-11-22 | 首版：13 类、Q-07 A |
| v1.1 | 2026-11-22 | 补 Student/Activity Repository、PolicyRegistry、RegistrationEvent；签名改 ID 入参/snake_case；补重复通知防护 |

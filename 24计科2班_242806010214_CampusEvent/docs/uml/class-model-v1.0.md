# CampusEvent 类模型 v1.0（方案甲）

> 版本：v1.0 ｜ 日期：2026-11-22 ｜ 对应类图：class-diagram-v1.0.drawio ｜ 需求基线：v1.3
> 设计选择：**方案甲**——名额检查作为公共不变量放在 CapacityChecker，策略只决定报名结果（Q-07 由 C 修正为 A，2026-11-22）。
> 依据：知识库《UML图速查》2.1 类图、《面向对象分析与设计》2.4 OOD 原则、《设计模式》2.5.9 策略 / 2.5.6 观察者；用例说明 v1.1。

## 1. 类清单（13 个）

| 序号 | 类 / 接口 | 类型 | 一句话职责 | 关键属性 | 关键操作 |
|---|---|---|---|---|---|
| 1 | Student | 实体 | 学生身份与姓名，报名人的唯一标识 | student_id、name | — |
| 2 | Activity | 实体 | 活动信息与容量/报名方式，支持软删除标记 | activity_id、title、category、start_at、location、capacity、policy_type、deleted_at | isBeforeStart(now): bool |
| 3 | Registration | 实体 | 一条报名记录及其状态 | registration_id、activity_id、student_id、status、created_at、updated_at | — |
| 4 | Message | 实体 | 站内通知记录 | message_id、student_id、activity_id、content、created_at、is_read | — |
| 5 | RegistrationRepository | 接口 | 报名持久化与已通过数统计 | — | save、findById、countApproved(activityId) |
| 6 | RegistrationService | 应用服务 | 编排提交/审批/取消，控制事务与事件发布 | policyRegistry、capacityChecker、repository、publisher | submit、approve、reject、cancel |
| 7 | RegistrationPolicy | 接口 | 报名策略契约：决定报名结果 | — | decide(activity): RegistrationStatus |
| 8 | DirectRegistrationPolicy | 策略实现 | 直接报名：返回“已通过” | — | decide(activity) |
| 9 | AuditRegistrationPolicy | 策略实现 | 审核型报名：返回“待审核” | — | decide(activity) |
| 10 | CapacityChecker | 领域服务 | 统一名额检查：统计已通过数、判断剩余名额、满员拒绝 | — | ensureAvailable(activity)、remaining(activity) |
| 11 | RegistrationEventPublisher | 事件发布者（Subject） | 维护观察者并发布报名/审批事件 | observers | subscribe、publish |
| 12 | RegistrationObserver | 接口 | 观察者契约 | — | onRegistrationEvent(event) |
| 13 | MessageObserver | 观察者实现 | 把事件写成 Message 记录（可扩展第二通知渠道） | — | onRegistrationEvent(event) |

说明：RegistrationStatus 为枚举，不是类；取值 待审核 / 已通过 / 已拒绝 / 已取消。

## 2. 关系与多重性

| 关系 | 源 | 目标 | 类型 | 多重性 / 说明 |
|---|---|---|---|---|
| 报名归属 | Student | Registration | 关联 | 1 — 0..*，一个学生可有多条报名 |
| 报名所属活动 | Activity | Registration | 关联 | 1 — 0..*，一个活动可有多条报名 |
| 策略实现 | DirectRegistrationPolicy | RegistrationPolicy | 实现（realization） | 虚线 + 空心三角 |
| 策略实现 | AuditRegistrationPolicy | RegistrationPolicy | 实现 | 同上 |
| 通知解耦 | RegistrationEventPublisher | RegistrationObserver | 关联 | 1 — 0..*，主题维护观察者列表 |
| 观察者实现 | MessageObserver | RegistrationObserver | 实现 | 同上 |
| 消息创建 | MessageObserver | Message | 依赖 | 事件触发时创建消息 |
| 消息归属 | Message | Student / Activity | 关联（属性表示） | * — 1；为可读性未画连线，见 note |

## 3. 依赖方向（虚线开放箭头）

| 依赖方 | 被依赖方 | 原因 |
|---|---|---|
| RegistrationService | RegistrationPolicy | 依赖抽象，不依赖具体策略（DIP） |
| RegistrationService | CapacityChecker | 提交/审批前的公共名额检查 |
| RegistrationService | RegistrationRepository | 保存/查询报名 |
| RegistrationService | RegistrationEventPublisher | 发布报名/审批事件 |
| RegistrationService | Registration / Activity | 创建报名、读取活动（图中两条虚线） |
| CapacityChecker | RegistrationRepository | countApproved 统计“已通过”数 |
| MessageObserver | Message | 写站内消息 |
| 策略实现 | RegistrationPolicy | 实现关系，不是依赖 |
| **策略实现** | **CapacityChecker** | **无依赖**（方案甲的关键：策略不判名额） |

## 4. 关键设计决策

1. **Q-07 = A**：名额检查集中在 CapacityChecker；策略只回答“已通过/待审核”。RegistrationService 根据策略返回状态决定是否调用 CapacityChecker（返回“已通过”才检查名额），不判断具体策略类型，避免类型分支。
2. **提交流程（甲）**：Service 公共校验（活动未开始、无重复有效报名）→ 策略 decide → 若“已通过”则 CapacityChecker.ensureAvailable → 创建报名 → publisher.publish。
3. **审批流程（甲）**：Service 校验待审核 → CapacityChecker.ensureAvailable → 条件更新状态（Q-05）→ publisher.publish。
4. **事务与通知（Q-04）**：Service 持有事务；MessageObserver 在同一事务内写 Message；写入失败抛异常，事务回滚，报名不生效；失败日志在事务外记录。
5. **软删除（Q-06）**：Activity.deleted_at 非空表示已下线；列表/详情/统计过滤 deleted_at 为空的活动；报名与消息保留。
6. **并发（Q-05）**：审批用条件更新（已通过数 < capacity 才更新）+ 唯一约束（同一学生同一活动只允许一条待审核/已通过，可用部分唯一索引），失败重试。
7. **观察者（B.3-3）**：Publisher 依赖 RegistrationObserver 接口；第二通知渠道只需新增观察者并注册，Service 不改。

## 5. 状态枚举

| 状态 | 含义 | 迁移 |
|---|---|---|
| PENDING（待审核） | 审核型报名已提交 | → APPROVED / REJECTED / CANCELLED |
| APPROVED（已通过） | 报名成功，占用名额 | → CANCELLED |
| REJECTED（已拒绝） | 审批拒绝，保留历史 | 终态；可重新申请（新建记录） |
| CANCELLED（已取消） | 学生取消，保留历史 | 终态；可重新申请（新建记录） |

## 6. 持久类清单（供后续 ERD）

Student、Activity、Registration、Message 四个实体持久化；其余为服务/策略/事件类，不建表。

## 7. UC → 类 / 操作追踪

| UC | 主要类 / 操作 |
|---|---|
| UC-01 管理活动 | RegistrationService、Activity、RegistrationRepository（活动与报名校验） |
| UC-02 浏览活动 | RegistrationService/查询、Activity、Registration（剩余名额） |
| UC-03 报名活动 | RegistrationService.submit、RegistrationPolicy.decide、CapacityChecker.ensureAvailable、Registration、Publisher |
| UC-04 审批报名 | RegistrationService.approve/reject、CapacityChecker、Registration、Publisher |
| UC-05 取消报名 | RegistrationService.cancel、Registration |
| UC-06 查看站内消息 | Message、MessageObserver |
| UC-07 查看活动统计 | RegistrationRepository.countApproved、Activity |

说明：UC-01/02 中活动查询与保存的 Repository 细节未在类图展开（RegistrationRepository 只覆盖报名；活动仓储可按同样方式补 ActivityRepository，本版不引入以避免类膨胀）。

## 8. 自检与待办

- 13 个类/接口，每个有职责与至少一个属性或操作；无孤立类。
- 每条关联有明确多重性；依赖方向符合 DIP。
- 策略实现不依赖 CapacityChecker（方案甲检查点）。
- 观察者链完整：Publisher → Observer ← MessageObserver → Message。
- 待办：画 2 张时序图 v1.0（直接/审核报名、审批）后，按 VOPC 回写操作与消息，核对类图操作是否齐全。
- 待办：ActivityRepository 是否在实现阶段引入，等时序图确认查询路径后再定。

## 9. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-11-22 | 首版：方案甲 13 类/接口、14 条关系、依赖方向、Q-07 A |

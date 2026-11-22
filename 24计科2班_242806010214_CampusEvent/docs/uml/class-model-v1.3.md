# CampusEvent 类模型 v1.3（方案甲）

> 版本：v1.3 ｜ 日期：2026-11-22 ｜ 对应类图：class-diagram-v1.3.drawio ｜ 需求基线：v1.3
> v1.3：按评审建议拆分 save 的“条件更新”语义，新增 RegistrationRepository.confirm_approval；save 只保留创建/简单状态更新。其余同 v1.2（补 ActivityService/MessageService/MessageRepository/PolicyProvider、count_pending、decide 上下文、修 DIP 表述）。
> 设计选择：方案甲——名额检查集中 CapacityChecker；策略只决定结果（Q-07 = A）。

## 1. 类清单（21 个）

| 序号 | 类 / 接口 | 类型 | 一句话职责 | 关键属性 | 关键操作 |
|---|---|---|---|---|---|
| 1 | Student | 实体 | 学生身份与姓名 | student_id、name | — |
| 2 | Activity | 实体 | 活动信息、容量/报名方式与软删除标记 | activity_id、title、category、start_at、location、capacity、policy_type、deleted_at | is_before_start(now) |
| 3 | Registration | 实体 | 报名记录与状态 | registration_id、activity_id、student_id、status、created_at、updated_at | — |
| 4 | Message | 实体 | 站内消息记录 | message_id、student_id、activity_id、content、created_at、is_read | — |
| 5 | StudentRepository | 接口 | 学生查询 | — | find_by_id |
| 6 | ActivityRepository | 接口 | 活动查询/保存/列表/软删除 | — | find_by_id、save、list_active、soft_delete |
| 7 | RegistrationRepository | 接口 | 报名持久化、有效报名查询、按状态统计、审批原子确认 | — | save、find_by_id、find_active、count_approved、count_pending、confirm_approval |
| 8 | MessageRepository | 接口 | 消息持久化、按学生查询、标记已读 | — | save、list_by_student、mark_read |
| 9 | ActivityService | 应用服务 | 编排活动创建/编辑/软删除/浏览（UC-01、UC-02） | activity_repo | create_activity、update_activity、soft_delete_activity、get_activity、list_activities |
| 10 | RegistrationService | 应用服务 | 编排报名/审批/取消，事务与事件（UC-03～05） | student_repo、activity_repo、registration_repo、policy_provider、capacity_checker、publisher | submit、approve、reject、cancel |
| 11 | MessageService | 应用服务 | 编排消息列表与已读（UC-06） | message_repo | list_messages、mark_read |
| 12 | PolicyProvider | 接口 | 按 policy_type 提供策略 | — | get(policy_type): RegistrationPolicy |
| 13 | PolicyRegistry | 注册表 | PolicyProvider 实现，登记/查找策略 | policies: dict | register、get |
| 14 | RegistrationPolicy | 接口 | 报名策略契约 | — | decide(activity, student): RegistrationStatus |
| 15 | DirectRegistrationPolicy | 策略实现 | 直接报名：返回“已通过” | — | decide(activity, student) |
| 16 | AuditRegistrationPolicy | 策略实现 | 审核型报名：返回“待审核” | — | decide(activity, student) |
| 17 | CapacityChecker | 领域服务 | 公共名额检查 | — | ensure_available、remaining |
| 18 | RegistrationEvent | 事件对象 | 报名/审批事件数据 | event_id、event_type、registration_id、student_id、activity_id、result_status、occurred_at | — |
| 19 | RegistrationEventPublisher | 发布者 | 维护观察者并发布事件 | observers | subscribe、publish |
| 20 | RegistrationObserver | 接口 | 观察者契约 | — | on_registration_event(event) |
| 21 | MessageObserver | 观察者实现 | 把事件写成 Message（经 Repository） | message_repo | on_registration_event(event) |

说明：RegistrationStatus 为枚举（PENDING/APPROVED/REJECTED/CANCELLED）。

## 2. 关系与多重性

| 关系 | 源 | 目标 | 类型 | 多重性 / 说明 |
|---|---|---|---|---|
| 报名归属 | Student | Registration | 关联 | 1 — 0..* |
| 报名所属活动 | Activity | Registration | 关联 | 1 — 0..* |
| 策略实现 | DirectRegistrationPolicy / AuditRegistrationPolicy | RegistrationPolicy | 实现 | 虚线 + 空心三角 |
| 策略提供者实现 | PolicyRegistry | PolicyProvider | 实现 | 虚线 + 空心三角 |
| 通知解耦 | RegistrationEventPublisher | RegistrationObserver | 关联 | 1 — 0..* |
| 观察者实现 | MessageObserver | RegistrationObserver | 实现 | 虚线 + 空心三角 |
| 消息创建 | MessageObserver | Message | 依赖 | 构造消息 |
| 消息持久化 | MessageObserver | MessageRepository | 依赖 | save |
| 消息归属 | Message | Student / Activity | 关联（属性表示） | * — 1；未画连线 |

## 3. 依赖方向

| 依赖方 | 被依赖方 | 原因 |
|---|---|---|
| RegistrationService | StudentRepository / ActivityRepository / RegistrationRepository | 读取/保存 |
| RegistrationService | PolicyProvider | 取策略（依赖接口，不再依赖 PolicyRegistry 具体类） |
| RegistrationService | RegistrationPolicy | 使用返回的策略接口 |
| RegistrationService | CapacityChecker | 公共名额检查 |
| RegistrationService | RegistrationEventPublisher | 发布事件 |
| CapacityChecker | RegistrationRepository | count_approved |
| PolicyProvider | RegistrationPolicy | 返回策略 |
| PolicyRegistry | RegistrationPolicy | 登记/返回 |
| RegistrationEventPublisher | RegistrationEvent / RegistrationObserver | 发布事件、通知观察者 |
| MessageObserver | RegistrationObserver / Message / MessageRepository | 实现观察者、构造并保存消息 |
| ActivityService | ActivityRepository / Activity | 活动 CRUD |
| MessageService | MessageRepository / Message | 消息列表与已读 |
| MessageRepository | Message | 持久化消息 |
| **策略实现** | **CapacityChecker** | **无依赖**（方案甲检查点） |

说明：RegistrationService 仍直接依赖 CapacityChecker 与 RegistrationEventPublisher 两个领域/基础设施服务；它们是组合根注入的具体类，不随报名规则变化。DIP 只对“变化点”（策略、仓储、观察者）强制抽象；这一点在 07 设计说明中同步说明。

## 4. 修复审前自查问题

| 问题 | 修复 |
|---|---|
| UC-01/02 无服务承接 | 新增 ActivityService（create/update/soft_delete/list/get） |
| UC-06 消息只写不读 | 新增 MessageRepository + MessageService（list/mark_read） |
| UC-07 缺待审核数 | RegistrationRepository 增加 count_pending |
| MessageObserver 直接持久化 | 改为依赖 MessageRepository.save |
| Service 依赖具体 PolicyRegistry | 抽出 PolicyProvider 接口，Registry 实现 |
| 策略接口缺上下文 | decide(activity, student) |
| DIP 表述过头 | §3 明确“变化点抽象、基础设施具体类注入” |
| 重复/取消/审批冲突边界 | 由报名/审批时序图 v1.3 与取消时序图 v1.0 补齐 |
| save 双语义 | 拆出 confirm_approval（v1.3）；save 只创建/简单状态更新 |

## 5. 状态枚举

| 状态 | 含义 | 迁移 |
|---|---|---|
| PENDING | 审核型提交 | → APPROVED / REJECTED / CANCELLED |
| APPROVED | 报名成功，占名额 | → CANCELLED（且活动未开始，或按 Q-03：开始后仅待审核可取消） |
| REJECTED | 审批拒绝 | 终态；可重新申请（新建记录） |
| CANCELLED | 学生取消 | 终态；可重新申请（新建记录） |

## 6. 持久类清单

Student、Activity、Registration、Message 四个实体持久化；其余为服务/策略/仓储/事件类。

## 7. UC → 类 / 操作追踪（补全）

| UC | 主要类 / 操作 |
|---|---|
| UC-01 管理活动 | ActivityService.create/update/soft_delete、ActivityRepository |
| UC-02 浏览活动 | ActivityService.list/get、ActivityRepository、RegistrationRepository.count_approved（余量） |
| UC-03 报名 | RegistrationService.submit、PolicyProvider.get、RegistrationPolicy.decide、CapacityChecker、RegistrationRepository、Publisher |
| UC-04 审批 | RegistrationService.approve/reject、CapacityChecker、RegistrationRepository、Publisher |
| UC-05 取消 | RegistrationService.cancel、RegistrationRepository、ActivityRepository（活动开始判断） |
| UC-06 消息 | MessageService.list/mark_read、MessageRepository、Message |
| UC-07 统计 | RegistrationRepository.count_approved/count_pending、ActivityRepository |

## 8. 自检

- 21 个类/接口；每个有职责与操作/属性；无孤立类。
- 策略、仓储、观察者依赖抽象；CapacityChecker/Publisher 具体类已说明。
- 重复通知防护、软删除、取消规则、统计口径均有落点。
- 评审已通过（2026-11-22，评审人王以欣）；可进入编码。

## 9. 设计构造类追溯

| 类 / 接口 | 来源 |
|---|---|
| PolicyProvider / PolicyRegistry | 3.3-B 策略选择 |
| CapacityChecker | Q-07 / 3.3-B（公共名额规则） |
| RegistrationEvent / Publisher / Observer | 3.3-C 事件分发 |
| StudentRepository / ActivityRepository / RegistrationRepository / MessageRepository | B.2-7 持久化 + DIP |
| ActivityService | UC-01 / UC-02 |
| MessageService | UC-06 |
| StudentRepository（仅 find_by_id） | 学生查询；为 DIP/测试保留，属薄接口 |

## 10. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.1 | 2026-11-22 | 17 类；加 2 仓储/Registry/Event |
| v1.2 | 2026-11-22 | 补 ActivityService/MessageService/MessageRepository/PolicyProvider；count_pending；decide 上下文；修 DIP 表述 |
| v1.3 | 2026-11-22 | 拆 confirm_approval（审批原子确认）；save 只保留创建/简单状态更新 |
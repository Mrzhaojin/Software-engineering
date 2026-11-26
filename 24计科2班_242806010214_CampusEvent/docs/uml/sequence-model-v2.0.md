# CampusEvent 时序模型 v2.0（CR-01 + CR-02）

> 版本：v2.0 ｜ 日期：2026-11-26 ｜ 基线：baseline-v1 ｜ 分支：change-v2
> 对应图：sequence-signup-v2.0.drawio、sequence-approval-v2.0.drawio
> 说明：v2.0 图聚焦 CR-01/CR-02 的变更分支；公共校验（学生/活动存在、开始时间、重复报名）与失败返回沿用 sequence-signup-v1.2 / sequence-approval-v1.3。

## 1. 报名时序 v2.0（年级限定 + 邮件）

参与者：Student、RegistrationService、PolicyProvider、GradeLimitedDirectPolicy、CapacityChecker、RegistrationRepository、RegistrationEventPublisher、MessageObserver、EmailObserver、EmailLogRepository、MockEmailSender。

| 消息 | 发送→接收 | 内容 |
|---|---|---|
| 1 | Student→Service | submit(student_id, activity_id) |
| 2 | Service→Provider | get(activity) |
| 3 | Provider→Service | 返回 GradeLimitedDirectPolicy（direct + grade_limited=1） |
| 4 | Service→Policy | decide(activity, student) |
| 5 | Policy→Service | grade∉{2,3} 时抛 PolicyRejectedError |
| 6 | Service→Student | 报名失败：“仅限大二、大三学生报名” |
| 7 | Policy→Service | grade∈{2,3} 时 APPROVED |
| 8–11 | Service/Capacity/RegRepo | ensure_available → count_approved → ok |
| 12–13 | Service→RegRepo | save(APPROVED) → Registration |
| 14 | Service→Publisher | publish(event) |
| 15 | Publisher→MessageObserver | on_registration_event（事务内） |
| 16 | Publisher→EmailObserver | on_registration_event（观察者最后） |
| 17–18 | EmailObserver→EmailLogRepo | find_by_event_key → 空 |
| 19–20 | EmailObserver→MockEmailSender | send(recipient, subject, content) → sent |
| 21 | EmailObserver→EmailLogRepo | save(EmailLog SENT) |
| 22–23 | EmailObserver→EmailLogRepo | 邮件失败时 catch，save(FAILED, error)，不抛出 |
| 24 | Service→Student | Registration 成功；邮件失败不影响报名 |

约束：名额/开始时间/重复报名仍由公共流程保证；年级策略只拒绝不符合年级者；邮件失败不改变报名状态。

## 2. 审批时序 v2.0（邮件）

参与者：Admin、RegistrationService、CapacityChecker、RegistrationRepository、Publisher、MessageObserver、EmailObserver、EmailLogRepository、MockEmailSender。

| 分支/消息 | 内容 |
|---|---|
| 1–3 | Admin 触发 approve/reject；Service 读取 Registration |
| 4–9 | 批准：ensure_available → count → confirm_approval；条件更新 0 行则冲突 |
| 10–11 | 拒绝：save(REJECTED) |
| 12 | publish(event)：APPROVAL_APPROVED / APPROVAL_REJECTED |
| 13 | MessageObserver 写站内消息（事务内） |
| 14–16 | EmailObserver 查 event_key 去重 |
| 17–21 | 邮件成功：send → save(SENT)；邮件失败：catch → save(FAILED) |
| 22 | Admin 看到审批结果；邮件失败不回滚 |

约束：审批并发仍由 confirm_approval 条件更新 + 唯一约束兜底；站内消息失败仍回滚（Q-04）；邮件失败只记录。

## 3. 追踪

| 测试 | 覆盖 |
|---|---|
| CR1-01/02 | 大二/大三通过（消息 7–13） |
| CR1-03/04 | 大一/大四拒绝（消息 5–6） |
| CR1-05 | 原 C1–C10 回归 |
| CR2-01 | 直接报名：站内+邮件（消息 14–21） |
| CR2-02 | 审批通过/拒绝：站内+邮件 |
| CR2-03 | 邮件失败：报名状态正确、FAILED 日志（消息 22–23） |
| CR2-04 | event_key 唯一，不重复 |
| CR2-05 | 原 C1–C10 回归 |

## 4. 版本

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.2/v1.3 | 2026-11-22 | 初始报名/审批时序 |
| v2.0 | 2026-11-26 | CR-01 年级拒绝分支；CR-02 邮件观察者/日志/失败不回滚 |

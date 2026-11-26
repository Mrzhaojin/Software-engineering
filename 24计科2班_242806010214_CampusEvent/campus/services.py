from datetime import datetime
import sqlite3
import uuid

from .errors import ValidationError, NotFoundError, ConflictError
from .events import RegistrationEvent


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _parse_dt(value):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError("时间格式不正确，请使用 YYYY-MM-DDTHH:MM")


class ActivityService:
    def __init__(self, activity_repo, db):
        self.activity_repo = activity_repo
        self.db = db

    def _validate(self, data):
        title = (data.get("title") or "").strip()
        category = (data.get("category") or "").strip()
        location = (data.get("location") or "").strip()
        policy_type = data.get("policy_type")
        try:
            capacity = int(data.get("capacity") or 0)
        except ValueError:
            raise ValidationError("人数上限必须是正整数")
        if not title or not category or not location:
            raise ValidationError("名称、类型、地点不能为空")
        if len(title) > 100 or len(category) > 60:
            raise ValidationError("名称/类型过长")
        if capacity <= 0:
            raise ValidationError("人数上限必须是正整数")
        if policy_type not in ("direct", "audit"):
            raise ValidationError("报名方式不正确")
        start_at = _parse_dt(data.get("start_at"))
        grade_limited = 1 if str(data.get("grade_limited") or "").lower() in ("1", "on", "true") else 0
        if grade_limited and policy_type != "direct":
            raise ValidationError("年级限定只能用于直接报名活动")
        return {
            "title": title,
            "category": category,
            "location": location,
            "capacity": capacity,
            "policy_type": policy_type,
            "grade_limited": grade_limited,
            "start_at": start_at.isoformat(timespec="minutes"),
        }

    def create(self, data):
        clean = self._validate(data)
        activity = {
            "activity_id": uuid.uuid4().hex,
            **clean,
            "deleted_at": None,
        }
        with self.db:
            self.activity_repo.save(activity)
        return activity

    def update(self, activity_id, data):
        existing = self.activity_repo.find_by_id(activity_id)
        if existing is None or existing["deleted_at"]:
            raise NotFoundError("活动不存在")
        clean = self._validate(data)
        activity = {
            "activity_id": activity_id,
            **clean,
            "deleted_at": existing["deleted_at"],
        }
        with self.db:
            self.activity_repo.save(activity)
        return activity

    def soft_delete(self, activity_id):
        with self.db:
            if not self.activity_repo.soft_delete(activity_id):
                raise NotFoundError("活动不存在或已下线")

    def get(self, activity_id, include_deleted=False):
        activity = self.activity_repo.find_by_id(activity_id)
        if activity is None or (activity["deleted_at"] and not include_deleted):
            raise NotFoundError("活动不存在")
        return activity

    def list(self, name=None):
        return self.activity_repo.list_active(name)


class RegistrationService:
    def __init__(self, student_repo, activity_repo, registration_repo,
                 policy_provider, capacity_checker, publisher, db):
        self.student_repo = student_repo
        self.activity_repo = activity_repo
        self.registration_repo = registration_repo
        self.policy_provider = policy_provider
        self.capacity_checker = capacity_checker
        self.publisher = publisher
        self.db = db

    def submit(self, student_id, activity_id):
        with self.db:
            student = self.student_repo.find_by_id(student_id)
            if student is None:
                raise NotFoundError("学生不存在")
            activity = self.activity_repo.find_by_id(activity_id)
            if activity is None or activity["deleted_at"]:
                raise NotFoundError("活动不存在")
            if datetime.fromisoformat(activity["start_at"]) <= datetime.now():
                raise ConflictError("活动已开始，不能报名")
            if self.registration_repo.find_active(student_id, activity_id):
                raise ConflictError("你已报名该活动，不能重复报名")

            policy = self.policy_provider.get(activity)
            status = policy.decide(activity, student)
            if status == "APPROVED":
                self.capacity_checker.ensure_available(activity)

            registration = {
                "registration_id": uuid.uuid4().hex,
                "activity_id": activity_id,
                "student_id": student_id,
                "status": status,
                "created_at": _now(),
                "updated_at": _now(),
            }
            try:
                self.registration_repo.save(registration)
            except sqlite3.IntegrityError:
                raise ConflictError("你已报名该活动，不能重复报名")

            event_type = "SIGNUP_APPROVED" if status == "APPROVED" else "SIGNUP_PENDING"
            self.publisher.publish(RegistrationEvent(
                event_type=event_type,
                registration_id=registration["registration_id"],
                student_id=student_id,
                activity_id=activity_id,
                result_status=status,
            ))
            return registration

    def approve(self, registration_id, admin_id):
        with self.db:
            registration = self.registration_repo.find_by_id(registration_id)
            if registration is None or registration["status"] != "PENDING":
                raise ConflictError("该报名不在待审核状态")
            activity = self.activity_repo.find_by_id(registration["activity_id"])
            if activity is None or activity["deleted_at"]:
                raise NotFoundError("活动不存在")
            self.capacity_checker.ensure_available(activity)
            if not self.registration_repo.confirm_approval(registration_id, activity["capacity"]):
                raise ConflictError("批准失败：名额已满或报名已被处理")
            self.publisher.publish(RegistrationEvent(
                event_type="APPROVAL_APPROVED",
                registration_id=registration_id,
                student_id=registration["student_id"],
                activity_id=registration["activity_id"],
                result_status="APPROVED",
            ))
            return registration

    def reject(self, registration_id, admin_id):
        with self.db:
            registration = self.registration_repo.find_by_id(registration_id)
            if registration is None or registration["status"] != "PENDING":
                raise ConflictError("该报名不在待审核状态")
            registration = dict(registration)
            registration["status"] = "REJECTED"
            registration["updated_at"] = _now()
            self.registration_repo.save(registration)
            self.publisher.publish(RegistrationEvent(
                event_type="APPROVAL_REJECTED",
                registration_id=registration_id,
                student_id=registration["student_id"],
                activity_id=registration["activity_id"],
                result_status="REJECTED",
            ))
            return registration

    def cancel(self, registration_id, student_id):
        with self.db:
            registration = self.registration_repo.find_by_id(registration_id)
            if registration is None or registration["student_id"] != student_id:
                raise NotFoundError("报名不存在")
            if registration["status"] not in ("PENDING", "APPROVED"):
                raise ConflictError("该报名当前不能取消")
            activity = self.activity_repo.find_by_id(registration["activity_id"])
            if activity is None:
                raise NotFoundError("活动不存在")
            started = datetime.fromisoformat(activity["start_at"]) <= datetime.now()
            if started and registration["status"] == "APPROVED":
                raise ConflictError("活动已开始，已通过报名不能取消")
            registration = dict(registration)
            registration["status"] = "CANCELLED"
            registration["updated_at"] = _now()
            self.registration_repo.save(registration)
            return registration


class MessageService:
    def __init__(self, message_repo, db):
        self.message_repo = message_repo
        self.db = db

    def list(self, student_id):
        return self.message_repo.list_by_student(student_id)

    def mark_read(self, message_id, student_id):
        with self.db:
            if not self.message_repo.mark_read(message_id, student_id):
                raise NotFoundError("消息不存在")
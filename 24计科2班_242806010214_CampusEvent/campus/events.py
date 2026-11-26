from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod
import logging
import uuid

from .repositories import MessageRepository


@dataclass
class RegistrationEvent:
    event_type: str
    registration_id: str
    student_id: str
    activity_id: str
    result_status: str
    occurred_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)


class RegistrationObserver(ABC):
    @abstractmethod
    def on_registration_event(self, event):
        raise NotImplementedError


class RegistrationEventPublisher:
    def __init__(self, observers=None):
        self.observers = list(observers or [])

    def subscribe(self, observer):
        self.observers.append(observer)

    def publish(self, event):
        for observer in self.observers:
            observer.on_registration_event(event)


CONTENT = {
    "SIGNUP_APPROVED": "报名成功：活动报名已通过。",
    "SIGNUP_PENDING": "报名已提交，等待管理员审核。",
    "APPROVAL_APPROVED": "审核结果：您的报名已通过。",
    "APPROVAL_REJECTED": "审核结果：您的报名已被拒绝。",
}


class MessageObserver(RegistrationObserver):
    def __init__(self, message_repo: MessageRepository):
        self.message_repo = message_repo

    def on_registration_event(self, event):
        self.message_repo.save({
            "message_id": uuid.uuid4().hex,
            "student_id": event.student_id,
            "activity_id": event.activity_id,
            "content": CONTENT.get(event.event_type, "报名状态更新。"),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "is_read": 0,
            "event_key": f"{event.event_type}:{event.registration_id}",
        })


EMAIL_SUBJECTS = {
    "SIGNUP_APPROVED": "报名成功通知",
    "APPROVAL_APPROVED": "审核通过通知",
    "APPROVAL_REJECTED": "审核拒绝通知",
}
EMAIL_CONTENT = {
    "SIGNUP_APPROVED": "你的活动报名已通过。",
    "APPROVAL_APPROVED": "你报名的活动已通过管理员审核。",
    "APPROVAL_REJECTED": "你报名的活动未通过管理员审核。",
}
EMAIL_EVENTS = {"SIGNUP_APPROVED", "APPROVAL_APPROVED", "APPROVAL_REJECTED"}


class EmailObserver(RegistrationObserver):
    """CR-02: mock email notification; failures are logged, never propagated."""

    def __init__(self, sender, email_repo):
        self.sender = sender
        self.email_repo = email_repo

    def on_registration_event(self, event):
        if event.event_type not in EMAIL_EVENTS:
            return
        event_key = f"{event.event_type}:{event.registration_id}"
        if self.email_repo.find_by_event_key(event_key):
            return
        recipient = f"{event.student_id}@campus.demo"
        subject = EMAIL_SUBJECTS[event.event_type]
        content = EMAIL_CONTENT[event.event_type]
        status = "SENT"
        error = None
        try:
            self.sender.send(recipient, subject, content)
        except Exception as exc:  # CR2-03: never re-raise
            status = "FAILED"
            error = str(exc)
            logging.getLogger(__name__).exception("mock email failed: %s", event_key)
        try:
            self.email_repo.save({
                "log_id": uuid.uuid4().hex,
                "registration_id": event.registration_id,
                "event_type": event.event_type,
                "recipient": recipient,
                "subject": subject,
                "content": content,
                "status": status,
                "error": error,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "event_key": event_key,
            })
        except Exception:
            logging.getLogger(__name__).exception("failed to persist email log: %s", event_key)

from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod
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

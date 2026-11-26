from abc import ABC, abstractmethod

from .errors import PolicyRejectedError


class RegistrationPolicy(ABC):
    @abstractmethod
    def decide(self, activity, student):
        """Return RegistrationStatus for the submission."""
        raise NotImplementedError


class DirectRegistrationPolicy(RegistrationPolicy):
    def decide(self, activity, student):
        return "APPROVED"


class AuditRegistrationPolicy(RegistrationPolicy):
    def decide(self, activity, student):
        return "PENDING"


class GradeLimitedDirectPolicy(RegistrationPolicy):
    """CR-01: compose direct registration with a grade eligibility rule."""

    def __init__(self, inner=None):
        self.inner = inner or DirectRegistrationPolicy()

    def decide(self, activity, student):
        if student["grade"] not in (2, 3):
            raise PolicyRejectedError("该活动仅限大二、大三学生报名")
        return self.inner.decide(activity, student)


class PolicyProvider(ABC):
    @abstractmethod
    def get(self, activity):
        raise NotImplementedError


class PolicyRegistry(PolicyProvider):
    def __init__(self):
        self._policies = {}
        self._grade_limited_policy = GradeLimitedDirectPolicy()

    def register(self, policy_type, policy):
        self._policies[policy_type] = policy

    def get(self, activity):
        policy_type = activity["policy_type"]
        if policy_type == "direct" and activity["grade_limited"]:
            return self._grade_limited_policy
        if policy_type not in self._policies:
            raise ValueError(f"unknown policy_type: {policy_type}")
        return self._policies[policy_type]

    @classmethod
    def default(cls):
        registry = cls()
        registry.register("direct", DirectRegistrationPolicy())
        registry.register("audit", AuditRegistrationPolicy())
        return registry

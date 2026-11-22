from abc import ABC, abstractmethod


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


class PolicyProvider(ABC):
    @abstractmethod
    def get(self, policy_type):
        raise NotImplementedError


class PolicyRegistry(PolicyProvider):
    def __init__(self):
        self._policies = {}

    def register(self, policy_type, policy):
        self._policies[policy_type] = policy

    def get(self, policy_type):
        if policy_type not in self._policies:
            raise ValueError(f"unknown policy_type: {policy_type}")
        return self._policies[policy_type]

    @classmethod
    def default(cls):
        registry = cls()
        registry.register("direct", DirectRegistrationPolicy())
        registry.register("audit", AuditRegistrationPolicy())
        return registry

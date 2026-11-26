class DomainError(Exception):
    pass


class ValidationError(DomainError):
    pass


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class CapacityExceededError(DomainError):
    pass


class PolicyRejectedError(DomainError):
    pass

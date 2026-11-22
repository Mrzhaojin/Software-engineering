from .errors import CapacityExceededError


class CapacityChecker:
    def __init__(self, registration_repo):
        self.registration_repo = registration_repo

    def remaining(self, activity):
        return max(0, activity["capacity"] - self.registration_repo.count_approved(activity["activity_id"]))

    def ensure_available(self, activity):
        if self.registration_repo.count_approved(activity["activity_id"]) >= activity["capacity"]:
            raise CapacityExceededError("名额已满")

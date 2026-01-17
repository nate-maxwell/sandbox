import json
from typing import DefaultDict


class AuditTable(object):
    def __init__(self) -> None:
        self._table: dict[str, list["AuditItem"]] = DefaultDict(list)

    def add_to_namespace(self, namespace: str, item: "AuditItem") -> None:
        self._table[namespace].append(item)

    def to_dict(self) -> dict:
        return {
            namespace: [item.to_dict() for item in items]
            for namespace, items in self._table.items()
        }


AUDIT_TABLE = AuditTable()


class AuditItem(object):

    def __init__(self, namespace: str) -> None:
        AUDIT_TABLE.add_to_namespace(namespace, self)

    def to_dict(self) -> dict:
        return self.__dict__


# -----------------------------------------------------------------------------


class DefaultSGSettings(AuditItem):
    def __init__(self) -> None:
        super().__init__("SGSettings")
        self.default_status = "ip"
        self.default_priority = 1
        self.default_duration = 5


class AnimationTaskSettings(DefaultSGSettings):
    def __init__(self) -> None:
        super().__init__()
        self.default_status = "wtg"
        self.task_type = "Animation"
        self.department = "ANM"
        self.default_duration = 10


class ModelingTaskSettings(DefaultSGSettings):
    def __init__(self) -> None:
        super().__init__()
        self.default_status = "rdy"
        self.task_type = "Modeling"
        self.department = "MDL"
        self.default_priority = 2
        self.default_duration = 8


class RiggingTaskSettings(DefaultSGSettings):
    def __init__(self) -> None:
        super().__init__()
        self.default_status = "wtg"
        self.task_type = "Rigging"
        self.department = "RIG"
        self.default_priority = 3
        self.default_duration = 15


class LightingTaskSettings(DefaultSGSettings):
    def __init__(self) -> None:
        super().__init__()
        self.default_status = "ip"
        self.task_type = "Lighting"
        self.department = "LGT"
        self.default_priority = 1
        self.default_duration = 7


# -----------------------------------------------------------------------------


AnimationTaskSettings()
ModelingTaskSettings()
RiggingTaskSettings()
LightingTaskSettings()


print(json.dumps(AUDIT_TABLE.to_dict(), indent=4))

output = """
{
    "SGSettings": [
        {
            "default_status": "wtg",
            "default_priority": 1,
            "default_duration": 10,
            "task_type": "Animation",
            "department": "ANM"
        },
        {
            "default_status": "rdy",
            "default_priority": 2,
            "default_duration": 8,
            "task_type": "Modeling",
            "department": "MDL"
        },
        {
            "default_status": "wtg",
            "default_priority": 3,
            "default_duration": 15,
            "task_type": "Rigging",
            "department": "RIG"
        },
        {
            "default_status": "ip",
            "default_priority": 1,
            "default_duration": 7,
            "task_type": "Lighting",
            "department": "LGT"
        }
    ]
}
"""

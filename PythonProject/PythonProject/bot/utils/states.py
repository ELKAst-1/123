from enum import Enum

class UserStates(Enum):
    FIRST_NAME = 1
    LAST_NAME = 2
    GROUP = 3
    PURPOSE = 4
    FILE = 5

class AdminStates(Enum):
    VIEW_REQUESTS = 1
    MANAGE_GROUPS = 2
    MANAGE_PURPOSES = 3
    ADD_GROUP = 4
    REMOVE_GROUP = 5
    ADD_PURPOSE = 6
    REMOVE_PURPOSE = 7

from enum import Enum


class PrivateQuestion(str, Enum):
    FAVORITE_FRUIT = "FAVORITE_FRUIT"
    BEST_FRIEND = "BEST_FRIEND"
    FIRST_PET = "FIRST_PET"
    FAVORITE_TEACHER = "FAVORITE_TEACHER"
    BIRTH_CITY = "BIRTH_CITY"

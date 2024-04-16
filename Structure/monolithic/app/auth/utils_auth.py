import datetime
import re

from core.utils import tokey
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


def bypass_token_request(phonenumber):
    return bool(re.search(settings.BYPASS_PHONENUMBER_REGEX, phonenumber))


def is_banned_phonenumber(phonenumber):
    hashed_phonenumber = tokey(phonenumber.country_code, phonenumber.national_number)
    if User.objects.filter(phonenumber_meta=hashed_phonenumber).exists():
        return True


def get_age(born):
    today = datetime.date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def get_dob_from_str(dob, fmt="%Y%m%d"):
    return datetime.datetime.strptime(dob, fmt)

from decimal import Decimal
from decimal import ROUND_HALF_UP

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


def get_business_managers_group_name(business_id):
    return f"business_{business_id}_managers"


def money_quantize(amount) -> Decimal:
    return Decimal(amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


_COUNTRY_NAME_TO_CODE = {
    "United States": "US",
    "Canada": "CA",
    "United Kingdom": "GB",
    "Australia": "AU",
    "New Zealand": "NZ",
    "South Africa": "ZA",
    "India": "IN",
    "China": "CN",
    "Japan": "JP",
    "Korea": "KR",
    "Thailand": "TH",
    "Vietnam": "VN",
    "France": "FR",
    "Germany": "DE",
    "Italy": "IT",
    "Spain": "ES",
    "Netherlands": "NL",
    "Belgium": "BE",
    "Switzerland": "CH",
    "Austria": "AT",
    "Sweden": "SE",
    "Norway": "NO",
    "Denmark": "DK",
    "Finland": "FI",
    "Iceland": "IS",
    "Ireland": "IE",
    "Portugal": "PT",
    "Greece": "GR",
    "Czech Republic": "CZ",
    "Slovakia": "SK",
    "Poland": "PL",
    "Romania": "RO",
    "Bulgaria": "BG",
    "Hungary": "HU",
}


def country_name_to_code(country_name: str, default: str = "CA") -> str:
    return _COUNTRY_NAME_TO_CODE.get(country_name, default)


def get_reminder_schedule_name(business_id: int, appointment_id: int, channel='sms') -> str:
    return f"reminder-{channel}-{business_id}-{appointment_id}"

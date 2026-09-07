"""Answers to simple system questions (time, date) — read straight from the
PC's own clock, no network involved."""

import datetime

WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
             "August", "September", "Oktober", "November", "Dezember"]


def current_time_text() -> str:
    now = datetime.datetime.now()
    return f"Es ist {now.hour} Uhr {now.minute:02d}"


def current_date_text() -> str:
    now = datetime.datetime.now()
    weekday = WEEKDAYS_DE[now.weekday()]
    month = MONTHS_DE[now.month - 1]
    return f"Heute ist {weekday}, der {now.day}. {month} {now.year}"


def answer(query: str) -> str:
    if query == "time":
        return current_time_text()
    if query == "date":
        return current_date_text()
    return "Das weiß ich nicht."

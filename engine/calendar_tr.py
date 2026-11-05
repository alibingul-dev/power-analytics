"""Türkiye day types for the hourly/daily profile: 0 = working day, 1 = Saturday or half-day eve (arife),
2 = Sunday or public holiday. Dates are Europe/Istanbul (UTC+3, no daylight saving since 2016).

Religious holidays move ~11 days a year, so they come from this table, not from past calendars.
2017-2027: Diyanet dates. 2028: astronomical estimate, Diyanet calendar not yet published (marked).
"""
from datetime import date, timedelta

FIXED = ["01-01", "04-23", "05-01", "05-19", "07-15", "08-30", "10-29"]
RAMAZAN = {2017: "06-25", 2018: "06-15", 2019: "06-04", 2020: "05-24", 2021: "05-13", 2022: "05-02",
           2023: "04-21", 2024: "04-10", 2025: "03-30", 2026: "03-20", 2027: "03-09", 2028: "02-26"}
KURBAN = {2017: "09-01", 2018: "08-21", 2019: "08-11", 2020: "07-31", 2021: "07-20", 2022: "07-09",
          2023: "06-28", 2024: "06-16", 2025: "06-06", 2026: "05-27", 2027: "05-16", 2028: "05-05"}
ESTIMATED_YEARS = {2028}


def _holidays():
    hol, eve = set(), set()
    for y in range(2017, 2029):
        for md in FIXED:
            if md == "07-15" and y < 2017:
                continue
            hol.add(date.fromisoformat(f"{y}-{md}"))
        eve.add(date(y, 10, 28))
        for table, n in ((RAMAZAN, 3), (KURBAN, 4)):
            d0 = date.fromisoformat(f"{y}-{table[y]}")
            eve.add(d0 - timedelta(days=1))
            for k in range(n):
                hol.add(d0 + timedelta(days=k))
    return hol, eve - hol


HOLIDAYS, EVES = _holidays()


def day_type(d):
    if d in HOLIDAYS or d.weekday() == 6:
        return 2
    if d in EVES or d.weekday() == 5:
        return 1
    return 0


DAY_TYPE_NAMES = {"tr": ["iş günü", "Cumartesi / arife", "Pazar / tatil"],
                  "en": ["working day", "Saturday / eve", "Sunday / holiday"]}

"""Deterministic fallback parser and repair logic for LLM interpretation."""

import re
from typing import Any
from app.schemas.interpretation import DirectiveInterpretation, DirectiveType


def parse_time_window(text: str) -> list[int]:
    """Extracts whole-hour time intervals [start, end) from text."""
    lower = text.lower()

    # Word to number mapping
    word_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
        "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
        "noon": 12, "midnight": 0,
    }

    def to_24h(hour_val: int | str, meridian: str | None) -> int:
        if isinstance(hour_val, str):
            hour_val = word_to_num.get(hour_val, int(hour_val))
        if meridian == "pm" and hour_val < 12:
            return hour_val + 12
        if meridian == "am" and hour_val == 12:
            return 0
        return hour_val

    # Pattern: 13:00 to 15:00 / 13:00 and 15:00
    m24 = re.search(r'(\d{1,2}):00\s*(?:to|until|and|-)\s*(\d{1,2}):00', lower)
    if m24:
        s, e = int(m24.group(1)), int(m24.group(2))
        return list(range(s, e))

    # Pattern: noon until 2 PM / 10 AM until noon
    m_noon1 = re.search(r'noon\s*(?:until|to|and|-)\s*(\d{1,2})\s*(am|pm)', lower)
    if m_noon1:
        s = 12
        e = to_24h(int(m_noon1.group(1)), m_noon1.group(2))
        return list(range(s, e))

    m_noon2 = re.search(r'(\d{1,2})\s*(am|pm)\s*(?:until|to|and|-)\s*noon', lower)
    if m_noon2:
        s = to_24h(int(m_noon2.group(1)), m_noon2.group(2))
        e = 12
        return list(range(s, e))

    # Pattern: "from one until three" (words)
    m_words = re.search(r'(?:from|between)?\s*(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*(?:until|to|and|-)\s*(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)', lower)
    if m_words:
        w1, w2 = m_words.group(1), m_words.group(2)
        # Typically afternoon if context implies 1-3 PM
        s = word_to_num[w1]
        e = word_to_num[w2]
        if s < 12 and ("panel washing" in lower or "afternoon" in lower or "solar" in lower):
            s += 12
            e += 12
        return list(range(s, e))

    # Pattern: 1-3 PM or 1 to 3 PM or 1 PM to 3 PM
    # e.g., "1 PM to 3 PM", "2 AM until 5 AM", "6 PM until 9 PM", "11 AM and 2 PM", "1-3 PM"
    m_meridian = re.search(r'(\d{1,2})\s*(am|pm)?\s*(?:until|to|and|-)\s*(\d{1,2})\s*(am|pm)', lower)
    if m_meridian:
        h1 = int(m_meridian.group(1))
        m1 = m_meridian.group(2)
        h2 = int(m_meridian.group(3))
        m2 = m_meridian.group(4)
        if m1 is None:
            m1 = m2  # inherit meridian if omitted on first hour (e.g. 1-3 PM)
        s = to_24h(h1, m1)
        e = to_24h(h2, m2)
        return list(range(s, e))

    return []


def fallback_parse_note(
    note: str,
    note_index: int,
    battery_capacity_kwh: float,
) -> DirectiveInterpretation:
    """Deterministically extracts structured directives from natural language note."""
    lower = note.lower()

    # 1. Distractors / no-op checks
    distractor_keywords = [
        "cafeteria", "menu", "sports office", "registration deadline", "seminar room",
        "booking", "library", "book-return", "club notices", "student affairs",
        "next week", "next month", "tomorrow"
    ]
    is_energy_related = any(k in lower for k in ["solar", "battery", "grid", "charge", "discharge", "feeder", "transformer", "inverter", "substation", "pv "])
    if any(k in lower for k in distractor_keywords) and not is_energy_related:
        return DirectiveInterpretation(
            note_index=note_index,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="This note does not affect today's 24-hour energy schedule.",
        )

    # 2. Solar Reduction
    if any(k in lower for k in ["solar", "rooftop solar", "pv production", "panel washing", "inverter work"]) and any(
        k in lower for k in ["wash", "clean", "drop", "fall", "reduc", "cloud", "leave", "forecast"]
    ):
        hours = parse_time_window(note)
        factor = 1.0

        # Check for reduction percentage vs remaining percentage
        m_red = re.search(r'(\d{1,2})%\s*reduction', lower)
        if m_red:
            reduction_pct = float(m_red.group(1))
            factor = round((100.0 - reduction_pct) / 100.0, 4)
        else:
            m_pct = re.search(r'(?:to|roughly|about)?\s*(\d{1,2})%', lower)
            if m_pct:
                factor = round(float(m_pct.group(1)) / 100.0, 4)
            elif "half" in lower:
                factor = 0.5
            elif "one-fifth" in lower:
                factor = 0.2
            elif "one-fourth" in lower or "one-quarter" in lower:
                factor = 0.25

        return DirectiveInterpretation(
            note_index=note_index,
            applies=True,
            directive_type=DirectiveType.SOLAR_REDUCTION,
            structured_adjustment={"hours": hours, "factor": factor},
            explanation=f"Solar availability is reduced to {factor*100:.0f}% during the specified window.",
        )

    # 3. Minimum Battery Reserve
    if ("battery" in lower or "data center" in lower) and any(
        k in lower for k in ["at least", "reserve", "remain in the battery", "stored in the battery"]
    ):
        hours = parse_time_window(note)
        min_kwh = 0.0

        # Check percentage
        m_pct = re.search(r'(\d{1,3})%\s*(?:of the battery capacity)?', lower)
        if m_pct:
            pct = float(m_pct.group(1))
            min_kwh = round((pct / 100.0) * battery_capacity_kwh, 2)
        else:
            m_kwh = re.search(r'(\d+(?:\.\d+)?)\s*kwh', lower)
            if m_kwh:
                min_kwh = float(m_kwh.group(1))

        return DirectiveInterpretation(
            note_index=note_index,
            applies=True,
            directive_type=DirectiveType.MINIMUM_BATTERY_RESERVE,
            structured_adjustment={"hours": hours, "minimum_energy_kwh": min_kwh},
            explanation=f"A minimum reserve of {min_kwh} kWh is maintained during the stated hours.",
        )

    # 4. No Charge Window
    if ("charger" in lower or "charging" in lower) and any(
        k in lower for k in ["isolated", "unavailable", "disabled", "maintenance", "outage", "do not charge"]
    ):
        hours = parse_time_window(note)
        return DirectiveInterpretation(
            note_index=note_index,
            applies=True,
            directive_type=DirectiveType.NO_CHARGE_WINDOW,
            structured_adjustment={"hours": hours},
            explanation="Battery charging is disabled during the specified maintenance window.",
        )

    # 5. No Discharge Window
    if ("discharge" in lower or "discharging" in lower) and any(
        k in lower for k in ["not discharge", "do not discharge", "must not discharge", "disabled", "unavailable", "testing"]
    ):
        hours = parse_time_window(note)
        return DirectiveInterpretation(
            note_index=note_index,
            applies=True,
            directive_type=DirectiveType.NO_DISCHARGE_WINDOW,
            structured_adjustment={"hours": hours},
            explanation="Battery discharging is disabled during the protection testing window.",
        )

    # 6. Max Grid Window
    if any(k in lower for k in ["grid", "feeder", "transformer", "substation", "intake"]) and any(
        k in lower for k in ["must not exceed", "limit is", "stay at or below", "capped at", "constrained"]
    ):
        hours = parse_time_window(note)
        max_grid = 0.0
        m_kwh = re.search(r'(\d+(?:\.\d+)?)\s*kwh', lower)
        if m_kwh:
            max_grid = float(m_kwh.group(1))
        return DirectiveInterpretation(
            note_index=note_index,
            applies=True,
            directive_type=DirectiveType.MAX_GRID_WINDOW,
            structured_adjustment={"hours": hours, "max_grid_kwh": max_grid},
            explanation=f"Grid import is capped at {max_grid} kWh during the restriction window.",
        )

    # Default to no_op if unknown / not applicable
    return DirectiveInterpretation(
        note_index=note_index,
        applies=False,
        directive_type=DirectiveType.NO_OP,
        structured_adjustment=None,
        explanation="This note does not affect today's energy schedule.",
    )


def fallback_parse_all(
    notes: list[str],
    battery_capacity_kwh: float,
) -> list[DirectiveInterpretation]:
    """Parses all notes using the deterministic fallback parser."""
    return [fallback_parse_note(note, idx, battery_capacity_kwh) for idx, note in enumerate(notes)]

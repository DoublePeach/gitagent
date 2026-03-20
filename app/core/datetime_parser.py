from __future__ import annotations

import re
from datetime import datetime, timedelta


WEEKDAY_MAP = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}


def _normalize_hour(hour: int, text: str) -> int:
    if any(word in text for word in ("下午", "晚上", "今晚", "傍晚")) and hour < 12:
        return hour + 12
    if "中午" in text and hour < 11:
        return hour + 12
    if "凌晨" in text and hour == 12:
        return 0
    return hour


def _extract_hour_minute(text: str) -> tuple[int, int] | None:
    match = re.search(r"(\d{1,2})(?::|点|时)(\d{1,2})?", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    if "半" in text:
        minute = 30
    return _normalize_hour(hour, text), minute


def parse_user_datetime(value: str | None) -> datetime | None:
    """将常见中文自然语言时间解析为 datetime。

    目前支持：
    - ISO / `YYYY-MM-DD HH:MM[:SS]`
    - `今晚6点` / `今天18:30`
    - `明天上午10点`
    - `这周五晚上8点` / `周五 20:00`
    """
    if not value:
        return None

    text = value.strip()
    if not text:
        return None

    # ISO / 标准日期时间
    try:
        normalized = text.replace("T", " ").replace("/", "-")
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    dt_match = re.search(
        r"(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?",
        text,
    )
    if dt_match:
        second = int(dt_match.group(6) or 0)
        return datetime(
            int(dt_match.group(1)),
            int(dt_match.group(2)),
            int(dt_match.group(3)),
            int(dt_match.group(4)),
            int(dt_match.group(5)),
            second,
        )

    hm = _extract_hour_minute(text)
    now = datetime.now()

    if hm and any(word in text for word in ("今天", "今日", "今晚", "今夜")):
        return now.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)

    if hm and any(word in text for word in ("明天", "明晚", "明早")):
        target = now + timedelta(days=1)
        return target.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)

    week_match = re.search(r"(?:这周|本周|周|星期)([一二三四五六日天])", text)
    if hm and week_match:
        weekday = WEEKDAY_MAP[week_match.group(1)]
        days_ahead = weekday - now.weekday()
        if days_ahead < 0:
            days_ahead += 7
        target = now + timedelta(days=days_ahead)
        return target.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)

    return None

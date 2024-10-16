from datetime import datetime
from typing import Optional


def iso_to_unix(iso_str: Optional[str]) -> int:
    if not iso_str:
        return 0
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except ValueError:
        return 0

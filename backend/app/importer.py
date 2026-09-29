import csv
import io
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Episode, Quality

KNOWN_ROBOTS = {"arm-01", "arm-02", "arm-03", "mobile-01", "humanoid-01"}
REQUIRED = {"episode_id", "robot_id", "task_name", "recorded_at", "duration_seconds", "operator_name", "quality"}


def parse_datetime(value: str) -> datetime:
    cleaned = value.strip().replace("Z", "+00:00")
    for parser in (
        lambda: datetime.fromisoformat(cleaned),
        lambda: datetime.strptime(cleaned, "%d/%m/%Y %H:%M"),
        lambda: datetime.strptime(cleaned, "%Y/%m/%d %H:%M"),
    ):
        try:
            parsed = parser()
            return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc)
        except ValueError:
            continue
    raise ValueError("invalid recorded_at")


def import_csv(db: Session, raw: bytes) -> dict:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("file must be UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or not REQUIRED.issubset(set(reader.fieldnames)):
        raise ValueError(f"missing required columns: {sorted(REQUIRED - set(reader.fieldnames or []))}")

    rows = list(reader)
    ids = {str(row.get("episode_id", "")).strip().upper() for row in rows}
    existing = set(db.scalars(select(Episode.episode_id).where(Episode.episode_id.in_(ids)))) if ids else set()
    seen = set(existing)
    errors, imported = [], 0
    for line, row in enumerate(rows, start=2):
        try:
            episode_id = row["episode_id"].strip().upper()
            robot_id = row["robot_id"].strip().lower()
            task_name = " ".join(row["task_name"].strip().lower().split())
            operator_name = " ".join(row["operator_name"].strip().split()).title()
            quality = row["quality"].strip().lower()
            if not episode_id or not task_name or not operator_name:
                raise ValueError("required value is blank")
            if episode_id in seen:
                raise ValueError("duplicate episode_id")
            if robot_id not in KNOWN_ROBOTS:
                raise ValueError("unknown robot_id")
            if quality not in {item.value for item in Quality}:
                raise ValueError("invalid quality")
            duration = int(row["duration_seconds"].strip())
            if duration <= 0:
                raise ValueError("duration_seconds must be positive")
            db.add(Episode(
                episode_id=episode_id, robot_id=robot_id, task_name=task_name,
                recorded_at=parse_datetime(row["recorded_at"]), duration_seconds=duration,
                operator_name=operator_name, quality=Quality(quality),
            ))
            seen.add(episode_id)
            imported += 1
        except (ValueError, KeyError, AttributeError) as exc:
            errors.append({"line": line, "episode_id": str(row.get("episode_id", "")).strip(), "reason": str(exc)})
    db.commit()
    return {"total_rows": len(rows), "imported": imported, "skipped": len(errors), "errors": errors}


from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.calendar_utils import create_ics_file  # noqa: E402


def test_create_ics_file_contains_timezone_block(tmp_path):
    ics_path = create_ics_file(
        title="目标岗位面试",
        start_time="2025-11-25 14:30, Asia/Shanghai",
        organizer="hr@example.com",
        attendee="candidate@example.com",
        location="国创产业园",
        description="test",
        out_dir=tmp_path,
    )

    content = Path(ics_path).read_text(encoding="utf-8")
    assert "BEGIN:VTIMEZONE" in content
    assert "TZID:Asia/Shanghai" in content
    assert "DTSTART;TZID=Asia/Shanghai:20251125T143000" in content
    assert "DTEND;TZID=Asia/Shanghai:20251125T151500" in content


def test_create_ics_file_custom_output_dir(tmp_path):
    out_dir = tmp_path / "ics"
    ics_path = create_ics_file(
        title="测试",
        start_time="2025-12-01 09:00, Asia/Beijing",
        organizer="hr@example.com",
        attendee="candidate@example.com",
        location="总部会议室",
        description="请提前10分钟到场",
        out_dir=out_dir,
    )

    generated = Path(ics_path)
    assert generated.exists()
    assert generated.parent == out_dir
    content = generated.read_text(encoding="utf-8")
    assert "TZID:Asia/Beijing" in content



ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.calendar_utils import create_ics_file  # noqa: E402


def test_create_ics_file_contains_timezone_block(tmp_path):
    ics_path = create_ics_file(
        title="目标岗位面试",
        start_time="2025-11-25 14:30, Asia/Shanghai",
        organizer="hr@example.com",
        attendee="candidate@example.com",
        location="国创产业园",
        description="test",
        out_dir=tmp_path,
    )

    content = Path(ics_path).read_text(encoding="utf-8")
    assert "BEGIN:VTIMEZONE" in content
    assert "TZID:Asia/Shanghai" in content
    assert "DTSTART;TZID=Asia/Shanghai:20251125T143000" in content
    assert "DTEND;TZID=Asia/Shanghai:20251125T151500" in content


def test_create_ics_file_custom_output_dir(tmp_path):
    out_dir = tmp_path / "ics"
    ics_path = create_ics_file(
        title="测试",
        start_time="2025-12-01 09:00, Asia/Beijing",
        organizer="hr@example.com",
        attendee="candidate@example.com",
        location="总部会议室",
        description="请提前10分钟到场",
        out_dir=out_dir,
    )

    generated = Path(ics_path)
    assert generated.exists()
    assert generated.parent == out_dir
    content = generated.read_text(encoding="utf-8")
    assert "TZID:Asia/Beijing" in content




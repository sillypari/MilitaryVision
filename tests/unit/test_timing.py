from persistent_tracker.utils.timing import format_media_time


def test_media_time_formats_minutes_and_hours() -> None:
    assert format_media_time(0.0) == "00:00"
    assert format_media_time(65.0) == "01:05"
    assert format_media_time(3661.0) == "1:01:01"

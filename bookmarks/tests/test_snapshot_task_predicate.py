import pytest

from bookmarks.services.tasks import is_html_snapshot_feature_active

SNAPSHOT_STATES = [
    pytest.param(True, False, True, id="enabled"),
    pytest.param(False, False, False, id="snapshots-disabled"),
    pytest.param(True, True, False, id="background-tasks-disabled"),
]


@pytest.mark.parametrize(("snapshots_enabled", "background_tasks_disabled", "expected"), SNAPSHOT_STATES)
def test_html_snapshot_feature_requires_enabled_snapshots_and_background_tasks(settings, snapshots_enabled, background_tasks_disabled, expected):
    settings.LD_ENABLE_SNAPSHOTS = snapshots_enabled
    settings.LD_DISABLE_BACKGROUND_TASKS = background_tasks_disabled
    assert is_html_snapshot_feature_active() is expected

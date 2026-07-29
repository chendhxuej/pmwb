"""ma-1 测试：会议行动项完整返回 + synced_to_todo 标记"""
import pytest
from sqlalchemy.orm import Session

from services.task_center import TaskCenterService
from tests.factories import MeetingFactory, TodoFactory

_counter = 0


def _next_meeting_id():
    global _counter
    _counter += 1
    return f"MEET-MA1-{_counter:03d}"


@pytest.fixture
def svc():
    return TaskCenterService()


def _make_meeting_with_action(db: Session, *, content="行动项A", owner="张三", status="pending", related_todo_id=None):
    m = MeetingFactory.create(db, meeting_id=_next_meeting_id(), title="测试会议")
    a = MeetingFactory.add_action(db, meeting_id=m.id, content=content, owner=owner)
    if status != "pending":
        a.status = status
        db.commit()
        db.refresh(a)
    if related_todo_id is not None:
        a.related_todo_id = related_todo_id
        db.commit()
        db.refresh(a)
    return m, a


class TestMeetingActionSyncedToTodo:
    """会议行动项不再去重，全部返回，含 synced_to_todo 标记。"""

    def test_unsynced_action_synced_to_todo_false(self, db, svc):
        """未同步的行动项 synced_to_todo=False"""
        m, a = _make_meeting_with_action(db)
        items = svc.collect_meeting_action(db)
        matched = [i for i in items if i.source_id == str(a.id)]
        assert len(matched) == 1
        assert matched[0].synced_to_todo is False

    def test_synced_action_still_appears(self, db, svc):
        """已同步的行动项不再被跳过，仍然出现在 meeting_action 来源"""
        m, a = _make_meeting_with_action(db, content="已同步行动项")
        todo = TodoFactory.create(db, title="同步的待办", category="meeting")
        a.related_todo_id = todo.id
        db.commit()
        db.refresh(a)

        items = svc.collect_meeting_action(db)
        matched = [i for i in items if i.source_id == str(a.id)]
        assert len(matched) == 1, "已同步行动项应出现在 meeting_action 来源"

    def test_synced_action_synced_to_todo_true(self, db, svc):
        """已同步的行动项 synced_to_todo=True"""
        m, a = _make_meeting_with_action(db, content="已同步行动项2")
        todo = TodoFactory.create(db, title="同步的待办2", category="meeting")
        a.related_todo_id = todo.id
        db.commit()
        db.refresh(a)

        items = svc.collect_meeting_action(db)
        matched = [i for i in items if i.source_id == str(a.id)]
        assert matched[0].synced_to_todo is True

    def test_mixed_synced_and_unsynced(self, db, svc):
        """混合场景：同步+未同步的行动项都返回"""
        m1, a1 = _make_meeting_with_action(db, content="未同步")
        m2, a2 = _make_meeting_with_action(db, content="已同步")
        todo = TodoFactory.create(db, title="同步的待办3", category="meeting")
        a2.related_todo_id = todo.id
        db.commit()
        db.refresh(a2)

        items = svc.collect_meeting_action(db)
        ids = {i.source_id for i in items}
        assert str(a1.id) in ids
        assert str(a2.id) in ids
        synced_map = {i.source_id: i.synced_to_todo for i in items}
        assert synced_map[str(a1.id)] is False
        assert synced_map[str(a2.id)] is True

    def test_todo_source_not_affected(self, db, svc):
        """个人待办来源不受影响，仍包含同步副本"""
        m, a = _make_meeting_with_action(db, content="将同步的行动项")
        todo = TodoFactory.create(db, title="同步的待办4", category="meeting")
        a.related_todo_id = todo.id
        db.commit()

        todo_items = svc.collect_todo(db)
        todo_ids = {t.source_id for t in todo_items}
        assert str(todo.id) in todo_ids, "同步的待办仍出现在 todo 来源"

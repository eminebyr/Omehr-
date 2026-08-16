import json
import sqlite3
import pytest


def test_business_audit_records_before_after_and_is_immutable(isolated_root):
    from services.audit_events import record, recent, _connect
    record(actor="ik", action="PERSONNEL_UPDATE", entity_type="personnel", entity_key="A", before={"x": 1}, after={"x": 2})
    row = recent(1)[0]
    assert row["actor"] == "ik"
    assert json.loads(row["before_json"]) == {"x": 1}
    assert json.loads(row["after_json"]) == {"x": 2}
    con = _connect()
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE business_audit SET actor='hack' WHERE id=?", (row["id"],))
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("DELETE FROM business_audit WHERE id=?", (row["id"],))
    con.close()

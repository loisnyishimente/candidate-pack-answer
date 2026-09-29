from datetime import datetime, timezone

from app.models import Episode, Quality
from conftest import TestSession


def make_request(client, headers, count=1):
    return client.post("/requests", headers=headers, json={"task_name":"pick cup","episodes_requested":count,"deadline":"2026-12-01","notes":"test"})


def add_episode(episode_id="EP-1", quality=Quality.good):
    with TestSession() as db:
        item=Episode(episode_id=episode_id,robot_id="arm-01",task_name="pick cup",recorded_at=datetime.now(timezone.utc),duration_seconds=20,operator_name="Olu",quality=quality)
        db.add(item);db.commit();return item.id


def test_client_only_sees_own_requests(client, auth):
    mine=auth("client@test.com"); other=auth("other@test.com")
    assert make_request(client,mine).status_code==201
    assert make_request(client,other).status_code==201
    assert len(client.get("/requests",headers=mine).json())==1
    assert client.get("/requests/2",headers=mine).status_code==404


def test_roles_own_their_transitions(client, auth):
    customer=auth("client@test.com"); ops=auth("ops@test.com")
    request_id=make_request(client,customer).json()["id"]
    assert client.post(f"/requests/{request_id}/status",headers=customer,json={"status":"in_progress"}).status_code==409
    assert client.post(f"/requests/{request_id}/status",headers=ops,json={"status":"in_progress"}).status_code==200
    assert client.post(f"/requests/{request_id}/status",headers=ops,json={"status":"accepted"}).status_code==409


def test_assignment_and_delivery_rules(client, auth):
    customer=auth("client@test.com"); ops=auth("ops@test.com")
    request_id=make_request(client,customer,2).json()["id"]
    client.post(f"/requests/{request_id}/status",headers=ops,json={"status":"in_progress"})
    good=add_episode(); bad=add_episode("EP-2",Quality.bad)
    assert client.post(f"/requests/{request_id}/assignments",headers=ops,json={"episode_ids":[bad]}).status_code==409
    assert client.post(f"/requests/{request_id}/assignments",headers=ops,json={"episode_ids":[good]}).status_code==200
    assert client.post(f"/requests/{request_id}/status",headers=ops,json={"status":"delivered"}).status_code==409


def test_episode_cannot_be_assigned_twice(client, auth):
    customer=auth("client@test.com"); ops=auth("ops@test.com"); episode=add_episode()
    ids=[]
    for _ in range(2):
        rid=make_request(client,customer).json()["id"];ids.append(rid)
        client.post(f"/requests/{rid}/status",headers=ops,json={"status":"in_progress"})
    assert client.post(f"/requests/{ids[0]}/assignments",headers=ops,json={"episode_ids":[episode]}).status_code==200
    assert client.post(f"/requests/{ids[1]}/assignments",headers=ops,json={"episode_ids":[episode]}).status_code==409


def test_operator_cannot_create_request_or_admin_users(client, auth):
    ops=auth("ops@test.com")
    assert make_request(client,ops).status_code==403
    assert client.get("/users",headers=ops).status_code==403


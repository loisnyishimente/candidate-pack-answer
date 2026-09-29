def test_import_is_idempotent_and_reports_bad_rows(client, auth):
    headers=auth("ops@test.com")
    content=("episode_id,robot_id,task_name,recorded_at,duration_seconds,operator_name,quality\n"
             "EP-1,ARM-01, Pick Cup ,2026-09-01T10:00:00,20, olu ,GOOD\n"
             "EP-2,unknown,pick cup,2026-09-01T10:00:00,20,Olu,good\n"
             "EP-3,arm-01,pick cup,not-a-date,20,Olu,good\n")
    first=client.post("/episodes/import",headers=headers,files={"file":("data.csv",content,"text/csv")})
    assert first.status_code==200
    assert first.json()["imported"]==1 and first.json()["skipped"]==2
    second=client.post("/episodes/import",headers=headers,files={"file":("data.csv",content,"text/csv")})
    assert second.json()["imported"]==0 and second.json()["skipped"]==3


def test_client_cannot_import(client, auth):
    result=client.post("/episodes/import",headers=auth("client@test.com"),files={"file":("x.csv","x","text/csv")})
    assert result.status_code==403


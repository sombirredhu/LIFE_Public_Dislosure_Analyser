from src.background_worker import BackgroundWorker, JobStatus


def _reset_singleton():
    BackgroundWorker._instance = None


def test_submit_job_generates_unique_ids(monkeypatch):
    _reset_singleton()
    worker = BackgroundWorker(max_workers=1)
    monkeypatch.setattr(worker.executor, "submit", lambda *args, **kwargs: None)

    jid1 = worker.submit_job("C:/tmp/sample.pdf")
    jid2 = worker.submit_job("C:/tmp/sample.pdf")

    assert jid1 != jid2
    assert jid1 in worker.jobs
    assert jid2 in worker.jobs


def test_clear_completed_jobs_removes_terminal_states():
    _reset_singleton()
    worker = BackgroundWorker(max_workers=1)

    worker.jobs = {
        "a": type("J", (), {"status": JobStatus.COMPLETED})(),
        "b": type("J", (), {"status": JobStatus.FAILED})(),
        "c": type("J", (), {"status": JobStatus.CANCELLED})(),
        "d": type("J", (), {"status": JobStatus.PENDING})(),
    }

    worker.clear_completed_jobs()
    assert "d" in worker.jobs
    assert "a" not in worker.jobs
    assert "b" not in worker.jobs
    assert "c" not in worker.jobs


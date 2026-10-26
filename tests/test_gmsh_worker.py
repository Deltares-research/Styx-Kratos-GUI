"""`core.gmsh_worker`: one gmsh process, serialised, and survivable (plan Task 1.1).

The module promises that a hard crash in a job -- an OCC boolean aborting the process --
is contained: the request that hit it fails, and the next one runs on a fresh worker."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from core import gmsh_worker
from tests import worker_jobs


@pytest.fixture(autouse=True)
def own_pool():
    # A pool of this test's own: the rest of the suite must not inherit a crashed worker.
    gmsh_worker.shutdown()
    yield
    gmsh_worker.shutdown()


def on_own_loop(make_coroutine):
    # On a thread of its own: pytest-playwright's sync API leaves a loop running on this one.
    with ThreadPoolExecutor(max_workers=1) as thread:
        return thread.submit(lambda: asyncio.run(make_coroutine())).result()


def run(job, *args):
    return on_own_loop(lambda: gmsh_worker.run(job, *args))


def test_a_job_runs_in_a_worker_process_with_gmsh_initialised():
    assert run(gmsh_worker.version_job).count(".") == 1
    assert run(worker_jobs.pid) != __import__("os").getpid()


def test_the_worker_is_spawned_never_forked():
    """Linux forks by default, and a fork copies only the thread that forked: a lock held
    by any other thread (the browser tests' server, Playwright's loop) stays held in the
    child forever. The worker deadlocked that way on the Ubuntu runner until the job's
    timeout. A spawned worker starts clean, as it always has on Windows."""
    import multiprocessing

    assert gmsh_worker.executor()._mp_context is multiprocessing.get_context("spawn")


def test_a_job_exception_crosses_the_process_boundary_with_its_message():
    with pytest.raises(ValueError, match="thin solid"):
        run(worker_jobs.fail, "boolean failed on a thin solid")


def test_after_a_job_exception_the_same_worker_carries_on():
    before = run(worker_jobs.pid)
    with pytest.raises(ValueError):
        run(worker_jobs.fail, "no")
    assert run(worker_jobs.pid) == before


def test_a_crashed_worker_fails_only_the_request_that_crashed_it():
    with pytest.raises(gmsh_worker.WorkerCrashed):
        run(worker_jobs.crash)


def test_the_next_request_after_a_crash_runs_on_a_fresh_worker():
    before = run(worker_jobs.pid)
    with pytest.raises(gmsh_worker.WorkerCrashed):
        run(worker_jobs.crash)
    after = run(worker_jobs.pid)
    assert after != before, "a replacement process, not the dead one"
    assert run(gmsh_worker.version_job), "and gmsh is initialised in it"


def test_a_job_queued_behind_a_crash_fails_too_and_the_pool_recovers_once():
    async def crash_and_queue():
        return await asyncio.gather(gmsh_worker.run(worker_jobs.crash),
                                    gmsh_worker.run(worker_jobs.pid),
                                    return_exceptions=True)

    crashed, queued = on_own_loop(crash_and_queue)
    assert isinstance(crashed, gmsh_worker.WorkerCrashed)
    assert isinstance(queued, gmsh_worker.WorkerCrashed), "it was in the dead pool too"
    assert isinstance(run(worker_jobs.pid), int), "one fresh pool serves what comes next"


def test_shutdown_is_idempotent():
    run(worker_jobs.pid)
    gmsh_worker.shutdown()
    gmsh_worker.shutdown()
    assert run(worker_jobs.pid), "and the next job starts a new pool"


def test_two_concurrent_jobs_are_serialised():
    async def both():
        return await asyncio.gather(gmsh_worker.run(worker_jobs.hold, 0.3),
                                    gmsh_worker.run(worker_jobs.hold, 0.3))

    (pid_a, start_a, end_a), (pid_b, start_b, end_b) = on_own_loop(both)
    assert pid_a == pid_b, "one worker"
    first, second = sorted([(start_a, end_a), (start_b, end_b)])
    assert second[0] >= first[1], "the second started only after the first finished"


# ── Through the API ─────────────────────────────────────────────────────────

def test_a_crash_is_a_readable_500_and_the_api_keeps_working(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        monkeypatch.setattr(gmsh_worker, "geometry_job", worker_jobs.crash_with_args)
        crashed = client.get("/api/geometry")
        assert crashed.status_code == 500
        assert "geometry engine" in crashed.json()["detail"]

        monkeypatch.undo()
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/geometry").status_code == 200, "the next request is served"


# ── In this process: the command line ──────────────────────────────────────

def test_a_job_can_run_in_this_process_with_gmsh_owned_for_it():
    """The command line runs one job and exits: a pool would cost a second interpreter
    for nothing. `run_here` initializes gmsh for the job and finalizes it after."""
    import gmsh

    assert not gmsh.isInitialized()

    assert gmsh_worker.run_here(gmsh_worker.version_job) == gmsh_worker.version_job()
    assert not gmsh.isInitialized()


def test_a_job_run_here_leaves_a_gmsh_it_did_not_start_alone():
    import gmsh

    from core.geometry import solid_model

    solid_model.initialize()
    try:
        gmsh_worker.run_here(gmsh_worker.version_job)
        assert gmsh.isInitialized()
    finally:
        gmsh.finalize()


@pytest.mark.skipif(not __import__("sys").platform.startswith("linux"),
                    reason="reads /proc; Windows has no SIGPIPE")
def test_gmsh_in_this_process_leaves_sigpipe_ignored():
    """gmsh sets SIGPIPE back to the default on Linux. Left so, the next write to a closed
    pipe -- the crashed worker's, in the tests above -- killed pytest itself (exit -13).
    Read from the kernel: Python's own `getsignal` keeps answering what it last set."""
    import signal

    def ignored() -> bool:
        with open("/proc/self/status") as status:
            mask = next(line for line in status if line.startswith("SigIgn:")).split()[1]
        return bool(int(mask, 16) >> (signal.SIGPIPE - 1) & 1)

    assert ignored()
    gmsh_worker.run_here(gmsh_worker.version_job)
    assert ignored()


def test_a_job_that_fails_here_raises_and_still_finalizes():
    import gmsh

    with pytest.raises(ValueError, match="no such thing"):
        gmsh_worker.run_here(worker_jobs.fail, "no such thing")
    assert not gmsh.isInitialized()


# ── Blocking, from wherever: a model script ────────────────────────────────

def test_a_blocking_job_runs_here_on_the_main_thread():
    assert gmsh_worker.run_blocking(worker_jobs.pid) == __import__("os").getpid()


def test_a_blocking_job_off_the_main_thread_runs_in_the_worker():
    """A route runs a model script on a worker thread, where gmsh cannot start: it
    installs a signal handler, which only the main thread may. So the job goes to the
    worker process, and the thread waits for it."""
    with ThreadPoolExecutor(max_workers=1) as thread:
        pid = thread.submit(gmsh_worker.run_blocking, worker_jobs.pid).result(timeout=120)
        version = thread.submit(gmsh_worker.run_blocking,
                                gmsh_worker.version_job).result(timeout=120)

    assert pid != __import__("os").getpid()
    assert version.count(".") == 1

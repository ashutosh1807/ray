import os
import sys

import httpx
import pytest

from ray import serve
from ray._common.test_utils import wait_for_condition
from ray.serve._private.constants import SERVE_SESSION_ID


def test_sticky_routing_via_header(serve_instance):
    @serve.deployment(num_replicas=2)
    class SessionApp:
        async def __call__(self, request):
            return os.getpid()

    session_id = "sess-abc-123"
    handle = serve.run(SessionApp.bind())
    headers = {SERVE_SESSION_ID: session_id}
    resp = httpx.get("http://localhost:8000", headers=headers)
    initial_pid = resp.json()

    for _ in range(10):
        resp = httpx.get("http://localhost:8000", headers=headers)
        assert resp.json() == initial_pid

    for _ in range(10):
        assert (
            handle.options(session_id=session_id).remote("blabla").result()
            == initial_pid
        )


def test_different_sessions_route_independently(serve_instance):
    @serve.deployment(num_replicas=2)
    class SessionApp:
        async def __call__(self, request):
            return os.getpid()

    serve.run(SessionApp.bind())

    headers_s1 = {SERVE_SESSION_ID: "s1"}
    resp_s1 = httpx.get("http://localhost:8000", headers=headers_s1)
    pid_s1 = resp_s1.json()

    headers_s2 = {SERVE_SESSION_ID: "s2"}
    resp_s2 = httpx.get("http://localhost:8000", headers=headers_s2)
    pid_s2 = resp_s2.json()

    for _ in range(10):
        resp = httpx.get("http://localhost:8000", headers=headers_s1)
        assert resp.json() == pid_s1
        resp = httpx.get("http://localhost:8000", headers=headers_s2)
        assert resp.json() == pid_s2


def test_no_header_distributes_across_replicas(serve_instance):
    @serve.deployment(num_replicas=2)
    class SessionApp:
        async def __call__(self, request):
            return os.getpid()

    serve.run(SessionApp.bind())

    def _requests_hit_both_replicas():
        pids = set()
        for _ in range(20):
            resp = httpx.get("http://localhost:8000")
            pids.add(resp.json())
        return len(pids) == 2

    wait_for_condition(_requests_hit_both_replicas, timeout=30)


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", "-s", __file__]))

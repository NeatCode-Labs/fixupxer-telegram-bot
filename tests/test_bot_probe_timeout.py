"""Total probe deadlines and cancellation cleanup, using offline HTTP transports."""
import asyncio

import httpx
import pytest

import fixupxer_bot as bot


class ProgressBody(httpx.AsyncByteStream):
    """Keep making progress without reaching EOF unless chunks are provided."""

    def __init__(self, chunks=None, delay=0.005):
        self.chunks = chunks
        self.delay = delay
        self.reads = 0
        self.closed = False
        self.started = asyncio.Event()

    async def __aiter__(self):
        while self.chunks is None or self.reads < len(self.chunks):
            await asyncio.sleep(self.delay)
            chunk = b"x" * 128 if self.chunks is None else self.chunks[self.reads]
            self.reads += 1
            self.started.set()
            yield chunk

    async def aclose(self):
        self.closed = True


@pytest.mark.parametrize("platform", ["instagram", "tiktok"])
def test_progressing_stream_times_out_closes_and_releases_waiter(monkeypatch, platform):
    async def run():
        health = bot._IG_HEALTH if platform == "instagram" else bot._TT_HEALTH
        host = "proxy.example" if platform == "instagram" else "vm.proxy.example"
        key = (host, "/p/test")
        body = ProgressBody()
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, headers={"content-type": "text/html"}, stream=body)

        def probe():
            if platform == "instagram":
                return bot._ig_probe("proxy.example", "/p/test")
            return bot._tt_probe("proxy.example", "/p/test", host=host)

        monkeypatch.setattr(bot, "_IG_PROBE_TOTAL_TIMEOUT", 0.1)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            monkeypatch.setattr(bot, "_probe_http_client", client)
            owner = asyncio.create_task(probe())
            await asyncio.wait_for(body.started.wait(), timeout=1)
            inflight = health._inflight[key]
            waiter = asyncio.create_task(probe())
            results = await asyncio.wait_for(asyncio.gather(owner, waiter), timeout=1)

            assert results == [(False, None, None), (False, None, None)]
            assert 0 < body.reads * 128 < bot._IG_MAX_BYTES
            assert body.closed
            assert inflight.is_set()
            assert health._inflight == {}
            assert health._cache_get(key) == {
                "passed": False, "og_url": None, "final_url": None,
            }
            assert len(health.circuit_get("proxy.example")["fails"]) == 1
            assert health.event_counts_1h("proxy.example") == (0, 1)
            assert await probe() == (False, None, None)
            assert len(requests) == 1
            assert requests[0].url.host == host

    asyncio.run(run())


def test_redirect_html_and_video_share_one_deadline(monkeypatch):
    async def run():
        # Each individual phase is shorter than the budget, but their combined
        # duration exceeds it. A fresh timeout for each phase would pass wrongly.
        redirect = ProgressBody()
        html = ProgressBody([
            b'<meta property="og:video" content="/video">',
        ], delay=0.12)
        video_redirect = ProgressBody()
        video_started = asyncio.Event()
        video_cancelled = asyncio.Event()
        requests = []

        async def handler(request):
            path = request.url.path
            requests.append(path)
            if path == "/p/test":
                await asyncio.sleep(0.12)
                return httpx.Response(302, headers={"location": "/page"}, stream=redirect)
            if path == "/page":
                return httpx.Response(200, headers={"content-type": "text/html"}, stream=html)
            if path == "/video":
                return httpx.Response(
                    302, headers={"location": "/movie.mp4"}, stream=video_redirect,
                )
            assert path == "/movie.mp4"
            video_started.set()
            try:
                await asyncio.sleep(0.12)
            except asyncio.CancelledError:
                video_cancelled.set()
                raise
            return httpx.Response(200, headers={"content-type": "video/mp4"})

        monkeypatch.setattr(bot, "_IG_PROBE_TOTAL_TIMEOUT", 0.3)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            monkeypatch.setattr(bot, "_probe_http_client", client)
            result = await asyncio.wait_for(bot._ig_probe("proxy.example", "/p/test"), 1)

        assert result == (False, None, None)
        assert video_started.is_set() and video_cancelled.is_set()
        assert requests == ["/p/test", "/page", "/video", "/movie.mp4"]
        assert redirect.closed and html.closed and video_redirect.closed
        assert redirect.reads == video_redirect.reads == 0
        assert html.reads == 1
        assert bot._IG_HEALTH._inflight == {}
        assert bot._IG_HEALTH._cache_get(("proxy.example", "/p/test"))["passed"] is False
        assert bot._IG_HEALTH.event_counts_1h("proxy.example") == (0, 1)

    asyncio.run(run())


def test_caller_cancellation_closes_stream_and_releases_waiter(monkeypatch):
    async def run():
        body = ProgressBody()

        def handler(request):
            return httpx.Response(200, stream=body)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            monkeypatch.setattr(bot, "_probe_http_client", client)
            owner = asyncio.create_task(bot._ig_probe("proxy.example", "/p/test"))
            await asyncio.wait_for(body.started.wait(), timeout=1)
            inflight = bot._IG_HEALTH._inflight[("proxy.example", "/p/test")]
            waiter = asyncio.create_task(bot._ig_probe("proxy.example", "/p/test"))
            # Let the second caller observe the existing in-flight probe.
            await asyncio.sleep(0)
            owner.cancel()
            with pytest.raises(asyncio.CancelledError):
                await owner
            assert await asyncio.wait_for(waiter, timeout=1) == (False, None, None)

        assert body.closed and inflight.is_set()
        assert bot._IG_HEALTH._inflight == {}
        assert bot._IG_HEALTH._cache_get(("proxy.example", "/p/test")) is None
        assert bot._IG_HEALTH.event_counts_1h("proxy.example") == (0, 0)

    asyncio.run(run())

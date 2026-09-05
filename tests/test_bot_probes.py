"""Resource bounds and cleanup for HTTP probes, with no network traffic."""
import asyncio

import httpx
import pytest

import fixupxer_bot as bot


class CountingBody(httpx.AsyncByteStream):
    def __init__(self, chunk=b"x" * 4096, count=1000):
        self.chunk = chunk
        self.count = count
        self.reads = 0
        self.closed = False

    async def __aiter__(self):
        for _ in range(self.count):
            self.reads += 1
            yield self.chunk

    async def aclose(self):
        self.closed = True


def run_probe(monkeypatch, handler):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            monkeypatch.setattr(bot, "_probe_http_client", client)
            return await bot._IG_HEALTH.probe("proxy.example", "/p/test")
    return asyncio.run(run())


def test_html_probe_stops_at_64_kib_and_closes_stream(monkeypatch):
    body = CountingBody()
    result = run_probe(monkeypatch, lambda request: httpx.Response(
        200, headers={"content-type": "text/html"}, stream=body,
    ))
    assert result[0] is False
    assert body.reads * len(body.chunk) == bot._IG_MAX_BYTES
    assert body.closed


@pytest.mark.parametrize("content_type", ["image/jpeg", "video/mp4"])
def test_media_probe_reads_headers_only(monkeypatch, content_type):
    body = CountingBody()
    result = run_probe(monkeypatch, lambda request: httpx.Response(
        200, headers={"content-type": content_type}, stream=body,
    ))
    assert result[0] is True
    assert body.reads == 0
    assert body.closed


def test_probe_finds_metadata_inside_bounded_html(monkeypatch):
    body = CountingBody(b'<meta property="og:image" content="https://media.example/photo">', 1)
    result = run_probe(monkeypatch, lambda request: httpx.Response(200, stream=body))
    assert result == (True, "https://media.example/photo", "https://proxy.example/p/test")
    assert body.closed


def test_compressed_html_is_not_decompressed_or_buffered(monkeypatch):
    body = CountingBody()
    def handler(request):
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(200, headers={"content-encoding": "gzip"}, stream=body)
    assert run_probe(monkeypatch, handler)[0] is False
    assert body.reads == 0
    assert body.closed


def test_redirect_body_is_never_downloaded(monkeypatch):
    redirect = CountingBody()
    media = CountingBody()
    requests = []
    def handler(request):
        requests.append(str(request.url))
        if len(requests) == 1:
            return httpx.Response(302, headers={"location": "/photo.jpg"}, stream=redirect)
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, stream=media)
    assert run_probe(monkeypatch, handler)[0] is True
    assert requests == ["https://proxy.example/p/test", "https://proxy.example/photo.jpg"]
    assert redirect.reads == media.reads == 0
    assert redirect.closed and media.closed


def test_redirect_loop_is_bounded_and_closes_every_response(monkeypatch):
    bodies = []
    def handler(request):
        body = CountingBody()
        bodies.append(body)
        return httpx.Response(302, headers={"location": "/loop"}, stream=body)
    assert run_probe(monkeypatch, handler)[0] is False
    assert len(bodies) == 4
    assert all(body.closed and body.reads == 0 for body in bodies)


def test_video_check_follows_redirect_without_reading_either_body(monkeypatch):
    bodies = []
    def handler(request):
        body = CountingBody()
        bodies.append(body)
        if len(bodies) == 1:
            return httpx.Response(302, headers={"location": "/movie.mp4"}, stream=body)
        return httpx.Response(206, headers={"content-type": "video/mp4"}, stream=body)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await bot._media_is_video(client, "https://proxy.example/video")
    assert asyncio.run(run()) is True
    assert all(body.closed and body.reads == 0 for body in bodies)


@pytest.mark.parametrize("target", ["file:///etc/passwd", "https://user:pass@example.com/video"])
def test_unsafe_redirect_structure_is_not_requested(monkeypatch, target):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": target}, stream=CountingBody())
    assert run_probe(monkeypatch, handler)[0] is False
    assert len(requests) == 1

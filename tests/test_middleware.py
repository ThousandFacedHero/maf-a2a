import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from maf_a2a.middleware import RequestLoggingMiddleware, RequestValidationMiddleware


def _make_app(*middleware_classes):
    app = FastAPI()

    @app.post("/test")
    async def echo(request: Request):
        body = await request.json()
        return JSONResponse(body)

    for cls in reversed(middleware_classes):
        app.add_middleware(cls)
    return app


def test_logging_middleware_logs_request(caplog):
    app = _make_app(RequestLoggingMiddleware)
    client = TestClient(app)
    with caplog.at_level(logging.INFO):
        resp = client.post("/test", json={"msg": "hello"})
    assert resp.status_code == 200
    assert any("POST /test" in r.message for r in caplog.records)


def test_logging_middleware_logs_response_status(caplog):
    app = _make_app(RequestLoggingMiddleware)
    client = TestClient(app)
    with caplog.at_level(logging.INFO):
        client.post("/test", json={"msg": "hello"})
    assert any("200" in r.message for r in caplog.records)


def test_validation_middleware_rejects_non_json():
    app = _make_app(RequestValidationMiddleware)
    client = TestClient(app)
    resp = client.post("/test", content=b"not json", headers={"content-type": "text/plain"})
    assert resp.status_code == 415

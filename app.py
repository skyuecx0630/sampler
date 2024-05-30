import logging
import json
import typing
import os

from fastapi import FastAPI, Request, Response


logger = logging.getLogger("uvicorn")
app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

stat_count = {}
stat_count_with_query = {}

recent_requests = []

IGNORE_PATH = list(
    map(str.strip, os.environ.get("IGNORE_PATH", "/favicon.ico, /ignoreme").split(","))
)


class PrettyJSONResponse(Response):
    # media_type = "application/json"
    media_type = "text/html"

    def render(self, content: typing.Any) -> bytes:
        return f"""
<script src="https://unpkg.com/@alenaksu/json-viewer@2.0.1/dist/json-viewer.bundle.js"></script>
<json-viewer id="json"></json-viewer>
<script>
    document.querySelector('#json').data = {
    json.dumps(
        content,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        separators=(", ", ": "),
    )
};
</script>
""".encode()


async def parse_request(request: Request):
    parsed_request = {}

    parsed_request["method"] = request.method
    parsed_request["url"] = (
        f"{request.url.path}{'?' if request.url.query else ''}{request.url.query}"
    )
    parsed_request["headers"] = dict(request.headers)

    if request.headers.get("content-type") == "application/json":
        try:
            body = await request.json()
        except:
            body = (await request.body()).decode()
    else:
        body = (await request.body()).decode()

    if request.cookies:
        parsed_request["cookies"] = dict(request.cookies)
    if body:
        parsed_request["body"] = body

    return parsed_request


def add_to_history(request):
    recent_requests.append(request)


def add_to_stat(request):
    record = f"{request.method} {request.url.path}"
    record_with_query = f"{request.method} {request.url.path}{'?' if request.url.query else ''}{request.url.query}"

    if stat_count.get(record) is None:
        stat_count[record] = 0
    if stat_count_with_query.get(record_with_query) is None:
        stat_count_with_query[record_with_query] = 0

    stat_count[record] += 1
    stat_count_with_query[record_with_query] += 1


async def record_request(request: Request):
    parsed_request = await parse_request(request)

    add_to_history(parsed_request)
    add_to_stat(request)

    logger.info(json.dumps(parsed_request, indent=2))


@app.get("/dummy/stats", status_code=200, response_class=PrettyJSONResponse)
def stats(query: bool = True):
    if query:
        return dict(sorted(stat_count_with_query.items(), key=lambda x: -int(x[1])))
    return dict(sorted(stat_count.items(), key=lambda x: -int(x[1])))


@app.get("/dummy/recent", status_code=200, response_class=PrettyJSONResponse)
def recent():
    return recent_requests[::-1]


@app.get("/dummy/flush", status_code=200)
def flush():
    global recent_requests, stat_count, stat_count_with_query
    recent_requests = []
    stat_count = {}
    stat_count_with_query = {}
    return {"message": "ok"}


# You can return fixed-response.
@app.get("/dummy/health", status_code=200)
def dummy_health():
    return {"status": "ok"}


# It should be processed only when no other route matches.
@app.api_route(
    "/{dummy:path}",
    methods=["GET", "POST", "PUT", "UPDATE", "DELETE", "HEAD", "OPTIONS"],
    status_code=500,
)
async def dummy(request: Request):
    if request.url.path not in IGNORE_PATH:
        await record_request(request)
    return {"message": "Oops"}

import logging
import json
import typing
import os
import urllib.parse


from fastapi import FastAPI, Request, Response
import httpx


logger = logging.getLogger("uvicorn")
app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

stat_count = {}
stat_count_with_query = {}

recent_requests = []

ENV_IGNORE_PATH = os.environ.get("IGNORE_PATH", "/favicon.ico, /ignoreme")
ignore_path = list(map(str.strip, ENV_IGNORE_PATH.split(",")))

ENV_IGNORE_HEALTH_CHECK = os.environ.get("IGNORE_HEALTH_CHECK", 1)
ignore_health_check = int(ENV_IGNORE_HEALTH_CHECK)

ENV_UPSTREAM_ENDPOINT = os.environ.get("UPSTREAM_ENDPOINT", None)
upstream_endpoint = ENV_UPSTREAM_ENDPOINT

http_client = httpx.AsyncClient()


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

    # if request.headers.get("content-type") == "application/json":
    #     try:
    #         body = await request.json()
    #     except:
    #         body = (await request.body()).decode()
    # else:
    body = (await request.body()).decode()

    if request.cookies:
        parsed_request["cookies"] = dict(request.cookies)
    if body:
        parsed_request["body"] = body

    return parsed_request


def add_to_history(parsed_request, response=None):
    if response:
        parsed_request["response"] = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response.content.decode(),
        }
    else:
        parsed_request["response"] = "NO UPSTREAM"

    recent_requests.append(parsed_request)


def add_to_stat(parsed_request):
    record = f'{parsed_request["method"]} {parsed_request["url"].split("?")[0]}'
    record_with_query = f'{parsed_request["method"]} {parsed_request["url"]}'

    if stat_count.get(record) is None:
        stat_count[record] = 0
    if stat_count_with_query.get(record_with_query) is None:
        stat_count_with_query[record_with_query] = 0

    stat_count[record] += 1
    stat_count_with_query[record_with_query] += 1


def record_request(parsed_request, response=None):
    path = parsed_request["url"].split("?")[0]
    user_agent = parsed_request["headers"].get("user-agent")

    if path in ignore_path:
        logger.info(f'Request to "{path}" skipped..')
        return
    if ignore_health_check and user_agent == "ELB-HealthChecker/2.0":
        logger.info(f"Health check from ELB skipped..")
        return

    add_to_history(parsed_request, response)
    add_to_stat(parsed_request)

    logger.info(json.dumps(parsed_request, indent=2))


async def send_to_upstream(upstream_endpoint, parsed_request):
    # async with httpx.AsyncClient() as client:
    url = urllib.parse.urlparse(upstream_endpoint)
    path = parsed_request["url"].split("?")[0]
    query = parsed_request["url"].split("?")[1] if "?" in parsed_request["url"] else ""
    url = url._replace(path=path, query=query)

    response = await http_client.send(
        http_client.build_request(
            method=parsed_request["method"],
            url=urllib.parse.urlunparse(url),
            headers=parsed_request["headers"],
            cookies=parsed_request.get("cookies"),
            content=parsed_request.get("body"),
        )
    )

    return response


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
    parsed_request = await parse_request(request)

    if upstream_endpoint:
        upstream_response = await send_to_upstream(upstream_endpoint, parsed_request)

        record_request(parsed_request, upstream_response)
        return Response(
            upstream_response.content,
            status_code=upstream_response.status_code,
            headers=dict(upstream_response.headers),
        )

    record_request(parsed_request)
    return {"message": "Oops"}

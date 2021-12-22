import json
import re

from datetime import date, timedelta, datetime
from pathlib import Path

import jinja_partials
import humanize
import more_itertools

from flask import Flask, render_template, request, Response, Blueprint
from flask.cli import load_dotenv
from flask_basicauth import BasicAuth
from slugify import slugify
from werkzeug.exceptions import NotFound

import db
import settings

load_dotenv()

# 1 Mo
CHUNK_SIZE = 1000000
VID_PATH = Path(settings.get("output_path", "./output"))
NB_VIDS_PER_ROW = 3

app = Flask(__name__)
jinja_partials.register_extensions(app)
blueprint = Blueprint(
    "media", __name__,
    static_url_path="/static/media", static_folder=VID_PATH,
)
app.register_blueprint(blueprint)
app.logger.debug(f"Input: {VID_PATH}")

if settings.get("basic_auth", "") == "1":
    app.config.update(**{
        "BASIC_AUTH_FORCE": True,
        "BASIC_AUTH_USERNAME": settings.get("basic_auth_username"),
        "BASIC_AUTH_PASSWORD": settings.get("basic_auth_password"),
    })
    BasicAuth(app)


def videos_to_rows(videos):
    return [
        list(row)
        for row in more_itertools.chunked(videos, NB_VIDS_PER_ROW)
    ]


@app.route("/")
def index():
    start = request.args.get("start")
    end = request.args.get("end")
    tags = request.args.get("tags", "").split(",")
    route = request.args.get("route", "")
    page = int(request.args.get("page", 1))

    # we want two rows
    _limit = NB_VIDS_PER_ROW * 2
    _offset = (page - 1) * _limit

    if not start:
        first = db.table.find_one(order_by="created_at")
        start = first["created_at"].date().isoformat()

    # Add 1 day to end date to include it in results
    if end:
        end = date.fromisoformat(end) + timedelta(days=1)
        end = end.isoformat()
    else:
        end = date.today().isoformat()

    where = []
    if start:
        where.append("created_at >= :start")
    if end:
        where.append("created_at <= :end")
    if route:
        where.append("route NOT NULL")
    where += [f"json_extract(tags, '$.{tag}') = 1" for tag in tags if tag]
    q = f"""
        SELECT * FROM videos WHERE
        {" AND ".join(where)}
        ORDER BY created_at DESC
        LIMIT {_limit}
        OFFSET {_offset}
    """

    videos = db.db.query(q, start=start, end=end)

    rows = videos_to_rows(videos)
    kwargs = {
        "rows": rows,
        "start": start,
        "end": end,
        "route": route,
        "page": page,
        "tags": db.get_tags(),
    }

    if "HX-Request" in request.headers:
        return jinja_partials.render_partial("partials/videos.html", **kwargs)

    return render_template("index.html", **kwargs)


@app.route("/videos/list")
def videos_list():
    videos = db.table.all(order_by="-created_at")
    return render_template("list.html", videos=videos, tags=db.get_tags())


@app.route("/videos/tag", methods=["PUT"])
def videos_tag():
    tags = request.form.get("tags")
    if tags:
        tags = json.loads(tags)
    videos_ids = request.form.getlist("ids")

    tags = {slugify(t["value"]): 1 for t in tags}
    for _id in videos_ids:
        video = db.table.find_one(id=_id)
        if not video:
            continue
        video_tags = video["tags"] or {}
        db.table.update(
            # merge existing and new tags
            {"id": video["id"], "tags": {**video_tags, **tags}},
            ["id"],
        )

    videos = db.table.all(order_by="-created_at")
    return jinja_partials.render_partial(
        "partials/videos_list.html",
        videos=videos
    )


@app.route("/videos/untag", methods=["PUT"])
def videos_untag():
    tags = request.form.get("tags")
    if tags:
        tags = json.loads(tags)
    videos_ids = request.form.getlist("ids")

    for _id in videos_ids:
        video = db.table.find_one(id=_id)
        if not video:
            continue
        tags = {slugify(t["value"]): 1 for t in tags}
        for tag in tags:
            q = f"""
                UPDATE videos
                SET tags = json_remove(tags, '$.{tag}')
                WHERE id = {video['id']}
                """
            db.db.query(q)

    videos = db.table.all(order_by="-created_at")
    return jinja_partials.render_partial(
        "partials/videos_list.html",
        videos=videos
    )


@app.route("/videos/<path:rel_path>")
def video(rel_path):
    video = db.table.find_one(path=rel_path)
    if not video:
        raise NotFound()
    return render_template("video.html", video=video)


def get_chunk(path, byte1=None, byte2=None):
    full_path = VID_PATH / Path(path)
    # avoid path traversal attempts
    full_path.resolve().relative_to(VID_PATH.resolve())
    if not full_path.exists():
        raise NotFound()

    file_size = full_path.stat().st_size
    start = 0

    if byte1 < file_size:
        start = byte1
    if byte2:
        length = byte2 + 1 - byte1
    else:
        # chunk size here
        length = start + CHUNK_SIZE
        if start + length > file_size:
            length = file_size - start

    with open(full_path, "rb") as f:
        f.seek(start)
        chunk = f.read(length)

    return chunk, start, length, file_size


@app.route("/videos/<path:path>/download")
def stream_data_file(path):
    range_header = request.headers.get("Range", None)
    byte_s, byte_e = 0, None
    if range_header:
        match = re.search(r"(\d+)-(\d*)", range_header)
        groups = match.groups()
        if groups[0]:
            byte_s = int(groups[0])
        if groups[1]:
            byte_e = int(groups[1])

    chunk, start, length, file_size = get_chunk(path, byte_s, byte_e)

    return Response(
        chunk, 206,
        mimetype="video/mp4",
        content_type="video/mp4",
        direct_passthrough=True,
        headers={
            "Content-Range": "bytes {0}-{1}/{2}".format(
                start, start + length - 1, file_size
            )
        }
    )


@app.template_filter()
def datetimeformat(value):
    if not value:
        return
    value = datetime.fromisoformat(value)
    date_fmt = "%Y-%m-%d %H:%M:%S"
    return f"{humanize.naturaltime(value)} — {value.strftime(date_fmt)}"


@app.template_filter()
def durationformat(value):
    if not value:
        return
    return humanize.precisedelta(float(value))


@app.template_filter()
def fromjson(value):
    if not value:
        return
    return json.loads(value)

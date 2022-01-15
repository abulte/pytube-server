import json
import re

from datetime import date, timedelta, datetime
from pathlib import Path

import jinja_partials
import jwt
import more_itertools

from flask import Flask, render_template, request, Response, Blueprint, g
from slugify import slugify
from werkzeug.exceptions import NotFound

from herotube import auth, db, settings, utils

from herotube.api import blueprint as api_bp


VID_PATH = Path(settings.get("output_path", "./output")).resolve()
NB_VIDS_PER_ROW = 3

app = Flask(__name__)
jinja_partials.register_extensions(app)
media_bp = Blueprint(
    "media", __name__,
    static_url_path="/static/media", static_folder=VID_PATH,
)
app.register_blueprint(media_bp)
app.register_blueprint(api_bp)

app.logger.debug(f"Input path: {VID_PATH}")

auth.init_app(app)

from herotube import filters  # noqa


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
    limit = NB_VIDS_PER_ROW * 2
    offset = (page - 1) * limit

    if not start:
        start = db.get_oldest_video()["created_at"].date().isoformat()

    # Add 1 day to end date to include it in results
    if end:
        end = date.fromisoformat(end) + timedelta(days=1)
        end = end.isoformat()
    else:
        end = date.today().isoformat()

    videos = db.get_videos(
        start=start,
        end=end,
        keys={"tags": [t for t in tags if t]},
        has_route=route,
        limit=limit,
        offset=offset,
    )

    rows = videos_to_rows(videos)
    kwargs = {
        "rows": rows,
        "start": start,
        "end": end,
        "route": route,
        "page": page,
        "tags": db.get_distinct_keys("tags"),
    }

    if "HX-Request" in request.headers:
        return jinja_partials.render_partial("partials/videos.html", **kwargs)

    return render_template("index.html", **kwargs)


@app.route("/videos/map")
def videos_map():
    videos = db.table.find(route={"not": None})
    bounds = db.get_videos_bounds()
    # add 1% padding to bounds
    bounds = [
        [bounds["minx"] * 0.99, bounds["miny"] * 0.99],
        [bounds["maxx"] * 1.01, bounds["maxy"] * 1.01]
    ]
    return render_template("map.html", videos=videos, bounds=bounds)


@app.route("/videos/<path:rel_path>")
def video(rel_path):
    video = db.table.find_one(path=rel_path)
    if not video:
        raise NotFound()
    token = jwt.encode({
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=30),
        "subject": f"video:{video['title']}",
    }, app.config["SECRET_KEY"], algorithm="HS256") if g.get("is_admin") else None
    return render_template("video.html", video=video, token=token)


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

    full_path = VID_PATH / Path(path)
    # avoid path traversal attempts
    full_path.resolve().relative_to(VID_PATH.resolve())
    if not full_path.exists():
        raise NotFound()

    chunk, start, length, file_size = utils.get_chunk(full_path, byte_s, byte_e)

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


@app.route("/videos/list")
def videos_list():
    videos = db.table.all(order_by="-created_at")
    return render_template("list.html", videos=videos,
                           tags=db.get_distinct_keys("tags"),
                           playlists=db.get_distinct_keys("playlists"))


@app.route("/videos/tags", methods=["PUT", "DELETE"])
def videos_tags():
    tags = request.form.get("tags")
    if tags:
        tags = json.loads(tags)
    videos_ids = request.form.getlist("ids")
    tags = {slugify(t["value"]): 1 for t in tags}

    if request.method == "PUT":
        db.add_keys("tags", videos_ids, tags)
    elif request.method == "DELETE":
        db.remove_keys("tags", videos_ids, tags)

    videos = db.table.all(order_by="-created_at")
    return jinja_partials.render_partial(
        "partials/videos_list.html",
        videos=videos
    )


@app.route("/videos/playlists", methods=["PUT", "DELETE"])
def videos_playlists():
    playlists = request.form.get("playlists")
    if playlists:
        playlists = json.loads(playlists)
    videos_ids = request.form.getlist("ids")
    playlists = {p["value"]: 1 for p in playlists}

    if request.method == "PUT":
        db.add_keys("playlists", videos_ids, playlists)
    elif request.method == "DELETE":
        db.remove_keys("playlists", videos_ids, playlists)

    videos = db.table.all(order_by="-created_at")
    return jinja_partials.render_partial(
        "partials/videos_list.html",
        videos=videos
    )


@app.route("/videos/playlists", methods=["GET"])
def list_videos_playlists():
    playlists = db.get_distinct_keys("playlists")
    return render_template("playlists.html", playlists=playlists, tolen=token)


@app.route("/videos/playlists/<playlist>", methods=["GET"])
def videos_playlist(playlist):
    if playlist not in db.get_distinct_keys("playlists"):
        raise NotFound()

    token = jwt.encode({
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=30),
        "subject": f"playlist:{playlist}",
    }, app.config["SECRET_KEY"], algorithm="HS256")

    videos = db.get_videos(keys={"playlists": [playlist]})

    rows = videos_to_rows(videos)
    return render_template("playlist.html", rows=rows, playlist=playlist, token=token)

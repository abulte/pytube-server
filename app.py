import re

from datetime import date
from pathlib import Path

import jinja_partials
import humanize
import more_itertools

from flask import Flask, render_template, request, Response, Blueprint
from werkzeug.exceptions import NotFound

import db
import settings

# 1 Mo
CHUNK_SIZE = 1000000
VID_PATH = Path(settings.get("output_path", "./output"))

app = Flask(__name__)
jinja_partials.register_extensions(app)
blueprint = Blueprint(
    "media", __name__,
    static_url_path="/static/media", static_folder=VID_PATH,
)
app.register_blueprint(blueprint)


@app.route("/")
def index():
    videos = db.table.all(order_by='-created_at')

    rows = [
        list(row)
        for row in more_itertools.chunked(videos, 2)
    ]

    first = db.table.find_one(order_by='created_at')
    first_date = first["created_at"].date().isoformat()

    return render_template(
        "index.html",
        rows=rows, root=VID_PATH, first_date=first_date
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
    date_fmt = "%Y-%m-%d %H:%M:%S"
    return f"{humanize.naturaltime(value)} — {value.strftime(date_fmt)}"


@app.template_filter()
def durationformat(value):
    if not value:
        return
    return humanize.precisedelta(float(value))


@app.context_processor
def utility_processor():
    def isodatetoday():
        return date.today().isoformat()
    return dict(isodatetoday=isodatetoday)

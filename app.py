import re

from pathlib import Path

import jinja_partials
import ffmpeg
from flask import Flask, render_template, request, Response
from werkzeug.exceptions import NotFound

import settings

# 1 Mo
CHUNK_SIZE = 1000000
VID_PATH = Path(settings.get("output_path", "./output"))

app = Flask(__name__)
jinja_partials.register_extensions(app)


@app.route("/")
def index():
    videos = [
        {
            "path": v,
            "metadata": ffmpeg.probe(str(v)).get("format"),
        } for v in VID_PATH.glob("**/*.mp4")
    ]
    return render_template("index.html", videos=videos, root=VID_PATH)


@app.route("/videos/<path:path>")
def video(path):
    return render_template("video.html", video=path)


def get_chunk(path, byte1=None, byte2=None):
    full_path = VID_PATH / Path(path)
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
        mimetype="video/mp4", content_type="video/mp4", direct_passthrough=True,
        headers={
            "Content-Range": "bytes {0}-{1}/{2}".format(
                start, start + length - 1, file_size
            )
        }
    )

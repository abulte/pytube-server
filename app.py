from pathlib import Path

import jinja_partials
import ffmpeg
from flask import Flask, render_template, send_from_directory

import settings

VID_PATH = Path(settings.get("output_path", "./output"))

app = Flask(__name__)
jinja_partials.register_extensions(app)


@app.route("/")
def index():
    _videos = VID_PATH.glob("**/*.mp4")
    # FIXME: dict comprehension
    videos = []
    for v in _videos:
        videos.append({
            "path": v,
            "metadata": ffmpeg.probe(str(v)).get("format"),
        })
    return render_template("index.html", videos=videos, root=VID_PATH)


@app.route("/videos/<path:path>")
def video(path):
    return render_template("video.html", video=path)


@app.route("/videos/<path:path>/download")
def stream_data_file(path):
    return send_from_directory(VID_PATH, path)

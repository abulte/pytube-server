from flask import request, session, g, current_app

import jwt

from flask_basicauth import BasicAuth

from herotube import settings, db

SHARABLE_ENDPOINTS = [
    "video",
    "videos_playlist",
    "stream_data_file",
    "static",
    "media.static"
]


def init_app(app):
    if settings.get("basic_auth", "") == "1":
        app.config.update(**{
            "BASIC_AUTH_FORCE": True,
            "BASIC_AUTH_REALM": "",
            "BASIC_AUTH_USERNAME": settings.get("basic_auth_username"),
            "BASIC_AUTH_PASSWORD": settings.get("basic_auth_password"),
            "SECRET_KEY": settings.get("secret_key"),
        })

    @app.before_request
    def require_auth():
        """
        Handles global BasicAuth (super user) and share tokens for videos
        """
        endpoint, args = request.endpoint, request.view_args

        def get_vid(args):
            # 2021-12-10/gx030136.mp4
            return args["rel_path"].split("/")[-1].split(".")[0]

        if endpoint in SHARABLE_ENDPOINTS:
            if request.args.get("token"):
                payload = {}
                token = request.args["token"]
                try:
                    payload = jwt.decode(
                        token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
                    )
                    session["auth"] = payload
                except jwt.DecodeError as e:
                    current_app.logger.info(f"Rejected token {token}: {e}")

                subject = payload.get("subject", "")
                if subject.startswith("playlist:") and endpoint == "videos_playlist":
                    if args["playlist"] == subject.lstrip("playlist:"):
                        return
                elif subject.startswith("video:") and endpoint == "video":
                    if get_vid(args) == subject.lstrip("video:"):
                        return

            elif session.get("auth"):
                _auth = session["auth"]
                # bypass static auth (no media here)
                if endpoint == "static":
                    return
                # find vid in any view_args to protect media static
                elif _auth["subject"].startswith("video:"):
                    if any([_auth["subject"].lstrip("video:") in a for a in args.values()]):
                        return
                elif _auth["subject"].startswith("playlist:"):
                    videos = db.get_videos(
                        keys={"playlists": [_auth["subject"].lstrip("playlist:")]}
                    )
                    vids = [v["title"] for v in videos]
                    for vid in vids:
                        if any([vid in a for a in args.values()]):
                            return

        # fallback on basicauth
        auth = BasicAuth()
        auth.app = current_app
        if not auth.authenticate():
            return auth.challenge()
        else:
            g.is_admin = True

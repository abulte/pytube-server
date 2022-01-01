from flask import request, session, g, current_app

import jwt

from flask_basicauth import BasicAuth

import settings

SHARABLE_ENDPOINTS = ["video", "stream_data_file", "static", "media.static"]


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

        if endpoint in SHARABLE_ENDPOINTS:
            if request.args.get("token") and endpoint == "video":
                token = request.args["token"]
                # 2021-12-10/gx030136.mp4
                vid = args["rel_path"].split("/")[-1].split(".")[0]
                try:
                    payload = jwt.decode(
                        token, current_app.config["SECRET_KEY"],
                        audience=vid, algorithms=["HS256"]
                    )
                    session["auth"] = payload
                    return
                except jwt.DecodeError as e:
                    current_app.logger.info(f"Rejected token {token}: {e}")
            elif session.get("auth"):
                # bypass static (no media here)
                if endpoint == "static":
                    return
                # find vid in any view_args to protect media static
                elif any([session["auth"]["aud"] in a for a in args.values()]):
                    return

        # fallback on basicauth
        auth = BasicAuth()
        auth.app = current_app
        if not auth.authenticate():
            return auth.challenge()
        else:
            g.is_admin = True

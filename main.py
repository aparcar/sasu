#!/usr/bin/python
# coding: utf-8
from flask import Flask, request, g, current_app
import json
from pathlib import Path
from rq import Connection, Queue
from os import getenv

from build import build
from common import get_hash, get_packages_hash

app = Flask(__name__)
app_settings = getenv("APP_SETTINGS", "config.DevelopmentConfig")
app.config.from_object(app_settings)


def get_profiles():
    if "profiles" not in g:
        g.profiles = json.loads(Path("profiles.json").read_text())
        print(f"Loaded {len(g.profiles)} profiles")
    return g.profiles


def get_packages():
    if "packages" not in g:
        g.packages = set(json.loads(Path("packages.json").read_text()))
        print(f"Loaded {len(g.packages)} packages")
    return g.packages


def get_queue():
    if "queue" not in g:
        with Connection():
            g.queue = Queue()
    return g.queue


def get_request_hash(request_data):
    request_data["packages_hash"] = get_packages_hash(request_data.get("packages", ""))
    request_array = [
        request_data.get("distro", ""),
        request_data.get("version", ""),
        request_data.get("profile", ""),
        request_data["packages_hash"],
        str(request_data.get("packages_diff", 0)),
    ]
    return get_hash(" ".join(request_array), 12)


def validate_request(request_data):
    target = get_profiles().get(request_data.get("profile", ""), {}).get("target")
    if not target:
        return (
            {
                "status": "bad_profile",
                "message": f"Unknown profile: {request_data['profile']}",
            },
            400,
        )
    else:
        request_data["target"] = target

    unknown_packages = set(request_data.get("packages", [])) - get_packages()
    if unknown_packages:
        return (
            {
                "status": "bad_packages",
                "message": f"Unknown package(s): {', '.join(unknown_packages)}",
            },
            422,
        )

    return (None, None)


@app.route("/api/build", methods=["POST"])
def api_build():
    request_data = dict(request.get_json())
    request_data = request.get_json()
    request_hash = get_request_hash(request_data)
    job = get_queue().fetch_job(request_hash)
    response = {}
    status = 200
    if job is None:
        response, status = validate_request(request_data)
        if not response:
            job = get_queue().enqueue(
                build,
                request_data,
                job_id=request_hash,
                result_ttl="24h",
                failure_ttl="12h",
            )
            status = 202

    if job.is_failed:
        status = 500
        response["message"] = job.exc_info.strip().split("\n")[-1]

    if job.is_queued:
        response = {"status": "queued"}

    if job.is_finished:
        response["url"] = current_app.config["STORE_URL"]
        response["build_at"] = job.ended_at
        response.update(json.loads(Path(job.result).read_text()))

    response["enqueued_at"] = job.enqueued_at

    return response, status


if __name__ == "__main__":
    app.run(debug=True)

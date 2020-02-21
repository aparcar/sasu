#!/usr/bin/python
# coding: utf-8

from flask import Flask, request, g, current_app, send_from_directory
from flask_cors import CORS
import json
from pathlib import Path
from rq import Connection, Queue
from os import getenv

from build import build
from common import get_str_hash, get_packages_hash, get_request_hash

app = Flask(__name__, static_url_path="", static_folder="yafs/")
app_settings = getenv("APP_SETTINGS", "config.DevelopmentConfig")
app.config.from_object(app_settings)

CORS(app, resources={r"/api/*": {"origins": "*"}})

def get_distros():
    return ["openwrt"]

def get_versions():
    if "versions" not in g:
        g.versions = json.loads(Path("versions.json").read_text())
        app.logger.info(f"Loaded {len(g.versions)} versions")
    return g.versions


def get_profiles():
    if "profiles" not in g:
        g.profiles = {}
        for version in get_versions():
            g.profiles[version] = json.loads(
                Path(f"profiles-{version}.json").read_text()
            )["profiles"]
            app.logger.info(f"Loaded {len(g.profiles[version])} profiles in {version}")
    return g.profiles


def get_packages():
    if "packages" not in g:
        g.packages = {}
        for version in get_versions():
            g.packages[version] = set(
                json.loads(Path(f"packages-{version}.json").read_text())
            )
            app.logger.info(f"Loaded {len(g.packages[version])} packages in {version}")
    return g.packages


def get_queue():
    if "queue" not in g:
        with Connection():
            g.queue = Queue()
    return g.queue


def validate_request(request_data):
    for needed in ["version", "profile"]:
        if needed not in request_data:
            return ({"status": "bad_version", "message": f"Missing {needed}"}, 400)


    if request_data.get("distro", "openwrt") not in get_distros():
        return (
            {
                "status": "bad_distro",
                "message": f"Unknown distro: {request_data['distro']}",
            },
            400,
        )

    if request_data.get("version", "") not in get_versions():
        return (
            {
                "status": "bad_version",
                "message": f"Unknown version: {request_data['version']}",
            },
            400,
        )

    target = (
        get_profiles()[request_data["version"]]
        .get(request_data.get("profile", ""), {})
        .get("target")
    )

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

    unknown_packages = (
        set(map(lambda p: p.strip("-"), request_data.get("packages", [])))
        - get_packages()[request_data["version"]]
    )
    if unknown_packages:
        return (
            {
                "status": "bad_packages",
                "message": f"Unknown package(s): {', '.join(unknown_packages)}",
            },
            422,
        )

    return (None, None)


@app.route("/")
@app.route("/<path:path>")
def root(path="index.html"):
    return send_from_directory("yafs/", path)


@app.route("/store/<path:path>")
def send_js(path):
    return send_from_directory("store", path)


@app.route("/api/profiles/<version>")
def api_profiles(version):
    return send_from_directory(".", f"profiles-{version}.json")


@app.route("/api/names/<version>")
def api_names(version):
    return send_from_directory(".", f"names-{version}.json")


@app.route("/api/packages/<version>")
def api_packages(version):
    return send_from_directory(".", f"packages-{version}.json")


@app.route("/api/versions")
def api_versions():
    return send_from_directory(".", "versions.json")


@app.route("/api/build", methods=["POST"])
def api_build():
    request_data = request.get_json()
    app.logger.debug(request_data)
    request_hash = get_request_hash(request_data)
    job = get_queue().fetch_job(request_hash)
    response = {}
    status = 200
    if not current_app.config["DEBUG"]:
        result_ttl = "24h"
        failure_ttl = "12h"
    else:
        result_ttl = "15m"
        failure_ttl = "15m"

    if job is None:
        response, status = validate_request(request_data)
        if not response:
            status = 202
            request_data["store"] = (
                Path(current_app.config["STORE_PATH"])
                / request_data["version"]
                / request_data["target"]
                / request_data["profile"]
            )

            request_data["packages"] = set(request_data["packages"])

            job = get_queue().enqueue(
                build,
                request_data,
                job_id=request_hash,
                result_ttl=result_ttl,
                failure_ttl=failure_ttl,
            )

    if job:
        if job.is_failed:
            status = 500
            response["message"] = job.exc_info.strip().split("\n")[-1]

        if job.is_queued or job.is_started:
            status = 202
            response = {"status": job.get_status()}

        if job.is_finished:
            response["url"] = (
                current_app.config["STORE_URL"] + "/" + str(job.result.parent)
            )
            response["build_at"] = job.ended_at
            response.update(json.loads(job.result.read_text()))

        response["enqueued_at"] = job.enqueued_at

    return response, status


if __name__ == "__main__":
    app.run(debug=True)

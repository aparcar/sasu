#!/usr/bin/python
# coding: utf-8
from flask import Flask, request, g
import json
import hashlib
from pathlib import Path

app = Flask(__name__)


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


def get_hash(string, length):
    h = hashlib.sha256()
    h.update(bytes(string, "utf-8"))
    response_hash = h.hexdigest()[:length]
    return response_hash


def get_packages_hash(packages):
    return get_hash(" ".join(sorted(list(set(packages)))), 12)


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
    if not request_data.get("profile", "") in get_profiles():
        return (1, "")
    unknown_packages = set(request_data.get("packages", [])) - get_packages()
    if unknown_packages:
        return (2, unknown_packages)


def lookup_request(request_data):
    request_hash = get_request_hash(request_data)
    print(request_hash)
    return False


@app.route("/api/build", methods=["POST"])
def entry_point():
    request_data = request.get_json()
    lookup = lookup_request(request_data)
    if lookup:
        return "Found", 200

    invalid = validate_request(request_data)
    if invalid:
        return f"Error {invalid}"

    return "OK", 202


if __name__ == "__main__":
    app.run(debug=True)

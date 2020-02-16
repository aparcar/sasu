import urllib.request
import re
from pathlib import Path
import json

version = "SNAPSHOT"


def download_package_indexes():
    base_url = "https://downloads.openwrt.org/snapshots/packages/x86_64/"
    sources = ["base", "luci", "packages", "routing", "telephony"]

    packages = set()
    for source in sources:
        print(f"Downloading {source}")
        source_content = (
            urllib.request.urlopen(f"{base_url}/{source}/Packages").read().decode()
        )
        source_packages = set(re.findall(r"Package: (.+)\n", source_content))
        print(f"Found {len(source_packages)} packages")
        packages.update(re.findall(r"Package: (.+)\n", source_content))

    print("Total of {len(packages)} packages found")

    Path("packages-SNAPSHOT.json").write_text(json.dumps(list(packages)))


def fill_metadata(dictionary, profile_info):
    dictionary.update(
        {
            "metadata_version": 1,
            "target": profile_info["target"],
            "version_commit": profile_info["version_commit"],
            "version_number": profile_info["version_number"],
            "link": "https://downloads.openwrt.org/snapshots/targets/%target/%file",
            "profiles": {},
        }
    )


def merge_json_files():
    profiles_json_overview = {}
    names_json_overview = {}

    profiles_json = Path("profiles/").glob("*.json")
    for profile_json in profiles_json:
        print(f"Merging {profile_json}")
        profile_info = json.loads(profile_json.read_text())

        if not profiles_json_overview:
            fill_metadata(profiles_json_overview, profile_info)
            fill_metadata(names_json_overview, profile_info)

        profiles_json_overview["profiles"][profile_info["id"]] = {
            "target": profile_info["target"]
        }

        for title in profile_info.get("titles", []):
            name = ""
            if title.get("title"):
                name = title.get("title")
            else:
                vendor = title.get("vendor", "")
                variant = title.get("variant", "")
                name = f"{vendor} {title['model']} {variant}"
            names_json_overview["profiles"][name.strip()] = {
                "target": profile_info["target"],
                "id": profile_info["id"],
                "images": profile_info["images"],
            }

    Path(f"profiles-{version}.json").write_text(json.dumps(profiles_json_overview))
    Path(f"names-{version}.json").write_text(json.dumps(names_json_overview))


merge_json_files()

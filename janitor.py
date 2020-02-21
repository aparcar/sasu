import urllib.request
import re
from pathlib import Path
import json

version = "SNAPSHOT"


def pretty_json_dump(filename, data):
    Path(filename).write_text(json.dumps(data, sort_keys=True, indent="  "))


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

    print(f"Total of {len(packages)} packages found")

    pretty_json_dump(f"packages-{version}.json", sorted(list(packages)))


def fill_metadata(dictionary, profile_info):
    dictionary.update(
        {
            "metadata_version": 1,
            "target": profile_info["target"],
            "version_commit": profile_info["version_commit"],
            "version_number": profile_info["version_number"],
            "url": "https://downloads.openwrt.org/snapshots/targets/%target",
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

    pretty_json_dump(f"profiles-{version}.json", profiles_json_overview)
    pretty_json_dump(f"names-{version}.json", names_json_overview)


merge_json_files()
download_package_indexes()

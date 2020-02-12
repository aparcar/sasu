import urllib.request
import re
from pathlib import Path
import json


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
    Path("packages.json").write_text(json.dumps(list(packages)))


def merge_json_files():
    profiles_json_overview = {}
    names_json_overview = {}

    profiles_json = Path("profiles/").glob("*.json")
    for profile_json in profiles_json:
        print(f"Merging {profile_json}")
        profile_data = json.loads(profile_json.read_text())
        profiles_json_overview[profile_data["id"]] = {"target": profile_data["target"]}
        for title in profile_data.get("titles", []):
            name = ""
            if title.get("title"):
                name = title.get("title")
            else:
                vendor = title.get("vendor", "")
                variant = title.get("variant", "")
                name = f"{vendor} {title['model']} {variant}"
            names_json_overview[name.strip()] = {
                "target": profile_data["target"],
                "id": profile_data["id"],
                "info": profile_data["image_prefix"] + ".json"
            }
    Path("profiles.json").write_text(json.dumps(profiles_json_overview))
    Path("names.json").write_text(json.dumps(names_json_overview))


merge_json_files()

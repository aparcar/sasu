import time
import urllib.request
import urllib
from pathlib import Path
import re
import nacl.signing
import struct
import base64
import tarfile
import subprocess
import time

from common import get_hash, get_packages_hash

keystr = "RWS1BD5w+adc3j2Hqg9+b66CvLR7NlHbsj7wjNVj0XGt/othDgIAOJS+"
base_url = "https://cdn.openwrt.org/snapshots/targets/{target}/{filename}"

def setup_ib(request):
    cache = Path("cache") / request["target"]
    download_file("sha256sums.sig")

    pkalg, keynum, pubkey = struct.unpack("!2s8s32s", base64.b64decode(keystr))
    sig = base64.b64decode((cache / "sha256sums.sig").read_text().splitlines()[-1])

    pkalg, keynum, sig = struct.unpack("!2s8s64s", sig)

    verify_key = nacl.signing.VerifyKey(pubkey, encoder=nacl.encoding.RawEncoder)
    try:
        verify_key.verify((cache / "sha256sums").read_bytes(), sig)
    except nacl.exceptions.CryptoError:
        print("bad signature")

    download_file("sha256sums")

    # openwrt-imagebuilder-ath79-generic.Linux-x86_64.tar.xz
    ib_search = re.search(
        r"^(.{64}) \*(openwrt-imagebuilder-.+?\.Linux-x86_64\.tar\.xz)$",
        (cache / "sha256sums").read_text(),
        re.MULTILINE,
    )

    assert ib_search

    ib_hash, ib_archive = ib_search.groups()

    download_file(ib_archive)

    tar = tarfile.open(cache / ib_archive)
    tar.extractall(path=cache)
    tar.close()

    (cache / ib_archive.rsplit(".", maxsplit=2)[0]).rename(cache / request["target"])

def build(request):
    cache = Path("cache") / request["target"]
    store = Path().cwd() / "store" / request["target"]

    if not (cache).is_dir():
        cache.mkdir(parents=True, exist_ok=True)

    if not (store).is_dir():
        store.mkdir(parents=True, exist_ok=True)

    def download_file(filename):
        urllib.request.urlretrieve(
            base_url.format(**{"target": request["target"], "filename": filename}),
            cache / filename,
        )

    sig_file = cache / "sha256sums.sig"
    if sig_file.is_file():
        last_modified = time.mktime(time.strptime(
            urllib.request.urlopen(
                base_url.format(
                    **{"target": request["target"], "filename": "sha256sums.sig"}
                )
            )
            .info()
            .get("Last-Modified"),
            "%a, %d %b %Y %H:%M:%S %Z",
        ))
        if sig_file.stat().st_mtime < last_modified:
            setup_ib(request)

    manifest = subprocess.run(
        [
            "make",
            "manifest",
            f"PROFILE={request['profile']}",
            f"PACKAGES={' '.join(request['packages'])}",
        ],
        text=True,
        capture_output=True,
        cwd=cache,
    )

    manifest_packages = set(
        list(map(lambda p: p.split()[0], manifest.stdout.splitlines()))
    )

    packages_hash = get_packages_hash(manifest_packages)

    if not (store / packages_hash).is_dir():
        (store / packages_hash).mkdir(parents=True, exist_ok=True)

    foo = subprocess.run(
        [
            "make",
            "image",
            f"PROFILE={request['profile']}",
            f"PACKAGES={' '.join(request['packages'])}",
            f"EXTRA_IMAGE_NAME={packages_hash}",
            f"BIN_DIR={store / packages_hash}",
        ],
        text=True,
        capture_output=True,
        cwd=cache,
    )

    return next(Path(store / packages_hash).glob("*.json"))

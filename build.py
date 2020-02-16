import time
import urllib.request
import json
import urllib
from pathlib import Path
import re
import nacl.signing
import struct
import base64
from shutil import rmtree
import tarfile
import subprocess

from common import get_packages_hash

keystr = "RWS1BD5w+adc3j2Hqg9+b66CvLR7NlHbsj7wjNVj0XGt/othDgIAOJS+"
base_url = "https://cdn.openwrt.org/snapshots/targets/{target}/{filename}"


def build(request):
    cache = (Path("cache") / request["target"]).parent
    target, subtarget = request["target"].split("/")
    store = Path().cwd() / "store" / request["target"]
    sums_file = Path(cache / f"{subtarget}_sums")
    sig_file = Path(cache / f"{subtarget}_sums.sig")

    def setup_ib(request):
        if (cache / subtarget).is_dir():
            rmtree(cache / subtarget)

        download_file("sha256sums", sums_file)
        download_file("sha256sums.sig", sig_file)

        pkalg, keynum, pubkey = struct.unpack("!2s8s32s", base64.b64decode(keystr))
        sig = base64.b64decode(sig_file.read_text().splitlines()[-1])

        pkalg, keynum, sig = struct.unpack("!2s8s64s", sig)

        verify_key = nacl.signing.VerifyKey(pubkey, encoder=nacl.encoding.RawEncoder)
        try:
            verify_key.verify(sums_file.read_bytes(), sig)
        except nacl.exceptions.CryptoError:
            assert False, "bad signature"

        # openwrt-imagebuilder-ath79-generic.Linux-x86_64.tar.xz
        ib_search = re.search(
            r"^(.{64}) \*(openwrt-imagebuilder-.+?\.Linux-x86_64\.tar\.xz)$",
            sums_file.read_text(),
            re.MULTILINE,
        )

        assert ib_search

        ib_hash, ib_archive = ib_search.groups()

        download_file(ib_archive)

        tar = tarfile.open(cache / ib_archive)
        tar.extractall(path=cache)
        tar.close()

        (cache / ib_archive).unlink()

        (cache / ib_archive.rsplit(".", maxsplit=2)[0]).rename(cache / subtarget)

    def download_file(filename, dest=None):
        urllib.request.urlretrieve(
            base_url.format(**{"target": request["target"], "filename": filename}),
            dest or (cache / filename),
        )

    if not (cache).is_dir():
        cache.mkdir(parents=True, exist_ok=True)

    if not (store).is_dir():
        store.mkdir(parents=True, exist_ok=True)

    if sig_file.is_file():
        last_modified = time.mktime(
            time.strptime(
                urllib.request.urlopen(
                    base_url.format(
                        **{"target": request["target"], "filename": "sha256sums.sig"}
                    )
                )
                .info()
                .get("Last-Modified"),
                "%a, %d %b %Y %H:%M:%S %Z",
            )
        )
        if sig_file.stat().st_mtime < last_modified:
            setup_ib(request)
    else:
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
        cwd=cache / subtarget,
    )

    manifest_packages = set(
        list(map(lambda p: p.split()[0], manifest.stdout.splitlines()))
    )

    packages_hash = get_packages_hash(manifest_packages)

    if not (store / packages_hash).is_dir():
        (store / packages_hash).mkdir(parents=True, exist_ok=True)

    image_build = subprocess.run(
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
        cwd=cache / subtarget,
    )

    assert not image_build.returncode, "ImageBuilder failed"

    Path(store / packages_hash / "buildlog.txt").write_text(image_build.stdout)

    return next(Path(store / packages_hash).glob("*.json"))
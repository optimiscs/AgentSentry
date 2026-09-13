"""Fetch official ModelScope weight copies, verifying the pinned HF identities.

Copy the small HF files into the target first when HF is unreachable on the host.
This fetcher never executes model repository code or changes model configuration.
"""

import argparse
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELSCOPE_REVISION = "e8885939589b1e032d291a1ceefd21b775e6277e"


def verify(path, expected):
    if path.stat().st_size != expected["size"]:
        raise ValueError("MODEL_SIZE_MISMATCH:" + path.name)
    sha = hashlib.sha256()
    git = hashlib.sha1(b"blob " + str(expected["size"]).encode() + b"\0")
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            sha.update(chunk)
            git.update(chunk)
    actual = sha.hexdigest() if expected["lfs_sha256"] else git.hexdigest()
    if actual != (expected["lfs_sha256"] or expected["git_blob_sha1"]):
        raise ValueError("MODEL_HASH_MISMATCH:" + path.name)
    return sha.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lock = json.loads((HERE / "model-lock.json").read_text())
    args.output.mkdir(parents=True, exist_ok=True)

    def fetch(pair):
        name, expected = pair
        if Path(name).name != name:
            raise ValueError("INVALID_MODEL_FILENAME")
        target = args.output / name
        if not target.exists():
            if not name.endswith(".safetensors"):
                raise ValueError("COPY_VERIFIED_HF_SMALL_FILES_FIRST:" + name)
            partial = target.with_suffix(target.suffix + ".partial")
            url = f"https://modelscope.cn/models/{lock['repo_id']}/resolve/{MODELSCOPE_REVISION}/{name}"
            subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                            "--retry", "3", "--connect-timeout", "20", "--max-time", "3600",
                            "--continue-at", "-", "--output", str(partial), url], check=True)
            verify(partial, expected)
            partial.rename(target)
        sha = verify(target, expected)
        print(json.dumps({"verified": name, "sha256": sha}), flush=True)
        return name, {"sha256": sha, "size": expected["size"]}

    with ThreadPoolExecutor(max_workers=4) as pool:
        files = dict(pool.map(fetch, lock["files"].items()))
    (args.output / "agentsentry-model.json").write_text(json.dumps({
        "repo_id": lock["repo_id"], "revision": lock["revision"],
        "weight_transport": "official ModelScope copy; verified against HF LFS SHA256",
        "modelscope_weight_revision": MODELSCOPE_REVISION, "files": files,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()

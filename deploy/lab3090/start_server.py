"""Start one pinned loopback model replica, retaining its exact process identity."""

import argparse
import hashlib
import json
import os
import socket
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--record-prefix", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    argv = config["arguments"]
    root = Path(config["cwd"])
    if argv[argv.index("--host") + 1] != "127.0.0.1":
        raise ValueError("LOOPBACK_ONLY")
    port = int(argv[argv.index("--port") + 1])
    with socket.socket() as connection:
        if connection.connect_ex(("127.0.0.1", port)) == 0:
            raise ValueError("MODEL_PORT_ALREADY_IN_USE")
    gpu = config["environment"]["CUDA_VISIBLE_DEVICES"]
    if gpu not in {"0", "1"}:
        raise ValueError("SINGLE_RESERVED_GPU_REQUIRED")
    used = subprocess.check_output([
        "nvidia-smi", "--id=" + gpu, "--query-gpu=memory.used",
        "--format=csv,noheader,nounits"], text=True)
    if int(used.strip()) > 512:
        raise ValueError("SELECTED_GPU_ALREADY_OCCUPIED")
    manifest = root / argv[argv.index("--model") + 1] / "agentsentry-model.json"
    if json.loads(manifest.read_text())["revision"] != config["model_revision"]:
        raise ValueError("MODEL_REVISION_MISMATCH")
    record = args.record_prefix.with_suffix(".json")
    if record.exists():
        raise ValueError("PROCESS_RECORD_ALREADY_EXISTS")
    with args.record_prefix.with_suffix(".log").open("x") as log:
        process = subprocess.Popen(
            [config["python"], *argv], cwd=root,
            env={**os.environ, **config["environment"]}, stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    state = {
        "pid": process.pid,
        "start_ticks": Path(f"/proc/{process.pid}/stat").read_text().rsplit(")", 1)[1].split()[19],
        "serving_config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "model_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "status": "STARTING",
    }
    record.write_text(json.dumps(state, indent=2) + "\n")
    print(json.dumps(state))


if __name__ == "__main__":
    main()

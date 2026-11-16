"""아주 작은 npm 레지스트리 흉내 (표준 라이브러리만 사용).

packages/ 아래의 패키지 폴더를 tarball 로 묶어 `npm install` 이 받아 갈 수 있게 해 준다.
인터넷이 막힌 환경의 '패키지 미러'가 어떤 모양인지, 그리고 opencode 의 "opencode-hello@1.0.0"
같은 npm 이름 지정이 레지스트리 주소(.npmrc / npm_config_registry)만 바꾸면 그대로 동작한다는 것을
오프라인으로 확인하려고 만들었다. 실제 미러(Verdaccio, Nexus, Artifactory ...)를 대체하지는 않는다.

    python mini_registry.py                 # 127.0.0.1:3919 에서 서비스
    python mini_registry.py --port 4000
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
import sys
import tarfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGES = HERE / "packages"


_tarballs: dict[Path, bytes] = {}


def build_tarball(pkg_dir: Path) -> bytes:
    """npm tarball 규칙: 모든 파일이 'package/' 아래에 있어야 한다.

    packument 의 shasum/integrity 와 실제로 내려 주는 tarball 의 바이트가 같아야 npm 이 받아 준다.
    "w:gz" 는 gzip 헤더에 현재 시각을 넣어서 초가 바뀌면 바이트가 달라지므로, 헤더 시각을 0 으로 고정하고
    패키지마다 한 번만 만들어 재사용한다.
    """
    if pkg_dir not in _tarballs:
        _tarballs[pkg_dir] = _make_tarball(pkg_dir)
    return _tarballs[pkg_dir]


def _make_tarball(pkg_dir: Path) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz, tarfile.open(fileobj=gz, mode="w") as tar:
        for path in sorted(pkg_dir.rglob("*")):
            if path.is_file() and "node_modules" not in path.parts:
                info = tarfile.TarInfo("package/" + path.relative_to(pkg_dir).as_posix())
                data = path.read_bytes()
                info.size = len(data)
                info.mtime = 0
                info.mode = 0o644
                tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class Registry(BaseHTTPRequestHandler):
    base_url = ""

    def log_message(self, fmt: str, *args: object) -> None:  # 요청 로그는 stderr 로
        sys.stderr.write("[registry] " + (fmt % args) + "\n")

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].lstrip("/")
        # 1) tarball: /<name>/-/<name>-<version>.tgz
        if "/-/" in path and path.endswith(".tgz"):
            name = path.split("/-/", 1)[0]
            pkg_dir = PACKAGES / name
            if pkg_dir.is_dir():
                return self._send(200, build_tarball(pkg_dir), "application/octet-stream")
        # 2) packument: /<name>
        pkg_dir = PACKAGES / path
        if "/" not in path and (pkg_dir / "package.json").is_file():
            meta = json.loads((pkg_dir / "package.json").read_text(encoding="utf-8"))
            tarball = build_tarball(pkg_dir)
            version = meta["version"]
            version_doc = dict(meta)
            version_doc["dist"] = {
                "tarball": f"{self.base_url}/{path}/-/{path}-{version}.tgz",
                "shasum": hashlib.sha1(tarball).hexdigest(),
                "integrity": "sha512-" + base64.b64encode(hashlib.sha512(tarball).digest()).decode(),
            }
            doc = {"name": path, "dist-tags": {"latest": version}, "versions": {version: version_doc}}
            return self._send(200, json.dumps(doc).encode("utf-8"), "application/json")
        self._send(404, b'{"error":"not found"}', "application/json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3919)
    args = parser.parse_args()
    Registry.base_url = f"http://{args.host}:{args.port}"
    server = ThreadingHTTPServer((args.host, args.port), Registry)
    print(f"mini registry: {Registry.base_url}  (packages: {', '.join(p.name for p in PACKAGES.iterdir() if p.is_dir())})", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

"""下载 Swagger UI 的静态资源到 app/static/swagger/（只需运行一次）。

为什么需要：FastAPI 的 /docs 默认从 cdn.jsdelivr.net 加载 JS/CSS，
国内网络常常连不上，表现为"页面 200 但一片空白"。
把资源下到本地后，内网、离线环境也能正常打开文档。

用法：
    python scripts/fetch_swagger_ui.py
"""

import io
import tarfile
import urllib.request
from pathlib import Path

VERSION = "5.17.14"
SOURCES = [
    f"https://registry.npmmirror.com/swagger-ui-dist/-/swagger-ui-dist-{VERSION}.tgz",
    f"https://registry.npmjs.org/swagger-ui-dist/-/swagger-ui-dist-{VERSION}.tgz",
]
TARGET = Path(__file__).resolve().parent.parent / "app" / "static" / "swagger"
WANTED = {"swagger-ui-bundle.js", "swagger-ui.css"}


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)

    for url in SOURCES:
        print(f"尝试下载: {url}")
        try:
            data = urllib.request.urlopen(url, timeout=120).read()
        except Exception as exc:
            print(f"  失败: {type(exc).__name__}: {exc}")
            continue

        print(f"  下载成功: {len(data) // 1024} KB")
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for member in tar.getmembers():
                name = Path(member.name).name
                if name in WANTED:
                    extracted = tar.extractfile(member)
                    if extracted is not None:
                        (TARGET / name).write_bytes(extracted.read())
                        print(f"  解出: {name}")
        break
    else:
        raise SystemExit("所有镜像都下载失败，请检查网络或手动下载 swagger-ui-dist")

    for name in sorted(WANTED):
        path = TARGET / name
        status = f"{path.stat().st_size // 1024} KB" if path.exists() else "缺失"
        print(f"  {name}: {status}")


if __name__ == "__main__":
    main()

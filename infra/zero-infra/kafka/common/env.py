# -*- coding: utf-8 -*-
"""`.env` 위치를 자동 탐색해 로드한다.

로컬(zero_data/.env)과 서버(opt/zero-infra/.env)의 폴더 구조가 다르므로,
호출하는 파일 위치에서 상위로 올라가며 `.env`를 찾는다. 어느 구조든 동작한다.
이미 os.environ에 값이 있으면(도커 env_file 등으로 주입) 덮어쓰지 않는다.
"""
import os
from pathlib import Path
from dotenv import load_dotenv


def find_and_load_env(start: Path | None = None, max_up: int = 6) -> Path | None:
    """start(기본: 이 파일 위치)에서 위로 올라가며 첫 번째 `.env`를 로드한다.
    로드한 경로를 반환하고, 못 찾으면 None. override=False라 기존 환경변수는 보존."""
    here = (start or Path(__file__)).resolve()
    for parent in [here, *here.parents][: max_up + 1]:
        candidate = parent / ".env"
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return candidate
    return None

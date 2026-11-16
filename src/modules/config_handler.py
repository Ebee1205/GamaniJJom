"""Load, read, modify and save a JSON config file backed by a pydantic model."""
import copy
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any, Generic, TypeVar

import orjson
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

UTF8_BOM = b"\xef\xbb\xbf"


class ConfigHandler(Generic[T]):
    """설정 파일 접근 창구.

    - 원본 JSON(dict)을 따로 들고 있어서, 모델에 정의되지 않은 키(예: secret_key)도
      저장할 때 사라지지 않는다.
    - 값을 바꿀 때마다 pydantic 모델로 검증하고, 실패하면 아무것도 바꾸지 않는다.
    - 저장은 임시 파일에 쓴 뒤 교체하므로, 도중에 실패해도 기존 파일이 깨지지 않는다.

    사용 예:
        handler = ConfigHandler("src/config/gamani-jjom.cfg.json", AppConfig)
        handler.load()
        handler.set("logger.level", "INFO")
        handler.save()
    """

    def __init__(self, path: str | Path, model: type[T]):
        self.path = Path(path)
        self._model_cls = model
        self._raw: dict[str, Any] = {}
        self._model: T | None = None
        self._dirty = False
        self._lock = RLock()

    # ------------------------------------------------------------------
    # 읽기
    # ------------------------------------------------------------------
    @property
    def model(self) -> T:
        """검증된 설정 객체. 읽기 전용으로 사용하고, 변경은 set()/update()로 한다."""
        if self._model is None:
            raise RuntimeError("설정이 아직 로드되지 않았습니다. load()를 먼저 호출하세요.")
        return self._model

    @property
    def is_dirty(self) -> bool:
        """저장되지 않은 변경이 있는지 여부."""
        return self._dirty

    def load(self) -> T:
        """파일을 읽어 검증한 뒤 설정 객체를 반환한다."""
        with self._lock:
            raw = self._read_file()
            self._model = self._model_cls.model_validate(raw)
            self._raw = raw
            self._dirty = False
            return self._model

    def get(self, key: str, default: Any = None) -> Any:
        """점(.)으로 구분한 경로로 값을 읽는다. 예: get("logger.level")"""
        with self._lock:
            try:
                return self._walk(self._raw, key.split("."))
            except KeyError:
                return default

    # ------------------------------------------------------------------
    # 수정
    # ------------------------------------------------------------------
    def set(self, key: str, value: Any) -> T:
        """값 하나를 바꾼다. 검증에 실패하면 pydantic.ValidationError, 변경은 취소된다."""
        return self.update({key: value})

    def update(self, changes: dict[str, Any]) -> T:
        """여러 값을 한 번에 바꾼다. 하나라도 검증에 실패하면 전부 취소된다."""
        with self._lock:
            candidate = copy.deepcopy(self._raw)
            for key, value in changes.items():
                self._assign(candidate, key.split("."), value)

            new_model = self._model_cls.model_validate(candidate)  # 실패 시 여기서 예외
            self._raw = candidate
            self._model = new_model
            self._dirty = True
            return new_model

    # ------------------------------------------------------------------
    # 저장
    # ------------------------------------------------------------------
    def save(self) -> None:
        """현재 설정을 파일에 저장한다. (BOM 없는 UTF-8, 들여쓰기 2칸)"""
        with self._lock:
            if self._model is None:
                raise RuntimeError("저장할 설정이 없습니다. load()를 먼저 호출하세요.")
            data = orjson.dumps(self._raw, option=orjson.OPT_INDENT_2) + b"\n"
            self._write_atomic(data)
            self._dirty = False

    # ------------------------------------------------------------------
    # 내부 구현
    # ------------------------------------------------------------------
    def _read_file(self) -> dict[str, Any]:
        # 윈도우 메모장이 붙이는 UTF-8 BOM 제거 (orjson은 BOM 불가)
        content = self.path.read_bytes().lstrip(UTF8_BOM)
        raw = orjson.loads(content)
        if not isinstance(raw, dict):
            raise ValueError(f"설정 파일의 최상위는 객체여야 합니다: {self.path}")
        return raw

    def _write_atomic(self, data: bytes) -> None:
        """같은 폴더의 임시 파일에 쓴 뒤 os.replace로 교체한다."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            dir=self.path.parent, prefix=self.path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "wb") as temp_file:
                temp_file.write(data)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_name, self.path)
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise

    @staticmethod
    def _walk(node: Any, parts: list[str]) -> Any:
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                raise KeyError(".".join(parts))
            node = node[part]
        return node

    @classmethod
    def _assign(cls, root: dict[str, Any], parts: list[str], value: Any) -> None:
        """경로의 마지막 키에 값을 넣는다. 중간 경로는 이미 존재하는 객체여야 한다."""
        parent = cls._walk(root, parts[:-1]) if len(parts) > 1 else root
        if not isinstance(parent, dict):
            raise KeyError(".".join(parts))
        parent[parts[-1]] = value


# --- how to use ConfigHandler ---
# handler = ConfigHandler("src/config/gamani-jjom.cfg.json", AppConfig)
# handler.load()                              # 읽기 + 검증
# handler.get("logger.level")                 # "DEBUG"
# handler.set("logger.level", "INFO")         # 수정 (메모리)
# handler.update({"logger.use_console": False, "environment": "prod"})
# handler.save()                              # 파일에 저장
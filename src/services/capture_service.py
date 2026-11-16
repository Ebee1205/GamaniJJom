"""Explicit replaceable placeholder: never reports a screenshot as successful."""
from src.models.window_schema import WindowInfo


class CaptureService:
    def capture(self, target: WindowInfo) -> None:
        raise NotImplementedError(
            "화면 캡처는 아직 준비 중입니다. 현재 버튼은 연결된 창을 확인하는 "
            "플레이스홀더이며 이미지·파일·클립보드를 만들지 않습니다."
        )

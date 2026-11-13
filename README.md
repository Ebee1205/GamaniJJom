# GamaniJJom — 가만히 좀

Windows 프로그램의 창 크기와 위치를 고정하는 데스크톱 도구입니다.
현재는 **실행 가능한 기본 GUI와 개발 환경**까지 구현되어 있습니다.
창 탐색·이동·크기 변경·고정 기능은 아직 구현되지 않았습니다.

## 실행

Windows, Python 3.11 이상이 필요합니다. 별도 런타임 패키지는 없습니다.
Tkinter는 Python 설치 시 Tcl/Tk 구성 요소가 포함되어 있어야 합니다.

```powershell
cd D:\GitHub\GamaniJJom
# .venv가 이미 있다면 생성 명령은 생략합니다.
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe main.py --check
.\.venv\Scripts\python.exe main.py
```

가상환경 활성화 없이도 위 명령으로 실행할 수 있습니다.
`--check`는 모듈과 Tkinter import를 검사하며, GUI 표시 자체는 검사하지 않습니다.

## 구조

```text
GamaniJJom/
├── main.py
├── pyproject.toml
├── requirements.txt
├── .run/GamaniJJom.run.xml
├── src/
│   ├── config/settings.py
│   ├── models/window.py
│   ├── ui/main_window.py
│   ├── services/lock_service.py
│   └── platform/windows/
│       ├── window_api.py
│       └── window_finder.py
├── assets/
└── tests/
```

`main.py`를 진입점으로 사용합니다. `__init__.py`를 만들지 않으며,
내부 모듈은 `from src.ui.main_window import MainWindow`처럼 절대 import합니다.
프로젝트 루트가 import 기준입니다. `src` 자체를 Sources Root로 지정하지 않습니다.
서비스와 Win32 어댑터는 역할을 적어 둔 골격입니다.
아이콘과 자동 테스트는 아직 추가하지 않았습니다.

## IntelliJ IDEA

1. JetBrains Python 플러그인을 활성화합니다.
2. Python SDK는 `.venv\Scripts\python.exe`를 사용합니다.
3. 프로젝트 SDK와 모듈 SDK를 같은 Python SDK로 설정합니다.
4. 실행 목록에서 `GamaniJJom`을 선택해 실행합니다.
5. 설정 파일을 반영하지 못하면 프로젝트를 닫았다가 다시 엽니다.

실행 설정은 루트 `main.py`, 작업 폴더는 프로젝트 루트이며 모듈 SDK를 상속합니다.
공식 Python 플러그인의 에디션·구독 조건은 JetBrains 안내를 확인하세요:
https://www.jetbrains.com/help/idea/python.html

## 다음 구현

- Win32 창 목록과 정보 조회
- 좌표·크기 입력 및 적용
- 다중 창 고정·해제와 종료 감지
- 설정 저장, 트레이 및 단축키

# GamaniJJom — 가만히 좀

Windows 10/11용 PySide6 창 컨트롤러입니다. 프로그램마다 작은 플로팅 툴바를 붙이고
창 위치·크기를 고정합니다. 설정 창을 닫아도 트레이에서 실행됩니다.

## 설치와 실행

Python 3.11 이상, PySide6 6.8 이상, Windows 대화형 데스크톱이 필요합니다.
이번 검증 환경은 Python 3.11 / PySide6 6.12.0입니다.

```powershell
cd D:\GitHub\GamaniJJom
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -B src/main.py --check
.\.venv\Scripts\python.exe -B src/main.py
# 대체 실행 및 1.2초 후 자동 종료 검사
.\.venv\Scripts\python.exe -B -m src.main
.\.venv\Scripts\python.exe -B -m src.main --smoke-test
```

`__init__.py` 없이 `from src...` 절대 import를 사용합니다. 직접 실행 시 진입점이
프로젝트 루트를 import 경로에 추가하므로 작업 폴더가 달라도 실행됩니다.
`python -m src.main`은 프로젝트 루트에서 실행하세요. 기본 설정·로그·QSS·SVG 경로는
프로젝트 루트 기준입니다. `--cfg`와 `GAMANI_CONFIG`도 유지합니다. 직접 전달한 상대
설정 경로만 작업 폴더 기준입니다. 기존 IntelliJ 설정은 수정하지 않았으며,
VS Code 실행·환경 검사·자동 종료 검사는 `.vscode/launch.json`에 있습니다.

## 사용

1. 처음 열리는 **프로그램 연결** 대화상자에서 다른 앱의 창을 클릭하거나 목록에서
   선택합니다. 다음 클릭 감시는 40ms 간격이며 클릭을 가로채지 않습니다.
   Esc 또는 20초 경과 시 취소합니다. 빠른 클릭이 누락되면 목록을 사용하세요.
2. 대상 앱을 활성화하면 외곽 오른쪽 위에 작은 툴바가 표시됩니다.
   화면 밖으로 나가는 부분은 대상 모니터의 작업 영역 안으로 보정합니다.
3. **핸들**을 드래그하면 대상 기준 오프셋을 변경합니다. 대상 창 자체를 움직이지 않습니다.
4. **Lock**은 현재 위치·크기를 기억하고 200ms마다 변경을 확인해 복구합니다.
   다시 클릭하면 해제합니다. Lock 버튼 우클릭으로 해당 대상의 좌표 창을 엽니다.
5. **Capture**는 준비 중입니다. 클릭 시 명시적 플레이스홀더 알림만 표시하며
   이미지·파일·클립보드를 생성하지 않습니다. 우클릭의 저장 옵션도 준비 중 알림입니다.
6. **더보기**에서 연결, 해당 대상의 위치·크기 설정, 연결 관리·설정,
   부착 위치 초기화, 숨기기, 연결 해제 및 종료를 선택합니다.
7. 트레이 더블클릭으로 **연결된 프로그램·설정** 창을 엽니다. 연결된 창을 선택해
   컨트롤러 표시, 좌표 변경, 연결 해제를 실행할 수 있습니다.
8. 설정 창을 닫으면 숨겨집니다. 트레이 또는 더보기의 **종료**로 앱을 종료합니다.

대상 이동·크기 변경을 따라가고 최소화·숨김·다른 앱 활성화 시 툴바를 숨깁니다.
대상 활성화 시 다시 나타납니다. 툴바의 자체 메뉴가 활성화되어 있는 동안은 메뉴를
유지하지만 다른 앱으로 전환하면 숨깁니다. 대상 사각형이 모니터 전체와 정확히
일치하면 전체 화면으로 간주해 숨깁니다. 대상 종료 또는 HWND/PID 변경 시 연결을 제거합니다.
같은 HWND/PID를 다시 연결하면 기존 툴바를 사용하며, 여러 창을 동시에 연결할 수 있습니다.
수동 숨김은 트레이의 **모든 컨트롤러 다시 표시** 또는 연결 관리의 표시 버튼으로 해제합니다.

## 좌표와 고정 정책

좌표는 네이티브 화면 픽셀, 크기는 창 바깥 테두리 기준입니다. 음수 X/Y를 지원하고
너비·높이는 1 이상이어야 합니다. 최소화·최대화 상태에서는 강제 복원하지 않으며
Lock 적용을 보류합니다. 일반 창으로 복원되면 기존 사각형의 감시를 재개합니다.
새 Lock 및 직접 좌표 변경은 일반 창에서만 허용합니다.

좌표 편집은 기존 Lock을 해제하고 변경 요청을 보낸 뒤 300ms 후 실제 결과를 읽어
성공·불일치·오류를 표시합니다. 비동기 변경이므로 앱의 크기 제한·권한·응답 지연으로
실제 결과가 다를 수 있습니다. Lock 요청을 5회 따르지 않으면 다음 확인에서 해제하고
알립니다. API 오류도 Lock을 해제합니다. 숨김·최소화 동안은 복구 요청을 보내지 않고,
다른 앱으로 전환한 일반 창의 Lock은 계속 유지합니다. 앱 종료·연결 해제는 Lock을 해제합니다.

## UI 구조와 책임

```text
src/ui/
  application.py                 서비스 생성과 최상위 Controller 연결
  resources.py                   프로젝트 루트 QSS·SVG 로딩
  wd/
    floating_toolbar.py          FloatingToolbarWindow: 최상위 투명 창
    settings.py                  SettingsWindow: 연결 관리 화면
  dlg/
    target_picker_dlg.py         TargetPickerDialog: 대상 선택·취소
    position_dlg.py              PositionDialog: 좌표 입력·결과 표시
  cmp/
    button_cmp.py                ButtonComponent: 공통 아이콘 버튼
    toolbar_cmp.py               ToolbarComponent: 핸들·버튼·더보기 메뉴
    window_list_cmp.py           WindowListComponent: 재사용 목록·선택 유지
    sys_tray_cmp.py              SystemTrayComponent: 트레이 표시·명령 신호
  cntr/
    toolbar_cntr.py              ToolbarController: 대상 1개·Lock·Capture·표시 정책
    settings_cntr.py             SettingsController: 목록·좌표 적용·결과 확인
    tray_cntr.py                 TrayController: 앱 생명주기·연결 목록·트레이 명령
src/services/toolbar_service.py  Win32 상태 조회·툴바 배치·마우스 선택
resource/qss/theme.qss           외부 테마
resource/icons/                 lock.svg / unlock.svg / capture.svg / more.svg
```

View(`wd/dlg/cmp`)는 Qt와 모델만 사용합니다. UI 신호 → Controller → Service →
기존 `adapters/windows` 순서로 호출하며 Controller도 Win32 API를 직접 import하지 않습니다.
서비스는 Qt 위젯을 알지 못합니다. Windows API·기존 모델·설정 파일의 위치는 보존했습니다.
인수인계의 `platform/models/config` 재배치는 권장안이므로 이번 UI 작업에 포함하지 않았습니다.

구 `ui/floating_toolbar.py`, `main_window.py`, `tray.py`는 새 View 클래스를 가리키는
이름 호환 모듈입니다. 옛 생성자·메서드·신호 API까지 보장하지 않습니다.
새 코드는 위 구조의 클래스를 직접 import하세요. 구 Tkinter `ui/components`는
기존 파일을 보존하기 위해 남겼으며 실행 경로에 포함되지 않습니다.

## 구현 범위와 검증

구현: UI 계층 분리, SVG 아이콘·외부 QSS, 다중 연결, 트레이, 대상 감시,
위치·크기 Lock, 해당 창 좌표 편집, 클릭·목록 선택.

미구현: 실제 스크린샷, 전역 단축키, 설정 저장·자동 재연결, WinEventHook, EXE 배포.
연결·오프셋·Lock 상태는 메모리에만 저장합니다. 툴바 부착 위치는 기본 외곽 오른쪽 위와
드래그 오프셋으로 제공하며 위치 프리셋 설정은 아직 없습니다.

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

29개 검사 통과, 건너뜀 없음. Qt 버튼·View·Controller, 목록 선택 유지, 좌표 적용과
결과 확인, 표시 정책, 중복 연결, 종료 정리, 마우스 선택 서비스, UI 계층 의존성,
기존 서비스와 실제 별도 Win32 창의 이동·Lock 복구를 확인했습니다.
실제 `--check`는 루트·src·무관한 폴더에서 통과했으며 직접·모듈 실행의
`--smoke-test`도 창과 트레이를 열고 정상 종료했습니다.

UI 상태 전이 검사는 서비스 대역을 사용합니다. 임의의 모든 외부 앱, 실제 마우스
드래그·혼합 DPI 모니터 이동·전체 화면 조합을 포괄하는 검사는 아닙니다.
샘플 데이터로 실제 위젯을 렌더링한 미리보기를 별도 제공합니다.

참고: [Qt 창 속성](https://doc.qt.io/qtforpython-6/PySide6/QtCore/Qt.html),
[Qt Test](https://doc.qt.io/qtforpython-6/PySide6/QtTest/index.html).

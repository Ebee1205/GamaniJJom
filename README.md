# GamaniJJom — 가만히 좀

Windows 10/11용 PySide6 플로팅 창 컨트롤러입니다. 대상 프로그램마다 작은 툴바를
연결하고 현재 위치·크기를 고정합니다. 관리 창을 닫아도 트레이에서 계속 실행됩니다.

## 설치와 실행

Python 3.11 이상과 Windows 대화형 데스크톱이 필요합니다.

```powershell
cd D:\GitHub\GamaniJJom
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -B src/main.py --check
.\.venv\Scripts\python.exe -B src/main.py
# 모듈 실행도 지원
.\.venv\Scripts\python.exe -B -m src.main
# 트레이와 선택 창을 열었다가 1.2초 후 종료
.\.venv\Scripts\python.exe -B src/main.py --smoke-test
```

`__init__.py` 없이 `from src...` 절대 import를 사용합니다. 직접 실행은 진입점이
프로젝트 루트를 `sys.path`에 추가하므로 작업 폴더와 무관합니다. `-m src.main`은
프로젝트 루트에서 실행하세요. 설정과 상대 로그 경로도 프로젝트 루트 기준입니다.
`--cfg` 및 `GAMANI_CONFIG`를 보존하며, 명시적으로 전달한 상대 설정 경로는 작업
폴더 기준입니다. 기존 IntelliJ 설정(`cwd=src`)은 수정하지 않았습니다.
VS Code에서는 폴더를 열고 `.venv` 인터프리터를 선택한 뒤 F5로 실행합니다.
`.vscode/launch.json`에 일반 실행·환경 검사·GUI 간단 검사를 추가했습니다.
`pyproject.toml`은 의존성 선언용이며 배포 패키징은 아직 제공하지 않습니다.

## 사용

1. 처음 표시되는 목록에서 창을 선택하고 **선택한 창 연결**을 누릅니다.
   HWND·PID·제목·좌표·크기를 표시하며 F5로 갱신합니다. 살아 있는 선택은 유지합니다.
2. 대상 앱을 활성화하면 외곽 오른쪽 위에 작은 툴바가 나타납니다.
   화면 밖으로 나가는 부분은 대상 모니터의 작업 영역 안으로 보정합니다.
3. **⠿** 핸들을 드래그하면 대상 기준 툴바 위치가 바뀝니다. 대상 창 자체는 움직이지 않습니다.
4. **Lock**은 누른 순간의 바깥 창 사각형을 저장합니다. 위치·크기가 변하면
   200ms 간격으로 감지해 원래 값으로 재적용합니다. 다시 누르면 해제합니다.
5. **Capture**는 명시적 플레이스홀더입니다. 준비 중이라는 알림을 표시하며
   이미지·PNG 파일·클립보드는 만들지 않습니다.
6. **···** 메뉴에서 대상 연결, 좌표 편집, 부착 위치 초기화, 숨기기, 연결 해제를 선택합니다.
   연결을 해제하면 Lock도 해제됩니다. 좌표 편집은 기존 Lock을 해제한 뒤 적용합니다.
7. 트레이 우클릭에서 **화면에서 창 선택**을 누르면 20초 동안 다음 마우스 클릭의
   최상위 창에 연결합니다. Esc 또는 시간 초과로 취소합니다. 클릭을 가로채지 않으므로
   클릭은 대상 앱에도 전달됩니다. 아주 빠른 클릭은 감지되지 않을 수 있어 목록 선택도 제공합니다.
8. 트레이 더블클릭으로 관리 창을 다시 엽니다. 닫기·Esc는 관리 창만 숨기며,
   트레이 또는 더보기의 **종료**로 프로그램을 종료합니다.

같은 HWND/PID를 다시 연결하면 기존 툴바를 재사용합니다. 서로 다른 창은 여러 개
연결할 수 있습니다. 대상 종료·PID 변경 시 연결을 제거합니다. 숨겨진 창, 최소화된 창,
다른 앱이 활성화된 경우에는 툴바를 숨깁니다. 대상이 다시 활성화되면 표시합니다.
트레이의 **모든 툴바 다시 표시**는 수동 숨김을 해제하며, 활성 대상에만 표시합니다.
대상 사각형이 모니터 전체와 정확히 일치하면 전체 화면으로 간주해 숨깁니다.
툴바는 별도 투명 도구 창이며 대상 프로세스에 코드를 주입하지 않습니다.

## 고정·좌표 동작

기존 `WindowService`, Win32 탐색·필터·PID 검증·`SetWindowPos`를 재사용합니다.
좌표는 네이티브 화면 픽셀, 크기는 바깥 창 테두리 기준입니다. 음수 X/Y를 지원하며
너비·높이는 1 이상이어야 합니다. Qt 좌표와 섞이지 않도록 툴바도 Win32 픽셀로 배치합니다.
사용자 입력 적용은 300ms 뒤 실제 결과를 읽어 성공 또는 불일치를 표시합니다.

최소화·최대화 상태에서는 Lock 적용을 중단하고 강제로 복원하지 않습니다.
일반 창으로 복원되면 저장한 사각형의 감시를 재개합니다. 해당 상태에서는 새 Lock과
좌표 적용을 거부합니다. 다른 앱으로 전환해도 일반 창의 Lock 감시는 계속됩니다.
창 활성화와 Z 순서를 바꾸지 않는 비동기 이동 요청을 사용합니다. 앱의 크기 제한이나
권한 때문에 실패할 수 있습니다. 요청을 따르지 않는 상태가 5회 지속되면 다음 확인에서
Lock을 해제하고 알립니다. API 오류도 Lock을 해제하고 알립니다.

## 구조

```text
src/main.py                           진입점·설정·로거·DPI·QApplication
src/ui/application.py                 생명주기·타이머·표시 정책·동작 연결
src/ui/floating_toolbar.py            투명 툴바·드래그·버튼 신호
src/ui/tray.py                        트레이와 연결 목록
src/ui/main_window.py                 필요 시 여는 Qt 대상 선택·좌표 편집
src/models/attachment.py              대상·Lock 사각형·툴바 오프셋
src/services/attach_service.py        연결 중복 방지·해제
src/services/lock_service.py          고정·유예·실패 정책
src/services/capture_service.py       교체 가능한 명시적 캡처 플레이스홀더
src/services/window_service.py        기존 탐색·PID 검증·좌표 적용
src/adapters/windows/window_api.py    기존 Win32 API + 상태·모니터·마우스 선택
src/ui/components/                   보존한 구 Tkinter 구성 요소 (실행 경로에서 제외)
```

이 단계는 Qt 기반 아키텍처와 기본 UX 골격입니다. WinEventHook 대신 200ms 타이머를
사용합니다. 전역 단축키, 실제 화면 캡처, 설정 저장, 재실행 시 자동 재연결은 아직 없습니다.
툴바 드래그·혼합 DPI 환경의 모니터 간 이동·시각적 배치는 실제 화면에서 추가 확인이 필요합니다.
연결 상태·Lock·툴바 오프셋은 메모리에만 있으며 종료 시 사라집니다.

## 검증

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

서비스 정책 테스트, 별도 테스트 프로세스의 실제 Win32 창 탐색·이동·Lock 복구·종료 감지,
서로 다른 작업 폴더에서의 진입점 부트스트랩 검사, Qt 위젯 기본 검사를 제공합니다.
네이티브 테스트는 자체 테스트 창만 변경하고 닫습니다. Qt가 없으면 위젯 검사만 건너뜁니다.
진입점 부트스트랩 검사는 Qt 실행 부분을 대체해 설정·로그·namespace import만 검사하므로
`--check`나 GUI 실행 성공을 의미하지 않습니다.

이번 작업 환경 결과: 11개 중 10개 통과, Qt 검사 1개 건너뜀. Python 구문·TOML·VS Code
JSON 검증 통과. PySide6 미설치 및 설치 시 네트워크 실패로 실제 `--check`와
`--smoke-test`는 `ModuleNotFoundError: PySide6`로 실패했습니다. Qt 화면 검증은 미완료입니다.

참고: [Qt 투명·비활성 표시 속성](https://doc.qt.io/qtforpython-6/PySide6/QtCore/Qt.html),
[Qt의 화면 배율 좌표](https://doc.qt.io/qtforpython-6/overviews/qtdoc-highdpi.html),
[SetWindowPos](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setwindowpos).

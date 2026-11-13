# GamaniJJom — 가만히 좀

Windows 창의 위치와 크기를 관리하는 데스크톱 도구입니다.

## 실행

현재 IntelliJ SDK는 `.venv\Scripts\python.exe` (Python 3.11)입니다.
Tkinter·ctypes 외에 기존 설정·로거에서 orjson과 pydantic을 사용합니다.
새 환경은 `python -m pip install -r requirements.txt`로 준비합니다.

```powershell
cd D:\GitHub\GamaniJJom
.\.venv\Scripts\python.exe src/main.py --check
.\.venv\Scripts\python.exe src/main.py
# 대체 실행
.\.venv\Scripts\python.exe -m src.main
```

`--check`는 설정·로거·UI/Win32 import를 검사하며 GUI 표시는 검사하지 않습니다.
기존 IntelliJ `main` 설정은 `src/main.py`, 작업 폴더는 `src`입니다.
진입점에서 프로젝트 루트를 import 경로에 추가하므로 그대로 실행할 수 있습니다.
기본 설정·로그 경로도 프로젝트 루트 기준으로 해석합니다. IDE 설정은 보존합니다.

## 사용

1. HWND(16진수), PID, 제목, X/Y/너비/높이를 조회합니다.
2. 목록 새로고침 또는 F5로 갱신합니다. 살아 있는 선택은 유지합니다.
3. 창을 선택하면 최신 좌표·크기가 입력란에 표시됩니다.
4. 정수를 입력하고 위치·크기 적용을 누릅니다. 실제 결과를 재조회합니다.

좌표는 화면 픽셀, 크기는 바깥 창 사각형 기준입니다. 음수 X/Y를 지원합니다.
너비·높이는 1 이상이어야 합니다. 최소화·최대화 창은 복원 후 적용합니다.
숨김·제목 없는 창, 도구 창, 일반 소유 팝업, DWM cloaked 창,
이 프로그램 자신의 프로세스 창은 제외합니다.

변경 요청은 포커스·창 순서를 유지하며 비동기로 전달됩니다. 300ms 뒤 실제 결과를
확인합니다. 대상 앱의 크기 제한·권한·응답 지연으로 결과가 다를 수 있습니다.
계속 고정하거나 자동 재적용하는 기능은 아직 없습니다.

## 구조

```text
src/main.py                         진입점·설정·로거·DPI 초기화
src/app_context.py                  기존 애플리케이션 설정
src/config/gamani-jjom.cfg.json      기존 설정 파일
src/models/window_schema.py         WindowInfo / WindowRect
src/ui/main_window.py               목록·선택·입력·결과 표시
src/services/window_service.py      목록·PID 확인·입력 검증·적용
src/services/lock_service.py        향후 다중 창 고정 정책용 골격
src/platform/windows/window_api.py  ctypes Win32 선언·조회·변경
src/platform/windows/window_finder.py 일반 창 필터링
```

`__init__.py` 없이 `from src...` 절대 import를 사용합니다.
기존 설정·로거·모델·고정 서비스 골격을 보존합니다.

## 검증

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Windows 대화형 데스크톱이 필요합니다. 별도 테스트 프로세스 창으로 조회·선택·갱신,
실제 위치/크기 변경, 입력 오류, PID 불일치, 종료 감지를 검사하고 테스트 창을 닫습니다.
사용자 앱은 테스트에서 이동하지 않습니다.

Win32 기준: [EnumWindows](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-enumwindows),
[GetWindowRect](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-getwindowrect),
[SetWindowPos](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setwindowpos).

다음 확장: 다중 창 선택, 고정 주기·해제, 종료 감지, 설정 저장.
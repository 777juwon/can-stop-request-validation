# G0 환경 점검과 설치 항목 결정

후속 안내: 이 문서는 설치 전 G0의 관측 기록이다. 이후 사용자가 설치 진행과 기존 0.9.14 제거를 승인했다. 현재 설치 및 실행 상태는 [SETUP_AND_SMOKE](SETUP_AND_SMOKE_2026-10-19.md)와 STATUS를 따른다. 아래의 미설치 및 기존 client 보존 계획은 G0 당시 상태를 보존한다.

점검일: 2026-10-19

기준 커밋: `94411a45aac647a0b9b0c811606d74c8f30d1df2`, 구현 기준선 v1.0.

결과: **G0 PASS — 환경 조사와 설치 계획 기록 완료**. G1~G4는 NOT_RUN이다. 이 판정은 vCAN 송수신, CARLA 실행 또는 시험 기한 충족을 의미하지 않는다.

## 1. 최신 문서 확보와 이전 작업 보존

원본 작업 폴더에서 `git pull --ff-only`를 실행하여 HEAD를 `62a193a`에서 `94411a4`로 전진시켰다. 브랜치는 main을 유지했다. 새 RESEARCH_BASELINE.md와 THESIS_OUTLINE.md를 포함한 v1.0 문서가 이제 실제 작업 폴더에 있다.

이전 미커밋 분석 파일 4개는 [백업 manifest](../evidence/g0/2026-10-19/pre_sync/manifest.json)에 기록한 경로로 원문과 SHA-256을 보존했다. 충돌하는 두 추적 파일은 백업을 검증한 뒤 apply_patch로 이전 HEAD 내용에 잠시 맞추어 fast-forward를 수행했다. 이후 최신 STATUS를 기준으로 현재 결과를 기록하고, 이전 WORKLOG 항목은 최신 이력과 합쳤다. 이전 분석 문서 본문도 유지했다.

동기화 증거: [checkout_sync.json](../evidence/g0/2026-10-19/checkout_sync.json). 커밋 생성, push, 브랜치 전환, reset 또는 stash는 수행하지 않았다.

## 2. 관측한 환경

| 항목 | 실제 관측 | 판단 |
| --- | --- | --- |
| OS | Ubuntu 22.04.5 LTS, x86_64 | 기준 OS 계열 확인 |
| 커널 | 6.8.0-138-generic | 현재 버전 기록 |
| CPU | AMD Ryzen 7 8845HS, 8코어/16스레드 | 현재 사양 기록 |
| RAM | 14 GiB, 당시 available 10 GiB | CARLA 실행 성능은 별도 확인 |
| Swap | 31 GiB, 당시 사용량 0 | 변경 필요 근거 없음 |
| 프로젝트 디스크 | 여유 200 GiB | 계획한 배포본 저장 공간은 확보 가능 |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU | 권한을 높인 조회에서 확인 |
| GPU 메모리 | 총 8188 MiB, 당시 여유 7806 MiB | 동적인 조회값이며 성능 측정 아님 |
| NVIDIA 드라이버 | 570.211.01 | 조회 성공, 재설치 필요 근거 없음 |
| Vulkan | libvulkan1 1.3.204.1-2 설치, vulkaninfo 없음 | 실제 Vulkan 장치 열거 미확인 |
| Git | 2.34.1 | 최신 기준선 fast-forward 성공 |
| Python | /usr/bin/python3, CPython 3.10.12 | 프로젝트 venv에 재사용할 인터프리터로 선택 |
| Python ABI | cpython-310-x86_64-linux-gnu, glibc 2.35 | 공식 cp310 Linux wheel과 태그상 호환 |
| pip | 현재 python3에서 25.3, 사용자 설치 경로 | 프로젝트 설치는 별도 venv에서 수행 예정 |
| venv | python3.10-venv 설치, venv/ensurepip 모듈 존재 | Python 또는 venv 지원 패키지 추가 설치 불필요 |
| 프로젝트 가상환경 | .venv, venv, env 모두 없음 | .venv 생성 예정, 아직 생성하지 않음 |
| 기존 Python 패키지 | carla 0.9.14, numpy 1.26.4 | 기존 환경 보존, 새 venv에서 분리 |
| CAN Python 패키지 | 현재 python3에 python-can/cantools 없음 | 프로젝트 환경에 설치 필요 |
| CAN 도구 | candump/cansend/cangen 및 can-utils 없음 | can-utils 설치 필요 |
| 네트워크 도구 | iproute2 5.15.0-1ubuntu2, modinfo/modprobe 존재 | 추가 설치 불필요 |
| vCAN 커널 지원 | CONFIG_CAN, CONFIG_CAN_RAW, CONFIG_CAN_VCAN 모두 m; vcan.ko 존재 | 별도 커널 빌드나 vCAN 패키지 설치 불필요 |
| CAN 소켓 | PF_CAN raw socket 생성/닫기 성공 | 소켓 지원 확인, 프레임 송수신은 미수행 |
| vCAN 인터페이스 | type vcan 조회 빈 결과, vcan0 없음 | G1에서 모듈 준비와 인터페이스 생성 필요 |
| CARLA 서버 | 프로젝트, 검사한 /opt 경로, PATH 및 carla-simulator 패키지에서 미확인 | 프로젝트용 0.9.15 서버 준비 계획 |

메모리와 디스크 값은 점검 시점의 값이다. 다른 개인 폴더나 회사 프로젝트를 탐색하지 않았다. CARLA 서버와 가상환경의 전역 부재를 증명한 것은 아니며, 프로젝트와 명시한 표준 경로에서의 결과다. 기존 carla 0.9.14는 Python client 메타데이터로 확인한 것이며 서버 설치의 증거가 아니다.

## 3. 실패 및 관측 한계

- 기본 샌드박스의 nvidia-smi 조회는 종료코드 9로 드라이버 통신에 실패했다. 명시적 승인을 받은 샌드박스 밖의 동일 조회는 종료코드 0으로 성공했다. 첫 실패를 호스트 드라이버 고장으로 판정하지 않았다. 두 결과를 [hardware.json](../evidence/g0/2026-10-19/hardware.json)에 함께 보존했다.
- dpkg-query의 종료코드 1에는 can-utils, Python 3.9 및 vulkan-tools의 미설치가 포함된다. python3-venv 메타패키지는 미설치지만 python3.10-venv는 설치되어 있으므로 추가 venv 패키지를 요구하지 않는다.
- `ip -details link show dev vcan0`은 종료코드 1, `Device "vcan0" does not exist.`였다. vCAN 드라이버 파일 존재를 실제 통신 성공으로 해석하지 않았다.
- PF_CAN 소켓 생성은 기능 탐지다. 커널의 자동 모듈 로드를 유발할 수 있으며 순수 파일 조회와 구분한다. 명시적 modprobe, 인터페이스 생성, 프레임 송신은 수행하지 않았다.
- Vulkan 장치 열거, CARLA 서버 실행, 서버/client 연결 및 차량 속도 관측은 수행하지 않았다.

## 4. 설치 대상으로 결정한 항목

| 순서 | 항목 | 결정과 근거 | 이번 실행 여부 |
| --- | --- | --- | --- |
| 1 | can-utils | G1의 독립 송수신 도구로 Ubuntu 패키지 설치 | 미설치 |
| 2 | 프로젝트 .venv | 기존 Python 3.10.12와 설치된 venv 지원 사용 | 미생성 |
| 3 | python-can==4.6.1 | 공개 참고 환경과 같은 버전, Python >=3.9 | 미설치 |
| 4 | cantools==40.7.1 | 공개 참고 환경과 같은 버전, Python >=3.9, python-can >=4.6.0 | 미설치 |
| 5 | vcan 모듈 및 vcan0 준비 | 드라이버는 이미 있음. G1 시작 시 상태 재확인 후 설정 | 미수행 |
| 6 | vulkan-tools | G2 전 GPU/Vulkan 점검용으로 권장 | 미설치 |
| 7 | CARLA 0.9.15 Linux 서버 | 공식 release의 배포본을 프로젝트 third_party 아래 별도 보관 | 미다운로드 |
| 8 | carla==0.9.15 Python client | 새 .venv에 cp310 Linux wheel 사용, 서버와 일치 | 미설치 |

기존 Python, 사용자 carla 0.9.14, numpy와 NVIDIA 드라이버는 유지한다. Python 3.9, conda, pyenv 또는 새 커널 설치는 현재 근거상 필요하지 않다. 이는 첫 실행 환경의 선택이며 SUT의 고정 요구사항과 수치를 변경한 것이 아니다.

CARLA 0.9.15의 공식 PyPI 파일 목록에 `carla-0.9.15-cp310-cp310-manylinux_2_27_x86_64.whl`이 있다. 현재 CPython 3.10/x86_64/glibc 2.35와 태그가 맞으므로 별도 Python 3.9 설치 대신 이 조합을 선택한다. 실제 import 및 서버 호환성은 설치 후 G2에서 확인한다. [공식 배포 파일](https://pypi.org/project/carla/0.9.15/#files)

의존성 상태도 확인했다. python-can 4.6.1은 2025-08-12 공개본이며 확인 시 PyPI 최신 버전도 4.6.1이었다. cantools 40.7.1은 2025-09-30 공개본이고 프로젝트에는 이후 릴리스가 있으나 최초 재현은 조사한 버전으로 고정한다. 추가 의존성 전체의 해결, import와 잠금 파일 생성은 아직 수행하지 않았다. [python-can](https://pypi.org/project/python-can/4.6.1/), [cantools](https://pypi.org/project/cantools/40.7.1/)

## 5. CARLA 다운로드 규모와 경로

[공식 0.9.15 release](https://github.com/carla-simulator/carla/releases/tag/0.9.15)가 연결한 Linux 배포 URL은 `https://downloads.carlasim.com/Linux/CARLA_0.9.15.tar.gz`다. HEAD 요청은 HTTP 200, Content-Length 8,386,636,048 bytes를 반환했다. 약 8.39 GB이며 본문은 다운로드하지 않았다. ETag를 SHA-256 검증값으로 해석하지 않는다.

공식 quick start는 설치 공간을 약 20 GB로 안내한다. 압축본과 해제본을 함께 보관할 공간까지 고려하고 실제 사용량은 설치 뒤 기록한다. 현재 여유는 200 GiB다. [공식 설치 안내](https://carla.readthedocs.io/en/0.9.15/start_quickstart/)

설치 예정 경로는 `third_party/CARLA_0.9.15/`이며 Git 제외 대상이다. 실제 서버/client 버전, 배포 URL, 로컬 파일 해시와 설치 후 용량을 기록해야 한다. 추가 맵 필요 여부는 G2에서 고정된 Town04의 제공 여부를 확인한다. 이번에는 서버, wheel 또는 추가 맵을 받지 않았다.

## 6. 다음 작업에 사용할 명령 제안

**아래는 모두 계획이며 이번에 실행하지 않았다.** 사용자 요청 범위는 설치 항목 결정까지다.

시스템 도구 설치:

```bash
sudo apt-get update
sudo apt-get install --no-install-recommends can-utils vulkan-tools
```

프로젝트 가상환경과 Python 패키지 준비:

```bash
python3.10 -m venv .venv
.venv/bin/python -m pip install --index-url https://pypi.org/simple --only-binary=:all: python-can==4.6.1 cantools==40.7.1 carla==0.9.15
.venv/bin/python -m pip check
```

이후 설치된 전체 의존성과 정확한 버전을 기록한다. 패키지 설치 명령은 아직 검증된 lock 파일이 아니다.

vCAN 준비는 다시 존재 여부를 조회한 뒤 수행한다. vcan0가 여전히 없을 때만 add한다.

```bash
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set dev vcan0 up
```

그다음 독립 프로세스 사이의 알려진 ID/DLC/payload, 주기 송신과 대상 송신 중단을 확인해 G1 증거를 남긴다. CARLA 배포본 확보와 단독 제어는 별도 G2 작업이다.

## 7. 증거와 검증 범위

| 파일 | 내용 |
| --- | --- |
| [hardware.json](../evidence/g0/2026-10-19/hardware.json) | OS, CPU, RAM, 디스크, 실패한 GPU 조회와 승인 후 성공 결과 |
| [software.json](../evidence/g0/2026-10-19/software.json) | 명령 존재, Python/pip/패키지, 커널 CAN 지원과 프로젝트 경로 점검 |
| [additional_checks.json](../evidence/g0/2026-10-19/additional_checks.json) | Git, CARLA 표준 경로, Python ABI와 vcan0 조회 |
| [dependency_metadata.json](../evidence/g0/2026-10-19/dependency_metadata.json) | 공식 PyPI의 버전, Python 조건, 파일 해시 및 공식 release 메타데이터 |
| [carla_download_probe.json](../evidence/g0/2026-10-19/carla_download_probe.json) | 공식 Linux 배포본 HEAD 결과와 다운로드하지 않았다는 범위 |
| [checkout_sync.json](../evidence/g0/2026-10-19/checkout_sync.json) | fast-forward 전후 커밋 및 백업 검증 |

환경 명령은 각 JSON에 실행 인자, 관측 출력과 종료코드로 기록했다. 네트워크 조회는 공개 메타데이터와 HEAD 요청으로 제한했다. 설치, vCAN 왕복과 CARLA 시나리오 시험은 미수행이다.

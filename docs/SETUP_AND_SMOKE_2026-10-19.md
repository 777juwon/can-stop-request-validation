# 환경 설치와 G1/G2 최소 실행 기록

작업일: 2026-10-19. 설계 기준선 v1.0, 기준 Git commit `94411a4`.

이 문서는 G0 이후의 설치 및 연결 확인 작업이다. SUT 구현, CAN 정지 요청의 차량 연동, 80회 본시험과 구분한다.

## 1. 요청 범위와 현재 상태

사용자는 다음 단계 실행, CARLA 0.9.15 설치와 기존 0.9.14 환경 제거를 허용했다. 직접 비밀번호를 입력해야 하는 명령은 사용자 터미널에서 실행할 수 있도록 준비한다.

| 항목 | 현재 관측 |
| --- | --- |
| 프로젝트 .venv | CPython 3.10.12로 생성 완료 |
| Python 패키지 | carla 0.9.15, python-can 4.6.1, cantools 40.7.1 설치 및 실제 import 확인 |
| 의존성 확인 | Python -I 격리 실행에서 pip check 통과 |
| 기존 CARLA 0.9.14 | 발견된 사용자 Python client만 pip uninstall 완료, 원래 패키지와 dist-info 경로 제거 확인 |
| 시스템 도구/vcan0 | 사용자 스크립트 실행 뒤 can-utils 2020.11.0-1, vulkan-tools 1.3.204.0+dfsg1-1, 실제 vcan0 UP 확인 |
| CARLA 서버 | 공식 배포본 다운로드 및 해제 완료, 실제 server/client 0.9.15 일치 |
| G1 실행 | PASS, 독립 수신에서 거리 20개와 심박 40개를 확인 |
| G2 실행 | PASS, run01 FAIL/run02 ENV_ERROR 보존 후 run03 및 최종 run04 PASS |
| 서버 종료 | Ctrl+C에서 Signal 11/exit 139를 2회 관측, 포트 종료 확인, 원인 미해결 |
| G3/G4 및 본시험 | NOT_RUN, 본시험 실행 0회 |

현재 설치된 Python 의존성은 [requirements.lock.txt](../requirements.lock.txt)에 기록한다. 기존 CARLA 서버 폴더는 확인한 경로에서 발견하지 못했으므로 임의의 다른 폴더를 삭제하지 않았다.

## 2. Python 설치와 격리

프로젝트 .venv는 시스템 Python을 변경하지 않고 생성했다. 설치 대상은 [requirements.txt](../requirements.txt)의 고정 버전 3개이며 공식 PyPI의 binary wheel을 사용했다. 설치 기록은 [pip_install.json](../evidence/setup/2026-10-19/pip_install.json), import와 격리 확인은 [python_environment.json](../evidence/setup/2026-10-19/python_environment.json)이다.

초기 venv의 pip 22.0.2는 `--report`를 지원하지 않아 첫 명령이 종료코드 2로 끝났다. 해당 시도에서는 설치가 진행되지 않았다. 이후 명령 결과를 자체 JSON에 기록하는 방식으로 설치를 완료했다.

또한 터미널에 설정된 외부 Python 경로 때문에 격리 옵션 없는 pip check/freeze에 기존 ROS 패키지 메타데이터가 섞였다. 프로젝트에 ROS 패키지를 추가하지 않았으며, 이후 Python `-I`로 외부 PYTHONPATH와 사용자 site 경로를 배제했다. 이 상태에서 실제 모듈 경로가 프로젝트 .venv인지 확인하고 pip check를 통과시켰다. lock 파일도 격리 상태에서 생성했다.

프로젝트 점검 명령:

```bash
bash tools/check_project.sh
```

이 명령은 격리된 Python으로 단위 검사와 pip check, 셸 문법 및 git diff 공백 검사를 실행한다. 단위 검사 39개와 pip check가 통과했다. 단위 검사의 성공을 G1/G2 실행 증거로 사용하지 않는다.

## 3. CARLA 0.9.14 제거

제거 전 메타데이터와 기록 파일 범위를 확인했다. 발견한 것은 `/home/parkjuwon/.local/lib/python3.10/site-packages`의 carla 0.9.14 client였다. 기록된 12개 경로가 해당 패키지와 dist-info에만 속하는지 확인한 뒤, 사용자 승인에 따라 작업 폴더 밖 파일 접근 권한을 받아 다음 명령을 실행했다.

```bash
python3 -m pip uninstall --yes carla
```

종료코드 0, `Successfully uninstalled carla-0.9.14`. 새 프로젝트 client 0.9.15는 별도 .venv에 있어 영향을 받지 않는다. [제거 전](../evidence/setup/2026-10-19/carla014_before.json), [제거 확인](../evidence/setup/2026-10-19/carla014_removal.json).

## 4. 시스템 권한 단계와 사용자 실행 기록

시스템 패키지 설치 시도는 `sudo: a password is required`, 종료코드 1이었다. 이를 설치 성공으로 처리하지 않았다.

사용자에게 전달한 명령:

```bash
sudo bash /home/parkjuwon/can-stop-request-validation/tools/setup_g1_host.sh
```

[setup_g1_host.sh](../tools/setup_g1_host.sh)는 can-utils/vulkan-tools 설치, 기존 vcan 모듈 준비, vcan0가 없을 때만 생성, 장치 종류 확인 후 UP 설정을 수행한다. 물리 CAN이나 같은 이름의 다른 종류 장치는 변경하지 않는다. 실제 G1 프레임 교환은 별도다.

사용자가 실행 완료를 알린 뒤 dpkg-query와 ip JSON으로 실제 상태를 재확인했다. [호스트 확인](../evidence/setup/2026-10-19/host_setup.json). 승인된 호스트 Vulkan 조회는 종료코드 0으로 NVIDIA GPU와 AMD GPU를 열거했다. 일부 ICD 하나를 건너뛰었다는 경고도 [Vulkan 요약](../evidence/setup/2026-10-19/vulkan_summary.json)에 보존했다.

## 5. G1 독립 vCAN 도구

[g1_vcan_smoke.py](../tools/g1_vcan_smoke.py)는 별도 PID의 송신기와 수신기로 실제 AF_CAN/CAN_RAW 프레임을 주고받는다. 연결 확인용 입력은 50 ms x 40슬롯으로, 거리 20개와 심박 40개를 송신하고 후반 20슬롯에서는 거리만 중단한다. 본시험 입력과 구분한다.

독립 관측 프레임의 ID/DLC/raw bytes, 순서, 수량, 송신 슬롯과 중단 후 심박 지속을 검사한다. 원시 JSONL, worker 결과, 실행 명령, 최종 판정을 새 출력 폴더에 저장한다. SIGTERM도 증거와 정리 경로를 거치도록 한다.

실제 실행한 명령이다. 재실행 시 출력 폴더는 존재하지 않는 새 run ID를 사용한다.

```bash
.venv/bin/python -I tools/g1_vcan_smoke.py --interface vcan0 --output-dir evidence/g1/g1-20261019-01
```

종료코드 0, G1 PASS. 별도 receiver와 sender 프로세스의 종료코드가 모두 0이며, 수신 관측 60개가 기대 ID/DLC/payload 및 순서와 일치했다. 거리 중단 뒤 20개 심박의 첫 관측부터 마지막 관측까지 949.955037 ms 동안 추가 거리 프레임이 없었다. 이는 연결 확인 구간이며 SUT 응답 지연이 아니다. [판정](../evidence/g1/g1-20261019-01/verdict.json), [명령과 프로세스](../evidence/g1/g1-20261019-01/commands.json), [원시 수신](../evidence/g1/g1-20261019-01/receiver.jsonl).

## 6. CARLA 서버와 G2 도구

공식 배포 URL: `https://downloads.carlasim.com/Linux/CARLA_0.9.15.tar.gz`.

사용량 중단 직전에는 다운로드 및 해제 중이었다. 재개 시 실제 [설치 기록](../evidence/setup/2026-10-19/server_install.json)의 COMPLETE와 필수 실행 파일을 확인했다. 해제는 2026-10-19 11:28:04 UTC에 완료돼 있었다. 다시 다운로드하거나 설치하지 않았다.

완료 파일은 `third_party/downloads/CARLA_0.9.15.tar.gz`, 설치 위치는 `third_party/CARLA_0.9.15/`다. 모두 Git 제외 대상이다. 크기는 8,386,636,048 bytes, 로컬 SHA-256은 `7b2f432ce74b251593f95dcc8dee6d99ad9625c2a71a2d6d48f24d879de19ef7`이다. 이는 로컬 무결성 식별값이며 upstream checksum과 대조한 진위 확인은 아니다. data 필터로 36,163개 archive member를 해제했고 일반 파일 논리 크기 합계는 20,205,989,874 bytes다. 외부 CarlaUE4.sh의 내용과 동적 라이브러리 의존성을 확인한 뒤 실행했다.

[start_carla_0915.sh](../tools/start_carla_0915.sh)는 offscreen, Low 품질, 음향 비활성화와 지정 RPC 포트로 서버를 시작한다. 이 프로세스에만 PRIME 환경 변수를 설정한다. 실제 NVIDIA GPU 사용은 `nvidia-smi pmon -c 1 -s um`에서 CARLA PID 36908, type C+G, framebuffer 2623 MB로 확인했다. GPU 모델은 RTX 4060 Laptop, driver 570.211.01이다. 엔진 로그의 GPU 식별이나 성능 벤치마크 결과로 확대하지 않는다. [NVIDIA PRIME 설명](https://download.nvidia.com/XFree86/Linux-x86_64/570.211.01/README/primerenderoffload.html)

초기 5초 연결 조회는 준비 대기로 timeout이었다. 다음 조회는 client의 기본 `~/carlaCache` 생성이 sandbox 쓰기 제한에 걸렸다. 권한을 받아 실행한 조회에서 server/client 0.9.15 연결을 확인했다. 프로젝트 밖 캐시 접근 때문에 실제 G2 실행도 해당 권한을 받아 진행했다. [서버 실행과 종료 기록](../evidence/setup/2026-10-19/server_runtime.json).

[g2_carla_smoke.py](../tools/g2_carla_smoke.py)는 전용 서버, 정확한 0.9.15 버전, 빈 world를 확인한다. 명시적으로 허용한 경우 Town04를 로드하고 Model3 한 대만 생성한다. 단일 동기 tick, Ackermann 목표 속도, 실제 get_velocity와 적용 제어로 이동 및 제동을 관찰한다. 자신이 생성한 actor만 제거하고 설정과 날씨를 복구한다.

실제 서버 시작 명령이다. 현재 서버는 종료돼 있으며, 필요할 때 다시 실행한다.

```bash
bash tools/start_carla_0915.sh
```

별도 터미널 또는 실행 프로세스:

```bash
.venv/bin/python -I tools/g2_carla_smoke.py --host 127.0.0.1 --port 2000 --exclusive-server --allow-world-load --output-dir evidence/g2/g2-20261019-04
```

G2는 단독 실행 확인이다. CAN 수신, 정지 요청, adapter 연결이나 논문 전체 시험의 성공을 의미하지 않는다. 시각은 호스트 monotonic과 CARLA frame/time을 분리 기록한다.

## 7. G2 실제 시도와 원인 분석

각 명령은 위와 같고 출력 폴더의 마지막 번호만 달랐다. 이미 존재하는 폴더를 재사용하지 않는다. 재실행은 새 run ID가 필요하다.

| 시도 | 종료코드 / 결과 | 관측 및 판단 |
| --- | --- | --- |
| [run01](../evidence/g2/g2-20261019-01/result.json) | 1 / FAIL | 초기 차속은 유지했지만 제동 45표본에서 brake=0, throttle>0. 제동 적용과 정지를 확인하지 못함 |
| [run02](../evidence/g2/g2-20261019-02/result.json) | 2 / ENV_ERROR | sticky_control=false 변경 후 이동하지 못해 30초 준비 제한으로 종료. 이 설정은 채택하지 않음 |
| [run03](../evidence/g2/g2-20261019-03/result.json) | 0 / PASS | sticky=true와 batch 제동으로 실제 적용 및 정지 확인 |
| [run04](../evidence/g2/g2-20261019-04/result.json) | 0 / PASS | 고정 frame 경계 처리까지 보완한 최종 소스로 서버 재시작 후 재확인 |

CARLA 0.9.15의 [Vehicle.cpp](https://github.com/carla-simulator/carla/blob/0.9.15/LibCarla/source/carla/client/Vehicle.cpp#L47-L56)는 동일한 VehicleControl의 전송을 생략한다. Ackermann 호출은 이 캐시를 변경하지 않아 초기 정차와 같은 brake=1을 다시 보낼 때 전환이 누락되는 동작과 run01 관측이 일치했다. sticky=false는 [서버 AI tick](https://github.com/carla-simulator/carla/blob/0.9.15/Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Vehicle/WheeledVehicleAIController.cpp#L129-L134)의 기본 제어 주입도 활성화해 Ackermann 주행에 영향을 준다. 이 동작은 run02의 이동 불가를 설명한다.

최종 수정은 sticky=true를 유지하고 `client.apply_batch_sync([ApplyVehicleControl(...)], False)`로 제동을 전달한다. 응답 1개, 오류 없음, actor ID 일치를 검사하고 별도로 world.tick을 한 번만 실행한다. [공식 batch 처리 경로](https://github.com/carla-simulator/carla/blob/0.9.15/Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Server/CarlaServer.cpp#L2304-L2374). 응답 성공과 실제 제동 적용은 별개로 판정한다.

또한 CARLA의 float32 0.05초가 누적되면 40간격이 2.0000000298초로 표현된다. 정확히 2초 끝 경계의 오판을 막도록 고정 40 frame 간격 안에서 정지 유지를 판정한다. 40간격 끝 성공과 41간격 실패의 회귀 검사를 추가했다. 기준선의 속도, 제동값, 0.5초 유지와 2초 창은 변경하지 않았다. run01~03의 당시 소스도 각 evidence 폴더에 보존하고 기록된 SHA-256과 일치함을 확인했다.

최종 run04: Town04, Model3, ClearNoon, spawn index 143, actor 147. 199개의 연속 frame에서 실제 평면 속도를 재계산했다. 준비는 호스트 7.863초, 정상 속도는 4.575~4.964 km/h에서 21표본 동안 유지했다. 최초 제동 적용은 frame 2608, 정지 유지 11표본의 완료는 그 뒤 시뮬레이션 0.550000008초다. 최대 tick 조회 소요 3.241051 ms와 일정 지연 0.126838 ms도 보존했다. 이 한정된 실행의 관측값이지 본시험 지연 분포가 아니다. [원시 차량 상태](../evidence/g2/g2-20261019-04/vehicle_states.jsonl), [독립 재계산](../evidence/g2/g2-20261019-04/observation_audit.json).

자체 actor 제거와 날씨 및 설정 복구 호출이 성공했고, 별도 [사후 조회](../evidence/g2/g2-20261019-04/post_cleanup.json)에서 관련 actor 없음, synchronous_mode=false, fixed_delta_seconds=null을 확인했다. Town04 로드는 명시 허용했으며 원래 맵으로 되돌리지 않았다. spawn 좌표는 G2 후보일 뿐 본시험 고정 좌표로 승인한 것은 아니다.

## 8. 종료 문제와 다음 단계

차량 정리와 설정 복구 이후 Ctrl+C로 서버를 종료할 때 두 번 모두 Signal 11/exit 139가 발생했다. 포트 2000/2001이 닫힌 것은 확인했지만 정상 종료로 기록하지 않는다. 공식 C++의 ConsoleCommand 경로도 조사했으나 설치된 Python binding에는 해당 명령이 없어 AttributeError로 끝났고, 서버에 quit 명령은 전송되지 않았다. 종료 crash의 원인은 미해결이며 장시간 무인 실행 전에 점검해야 한다.

다음 기능 단계는 G3다. 별도 vCAN 송신기에서 v1.0 StopRequest를 보내고 단일 adapter의 수신, 제동 호출, 적용 frame, 실제 차속을 각각 확인한다. G4의 거리 타임아웃 SUT와 80회 본시험은 아직 시작하지 않는다. 설치와 G2 결과를 근거로 전체 통합을 PASS 처리하지 않는다.

# 80회 결과 분석과 재현 안내

2026-11-02. 원래80회만 대상으로 오프라인 분석을 완료했다. **COMPLETE80, 실행별 전체PASS70/FAIL10, 정리PASS80**이다. FAIL10건은 전부A/T-04의R-04다. 예비/개발 확인이나 추가 실행을 분모에 섞지 않았다. 동결한 독립 oracle로80개 원시 로그를 재계산했고 저장한 판정/지표와80개 모두 일치했다. 추가 CAN/CARLA 실행은0회다.

## 산출물

| 파일 | 내용 |
| --- | --- |
| [실행별 측정값](../analysis/main-20261102/per_run_metrics.csv) | 80행. 식별/판정/요청 유무/처리/정지/일정 지연/요구사항 상태 |
| [셀별 결과](../analysis/main-20261102/cell_outcomes.csv) | 4개 시나리오 x A/B의 원래 시도/COMPLETE/PASS/FAIL/미관측 수 |
| [통계표](../analysis/main-20261102/metric_statistics.csv) | 지표별 관측/결측/비해당 분모와 최소/중앙/최대 |
| [요구사항 추적표](../analysis/main-20261102/requirement_traceability.csv) | 셀/요구사항별 PASS/FAIL/N/A/비해당과 원시 증거 파일 |
| [같은 반복의 A/B 대응](../analysis/main-20261102/paired_observations.csv) | 40쌍. 둘 다 관측된 경우에만 B-A 요청 시각 차이 계산 |
| [분석 재현 기록](../analysis/main-20261102/analysis_manifest.json) | 사용한741개 입력/보존소스 파일SHA, 동결20개와 분석코드SHA, 도구/글꼴 버전, 대표8개 ID |
| [제4~5장](THESIS_CHAPTERS_4_5.md) | 실제 결과표/그림과 해석 및 한계를 반영한 본문 |
| [최종5장 통합 원고](THESIS_DRAFT.md) | 국문초록, 갱신한 제1~3장, 제4~5장과 참고문헌 |

실험 원시 파일은 로컬 `runs/main-v1-20261101`에 유지한다. 표와 그래프를 저장소에서 검토할 수 있지만 전체 원시 로그가 없는 다른 체크아웃에서 재판정을 수행했다고 주장하지 않는다. 제출한 작성계획서/HWP와 연구 설계 v1.0의 수치는 수정하지 않았다.

## 결과 해석

- T-01은 A/B 각각10회 모두 정상 주행과 순번 회전을 확인했다. R-01/R-05 PASS, 정지 지표는N/A다.
- T-02와 T-03은 각각 A/B10회 모두 요청/실제 제동/정지와 유지 기준을 만족했다.
- T-04 A는10회 미요청으로 R-04 FAIL이다. B는10회 순번 만료(reason3) 요청과 실제 정지/잠금 유지PASS다. 미요청을0 ms 응답이나 정지 성공으로 바꾸지 않았다.
- R-06/R-07을 평가할 수 있는 실행은50회이며 모두PASS다. R-08은PASS50/N/A10/시나리오 비해당20으로 분모를 구분한다. R-09는80회PASS다.
- 작은 시간 차이는 처리 성능의 통계적 우위를 뜻하지 않는다. 동일 반복의 B-A 요청 관측 차이는 양수/음수가 모두 있었고, 호스트 일정 지연과 반복 호출의 큰 지연값도 보존했다. 최대 송신 시작 지연43.512419ms, 최대 기록 tick 일정 지연22.936023ms였다.

통계 단위는 원래 시도다. adapter의 실행 내부 최댓값10개의 중앙값을 모든 개별 호출의 중앙값과 혼동하지 않는다. 요청 관측은 호스트 monotonic, 정지 창은 CARLA frame/시뮬레이션 시간을 쓴다.50개 정지 실행의 유지 완료는 모두11frame 간격인 명목0.55초였으며,0.05초의 표본 간격/고정 차량 모델보다 세밀한 차이를 주장하지 않는다.

## 그래프5종

모든 그림은300dpi PNG와 벡터SVG/PDF를 함께 제공한다. PDF의 한글 글꼴을 포함하고 SVG는 글자를 경로로 저장했다. 대표 시계열은 각 셀의 첫 반복R01로 고정했으며 분포 그림은10개 원래 값을 모두 표시한다.

| 그림 | PNG | 벡터 |
| --- | --- | --- |
| 4-1 시나리오별 판정 수 | [PNG](../analysis/main-20261102/figures/fig4-1_outcomes.png) | [SVG](../analysis/main-20261102/figures/fig4-1_outcomes.svg), [PDF](../analysis/main-20261102/figures/fig4-1_outcomes.pdf) |
| 4-2 요청 관측 분포 확대 | [PNG](../analysis/main-20261102/figures/fig4-2_request_latency.png) | [SVG](../analysis/main-20261102/figures/fig4-2_request_latency.svg), [PDF](../analysis/main-20261102/figures/fig4-2_request_latency.pdf) |
| 4-3 실행별 adapter 최댓값 | [PNG](../analysis/main-20261102/figures/fig4-3_adapter_maxima.png) | [SVG](../analysis/main-20261102/figures/fig4-3_adapter_maxima.svg), [PDF](../analysis/main-20261102/figures/fig4-3_adapter_maxima.pdf) |
| 4-4 T-04 호스트 시계열 | [PNG](../analysis/main-20261102/figures/fig4-4_t04_host_timeline.png) | [SVG](../analysis/main-20261102/figures/fig4-4_t04_host_timeline.svg), [PDF](../analysis/main-20261102/figures/fig4-4_t04_host_timeline.pdf) |
| 4-5 실제 속도와 적용 제동 | [PNG](../analysis/main-20261102/figures/fig4-5_vehicle_motion.png) | [SVG](../analysis/main-20261102/figures/fig4-5_vehicle_motion.svg), [PDF](../analysis/main-20261102/figures/fig4-5_vehicle_motion.pdf) |

그림4-2는 조건별 분포를 확대한 서로 다른 세로축이다. 판정 상한100/300ms는 범위 밖임을 명시했다. 그림4-4의5~8초 음영은 호스트의 명목 입력 구간이며 그림4-5의 시뮬레이션 축에 옮기지 않았다. 실제 화면 캡처는 아직 없으며 이 그래프를 촬영 사진으로 설명하지 않는다.

## 직접 재현

현재 장치의 분석 환경과 결과는 이미 준비했다. 아래 초기 설치는 새 환경에서만 필요하다. 같은 Python3.10을 사용하면서 실험용 `.venv`와 동결한 requirements.lock.txt를 보존하도록 `.venv-analysis`에 분리했다. 직접 의존성은 [고정 요구사항](../requirements-analysis.txt), 전체 버전은 [분석 잠금 파일](../requirements-analysis.lock.txt)이다. Python3.10 지원을 [Matplotlib PyPI](https://pypi.org/project/matplotlib/3.10.8/)와 [NumPy PyPI](https://pypi.org/project/numpy/2.2.6/)에서 확인하고 바이너리 패키지를 설치했다. 시스템 패키지/드라이버는 변경하지 않았다.

```bash
cd /home/parkjuwon/can-stop-request-validation
.venv/bin/python -I -m venv .venv-analysis
.venv-analysis/bin/python -I -m pip install --only-binary=:all: -r requirements-analysis.lock.txt
```

분석은 기존 폴더를 덮어쓰지 않는다. 아래 명령은 **사용자 재현 예정**이며 존재하지 않는 출력 이름을 사용한다. 서버/vcan0는 필요 없다. `/usr/share/fonts/truetype/nanum/NanumGothic.ttf`를 사용하며 해시는 manifest에 남긴다.

```bash
.venv-analysis/bin/python -I tools/analyze_main_results.py \
  --campaign runs/main-v1-20261101 \
  --output-dir analysis/reproduction-01
```

기대: status=COMPLETE, original_attempts=80, outcomes의PASS70/FAIL10, new_experiments_executed=0. 원본SHA/동결 코드/재판정이 불일치하면 중단하며 기존 증거는 수정하지 않는다. 라이브러리 없이 표 검증만 재현하려면 기존 `.venv`에서 `--no-figures`를 추가해 새 출력 경로로 실행할 수 있다.

```bash
bash tools/run_self_checks.sh check
.venv-analysis/bin/python -I -m pip --no-cache-dir --disable-pip-version-check check
```

통합 원고의 원본은 THESIS_ABSTRACT.md, THESIS_CHAPTERS_1_3.md, THESIS_CHAPTERS_4_5.md다. 본문을 수정한 뒤 통합본 교체를 명시하려면 다음 명령을 사용한다. 원래 HWP 파일은 접근하지 않는다.

```bash
.venv/bin/python -I tools/build_thesis_draft.py --overwrite
```

## 남은 확인

서버 프로세스의 정상 종료는 아직 미확인이고 기존 Signal11/139 문제는 해결했다고 표시하지 않았다. 논문용 시각화 촬영, HWP 학교 양식/실제20쪽 편집과 지도교수 검토는 별도다. 본문/표/그림의 반영 완료와 최종 제출 준비 완료를 구분한다.

후속 촬영 기록: 같은 날 사용자 위임으로 [별도 위치 재구성 사진6개](CARLA_CAPTURES_2026-11-02.md)를 저장했다. 촬영 자원 정리는PASS였지만 서버 종료Signal11/139가 다시 발생했다. 이는 이 보고서의80회 정량 분석과 구분하는 후속 기록이며 원본 분석manifest/판정/수치를 변경하지 않았다. 원고 검토와HWP편집은 사용자가Windows에서 진행한다.

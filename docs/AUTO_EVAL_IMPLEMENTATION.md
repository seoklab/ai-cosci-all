# AI-CoSci 코드 구조 및 자동 평가 구현 요약

## 전체 코드 구조

### 1. **핵심 Agent 코드** (`src/agent/`)

#### `agent.py` - 기본 Agent 클래스
- `BioinformaticsAgent`: 생물정보학 질문에 답하는 기본 에이전트
  - `run()`: 단일 질문에 대한 답변 생성 (도구 사용, 반복 추론)
  - `run_with_critic()`: Critic 피드백 루프 포함한 답변 생성
  - 최대 30회 반복 (도구 호출, LLM 추론)
  
- `ScientificAgent`: Virtual Lab용 페르소나 기반 에이전트
  - `BioinformaticsAgent`를 상속
  - 특정 역할(PI, Immunologist, Computational Biologist 등) 수행

#### `meeting.py` - Virtual Lab (병렬 방식)
- `VirtualLabMeeting`: 다중 에이전트 협업 시스템
  - **Phase 1**: PI가 팀 구성 및 안건 설정
  - **Phase 2**: 전문가들이 **병렬로** 분석 수행 (`_run_specialists_parallel()`)
  - **Phase 3**: Critic이 각 라운드 검토
  - **Phase 4**: PI가 최종 종합
  
- `run_virtual_lab()`: 편의 함수

#### `meeting_refactored.py` - Subtask-Centric Virtual Lab (순차 방식)
- 연구 계획 기반 순차적 협업
- PI가 subtask 계획 → 전문가들이 **순차적으로** 해결
- Red Flag 시스템으로 품질 관리

### 2. **CLI 인터페이스** (`src/cli.py`)

#### 지원하는 모드:
1. **Single Agent**: 단일 에이전트가 답변 생성
2. **With Critic**: Single Agent + Critic 피드백 루프
3. **Virtual Lab**: 병렬 다중 에이전트 협업
4. **Subtask-Centric**: 순차적 연구 계획 기반 협업
5. **LangGraph**: LangGraph 워크플로우
6. **Combined**: LangGraph + Consensus

#### 주요 함수:
- `save_answer_to_file()`: 최종 답변을 마크다운 파일로 저장
- `auto_evaluate_and_save()`: FastChat 방식 자동 평가 수행

### 3. **평가 시스템** (`src/evaluation/`)

#### `pairwise_evaluator.py` - 두 답변 비교 평가
- `OpenRouterJudge`: 두 답변을 비교하는 Judge
- `evaluate_pairwise()`: A vs B 비교 후 승자 결정
- 독립 실행 가능 (CLI 도구)

#### `single_evaluator.py` - 단일 답변 평가 (새로 구현)
- `SingleAnswerJudge`: FastChat의 single-v1 방식 구현
- `evaluate()`: 1-10점 스케일로 답변 품질 평가
- 평가 기준:
  - Scientific Accuracy (30%)
  - Evidence Quality (20%)
  - Methodological Rigor (15%)
  - Completeness (15%)
  - Clarity (10%)
  - Critical Thinking (10%)

### 4. **도구 (Tools)** (`src/tools/`)

- `execute_python`: Python 코드 실행 (데이터 분석)
- `search_pubmed`: PubMed 초록 검색
- `search_literature`: PaperQA 기반 전문 문헌 검색
- `query_database`: 생물정보학 데이터베이스 쿼리
- `read_file`: 파일 읽기
- `find_files`: 파일 검색

---

## 자동 평가 구현 상세

### 1. **구현된 기능**

#### A. Pairwise 평가 (이미 구현됨)
```bash
python src/evaluation/pairwise_evaluator.py \
  -q "연구 질문" \
  -a answer_a.md \
  -b answer_b.md \
  --verbose
```

#### B. Single Answer 자동 평가 (새로 구현)
```bash
# CLI에서 자동 평가 활성화
python -m src.cli \
  --question "연구 질문" \
  --auto-eval \
  --verbose
```

### 2. **FastChat 적용 방식**

#### FastChat의 LLM-as-a-Judge 접근법:
1. **Single Answer Grading**: GPT-4가 답변을 1-10점으로 평가
2. **Pairwise Comparison**: 두 답변을 직접 비교하여 승자 결정

#### AI-CoSci 구현:
```python
# single_evaluator.py
class SingleAnswerJudge:
    def evaluate(self, question, answer):
        # FastChat의 single-v1 프롬프트를 biomedical 특화로 수정
        prompt = self.create_biomedical_evaluation_prompt(question, answer)
        
        # OpenRouter API로 Judge 모델 호출
        response = self.call_judge_model(prompt)
        
        # [[8]] 형태의 점수 추출
        score = self._extract_score(response)
        
        return SingleEvaluationResult(score, explanation)
```

### 3. **통합 플로우**

```
사용자 질문 입력
    ↓
Agent/Virtual Lab이 답변 생성
    ↓
답변을 파일로 저장
    ↓
[--auto-eval 플래그가 있으면]
    ↓
auto_evaluate_and_save() 호출
    ↓
SingleAnswerJudge가 평가 수행
    ↓
tests/evaluation/auto_eval_{timestamp}.md에 결과 저장
    ↓
터미널에 점수 표시 (예: 📊 FINAL SCORE: 8.2/10.0)
```

### 4. **사용 예시**

#### 예시 1: Single Agent + 자동 평가
```bash
python -m src.cli \
  --question "What are the molecular mechanisms of CRISPR-Cas9?" \
  --auto-eval \
  --verbose
```

#### 예시 2: Virtual Lab + 자동 평가
```bash
python -m src.cli \
  --question "Identify drug targets for Alzheimer's disease" \
  --virtual-lab \
  --rounds 2 \
  --team-size 3 \
  --auto-eval \
  --eval-model "anthropic/claude-3.5-sonnet"
```

#### 예시 3: 커스텀 Judge 모델 사용
```bash
python -m src.cli \
  -q "Gene therapy approaches" \
  --auto-eval \
  --eval-model "openai/gpt-4" \
  -v
```

---

## 현재 구현 상태

### ✅ 완료된 기능

1. **Pairwise 평가 시스템**
   - FastChat 방식 적용
   - OpenRouter API 사용
   - Markdown 결과 파일 생성
   - `tests/evaluation/` 폴더에 저장

2. **Single Answer 자동 평가**
   - FastChat single-v1 방식 구현
   - Biomedical 특화 평가 기준
   - 1-10점 스케일 스코어링
   - CLI 통합 (`--auto-eval` 플래그)

3. **모든 모드 지원**
   - Single Agent
   - With Critic
   - Virtual Lab (병렬)
   - Subtask-Centric (순차)
   - LangGraph
   - Combined

### 📋 주요 파일 위치

```
src/
├── agent/
│   ├── agent.py              # BioinformaticsAgent, ScientificAgent
│   ├── meeting.py            # Virtual Lab (병렬 방식)
│   └── meeting_refactored.py # Subtask-Centric (순차 방식)
├── cli.py                    # CLI 인터페이스 + 자동 평가 통합
├── evaluation/
│   ├── pairwise_evaluator.py # 두 답변 비교 평가
│   ├── single_evaluator.py   # 단일 답변 자동 평가
│   └── README.md             # 평가 시스템 가이드
└── tools/
    └── implementations.py    # 도구 함수들

tests/
└── evaluation/               # 평가 결과 저장 위치
    ├── pairwise_result_*.md
    └── auto_eval_*.md
```

---

## Agent 대화 및 협업 흐름

### Virtual Lab (병렬 방식) - `meeting.py`

```python
# Phase 1: PI Opening
pi.run("Open meeting and set agenda")

# Phase 2: Specialists (병렬 실행)
for round in range(num_rounds):
    # 모든 전문가가 동시에 분석
    specialist_responses = _run_specialists_parallel()
    # asyncio.gather()로 병렬 실행
    
    # Critic 검토
    critic.run("Review the round")
    
    # PI 중간 정리
    pi.run("Synthesize the round")

# Phase 3: Final Synthesis
final_answer = pi.run("Synthesize all findings")
```

### Subtask-Centric (순차 방식) - `meeting_refactored.py`

```python
# Step 1: Research Plan
research_plan = pi.create_research_plan()

# Step 2: Sequential Execution
for subtask in research_plan:
    # 적합한 전문가 선택
    specialist = select_specialist(subtask)
    
    # 전문가가 subtask 수행
    result = specialist.run(subtask)
    
    # Red Flag 검사
    red_flags = check_red_flags(result)
    
    # 필요시 재수행
    if red_flags:
        result = specialist.run(subtask_with_feedback)

# Step 3: Final Synthesis
final_answer = pi.synthesize_all_results()
```

---

## 확인 가능한 코드 위치

1. **Agent 대화 로직**: `src/agent/meeting.py:316-380` (`run_meeting()` 메서드)
2. **병렬 실행**: `src/agent/meeting.py:281-314` (`_run_specialists_parallel()`)
3. **도구 호출**: `src/agent/agent.py:129-157` (`call_tool()` 메서드)
4. **Critic 피드백**: `src/agent/agent.py:423-541` (`run_with_critic()`)
5. **자동 평가 통합**: `src/cli.py:82-158` (`auto_evaluate_and_save()`)
6. **평가 프롬프트**: `src/evaluation/single_evaluator.py:38-75`

---

## 실행 예시

```bash
# 1. 기본 실행 (자동 평가 포함)
python -m src.cli \
  --question "What are the key challenges in mRNA vaccine development?" \
  --auto-eval

# 2. Virtual Lab + 자동 평가
python -m src.cli \
  --question "Identify drug targets for Parkinson's disease" \
  --virtual-lab \
  --rounds 3 \
  --team-size 4 \
  --auto-eval \
  --verbose

# 3. 두 답변 비교 평가 (독립 실행)
python src/evaluation/pairwise_evaluator.py \
  -q "Cancer immunotherapy mechanisms" \
  -a tests/answer_a.md \
  -b tests/answer_b.md \
  -v
```

---

**마지막 업데이트:** 2025-12-19

# AI 모델 비교 (PR-0301/0302/0303)

데이터팀 요청으로, 상품 AI 한줄요약(PR-0301)/감미료 설명(PR-0302)/사용자 맞춤 설명(PR-0303)
기능에 어떤 모델을 쓸지 정하기 전에 여러 프로바이더의 모델을 같은 입력으로 돌려서
비교하는 용도의 일회성 도구입니다. **실제 서비스 코드(product-service)는 전혀
건드리지 않고, 프롬프트만 그대로 복사해와서 씁니다.**

챗봇(MN-011x)/Vision(RC-0103)은 이 비교 범위에 없습니다.

## 준비

```
cd tools/model-eval
pip install -r requirements.txt
cp .env.example .env
```

`.env`에 채울 값:
- `POSTGRES_*`: product-service `.env`에 있는 값 그대로 복사 (읽기 전용 조회만 함)
- `ANTHROPIC_API_KEY`: product-service와 동일한 값 재사용 가능
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION`: Bedrock 호출용. `AWS_PROFILE` 환경변수로 대체 가능(그 경우 access key 줄은 비워두면 boto3가 알아서 profile을 씀)
- `OPENAI_API_KEY`, `GEMINI_API_KEY`: 각 프로바이더 키

## 비교 대상 모델 조정

`config.py`의 `CANDIDATES` 리스트를 직접 수정하세요. **Bedrock/OpenAI/Gemini 쪽 model_id는
예시값**이라 실행 전에 반드시 실제 계정에서 사용 가능한 모델 id로 확인·교체해야 합니다.

- Bedrock: `aws bedrock list-foundation-models --region $AWS_REGION` 또는 콘솔에서 확인
- OpenAI/Gemini: 각 대시보드에서 계정이 접근 가능한 모델명 확인

## 실행

```
python run_eval.py
```

`EVAL_SAMPLE_SIZE`(기본 5)개 실제 상품에 대해, 후보 모델 전체 x 기능(PR-0301/0302/0303,
PR-0303은 샘플 유저 프로필 2종) 조합을 전부 호출합니다. 상품 수 x 모델 수만큼 호출이
나가므로 API 비용이 발생합니다 — 처음엔 `EVAL_SAMPLE_SIZE=1~2`, `CANDIDATES`도 일부만
남겨서 한 바퀴 돌려보고 늘리는 걸 권장합니다.

## 결과

`results/eval_{시각}.md` (모델별 응답 전체를 표로 정리, 사람이 읽고 비교하는 용도)와
`results/eval_{시각}.csv` (응답시간/토큰/에러 포함, 스프레드시트로 정렬·집계하는 용도)
두 개가 생성됩니다. 둘 다 `.gitignore`돼 있어서 커밋되지 않습니다 — 결과 공유는
파일을 직접 전달하거나 팀 채널에 업로드하세요.

## 알아두면 좋은 것

- PR-0302(감미료 설명)는 감미료 태그가 없는 상품이면 실제 서비스처럼 건너뜁니다 —
  `db.py`가 감미료 태그가 있는 상품을 우선으로 뽑아오긴 하지만, `EVAL_SAMPLE_SIZE`가
  작으면 전부 감미료 없는 상품일 수도 있습니다.
- PR-0303(사용자 맞춤 설명)은 실제 유저 건강정보 대신 `config.py`의
  `SAMPLE_USER_PROFILES` 고정값 2개를 씁니다 — 실제 서비스는 로그인한 사용자마다
  다른 값을 쓰지만, 모델 비교가 목적이라 입력을 고정해야 결과가 비교 가능합니다.
- 에러(키 누락, 모델 id 오류, rate limit 등)는 죽지 않고 표에 "에러" 셀로 기록되고
  나머지 모델/상품은 계속 진행됩니다.

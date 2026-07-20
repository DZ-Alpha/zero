# RAG 적재·검색 수동 검증 절차

로컬에 pgvector가 없으므로 서버 pgvector(10.10.20.10)에 SSH 터널로 연결해 수동 검증한다.
**원격 DB에 스키마 생성·데이터 적재 전 반드시 사용자 승인을 받는다.**

## 1. SSH 터널
```
ssh -L 15432:10.10.20.10:5432 zero@192.168.0.54
```
로컬 .env: `POSTGRES_HOST=localhost`, `POSTGRES_PORT=15432`, `EMBED_REGION=ap-northeast-2`, `RAG_ENABLED=true`.

## 2. 스키마 생성 (최초 1회, 승인 후)
```
psql "host=localhost port=15432 dbname=test_db user=..." -f app/rag/ingest/schema.sql
```

## 3. 지식문서 3종 적재
```
cd ai-service
python -m app.rag.ingest.load_rag_docs app/rag/knowledge/sugar_labeling_kfda.md "식약처 표시기준 고시"
python -m app.rag.ingest.load_rag_docs app/rag/knowledge/who_sugar_guideline.md "WHO 유리당 권고"
python -m app.rag.ingest.load_rag_docs app/rag/knowledge/kdris_sugar_energy.md "KDRIs 당류·에너지"
```
각 실행이 "N개 청크 적재 완료"를 출력해야 한다.

## 4. 검색 검증
대표 질문으로 top-k에 기대 문서가 오는지 확인(파이썬 REPL 또는 임시 스크립트):
- "무설탕이면 열량도 0이야?" → 식약처 무당류/무열량 정의 청크가 상위
- "하루에 당 얼마까지 괜찮아?" → WHO 10% + KDRIs 당류 기준 청크가 상위

검증 결과(어떤 청크가 상위에 왔는지)를 이 문서 하단에 기록한다.

## 5. 검증 결과 (2026-07-20 실행 완료)

DB `zero` @ 10.10.20.10:5432 (터널 localhost:15432), pgvector 확장 확인됨.
상품벡터는 `service.product_embeddings`에 존재(설계 가정과 일치).

적재: `ai_rag.rag_documents`에 총 18청크
- sugar_labeling_kfda.md: 7청크
- who_sugar_guideline.md: 6청크
- kdris_sugar_energy.md: 5청크

검색 검증 (Cohere Embed v4 search_query → 코사인 top-3):

Q: "무설탕이면 열량도 0이야?"
- [0.679] (식약처) 무열량 정의 — "무당류/무설탕이라도 열량이 0이 아닐 수…"  ← 정확
- [0.555] (식약처) 무당류 정의
- [0.474] (식약처) 저열량 정의

Q: "하루에 당 얼마까지 괜찮아?"
- [0.574] (WHO) 유리당 10% 미만 권고  ← 정확
- [0.570] (WHO) 계산 예시(2000kcal→당 50g)
- [0.566] (KDRIs) 총당류 10~20% 기준

→ 두 질문 모두 의미적으로 정확한 근거 청크가 top-3에 검색됨. RAG 파이프라인 실동작 확인.

주의(이월): 지식문서 수치는 대표값이므로 실제 최신 식약처 고시번호·KDRIs 판 연도로 대조 검증 필요.
로컬 검증은 psycopg 동기 쿼리로 수행(asyncpg 미설치). 서비스 런타임은 asyncpg 사용(requirements에 포함).

-- kafka/migrations/009_content_schema.sql
-- 읽을거리·큐레이션 컬렉션을 DB 로 내린다.
--
-- 지금은 프론트에 하드코딩돼 있다:
--   - components/HomeDashboard.tsx 의 readingList 4건(제목만, 본문 없음)
--   - components/HomeAdBanner.tsx 의 광고 슬라이드 3건
-- 콘텐츠를 하나 늘릴 때마다 프론트 배포가 필요한 구조라, 운영·마케팅이 손을 못 댄다.
-- 테이블로 내리면 배포 없이 콘텐츠를 추가할 수 있다.
--
-- collections 는 두 방식을 모두 지원한다:
--   - rule_json 이 있으면 규칙 기반(동적) — 상품이 늘면 컬렉션도 자동으로 커진다
--   - collection_products 에 직접 넣으면 수동 큐레이션
-- 규칙 해석은 백엔드가 하고, 이 마이그레이션은 스키마와 시드만 만든다.

CREATE SCHEMA IF NOT EXISTS content;

CREATE TABLE IF NOT EXISTS content.articles (
    slug          TEXT        PRIMARY KEY,
    category      TEXT        NOT NULL,
    title         TEXT        NOT NULL,
    summary       TEXT,
    body_md       TEXT,
    read_minutes  SMALLINT,
    source_note   TEXT,
    sort_order    SMALLINT    NOT NULL DEFAULT 100,
    is_published  BOOLEAN     NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN content.articles.body_md IS
    '본문(마크다운). 시드 시점에는 비어 있을 수 있다 — is_published=false 로 두고 본문이 채워지면 공개한다.';
COMMENT ON COLUMN content.articles.source_note IS
    '근거 출처 표기. 식약처/WHO/KDRIs 등. 고시 번호는 검증 후 기입한다.';

CREATE TABLE IF NOT EXISTS content.collections (
    slug         TEXT        PRIMARY KEY,
    title        TEXT        NOT NULL,
    subtitle     TEXT,
    rule_json    JSONB,
    sort_order   SMALLINT    NOT NULL DEFAULT 100,
    is_published BOOLEAN     NOT NULL DEFAULT false,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN content.collections.rule_json IS
    '규칙 기반 컬렉션 정의. 예: {"category":"BEVERAGE","max_sugar":0}. NULL 이면 collection_products 수동 큐레이션.';

CREATE TABLE IF NOT EXISTS content.collection_products (
    slug       TEXT     NOT NULL REFERENCES content.collections(slug) ON DELETE CASCADE,
    product_id UUID     NOT NULL,
    position   SMALLINT NOT NULL DEFAULT 0,
    PRIMARY KEY (slug, product_id)
);

-- ── 시드: 컬렉션 ────────────────────────────────────────────────────────────
-- 전부 실제 데이터 분포(service.mv_category_sugar_stats, 2026-08-09)에 근거한다.
-- 숫자를 지어내지 않았다. 규칙 기반이므로 상품이 늘면 컬렉션도 같이 커진다.
INSERT INTO content.collections (slug, title, subtitle, rule_json, sort_order, is_published) VALUES
 ('zero-drinks',      '당류 0g 음료 전부',        '음료 994종 중 569종이 당류 0g입니다',
    '{"category":"BEVERAGE","max_sugar":0}'::jsonb, 10, true),
 ('hard-mode-jam',    '잼에서 그나마 나은 선택',  '잼·스프레드는 평균 4.9g으로 당류 0g 제품이 아직 없는 분야입니다',
    '{"category":"JAM_SPREAD","sort":"sugar_asc","limit":10}'::jsonb, 20, true),
 ('zero-snack',       '당류 0g 간식',             '베이커리·간식 432종 중 128종',
    '{"category":"BAKERY_SNACK","max_sugar":0}'::jsonb, 30, true),
 ('low-sugar-sauce',  '소스는 당류가 숨어 있어요','소스·조미 평균 3.5g, 중앙값 2.0g',
    '{"category":"SAUCE_SEASONING","sort":"sugar_asc","limit":12}'::jsonb, 40, true),
 ('dairy-low-sugar',  '당류 낮은 유제품',         '유제품 평균 1.2g으로 카테고리 중 가장 낮습니다',
    '{"category":"DAIRY","sort":"sugar_asc","limit":12}'::jsonb, 50, true),
 ('watch-out-special','특수영양식은 확인이 필요해요','평균 6.3g으로 카테고리 중 당류가 가장 높습니다',
    '{"category":"SPECIAL_NUTRITION","sort":"sugar_desc","limit":10}'::jsonb, 60, true)
ON CONFLICT (slug) DO NOTHING;

-- ── 시드: 읽을거리 ──────────────────────────────────────────────────────────
-- 제목·요약은 프론트 하드코딩(readingList)에 있던 것을 옮기고, 근거가 실제로
-- 있는 주제를 추가했다. 본문(body_md)은 비워 두고 is_published=false 로 둔다 —
-- 본문 없는 글을 공개 상태로 만들지 않는다.
INSERT INTO content.articles (slug, category, title, summary, read_minutes, source_note, sort_order, is_published) VALUES
 ('zero-sugar-not-zero-calorie','성분 읽기','제로슈거인데 당류가 0g이 아닐 수 있나요?',
  '무당류와 무열량은 별개 기준입니다. 표시 문구와 영양성분표를 함께 봐야 하는 이유를 정리했어요.',
  3,'식약처 「식품등의 표시기준」(고시 번호 확인 필요)',10,false),
 ('allulose-vs-erythritol','감미료','알룰로스와 에리스리톨은 무엇이 다를까요?',
  '자주 쓰이는 대체 감미료 두 가지의 열량과 특징을 쉬운 말로 비교했어요.',
  4,'감미료 일반 특성',20,false),
 ('reduce-sugar-habit','식단 기록','간식을 끊지 않고 당류를 줄이는 방법',
  '먹는 시간을 바꾸고 양을 기록하는 작은 습관부터 시작해요.',
  3,NULL,30,false),
 ('read-nutrition-label','처음 읽기','영양성분표는 이 세 줄부터 보면 쉬워요',
  '열량, 당류, 1회 제공량을 순서대로 확인해보세요.',
  2,'식약처 「식품등의 표시기준」(고시 번호 확인 필요)',40,false),
 ('who-daily-sugar','기준','하루 당류 몇 g까지 괜찮을까요?',
  'WHO는 유리당을 총열량의 10% 미만으로 권고합니다. 2000kcal 기준 약 50g, 5% 기준은 약 25g이에요.',
  3,'WHO 유리당 섭취 가이드라인 / 한국인 영양소 섭취기준(KDRIs)',50,false),
 ('sugar-alcohol-belly','감미료','당알코올을 먹으면 왜 배가 불편할까요?',
  '말티톨·소비톨·자일리톨 같은 당알코올의 공통 특징과, 에리스리톨이 상대적으로 편한 이유를 설명해요.',
  4,'감미료 일반 특성',60,false),
 ('sweetener-ranking','감미료','제로 제품에 가장 많이 쓰이는 감미료는?',
  '우리 DB의 상품 2,427종을 세어보니 수크랄로스가 가장 많았어요. 이름은 유명한데 실제로는 거의 안 쓰이는 감미료도 있습니다.',
  4,'자사 상품 데이터 집계(service.mv_sweetener_catalog)',70,false),
 ('no-added-sugar-trap','성분 읽기','"무가당"은 당류 0g이라는 뜻이 아니에요',
  '당을 넣지 않았을 뿐 원재료에 원래 있던 당은 그대로입니다. 과일주스가 대표적인 예예요.',
  3,'식약처 「식품등의 표시기준」(고시 번호 확인 필요)',80,false)
ON CONFLICT (slug) DO NOTHING;

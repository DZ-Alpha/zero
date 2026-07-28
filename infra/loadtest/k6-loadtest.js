// k6 부하테스트 v2 — Docker 단계 production 실측 (K8s 시방서 requests/limits/replicas 근거)
// 실행 순서·명령·관측 쿼리: docs/부하테스트_창1_런북_20260727.md
//
// 사용법(k6 -e 플래그):
//   MODE=smoke|ramp|steady|spike|soak
//   SERVICE=product|recipe|ingredients|main|community|diet|login|ai|all|upload
//     ⚠️ all = 읽기 전용 8종. upload(쓰기)는 명시해야만 실행된다.
//   JWT_SECRET=<HS256 공유 시크릿>  ← 인증 엔드포인트용. env로만 주입, 파일/히스토리 금지
//   TEST_USER_ID=<실존 user_id>     ← mypage만 실존 필요(404 방지). diet는 아무 값도 동작
//   DURATION=<soak 지속시간>        ← soak 전용, 기본 2h (야간 권장)
//   SLO_MS=<임계 ms>                ← 기본 500. 업로드는 전송시간 포함이라 1500~3000 권장
//   PHOTO_KB / PRE_VUS / MAX_VUS    ← 업로드 전용. 예: -e PHOTO_KB=2048 -e PRE_VUS=20 -e MAX_VUS=60
//
// 실무 요소 (k6 공식 문서 근거):
//   - open model 램핑: grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/
//   - 파라미터 랜덤화: grafana.com/docs/k6/latest/examples/data-parameterization/
//     (고정 파라미터는 DB 캐시가 항상 워밍된 최상 조건만 재서 자원을 과소 측정)
//   - setup()에서 실데이터 ID 수집: grafana.com/docs/k6/latest/using-k6/test-lifecycle/
//     (가짜 ID로 상세 조회하면 404만 재게 됨)
//   - JWT 직접 서명(HS256): 백엔드 인증이 "서명 검증만"이라(diet-service/app/core/auth.py)
//     로그인 플로우(소셜 OAuth = 외부 종속) 없이 유효 토큰 생성 가능.
//     클레임 구조는 login-service/app/services/jwt_service.py 그대로 복제.
//
// 버전 고정: grafana/k6:1.3.0 (R7 — 회차 간 비교를 위해)
import http from 'k6/http';
import { check, sleep } from 'k6';
import exec from 'k6/execution';
import crypto from 'k6/crypto';
import { b64encode } from 'k6/encoding';

const BASE = __ENV.BASE_URL || 'http://10.10.10.30:8080';
const MODE = __ENV.MODE || 'smoke';
const SERVICE = __ENV.SERVICE || 'all';
const MAX = Number(__ENV.MAX || 200); // ramp 최고 RPS
const RATE = Number(__ENV.RATE || 50); // steady 고정 RPS
const JWT_SECRET = __ENV.JWT_SECRET || '';
const TEST_USER_ID = Number(__ENV.TEST_USER_ID || 1);
const SLO_MS = Number(__ENV.SLO_MS || 500); // 업로드는 전송시간 때문에 별도 SLO 필요
const PRE_VUS = Number(__ENV.PRE_VUS || 100);
const MAX_VUS = Number(__ENV.MAX_VUS || 500);
const PHOTO_KB = Number(__ENV.PHOTO_KB || 2048); // 폰 사진 압축 후 통상 크기

const rnd = (n) => Math.floor(Math.random() * n);
const pick = (arr) => arr[rnd(arr.length)];
const KEYWORDS = ['제로', '콜라', '사이다', '과자', '아이스크림', '초코', '젤리', '음료'];
const INITIALS = ['제', '콜', '사', '과', '초', '젤'];

// jwt_service.create_access_token과 동일한 클레임 — sub(str) + user_id(int) 병행,
// product/ingredients/diet가 payload["user_id"]를 읽는 컨벤션이라 둘 다 필수.
function mintJwt(userId) {
  const now = Math.floor(Date.now() / 1000);
  const enc = (o) => b64encode(JSON.stringify(o), 'rawurl');
  const head = enc({ alg: 'HS256', typ: 'JWT' });
  const body = enc({
    sub: String(userId), user_id: userId, provider: 'loadtest',
    nickname: 'loadtest', role: 'user', iat: now, exp: now + 3 * 3600, // 3h 후 자동 무효
  });
  const sig = crypto.hmac('sha256', JWT_SECRET, `${head}.${body}`, 'base64rawurl');
  return `${head}.${body}.${sig}`;
}

// 최근 3개월(calender), 최근 30일(records) — 실사용 패턴 근사
const _now = new Date();
const CAL_MONTHS = [0, 1, 2].map((k) => {
  const d = new Date(_now.getFullYear(), _now.getMonth() - k, 1);
  return { y: d.getFullYear(), m: d.getMonth() + 1 };
});
const recentDate = () => new Date(Date.now() - rnd(30) * 86400000).toISOString().slice(0, 10);

// 라우팅은 infra/b-gateway/nginx.conf 실측 기준.
// 주의: /b/search → product-service (main 아님). main은 /b/home/*.
const SERVICES = {
  product: [
    {
      name: 'search',
      build: () => {
        const q = Math.random() < 0.6 ? `&query=${encodeURIComponent(pick(KEYWORDS))}` : '';
        const s = Math.random() < 0.3 ? '&sort=abc' : '';
        return `/b/search?page=${1 + rnd(5)}${q}${s}`;
      },
    },
    { name: 'search-recommend', build: () => `/b/search/recommend?query=${encodeURIComponent(pick(INITIALS))}` },
  ],
  recipe: [
    {
      name: 'recipes-list',
      build: () => {
        const s = Math.random() < 0.4 ? '&sort=sugarReduction' : '';
        const src = Math.random() < 0.3 ? '&source=youtube' : '';
        return `/b/recipes?page=${1 + rnd(5)}${s}${src}`;
      },
    },
    { name: 'recipes-detail', needsIds: 'recipeIds', build: (d) => `/b/recipes/${pick(d.recipeIds)}` },
  ],
  ingredients: [
    { name: 'tags-allergen', build: () => '/b/tags/allergen' },
    { name: 'tags-category', build: () => '/b/tags/category' },
  ],
  main: [
    // rank/item은 DB를 안 타는 스텁 — 프레임워크 상한. home/me는 토큰 디코드만(DB 없음).
    // 즉 main의 R은 여전히 "상한값"으로 해석할 것 (실질 DB 워크로드 GET가 없음).
    { name: 'home-rank-item', build: () => '/b/home/rank/item' },
    { name: 'home-me', auth: true, build: () => '/b/home/me' },
  ],
  community: [
    { name: 'gam-list', build: () => '/b/community/gam-list' },
    { name: 'gam-detail', needsIds: 'gamIds', build: (d) => `/b/community/gam-list/${pick(d.gamIds)}` },
    { name: 'notice-list', build: () => '/b/community/notice' },
  ],
  diet: [
    {
      name: 'diet-calender',
      auth: true,
      build: () => {
        const c = pick(CAL_MONTHS);
        return `/b/diet/calender?year=${c.y}&month=${c.m}`;
      },
    },
    { name: 'diet-records', auth: true, build: () => `/b/diet/records?date=${recentDate()}` },
  ],
  login: [
    // 소셜 OAuth 플로우는 외부(구글/카카오) 종속이라 부하 대상이 아님 —
    // login-service의 자체 워크로드(DB 조회)는 mypage GET가 대표.
    { name: 'user-mypage', auth: true, build: () => '/b/user/mypage' },
  ],
  ai: [
    // Bedrock을 안 타는 유일한 GET(비인증 게스트 허용) — ai 컨테이너의 웹/스토리지
    // 경로만 측정. 챗봇 본경로(POST)는 외부 LLM 과금·쿼터 종속이라 부하 금지(창2 관찰만).
    { name: 'ai-history', build: () => `/b/ai/chatbot/history?session_id=loadtest-${1 + rnd(20)}` },
  ],

  // ⚠️ 쓰기 경로 — SERVICE=upload로 명시할 때만 실행된다(all에 포함 안 됨).
  // 이 서비스의 대표 워크로드이자 유일한 대용량 요청 경로라 K8s limits 산정에 가장 중요하다:
  //  - diet-service가 `data = await file.read()`로 파일 전체를 메모리에 올린다
  //    (uploads.py:24) → 동시 업로드 N개 × 사진 크기가 그대로 메모리 피크
  //  - b-gateway는 큰 본문을 /tmp에 버퍼링하는데 그 /tmp가 tmpfs(=RAM)라
  //    게이트웨이 256m 한도에도 같이 얹힌다 → 게이트웨이가 먼저 죽을 수 있음
  //  - MinIO(DB VM)에 실제 객체가 쌓인다 → 사후 정리 필요(성애님 협의)
  // Bedrock은 안 탄다: POST /diet/upload(meal_log 생성 + Kafka 이벤트)를 호출하지
  // 않는 한 AI 분석이 트리거되지 않는다. 여기서는 저장 경로만 잰다.
  upload: [
    { name: 'diet-photo-upload', auth: true, upload: true, build: () => '/b/uploads/diet-photo' },
  ],
};
const READONLY = ['product', 'recipe', 'ingredients', 'main', 'community', 'diet', 'login', 'ai'];
if (SERVICE !== 'all' && !SERVICES[SERVICE]) throw new Error(`unknown SERVICE: ${SERVICE}`);

// 업로드용 더미 이미지 — storage.py는 content_type만 검사하고 디코딩은 하지 않으므로
// (_ALLOWED_CONTENT_TYPES) 합성 바이트로 충분하다. JPEG 매직만 앞에 둔다.
// 주의: VU마다 사본이 생긴다 → VU 수 × PHOTO_KB 만큼 생성기 메모리를 쓴다.
// 업로드 run은 -e PRE_VUS=20 -e MAX_VUS=60 처럼 낮춰서 돌릴 것.
const PHOTO = SERVICE === 'upload' ? (() => {
  const b = new Uint8Array(PHOTO_KB * 1024);
  b[0] = 0xff; b[1] = 0xd8; b[2] = 0xff; b[3] = 0xe0; // SOI + APP0
  for (let i = 4; i < b.length; i += 997) b[i] = i & 0xff; // 전부 0이면 비현실적이라 성기게 채움
  return b.buffer;
})() : null;

const SCENARIOS = {
  smoke: { smoke: { executor: 'constant-vus', vus: 1, duration: '1m' } },
  ramp: {
    ramp: {
      executor: 'ramping-arrival-rate', // open model — 서버가 느려져도 부하 유지
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: PRE_VUS,
      maxVUs: MAX_VUS,
      stages: [{ target: MAX, duration: '6m' }],
    },
  },
  steady: {
    steady: {
      executor: 'constant-arrival-rate',
      rate: RATE,
      timeUnit: '1s',
      duration: '3m',
      preAllocatedVUs: PRE_VUS,
      maxVUs: MAX_VUS,
    },
  },
  // 창2+ 전용 — k6 공식 test types의 spike/soak 패턴
  // (grafana.com/docs/k6/latest/testing-guides/test-types/)
  spike: {
    // 시연 오픈 순간 시뮬레이션: 10초 만에 MAX RPS 급등 → 1분 유지 → 급락 → 회복 관찰.
    // 판정: 급등 구간 에러율과, 급락 후 p95가 평상시로 돌아오는 데 걸리는 시간.
    spike: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 200,
      maxVUs: 500,
      stages: [
        { target: MAX, duration: '10s' },
        { target: MAX, duration: '1m' },
        { target: 5, duration: '10s' },
        { target: 5, duration: '2m' },
      ],
    },
  },
  soak: {
    // 누수 판정: knee의 50~80% RPS로 장시간 유지하며 메모리 우상향 여부 관찰.
    // login이 무트래픽에도 256Mi의 97.6%까지 기어오른 누수 의심 검증용 — 야간 실행.
    soak: {
      executor: 'constant-arrival-rate',
      rate: RATE,
      timeUnit: '1s',
      duration: __ENV.DURATION || '2h',
      preAllocatedVUs: 100,
      maxVUs: 300,
    },
  },
};
if (!SCENARIOS[MODE]) throw new Error(`unknown MODE: ${MODE}`);

export const options = {
  scenarios: SCENARIOS[MODE],
  thresholds: {
    http_req_duration: [`p(95)<${SLO_MS}`], // SLO — 이 선을 넘는 순간이 knee
    http_req_failed: ['rate<0.01'],
  },
  discardResponseBodies: true, // 생성기(harbor) 자원 절약 — R4 (setup은 개별 override)
};

// 1회 실행: 토큰 발급 + 상세조회용 실데이터 ID 수집 (regex — 응답 스키마에 비종속)
export function setup() {
  if (!JWT_SECRET) {
    console.warn('JWT_SECRET 미지정 — 인증 엔드포인트(home-me/diet/mypage) 건너뜀');
  }
  const token = JWT_SECRET ? mintJwt(TEST_USER_ID) : '';
  const text = { responseType: 'text' };
  const extract = (re, body) => {
    const out = [];
    let m;
    while ((m = re.exec(body)) !== null && out.length < 50) out.push(m[1]);
    return out;
  };
  let recipeIds = [];
  let gamIds = [];
  const r = http.get(`${BASE}/b/recipes?page=1`, text);
  if (r.status === 200 && r.body) recipeIds = extract(/"id"\s*:\s*(\d+)/g, r.body);
  const g = http.get(`${BASE}/b/community/gam-list`, text);
  if (g.status === 200 && g.body) {
    gamIds = extract(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/g, g.body);
  }
  console.log(`setup: token=${token ? 'yes' : 'no'} recipeIds=${recipeIds.length} gamIds=${gamIds.length}`);
  return { token, recipeIds, gamIds };
}

function activeTargets(data) {
  // 'all'은 읽기 전용만 — 쓰기(upload)는 SERVICE=upload로 명시해야 실행된다
  const base = SERVICE === 'all' ? READONLY.flatMap((k) => SERVICES[k]) : SERVICES[SERVICE];
  return base.filter((t) => (!t.auth || data.token) && (!t.needsIds || (data[t.needsIds] || []).length > 0));
}

function hit(t, data) {
  const params = { tags: { name: t.name } }; // name 태그 — 카디널리티 통제 (R3)
  if (t.auth) params.headers = { Authorization: `Bearer ${data.token}` };
  const url = `${BASE}${t.build(data)}`;
  const res = t.upload
    ? http.post(url, { file: http.file(PHOTO, 'meal.jpg', 'image/jpeg') }, params)
    : http.get(url, params);
  check(res, { [`${t.name} 200`]: (r) => r.status === 200 });
}

export default function (data) {
  const targets = activeTargets(data);
  if (MODE === 'smoke') {
    // 전 엔드포인트 순회 — 경로·라우팅·인증 검증
    for (const t of targets) {
      hit(t, data);
      sleep(1);
    }
  } else {
    // 요청 1개/iteration — arrival rate가 곧 RPS (R 환산의 전제)
    hit(targets[exec.scenario.iterationInTest % targets.length], data);
  }
}

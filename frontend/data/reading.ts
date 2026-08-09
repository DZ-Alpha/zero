export type ReadingSection = {
  heading: string;
  paragraphs: string[];
  bullets?: string[];
};

export type ReadingSource = {
  label: string;
  href?: string;
};

export type ReadingArticle = {
  slug: string;
  category: string;
  title: string;
  summary: string;
  readMinutes: number;
  cover: string;
  coverCaption: string;
  takeaways: string[];
  sections: ReadingSection[];
  checklist: string[];
  sources: ReadingSource[];
  cta: { label: string; href: string };
};

export const readingArticles: ReadingArticle[] = [
  {
    slug: "zero-sugar-not-zero-calorie",
    category: "성분 읽기",
    title: "제로슈거인데 왜 열량은 0이 아닐까요?",
    summary: "포장 앞면의 ‘제로’ 한 단어보다 영양성분표의 기준량과 당류, 열량을 함께 읽는 법을 정리했어요.",
    readMinutes: 4,
    cover: "0g ≠ 0kcal",
    coverCaption: "제로가 가리키는 항목부터 확인",
    takeaways: [
      "제로슈거와 제로칼로리는 같은 뜻이 아니에요.",
      "표시량과 실제로 먹는 양이 다르면 섭취량도 달라져요.",
      "비교할 때는 100g·100mL처럼 기준을 먼저 맞춰야 해요.",
    ],
    sections: [
      {
        heading: "‘제로’ 뒤에 붙은 단어가 핵심이에요",
        paragraphs: [
          "제품 앞면의 큰 글자는 빠르게 특징을 전달하지만, 무엇이 제로인지까지 읽어야 정확해요. 제로슈거는 당류에 관한 표현이고 제로칼로리는 열량에 관한 표현이라 서로 대신할 수 없습니다.",
          "당류가 낮아도 지방이나 탄수화물 등에서 열량이 생길 수 있어요. 반대로 열량이 낮다는 말만으로 당류까지 낮다고 판단할 수도 없습니다.",
        ],
      },
      {
        heading: "숫자는 ‘얼마를 기준으로 썼는지’와 한 세트예요",
        paragraphs: [
          "영양성분표가 1회 제공량 기준인지, 포장 전체 기준인지 먼저 확인하세요. 한 병이 2회분인데 전부 마셨다면 표시된 수치를 두 배로 계산해야 실제 섭취량과 가까워집니다.",
          "두 제품을 비교할 때 한쪽은 한 봉지, 다른 쪽은 100g 기준이라면 숫자만 나란히 놓아서는 의미가 없어요. 같은 중량이나 용량으로 맞춘 뒤 당류와 열량을 보세요.",
        ],
      },
      {
        heading: "포장 앞에서 10초만 이렇게 보세요",
        paragraphs: ["복잡한 계산보다 아래 순서를 습관으로 만드는 편이 오래 갑니다."],
        bullets: ["제로 뒤에 붙은 단어 확인", "총 내용량과 영양정보 기준량 확인", "실제로 먹을 양만큼 당류·열량 환산"],
      },
    ],
    checklist: ["제로슈거와 제로칼로리를 구분했나요?", "한 번에 먹을 양을 기준으로 계산했나요?", "비교 제품의 단위를 맞췄나요?"],
    sources: [
      { label: "식품의약품안전처 2024 자주하는 질문집 — 영양성분 강조 표시", href: "https://www.mfds.go.kr/etc/ebook/2410_42929/index.html" },
      { label: "식품의약품안전처 「식품등의 표시기준」 개정 안내", href: "https://www.mfds.go.kr/brd/m_207/view.do?seq=14712" },
    ],
    cta: { label: "같은 단위로 저당 제품 비교하기", href: "/search" },
  },
  {
    slug: "who-daily-sugar",
    category: "하루 기준",
    title: "하루 당류 50g, 모두에게 같은 답일까요?",
    summary: "WHO의 10% 기준이 어떻게 50g이 되는지, 당당의 기록 수치와는 무엇이 다른지 짚어봅니다.",
    readMinutes: 4,
    cover: "10% → 50g",
    coverCaption: "2,000kcal일 때의 계산 예시",
    takeaways: [
      "WHO 기준은 ‘유리당’을 총 섭취 열량의 10% 미만으로 줄이라는 권고예요.",
      "2,000kcal를 기준으로 계산하면 약 50g이지만 개인 목표는 달라질 수 있어요.",
      "당당의 제품 당류 기록은 유리당과 완전히 같은 지표가 아니에요.",
    ],
    sections: [
      {
        heading: "50g은 고정된 정답이 아니라 계산 예시예요",
        paragraphs: [
          "WHO는 성인과 어린이의 유리당 섭취를 하루 총열량의 10% 미만으로 줄이도록 권고하고, 5% 미만으로 더 낮추면 추가 이점이 있을 수 있다고 설명합니다.",
          "당 1g을 4kcal로 계산하면 2,000kcal의 10%인 200kcal는 약 50g이 됩니다. 하루 섭취 열량이 다르면 같은 방식으로 계산한 값도 달라집니다.",
        ],
      },
      {
        heading: "‘유리당’과 영양성분표의 ‘당류’는 범위가 달라요",
        paragraphs: [
          "WHO의 유리당에는 제조·조리 중 넣은 당과 꿀, 시럽, 과일주스·농축액에 자연적으로 존재하는 당이 포함됩니다. 반면 제품 영양성분표의 당류는 식품에 들어 있는 단당류와 이당류의 합을 보여주는 값이라 범위가 정확히 같지 않습니다.",
          "당당은 제품과 기록에서 확인 가능한 ‘당류’를 합산합니다. 따라서 앱의 하루 목표는 생활 기록을 위한 참고선으로 보고, WHO의 유리당 권고와 동일한 의료 기준처럼 해석하지 않는 게 중요해요.",
        ],
      },
      {
        heading: "하루 한 번보다 일주일 흐름을 보세요",
        paragraphs: [
          "어느 날 목표를 넘었다고 식사를 실패한 것은 아니에요. 음료, 간식, 소스처럼 자주 반복되는 항목을 일주일 단위로 찾아 한 가지만 바꾸는 편이 현실적입니다.",
        ],
        bullets: ["가장 자주 먹은 단 음료 확인", "같은 제품의 실제 섭취량 확인", "한 번에 하나의 대안만 바꿔보기"],
      },
    ],
    checklist: ["내 목표가 어떤 열량 기준인지 확인했나요?", "당류와 유리당을 같은 말로 보지 않았나요?", "하루 수치보다 반복되는 습관을 찾았나요?"],
    sources: [
      { label: "WHO — Sugars intake for adults and children", href: "https://www.who.int/publications-detail-redirect/WHO-NMH-NHD-15.3" },
      { label: "WHO — Healthy diet fact sheet", href: "https://www.who.int/news-room/fact-sheets/detail/healthy-diet" },
    ],
    cta: { label: "내 하루 기록 확인하기", href: "/diet" },
  },
  {
    slug: "sugar-alcohol-belly",
    category: "감미료",
    title: "제로 간식을 먹고 배가 불편했던 이유",
    summary: "말티톨·소비톨 같은 당알코올의 공통점과 처음 먹는 제품을 편하게 확인하는 방법을 담았어요.",
    readMinutes: 5,
    cover: "배가 꾸르륵?",
    coverCaption: "당알코올은 섭취량도 함께 보기",
    takeaways: [
      "일부 당알코올은 몸에 완전히 흡수되지 않아 복부 불편을 만들 수 있어요.",
      "같은 성분도 제품의 함량과 먹는 양, 개인차에 따라 느낌이 달라요.",
      "‘무설탕’만 보고 많이 먹기보다 원재료와 1회분을 확인하세요.",
    ],
    sections: [
      {
        heading: "단맛은 나지만 설탕과 흡수 방식이 달라요",
        paragraphs: [
          "당알코올은 탄수화물의 한 종류로 에리스리톨, 말티톨, 소비톨, 자일리톨 등이 있습니다. 설탕보다 천천히 또는 불완전하게 흡수되는 특성 때문에 제품의 당류와 열량을 낮추는 데 쓰입니다.",
          "흡수되지 않은 일부가 대장으로 이동하면 가스, 복부 팽만, 설사 같은 불편이 생길 수 있습니다. 모든 사람에게 같은 양에서 같은 반응이 나타나는 것은 아닙니다.",
        ],
      },
      {
        heading: "성분 이름 하나보다 ‘얼마나 먹었는지’가 중요해요",
        paragraphs: [
          "같은 말티톨 제품이라도 함량과 1회분은 다릅니다. 처음 먹는 제품을 큰 봉지째 먹으면 어떤 성분에 반응했는지 알아채기도 어려워요.",
          "원재료명 앞쪽에 표시된 성분일수록 일반적으로 사용 비중이 높은 편입니다. 여러 당알코올이 함께 들어 있는지도 확인해보세요.",
        ],
      },
      {
        heading: "처음 먹는 제로 간식이라면",
        paragraphs: ["아래처럼 작은 단위로 확인하면 내게 맞는 제품을 찾기 쉬워집니다."],
        bullets: ["표시된 1회분 이하로 시작", "같은 날 비슷한 제품을 여러 개 겹쳐 먹지 않기", "불편감이 반복되면 제품명과 섭취량 기록"],
      },
    ],
    checklist: ["원재료명에서 당알코올을 확인했나요?", "한 번에 먹을 양이 1회분을 넘지 않나요?", "불편이 반복되면 섭취를 중단하고 전문가와 상의하세요."],
    sources: [
      { label: "미국 FDA — Interactive Nutrition Facts Label: Sugar Alcohols", href: "https://www.accessdata.fda.gov/scripts/interactivenutritionfactslabel/assets/InteractiveNFL_SugarAlcohols_October2021.pdf" },
    ],
    cta: { label: "감미료별 제품 살펴보기", href: "/search" },
  },
  {
    slug: "read-nutrition-label",
    category: "처음 읽기",
    title: "영양성분표는 세 군데만 먼저 보세요",
    summary: "총 내용량, 영양정보 기준량, 당류. 이 순서만 익혀도 제품 비교가 훨씬 빨라져요.",
    readMinutes: 3,
    cover: "1 → 2 → 3",
    coverCaption: "내용량 · 기준량 · 당류",
    takeaways: [
      "포장 전체와 영양정보 기준량이 같은지 먼저 봐요.",
      "실제로 먹을 양에 맞춰 당류와 열량을 계산해요.",
      "제품 비교는 같은 중량·용량 기준으로 해요.",
    ],
    sections: [
      {
        heading: "첫째, 포장에 총 몇 g·mL가 들었는지",
        paragraphs: ["제품 앞이나 뒷면의 총 내용량을 먼저 찾으세요. 작은 병처럼 보여도 영양정보가 절반 기준일 수 있고, 큰 봉지도 낱개 한 개 기준으로 표시될 수 있습니다."],
      },
      {
        heading: "둘째, 영양정보가 어느 양을 기준으로 하는지",
        paragraphs: ["‘총 내용량당’, ‘100g당’, ‘1회 제공량당’ 같은 문구를 확인합니다. 이 줄을 놓치면 당류 5g을 먹었다고 생각했는데 실제로는 10g을 먹는 식의 차이가 생겨요."],
      },
      {
        heading: "셋째, 당류와 열량을 같이 보기",
        paragraphs: ["당류가 낮아진 대신 열량이나 지방이 반드시 높아지는 것은 아니고, 그 반대도 아닙니다. 두 수치를 따로 보고 내 기록에서 더 필요한 기준을 선택하세요."],
        bullets: ["총 내용량 확인", "영양정보 기준량 확인", "실제 섭취량으로 환산", "같은 단위 제품끼리 비교"],
      },
    ],
    checklist: ["포장 전체가 몇 회분인지 찾았나요?", "당류 숫자 옆의 기준량을 확인했나요?", "한 번에 먹을 양으로 다시 계산했나요?"],
    sources: [
      { label: "식품안전나라 — 영양표시 확인 안내", href: "https://www.foodsafetykorea.go.kr/upload/20150824/20150824011539_1440389739434.pdf" },
    ],
    cta: { label: "제품 영양정보 비교하기", href: "/search" },
  },
  {
    slug: "allulose-vs-erythritol",
    category: "감미료",
    title: "알룰로스와 에리스리톨, 이름 말고 뭘 봐야 할까요?",
    summary: "어느 쪽이 무조건 낫다는 결론 대신, 제품 전체와 내 섭취 경험을 비교하는 기준을 알려드려요.",
    readMinutes: 4,
    cover: "A vs E",
    coverCaption: "감미료보다 완성된 제품을 비교",
    takeaways: ["감미료 하나만으로 제품 전체를 평가할 수 없어요.", "당류·열량·1회분·함께 든 성분을 같이 보세요.", "맛과 소화 편안함은 개인차가 있어 작은 양부터 확인해요."],
    sections: [
      { heading: "둘 다 단맛을 내지만 완성된 제품은 달라요", paragraphs: ["알룰로스나 에리스리톨이라는 이름만 보고 제품의 당류와 열량을 예상하기는 어렵습니다. 설탕, 시럽, 전분, 지방 등 다른 원재료가 함께 들어갈 수 있기 때문이에요.", "같은 감미료를 쓴 제품끼리도 1회분과 영양값은 달라요. 감미료 이름은 출발점이고 최종 판단은 영양성분표에서 해야 합니다."] },
      { heading: "맛과 사용감도 선택 기준이에요", paragraphs: ["음료, 소스, 베이커리처럼 제품 형태가 달라지면 단맛의 느낌과 뒷맛도 달라집니다. 온라인 평가보다 내가 자주 먹을 형태에서 적은 양을 직접 확인하는 편이 정확해요."] },
      { heading: "비교 순서를 정해두세요", paragraphs: ["복잡한 성분표 앞에서 아래 네 가지만 같은 순서로 보면 선택 속도가 빨라집니다."], bullets: ["실제로 먹을 1회분", "당류와 열량", "감미료가 한 종류인지 혼합인지", "먹은 뒤 내 컨디션"] },
    ],
    checklist: ["감미료 이름만으로 고르지 않았나요?", "같은 양을 기준으로 영양값을 비교했나요?", "처음 먹는 제품은 적은 양으로 시작했나요?"],
    sources: [{ label: "미국 FDA — Sugar Alcohols 안내", href: "https://www.accessdata.fda.gov/scripts/interactivenutritionfactslabel/assets/InteractiveNFL_SugarAlcohols_October2021.pdf" }],
    cta: { label: "감미료 필터로 제품 보기", href: "/search" },
  },
  {
    slug: "reduce-sugar-habit",
    category: "식단 기록",
    title: "간식을 끊지 않고 당류를 줄이는 현실적인 순서",
    summary: "의지보다 환경을 바꾸는 네 단계. 자주 먹는 간식 하나부터 기록하고 바꿔보세요.",
    readMinutes: 4,
    cover: "끊기보다 바꾸기",
    coverCaption: "반복되는 한 가지부터",
    takeaways: ["모든 간식을 한꺼번에 끊지 않아도 돼요.", "가장 자주 먹는 한 가지를 찾는 게 먼저예요.", "대체 제품은 맛과 양까지 비슷해야 오래 유지돼요."],
    sections: [
      { heading: "먼저 ‘많이’보다 ‘자주’를 찾으세요", paragraphs: ["한 번 먹은 케이크보다 매일 마시는 음료나 습관처럼 집어 드는 간식이 전체 흐름을 더 크게 바꿀 수 있어요. 일주일 기록에서 가장 자주 등장한 항목 하나를 골라보세요."] },
      { heading: "대안은 같은 역할을 해야 해요", paragraphs: ["출출함을 달래는 간식을 음료로 바꾸거나, 탄산이 당겨 마시는 제품을 견과로 바꾸면 오래 가기 어렵습니다. 같은 식품군, 비슷한 양과 사용 상황 안에서 당류가 의미 있게 낮은 제품을 찾아야 해요."] },
      { heading: "4단계로 한 가지만 바꿔보세요", paragraphs: ["완벽한 식단보다 반복 가능한 작은 변화가 목표입니다."], bullets: ["7일 동안 평소대로 기록", "가장 자주 먹은 간식 하나 선택", "같은 종류의 낮은 당류 제품 비교", "다음 7일 동안 맛·포만감·컨디션 기록"] },
    ],
    checklist: ["일주일에 가장 자주 먹은 항목을 찾았나요?", "같은 종류 안에서 대안을 골랐나요?", "먹는 양까지 비슷하게 비교했나요?"],
    sources: [{ label: "당당 식단 기록을 활용한 생활 실천 가이드" }],
    cta: { label: "오늘 간식 기록하기", href: "/diet" },
  },
  {
    slug: "no-added-sugar-trap",
    category: "성분 읽기",
    title: "‘무가당’인데 당류가 적혀 있는 이유",
    summary: "당을 따로 넣지 않았다는 말과 식품에 원래 들어 있는 당류를 구분하면 포장 문구가 선명해져요.",
    readMinutes: 4,
    cover: "무가당 ≠ 무당",
    coverCaption: "첨가 여부와 최종 함량은 다른 질문",
    takeaways: ["무가당은 제조 중 당류를 첨가했는지에 관한 표현이에요.", "과일·우유 원료에는 원래 당류가 있을 수 있어요.", "최종 당류 함량은 반드시 영양성분표에서 확인해요."],
    sections: [
      { heading: "‘넣지 않았다’와 ‘들어 있지 않다’는 달라요", paragraphs: ["무가당 또는 설탕 무첨가는 제조 과정에서 설탕류를 따로 넣지 않았다는 의미로 사용됩니다. 과일, 우유, 곡물처럼 원재료 자체에 들어 있던 당류까지 사라졌다는 뜻은 아니에요."] },
      { heading: "과일주스가 이해하기 쉬운 예예요", paragraphs: ["설탕을 따로 넣지 않은 주스라도 과일에서 온 당류가 영양성분표에 표시될 수 있습니다. 그래서 앞면의 무가당 문구와 뒷면의 당류 g이 동시에 존재할 수 있어요."] },
      { heading: "두 문장을 따로 확인하세요", paragraphs: ["앞면에서는 ‘제조 중 무엇을 넣지 않았는가’를, 영양성분표에서는 ‘완성된 제품에 당류가 얼마나 있는가’를 확인하면 됩니다."], bullets: ["무가당·설탕 무첨가 문구 확인", "원재료명에서 농축액·시럽 등 확인", "영양성분표의 최종 당류 확인"] },
    ],
    checklist: ["무가당을 당류 0g으로 해석하지 않았나요?", "원재료 자체의 당류 가능성을 봤나요?", "최종 당류 g을 확인했나요?"],
    sources: [{ label: "식품의약품안전처 — 무가당·설탕 무첨가 표시기준 안내", href: "https://www.mfds.go.kr/brd/m_207/view.do?seq=14712" }],
    cta: { label: "무가당 제품 영양정보 보기", href: "/search" },
  },
  {
    slug: "sweetener-ranking",
    category: "데이터 노트",
    title: "제로 제품에는 어떤 감미료가 자주 쓰일까요?",
    summary: "당당 상품 DB에서 감미료 태그를 모아보고, 순위를 볼 때 놓치지 말아야 할 한계까지 함께 적었습니다.",
    readMinutes: 4,
    cover: "DB로 세어보기",
    coverCaption: "상품 원재료 태그 기준",
    takeaways: ["당당 DB에서는 수크랄로스 태그가 가장 자주 연결돼 있어요.", "한 제품에 여러 감미료가 함께 쓰일 수 있어요.", "원재료 정보가 비어 있는 제품은 집계에서 빠질 수 있어요."],
    sections: [
      { heading: "이 순위는 판매량 순위가 아니에요", paragraphs: ["당당이 수집한 상품의 원재료명과 연결된 감미료 태그를 센 결과입니다. 많이 팔린 제품이나 실제 섭취량을 뜻하지 않고, 현재 DB 안에서 어떤 이름이 자주 등장하는지 보여줘요."] },
      { heading: "수크랄로스가 가장 자주 보였어요", paragraphs: ["현재 데이터에서는 수크랄로스가 가장 많은 상품에 연결됐습니다. 에리스리톨, 알룰로스처럼 익숙한 이름도 보이지만 한 제품에 두세 가지 감미료가 함께 들어가는 경우가 있어 단순 합계는 제품 수와 다를 수 있어요."] },
      { heading: "숫자보다 제품 한 개의 조합을 보세요", paragraphs: ["인기 순위가 나에게 더 잘 맞는 감미료를 의미하지는 않습니다. 제품 상세에서 감미료 조합과 당류, 열량, 1회분을 함께 확인하세요."], bullets: ["집계 기준일 확인", "복수 감미료 사용 여부 확인", "원재료 누락 가능성 확인"] },
    ],
    checklist: ["판매량 순위로 오해하지 않았나요?", "한 제품의 감미료 조합을 확인했나요?", "당류와 열량도 함께 비교했나요?"],
    sources: [{ label: "당당 상품 데이터 — service.mv_sweetener_catalog (2026-08-09 집계)" }],
    cta: { label: "감미료별 제품 찾아보기", href: "/search" },
  },
];

const legacySlugAliases: Record<string, string> = {
  "zero-sugar-label": "zero-sugar-not-zero-calorie",
  "sweetener-guide": "allulose-vs-erythritol",
  "snack-sugar-balance": "reduce-sugar-habit",
  "nutrition-label-first": "read-nutrition-label",
};

export function getReadingArticle(slug: string) {
  const canonicalSlug = legacySlugAliases[slug] ?? slug;
  return readingArticles.find((article) => article.slug === canonicalSlug);
}

export const featuredReadingArticles = [
  "zero-sugar-not-zero-calorie",
  "who-daily-sugar",
  "sugar-alcohol-belly",
  "read-nutrition-label",
].map((slug) => getReadingArticle(slug)).filter((article): article is ReadingArticle => Boolean(article));

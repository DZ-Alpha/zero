/* Vision이 뱉는 요리명으로 레시피를 찾기 위한 질의어 폴백.
 *
 * recipe-service의 검색은 이름 통짜 ILIKE 하나뿐이라(recipe_store.py) Vision의
 * 요리명이 그대로 걸리는 경우가 거의 없다 - 실사용 10건 중 1건만 히트했다
 * (2026-08-12 추가 지시서 §4). 레시피 자체는 있는데(1,722건) 질의어가 안 맞는
 * 것이라, 백엔드를 건드리지 않고 질의어를 단계적으로 넓혀서 찾는다.
 *
 *   1) 통짜        "닭가슴살 토마토 파스타"
 *   2) 공백 토큰   "닭가슴살" "토마토" "파스타"   (2글자 이상)
 *   3) 요리 접미사 "볶음밥" "떡볶이" "치킨"       (사전 기반)
 *
 * 공백이 없는 복합명사(스팸김치볶음밥, 치즈떡볶이)는 2단계로 안 되고 3단계가
 * 필요하다. 한 글자 토큰까지는 내려가지 않는다 - 노이즈가 급증한다.
 */

// 긴 접미사가 먼저 걸리도록 길이 내림차순으로 유지한다("스팸김치볶음밥"이
// "밥"이 아니라 "볶음밥"으로 잡혀야 한다).
const DISH_SUFFIXES = [
  "프라푸치노",
  "샌드위치",
  "떡볶이",
  "볶음밥",
  "팟타이",
  "파스타",
  "샐러드",
  "스무디",
  "리조또",
  "덮밥",
  "김밥",
  "치킨",
  "버거",
  "포케",
  "찌개",
  "볶음",
  "무침",
  "구이",
  "조림",
  "튀김",
  "라떼",
  "스프",
  "커리",
  "면",
  "밥",
  "국",
  "탕",
  "죽",
  "전",
  "빵",
].sort((a, b) => b.length - a.length);

const MIN_TOKEN_LENGTH = 2;

function compact(value: string): string {
  return value.replace(/\s+/g, "");
}

/** 이 이름으로 시도해볼 질의어를 넓은 순서대로 돌려준다. 첫 번째가 정확 매칭. */
export function recipeQueryCandidates(name: string): string[] {
  const trimmed = name.trim();
  if (!trimmed) return [];

  const candidates: string[] = [trimmed];

  const tokens = trimmed
    .split(/\s+/)
    .filter((token) => token.length >= MIN_TOKEN_LENGTH)
    .sort((a, b) => b.length - a.length);
  candidates.push(...tokens);

  // 접미사는 이름 끝에 붙은 것을 먼저 본다 - "치즈떡볶이"의 떡볶이처럼 요리
  // 종류를 가리키는 자리다. 끝에서 못 찾으면 이름 안에 든 것까지 본다.
  const compacted = compact(trimmed);
  const suffix =
    DISH_SUFFIXES.find((item) => compacted.endsWith(item)) ??
    DISH_SUFFIXES.find((item) => compacted.includes(item));
  if (suffix) candidates.push(suffix);

  return candidates.filter((value, index) => value.length > 0 && candidates.indexOf(value) === index);
}

/** 몇 번째 후보가 히트했는지로 "정확 매칭인지"를 판단한다. */
export function isFallbackQuery(candidateIndex: number): boolean {
  return candidateIndex > 0;
}

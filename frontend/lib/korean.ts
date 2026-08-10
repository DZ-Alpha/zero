/* 조사 자동 선택. "D-말티톨을(를) 사용했어요"처럼 괄호를 그대로 노출하지 않기 위해
   마지막 글자의 받침을 보고 조사를 고른다. 한글이 아닌 문자로 끝나면 읽는 소리를
   기준으로 판단한다(숫자·알파벳). */

const LATIN_WITH_FINAL = new Set(["l", "m", "n", "r", "ng"]);
const DIGIT_HAS_FINAL: Record<string, boolean> = {
  "0": true, // 영
  "1": true, // 일
  "3": true, // 삼
  "6": true, // 육
  "7": true, // 칠
  "8": true, // 팔
  "2": false,
  "4": false,
  "5": false,
  "9": false,
};

/** 마지막 글자에 받침이 있으면 true. */
export function hasFinalConsonant(word: string): boolean {
  const last = word.trim().slice(-1);
  if (!last) return false;

  const code = last.charCodeAt(0);
  if (code >= 0xac00 && code <= 0xd7a3) return (code - 0xac00) % 28 !== 0;
  if (last >= "0" && last <= "9") return DIGIT_HAS_FINAL[last] ?? false;

  const lower = last.toLowerCase();
  if (lower >= "a" && lower <= "z") {
    const tail = word.trim().slice(-2).toLowerCase();
    return LATIN_WITH_FINAL.has(tail) || LATIN_WITH_FINAL.has(lower);
  }
  return false;
}

/** 단어에 맞는 조사를 붙여 돌려준다. `withParticle("말티톨", "을")` → "말티톨을" */
export function withParticle(word: string, particle: "을" | "이" | "은" | "와" | "로"): string {
  const final = hasFinalConsonant(word);
  const pair: Record<string, [string, string]> = {
    을: ["을", "를"],
    이: ["이", "가"],
    은: ["은", "는"],
    와: ["과", "와"],
    로: ["으로", "로"],
  };
  const [withFinal, withoutFinal] = pair[particle];
  // 'ㄹ' 받침은 '로' 앞에서 예외적으로 받침이 없는 것처럼 쓴다(말티톨로).
  if (particle === "로" && word.trim().slice(-1) >= "가") {
    const code = word.trim().charCodeAt(word.trim().length - 1);
    if (code >= 0xac00 && code <= 0xd7a3 && (code - 0xac00) % 28 === 8) return `${word}로`;
  }
  return `${word}${final ? withFinal : withoutFinal}`;
}

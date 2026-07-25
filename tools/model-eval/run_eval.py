import asyncio
import csv
import sys
from datetime import datetime
from pathlib import Path

import config
from db import SampleProduct, fetch_sample_products
from prompts import product_summary_prompt, sweetener_description_prompt, user_feature_info_prompt
from providers import CALLERS, CallResult

RESULTS_DIR = Path(__file__).parent / "results"


async def run_one(feature: str, candidate, prompt: str) -> tuple[str, str, CallResult]:
    caller = CALLERS[candidate.provider]
    result = await caller(candidate.model_id, prompt)
    return feature, candidate.label, result


async def eval_product(product: SampleProduct) -> list[tuple[str, str, CallResult]]:
    tasks = []
    for candidate in config.CANDIDATES:
        tasks.append(run_one("PR-0301 (한줄요약)", candidate, product_summary_prompt(product)))

        sweetener_prompt = sweetener_description_prompt(product)
        if sweetener_prompt:
            tasks.append(run_one("PR-0302 (감미료 설명)", candidate, sweetener_prompt))

        for profile in config.SAMPLE_USER_PROFILES:
            prompt = user_feature_info_prompt(
                product,
                profile["birth_year"],
                profile["gender"],
                profile["daily_calorie_target"],
                profile["daily_sugar_target_g"],
            )
            tasks.append(run_one(f"PR-0303 (맞춤설명·{profile['label']})", candidate, prompt))

    return await asyncio.gather(*tasks)


async def main() -> None:
    print(f"상품 {config.EVAL_SAMPLE_SIZE}개 조회 중...")
    products = await fetch_sample_products(config.EVAL_SAMPLE_SIZE)
    if not products:
        print("조회된 상품이 없어요 - DB 연결/EVAL_SAMPLE_SIZE 확인해주세요.")
        sys.exit(1)
    print(f"{len(products)}개 상품으로 {len(config.CANDIDATES)}개 모델 비교 시작...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    RESULTS_DIR.mkdir(exist_ok=True)
    md_path = RESULTS_DIR / f"eval_{timestamp}.md"
    csv_path = RESULTS_DIR / f"eval_{timestamp}.csv"

    md_lines = [f"# AI 모델 비교 결과 ({timestamp})", ""]
    csv_rows = [["product", "feature", "model", "latency_s", "input_tokens", "output_tokens", "error", "output"]]

    for product in products:
        print(f"- {product.product_name} 처리 중...")
        results = await eval_product(product)

        md_lines.append(f"## {product.product_name} ({product.product_id})")
        by_feature: dict[str, list[tuple[str, CallResult]]] = {}
        for feature, label, result in results:
            by_feature.setdefault(feature, []).append((label, result))
            csv_rows.append([
                product.product_name, feature, label,
                f"{result.latency_s:.2f}", result.input_tokens, result.output_tokens,
                result.error or "", (result.text or "").replace("\n", " "),
            ])

        for feature, entries in by_feature.items():
            md_lines.append(f"\n### {feature}\n")
            md_lines.append("| 모델 | 응답시간(s) | 토큰(in/out) | 결과 |")
            md_lines.append("|---|---|---|---|")
            for label, result in entries:
                if result.error:
                    cell = f"**에러**: {result.error}"
                else:
                    cell = (result.text or "").replace("\n", "<br>").replace("|", "\\|")
                tokens = f"{result.input_tokens or '-'}/{result.output_tokens or '-'}"
                md_lines.append(f"| {label} | {result.latency_s:.2f} | {tokens} | {cell} |")
        md_lines.append("")

    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(csv_rows)

    print(f"\n완료. 결과: {md_path}, {csv_path}")


if __name__ == "__main__":
    asyncio.run(main())

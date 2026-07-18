import fs from "node:fs";
import path from "node:path";

const sourceDir = path.resolve(process.cwd(), "..", "recipes");
const outputPath = path.resolve(process.cwd(), "data", "recipeDatabase.generated.json");

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (char === '"') {
      if (quoted && text[index + 1] === '"') {
        field += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (char === "," && !quoted) {
      row.push(field);
      field = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && text[index + 1] === "\n") index += 1;
      row.push(field);
      field = "";
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
    } else {
      field += char;
    }
  }

  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }

  const headers = rows.shift() ?? [];
  return rows.map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""])));
}

function readCsv(name) {
  return parseCsv(fs.readFileSync(path.join(sourceDir, name), "utf8").replace(/^\uFEFF/, ""));
}

function number(value) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function categoryFor(name) {
  if (/국수|파스타|우동|면|냉면/.test(name)) return "면";
  if (/떡볶이|부꾸미|전|튀김/.test(name)) return "분식";
  if (/잼|소스|드레싱|스프레드|청$|시럽/.test(name)) return "소스";
  if (/케이크|빵|모찌|라떼|쿠키|디저트|아이스|주스|오트밀크/.test(name)) return "간식";
  if (/김치|나물|무침|장아찌|볶음$|가니쉬|반찬/.test(name)) return "반찬";
  return "한 끼";
}

function estimatedTime(stepCount) {
  if (stepCount <= 3) return "약 10분";
  if (stepCount <= 5) return "약 20분";
  if (stepCount <= 8) return "약 30분";
  return "약 40분";
}

function sourceUrl(recipe) {
  return recipe.source === "유튜브"
    ? `https://www.youtube.com/watch?v=${recipe.video_id}`
    : `https://www.10000recipe.com/recipe/${recipe.id}`;
}

const recipeRows = readCsv("recipes.csv");
const ingredientRows = readCsv("recipe_ingredients.csv");
const ingredientsByRecipe = new Map();

for (const ingredient of ingredientRows) {
  const current = ingredientsByRecipe.get(ingredient.recipe_id) ?? [];
  current.push(ingredient);
  ingredientsByRecipe.set(ingredient.recipe_id, current);
}

const relevant = /저당|저염|다이어트|제로|알룰로스|곤약|샐러드/;
const excluded = /혈당|당뇨|해독|디톡스|효과 최고|걱정없는/;
const tones = ["lime", "mint", "sand", "lavender"];

const candidates = recipeRows.flatMap((recipe) => {
  if (recipe.source !== "만개의레시피" || !relevant.test(recipe.name) || excluded.test(recipe.name) || !recipe.thumbnail_url) return [];
  const ingredients = ingredientsByRecipe.get(recipe.id) ?? [];
  if (ingredients.length < 3) return [];
  const known = ingredients.filter((item) => number(item.sugar_g) !== null && number(item.kcal) !== null);
  if (known.length !== ingredients.length) return [];

  let steps;
  try {
    steps = JSON.parse(recipe.steps || "[]");
  } catch {
    return [];
  }
  if (!Array.isArray(steps) || steps.length < 2) return [];

  const sugar = known.reduce((sum, item) => sum + number(item.sugar_g), 0);
  const kcal = known.reduce((sum, item) => sum + number(item.kcal), 0);
  if (sugar < 0 || sugar > 60 || kcal < 20 || kcal > 1200) return [];

  return [{ recipe, ingredients, steps, sugar, kcal, category: categoryFor(recipe.name) }];
}).sort((a, b) => new Date(b.recipe.published_at) - new Date(a.recipe.published_at));

const categoryCounts = new Map();
const selected = [];
for (const candidate of candidates) {
  const count = categoryCounts.get(candidate.category) ?? 0;
  if (count >= 12) continue;
  categoryCounts.set(candidate.category, count + 1);
  selected.push(candidate);
  if (selected.length === 48) break;
}

const generated = selected.map(({ recipe, ingredients, steps, sugar, kcal, category }, index) => {
  const ingredientNames = ingredients.slice(0, 3).map((item) => item.name.replaceAll("_", " "));
  return {
    slug: `db-${recipe.id}`,
    databaseId: recipe.id,
    title: recipe.name.replace(/^﻿/, "").trim(),
    author: "만개의레시피 DB",
    category,
    servings: "등록 재료 전체",
    time: estimatedTime(steps.length),
    difficulty: "단계별 안내",
    summary: `${ingredientNames.join(", ")} 등을 활용해 만드는 레시피예요.`,
    ingredients: ingredients.map((item) => `${item.name.replaceAll("_", " ")}${item.amount ? ` ${item.amount}` : ""}`.trim()),
    steps: steps.map((description, stepIndex) => ({ title: `${stepIndex + 1}단계`, description })),
    sourceUrl: sourceUrl(recipe),
    estimatedSugar: Math.round(sugar * 100) / 100,
    estimatedCalories: Math.round(kcal),
    estimatedProtein: 0,
    comparisonSugar: 0,
    comparisonCalories: 0,
    comparisonStatus: "pending",
    nutritionCoverage: 100,
    publishedAt: recipe.published_at,
    thumbnail: recipe.thumbnail_url,
    savedDemo: Math.max(120, 520 - index * 7),
    tone: tones[index % tones.length],
    keywords: ingredientNames,
  };
});

fs.writeFileSync(outputPath, `${JSON.stringify(generated, null, 2)}\n`, "utf8");
console.log(`Generated ${generated.length} recipes from ${recipeRows.length} recipe rows.`);

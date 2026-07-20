"use client";

import Link from "next/link";
import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { RecordDateNavigator } from "@/components/RecordDateNavigator";
import { LoginPromptDialog } from "@/components/SystemFeedback";
import { products, recipes } from "@/data/catalog";
import { PRODUCT_CATEGORIES } from "@/data/taxonomy";
import { DietRecord, DietRecordsByDate, getTodayKey, MealType, useDietRecords } from "@/hooks/useDietRecords";
import { useProductCatalog } from "@/hooks/useProductCatalog";
import { useRecipeCatalog } from "@/hooks/useRecipeCatalog";
import { useUserSettings } from "@/hooks/useUserSettings";
import { useAuthSession } from "@/hooks/useAuthSession";
import { getAccessToken } from "@/lib/api/client";
import {
  confirmDietPhoto,
  DietAnalysisItem,
  DietPhotoStatusResponse,
  getDietPhotoStatus,
  getProductDetail,
  getRecipeDetail,
  uploadDietPhoto,
  uploadDietPhotoFile,
} from "@/lib/api/zerocheck";

// worker 분석은 비동기라 202로 등록만 되고, 결과는 폴링으로 받는다. 60초
// 넘으면 "아직 분석 중" 상태로 그냥 보여주고 폴링을 멈춘다.
const POLL_DELAYS_MS = [1000, 2000, 3000, 5000];
const POLL_MAX_MS = 60_000;

async function pollDietPhotoStatus(token: string, mealLogId: string): Promise<DietPhotoStatusResponse> {
  const start = Date.now();
  let attempt = 0;
  for (;;) {
    const status = await getDietPhotoStatus(token, mealLogId);
    if (status.status !== "PENDING" && status.status !== "PROCESSING") return status;
    if (Date.now() - start >= POLL_MAX_MS) return status;
    await new Promise((resolve) => window.setTimeout(resolve, POLL_DELAYS_MS[Math.min(attempt, POLL_DELAYS_MS.length - 1)]));
    attempt += 1;
  }
}

type Source = "recipe" | "photo" | "product" | "favorite";
type FoodItem = {
  id: string;
  name: string;
  kind: "레시피" | "식품" | "사진 분석";
  category: string;
  sugar: number;
  calories: number;
  note: string;
  href: string;
  favorite?: boolean;
  nutritionAvailable: boolean;
};

const meals: MealType[] = ["아침", "점심", "저녁", "간식"];
const sourceTabs: { id: Source; label: string }[] = [
  { id: "photo", label: "사진 입력" },
  { id: "recipe", label: "레시피" },
  { id: "product", label: "식품 검색" },
  { id: "favorite", label: "즐겨찾기" },
];
const acceptedImageTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const maxImageBytes = 10 * 1024 * 1024;

const favoriteRecipeIds = new Set(recipes.filter((_, index) => index === 0 || index === 4).map((recipe) => recipe.databaseId ?? recipe.slug));
const favoriteProductIds = new Set(products.filter((_, index) => index === 0 || index === 3 || index === 5).map((product) => product.backendId ?? product.slug));
function percent(value: number, max: number) {
  return Math.min(100, Math.round((value / max) * 100));
}

function roundSugar(value: number) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function sugarText(value: number) {
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(roundSugar(value));
}

export function RecordMealModal({
  meal,
  initialDate = getTodayKey(),
  minDate = "2026-06-01",
  maxDate = getTodayKey(),
  existingRecordsByDate,
  onClose,
  onSaved,
}: {
  meal: MealType;
  initialDate?: string;
  minDate?: string;
  maxDate?: string;
  existingRecordsByDate?: DietRecordsByDate;
  onClose: () => void;
  onSaved?: (dateKey: string, record: DietRecord) => void;
}) {
  const { recordsByDate: hookRecordsByDate, addRecord, addServerRecord } = useDietRecords();
  const { ready: authReady, signedIn } = useAuthSession();
  const recordsByDate = existingRecordsByDate ?? hookRecordsByDate;
  const { goals } = useUserSettings();
  const [recordDate, setRecordDate] = useState(initialDate);
  const [source, setSource] = useState<Source>("photo");
  const [selected, setSelected] = useState<FoodItem | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("전체");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [fileError, setFileError] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [serverMealLogId, setServerMealLogId] = useState<string | null>(null);
  const [draftItems, setDraftItems] = useState<DietAnalysisItem[] | null>(null);
  const [draftConfidence, setDraftConfidence] = useState<number | null>(null);
  const [confirmState, setConfirmState] = useState<"idle" | "confirming" | "error">("idle");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [loginPrompt, setLoginPrompt] = useState(false);
  const [resolvingItemId, setResolvingItemId] = useState<string | null>(null);
  const [selectionError, setSelectionError] = useState("");
  const photoInput = useRef<HTMLInputElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const recipeCatalog = useRecipeCatalog(recipes);
  const productCategoryCode = PRODUCT_CATEGORIES.find((item) => item.label === category)?.code;
  const productCatalog = useProductCatalog({
    query: source === "product" && query.trim() ? query.trim() : undefined,
    category: source === "product" ? productCategoryCode : undefined,
    sort: "rank",
  });

  const recipeLibrary = useMemo<FoodItem[]>(() => recipeCatalog.recipes
    .filter((recipe) => recipe.category !== "소스")
    .map((recipe) => {
      const id = recipe.databaseId ?? recipe.slug;
      return {
        id: `recipe-${id}`,
        name: recipe.title,
        kind: "레시피",
        category: recipe.category,
        sugar: recipe.estimatedSugar,
        calories: recipe.estimatedCalories,
        note: Number(recipe.nutritionCoverage ?? 0) > 0 ? `${recipe.summary} 등록된 재료 영양값을 합산했어요.` : "자세한 재료와 영양정보는 상세에서 확인할 수 있어요.",
        href: `/recipes/${id}`,
        favorite: favoriteRecipeIds.has(id),
        nutritionAvailable: Number(recipe.nutritionCoverage ?? 0) > 0,
      };
    }), [recipeCatalog.recipes]);

  const productLibrary = useMemo<FoodItem[]>(() => productCatalog.products.map((product) => {
    const id = product.backendId ?? product.slug;
    return {
      id: `product-${id}`,
      name: product.title,
      kind: "식품",
      category: product.category,
      sugar: product.sugar,
      calories: product.calories,
      note: `${product.summary} ${product.serving} 기준이에요.`,
      href: `/product/${id}`,
      favorite: favoriteProductIds.has(id),
      nutritionAvailable: product.nutritionAvailable !== false,
    };
  }), [productCatalog.products]);

  const library = useMemo(() => [...recipeLibrary, ...productLibrary], [productLibrary, recipeLibrary]);

  useEffect(() => {
    closeButton.current?.focus();
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape" && saveState !== "saving") onClose();
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onClose, saveState]);

  useEffect(() => () => {
    if (photoPreview) URL.revokeObjectURL(photoPreview);
  }, [photoPreview]);

  const totals = useMemo(() => (recordsByDate[recordDate] ?? []).reduce((sum, item) => ({
    sugar: roundSugar(sum.sugar + item.sugar),
    calories: sum.calories + item.calories,
  }), { sugar: 0, calories: 0 }), [recordDate, recordsByDate]);

  const filtered = library.filter((item) => {
    const kindMatch = source === "recipe" ? item.kind === "레시피" : source === "product" ? item.kind === "식품" : source === "favorite" ? item.favorite : true;
    const queryMatch = item.name.includes(query) || item.category.includes(query);
    const categoryMatch = category === "전체" || item.category === category;
    return kindMatch && queryMatch && categoryMatch;
  }).slice(0, 24);

  const categories = source === "recipe"
    ? ["전체", ...Array.from(new Set(recipeLibrary.map((item) => item.category)))]
    : source === "product"
      ? ["전체", ...Array.from(new Set(productLibrary.map((item) => item.category)))]
      : ["전체"];

  async function selectLibraryItem(item: FoodItem) {
    setSelectionError("");
    if (item.nutritionAvailable) {
      setSelected(item);
      return;
    }

    setResolvingItemId(item.id);
    try {
      if (item.kind === "식품") {
        const id = item.id.replace(/^product-/, "");
        const detail = await getProductDetail(id);
        if (detail.dang == null && detail.cal == null) throw new Error("nutrition unavailable");
        setSelected({
          ...item,
          sugar: Number(detail.dang ?? 0),
          calories: Math.round(Number(detail.cal ?? 0)),
          note: `${detail.brand ?? "제품"}의 상세 영양정보를 불러왔어요.`,
          nutritionAvailable: true,
        });
      } else {
        const id = Number(item.id.replace(/^recipe-/, ""));
        if (!Number.isFinite(id)) throw new Error("invalid recipe id");
        const detail = await getRecipeDetail(id);
        if (detail.nutrition?.totalSugarG == null && detail.nutrition?.totalKcal == null) throw new Error("nutrition unavailable");
        setSelected({
          ...item,
          sugar: Number(detail.nutrition?.totalSugarG ?? 0),
          calories: Math.round(Number(detail.nutrition?.totalKcal ?? 0)),
          note: "등록된 재료의 영양정보를 합산했어요.",
          nutritionAvailable: true,
        });
      }
    } catch {
      setSelectionError("영양정보를 불러오지 못했어요. 상세 화면에서 확인한 뒤 다시 시도해 주세요.");
    } finally {
      setResolvingItemId(null);
    }
  }

  async function analyzePhoto() {
    if (!photoFile) {
      photoInput.current?.click();
      return;
    }
    if (photoFile.size === 0) {
      setAnalysisError("사진을 분석하지 못했어요. 다른 사진을 고르거나 다시 시도해 주세요.");
      return;
    }
    if (!authReady || !signedIn) {
      setLoginPrompt(true);
      return;
    }
    setAnalysisError("");
    setIsAnalyzing(true);
    setUploadProgress(18);

    // 실제 백엔드에 사진을 등록한다: gateway -> MinIO(object_key) -> RC-0101
    // /diet/upload(202, PENDING) -> Vision worker가 비동기로 분석 -> 폴링.
    // 업로드 성공 == 분석 완료가 아니다 - 반드시 상태를 폴링해서 확인한다.
    const token = getAccessToken();
    if (!token) {
      setIsAnalyzing(false);
      setLoginPrompt(true);
      return;
    }

    let registeredId: string;
    try {
      const { object_key } = await uploadDietPhotoFile(token, photoFile);
      setUploadProgress(45);
      const mealType = ({ 아침: "BREAKFAST", 점심: "LUNCH", 저녁: "DINNER", 간식: "SNACK" } as const)[meal];
      const registered = await uploadDietPhoto(token, object_key, mealType, recordDate);
      registeredId = registered.meal_log_id;
      setUploadProgress(65);
    } catch {
      setIsAnalyzing(false);
      setUploadProgress(0);
      setAnalysisError("사진을 서버에 등록하지 못했어요. 연결을 확인하고 다시 시도해 주세요.");
      return;
    }
    setServerMealLogId(registeredId);

    let status: DietPhotoStatusResponse;
    try {
      status = await pollDietPhotoStatus(token, registeredId);
    } catch {
      setIsAnalyzing(false);
      setUploadProgress(0);
      setAnalysisError("분석 상태를 확인하지 못했어요. 잠시 후 다시 시도해 주세요.");
      return;
    }

    setUploadProgress(100);
    await new Promise((resolve) => window.setTimeout(resolve, 380));
    setIsAnalyzing(false);

    const serverItems = status["list-diet"] ?? [];

    if (status.status === "AWAITING_CONFIRMATION") {
      // pending은 오류가 아니다 - 확신이 낮을 때 사용자가 확인/수정하는 화면으로 넘긴다.
      setDraftItems(serverItems);
      setDraftConfidence(status.confidence ?? null);
      return;
    }

    if (status.status === "FAILED") {
      setAnalysisError("사진 분석에 실패했어요. 다른 사진으로 다시 시도해 주세요.");
      return;
    }

    if (status.status === "COMPLETED" && serverItems.length > 0) {
      const analyzedSugar = serverItems.reduce((sum, item) => sum + Number(item.dang ?? 0), 0);
      const analyzedCalories = serverItems.reduce((sum, item) => sum + Number(item.calo ?? 0), 0);
      setSelected({
        id: `vision-${registeredId}`,
        name: serverItems.map((item) => item.name).filter(Boolean).join(", ") || "사진으로 분석한 식단",
        kind: "사진 분석",
        category: "사진으로 계산",
        sugar: roundSugar(analyzedSugar),
        calories: Math.round(analyzedCalories),
        note: "AI가 사진에서 인식한 결과예요. 양을 조절하면 다시 계산할 수 있어요.",
        href: "/diet",
        nutritionAvailable: true,
      });
      return;
    }

    // 60초 넘게 폴링해도 여전히 PENDING/PROCESSING인 경우 - worker가 느릴 뿐 오류는 아니다.
    setSelected({
      id: `vision-${registeredId}`,
      name: "사진 분석을 기다리고 있어요",
      kind: "사진 분석",
      category: "사진으로 계산",
      sugar: 0,
      calories: 0,
      note: "사진은 서버에 등록했어요. 분석이 끝나면 실제 영양정보로 표시할게요.",
      href: "/diet",
      nutritionAvailable: false,
    });
  }

  function removeDraftItem(index: number) {
    setDraftItems((current) => (current ? current.filter((_, i) => i !== index) : current));
  }

  async function confirmDraft() {
    if (!draftItems || !serverMealLogId) return;
    const token = getAccessToken();
    if (!token) {
      setLoginPrompt(true);
      return;
    }
    setConfirmState("confirming");
    try {
      await confirmDietPhoto(
        token,
        serverMealLogId,
        draftItems.map((item) => ({ name: item.name, sugar: Number(item.dang ?? 0), calories: Number(item.calo ?? 0) })),
      );
      const analyzedSugar = draftItems.reduce((sum, item) => sum + Number(item.dang ?? 0), 0);
      const analyzedCalories = draftItems.reduce((sum, item) => sum + Number(item.calo ?? 0), 0);
      setSelected({
        id: `vision-${serverMealLogId}`,
        name: draftItems.map((item) => item.name).filter(Boolean).join(", ") || "사진으로 분석한 식단",
        kind: "사진 분석",
        category: "사진으로 계산",
        sugar: roundSugar(analyzedSugar),
        calories: Math.round(analyzedCalories),
        note: "확인한 내용으로 저장했어요.",
        href: "/diet",
        nutritionAvailable: true,
      });
      setDraftItems(null);
      setDraftConfidence(null);
      setConfirmState("idle");
    } catch {
      setConfirmState("error");
    }
  }

  function selectPhoto(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setFileError("");
    setAnalysisError("");
    if (!acceptedImageTypes.has(file.type)) {
      setFileError("JPG, PNG, WEBP 형식의 사진을 선택해 주세요.");
      event.target.value = "";
      return;
    }
    if (file.size > maxImageBytes) {
      setFileError("사진 크기는 10MB 이하로 선택해 주세요.");
      event.target.value = "";
      return;
    }
    if (photoPreview) URL.revokeObjectURL(photoPreview);
    setPhotoFile(file);
    setPhotoPreview(URL.createObjectURL(file));
  }

  function resetPhoto() {
    if (photoPreview) URL.revokeObjectURL(photoPreview);
    setPhotoFile(null);
    setPhotoPreview(null);
    setFileError("");
    setAnalysisError("");
    setUploadProgress(0);
    setServerMealLogId(null);
    if (photoInput.current) photoInput.current.value = "";
  }

  async function saveItem() {
    if (!selected) return;
    if (!authReady || !signedIn) {
      setLoginPrompt(true);
      return;
    }
    setSaveState("saving");

    // 레시피/식품은 이번에 실제 서버에 저장한다(RC-0113). 사진은 analyzePhoto()/
    // confirmDraft()에서 이미 /diet/upload(+필요시 confirm)로 서버에 저장이 끝난
    // 상태라 다시 만들지 않고, 캘린더 서버 병합과 같은 id로 로컬에 낙관적으로만 반영한다.
    if (selected.kind === "레시피" || selected.kind === "식품") {
      try {
        const itemId = selected.id.replace(/^(recipe|product)-/, "");
        const record = await addServerRecord(recordDate, {
          meal,
          itemType: selected.kind === "레시피" ? "recipe" : "product",
          itemId,
          sugar: selected.sugar,
          calories: selected.calories,
          name: selected.name,
          category: selected.category,
          note: selected.note,
          href: selected.href,
        });
        onSaved?.(recordDate, record);
        setSaveState("saved");
        window.setTimeout(onClose, 720);
      } catch {
        setSaveState("error");
      }
      return;
    }

    const isServerPhoto = selected.kind === "사진 분석" && serverMealLogId;
    const record: DietRecord = {
      id: isServerPhoto ? `server-${serverMealLogId}` : `${selected.id}-${Date.now()}`,
      meal,
      name: selected.name,
      sugar: selected.sugar,
      calories: selected.calories,
      kind: selected.kind,
      category: selected.category,
      note: selected.note,
      href: selected.href,
      source: isServerPhoto ? "server" : "local",
    };
    try {
      addRecord(recordDate, record);
      onSaved?.(recordDate, record);
      setSaveState("saved");
      window.setTimeout(onClose, 720);
    } catch {
      setSaveState("error");
    }
  }

  const nextMeal = meals[Math.min(meals.indexOf(meal) + 1, meals.length - 1)];

  return (
    <>
    <div className="meal-panel-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="meal-entry-panel" role="dialog" aria-modal="true" aria-label={`${meal} 기록 추가`} onMouseDown={(event) => event.stopPropagation()}>
        <header className="meal-entry-head">
          <div>
            {selected && <button type="button" className="panel-back" onClick={() => setSelected(null)}>← 이전</button>}
            <p className="eyebrow">{meal}에 담기</p>
            <h2>{selected ? selected.name : "어떤 방식으로 기록할까요?"}</h2>
          </div>
          <button ref={closeButton} type="button" className="panel-close" onClick={onClose} aria-label="닫기">×</button>
        </header>

        <RecordDateNavigator value={recordDate} onChange={(date) => { setRecordDate(date); setSelected(null); }} min={minDate} max={maxDate} />

        {draftItems ? (
          <div className="vision-draft">
            <p className="eyebrow">사진 인식 확신이 낮아요</p>
            <h3>인식된 음식을 확인하고 필요하면 지워주세요</h3>
            {draftConfidence != null && <small>인식 확신도 {Math.round(draftConfidence * 100)}%</small>}
            {confirmState === "error" && <p className="vision-file-error" role="alert">확정하지 못했어요. 다시 시도해 주세요.</p>}
            {draftItems.length === 0 ? (
              <p className="entry-data-state">인식된 음식이 없어요. 다른 사진으로 다시 시도해 주세요.</p>
            ) : (
              <ul className="vision-draft-list">
                {draftItems.map((item, index) => (
                  <li key={`${item.name}-${index}`}>
                    <span>{item.name}</span>
                    <small>당류 {item.dang ?? 0}g · {item.calo ?? 0}kcal</small>
                    <button type="button" onClick={() => removeDraftItem(index)} aria-label={`${item.name} 지우기`}>×</button>
                  </li>
                ))}
              </ul>
            )}
            <footer className="mini-detail-actions">
              <button type="button" onClick={() => { setDraftItems(null); setDraftConfidence(null); resetPhoto(); }}>다른 사진으로 다시 시도</button>
              <button
                type="button"
                className="solid-button"
                onClick={confirmDraft}
                disabled={draftItems.length === 0 || confirmState === "confirming"}
              >
                {confirmState === "confirming" ? "저장하고 있어요" : "확인하고 저장하기"}
              </button>
            </footer>
          </div>
        ) : !selected ? (
          <>
            <div className="entry-source-tabs">{sourceTabs.map((tab) => <button type="button" className={source === tab.id ? "is-active" : ""} key={tab.id} onClick={() => { setSource(tab.id); setCategory("전체"); }}>{tab.label}</button>)}</div>
            {source === "photo" ? (
              isAnalyzing ? (
                <div className="vision-loading" role="status" aria-live="polite">
                  <div className="vision-spinner" aria-hidden="true"><i /></div>
                  <h3>{uploadProgress < 55 ? "사진을 안전하게 올리고 있어요" : "사진에서 음식을 찾고 있어요"}</h3>
                  <p>{uploadProgress < 55 ? "창을 닫지 않고 잠시만 기다려 주세요." : "음식의 종류와 양을 확인한 뒤 당류와 칼로리를 계산할게요."}</p>
                  <div className="upload-progress" aria-label={`업로드 ${uploadProgress}%`}><i style={{ transform: `scaleX(${uploadProgress / 100})` }} /></div>
                  <ol><li className="is-done">사진을 확인했어요</li><li className="is-active">음식과 양을 찾고 있어요</li><li>영양 수치를 계산할게요</li></ol>
                </div>
              ) : analysisError ? (
                <div className="vision-error" role="alert"><span aria-hidden="true" /><h3>사진을 분석하지 못했어요.</h3><p>{analysisError}</p><div><button type="button" onClick={resetPhoto}>다른 사진 고르기</button><button type="button" className="solid-button" onClick={analyzePhoto}>다시 분석하기</button></div></div>
              ) : (
                <div className="vision-upload">
                  <input ref={photoInput} className="vision-file-input" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={selectPhoto} />
                  {photoPreview ? <div className="vision-photo-preview"><img src={photoPreview} alt="선택한 음식 사진 미리보기" /><div><button type="button" onClick={() => photoInput.current?.click()}>바꾸기</button><button type="button" onClick={resetPhoto}>지우기</button></div></div> : <div className="camera-mark" aria-hidden="true">⌁</div>}
                  <h3>음식이나 제품 사진을 올려주세요</h3>
                  <p>{photoFile ? `${photoFile.name}을 선택했어요.` : "사진을 올리면 음식의 양을 확인하고 당류와 칼로리를 계산해요."}</p>
                  <small>JPG, PNG, WEBP · 최대 10MB</small>
                  {fileError && <p className="vision-file-error" role="alert">{fileError}</p>}
                  <button type="button" className="solid-button" onClick={analyzePhoto}>{photoFile ? "당류·칼로리 확인하기" : "사진 선택하기"}</button>
                </div>
              )
            ) : (
              <div className="entry-browser">
                <div className="entry-search"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={source === "recipe" ? "음식이나 레시피 검색" : source === "product" ? "제품명이나 브랜드 검색" : "즐겨찾기 검색"} /><span>⌕</span></div>
                <div className="entry-categories">{categories.map((item) => <button type="button" className={category === item ? "is-active" : ""} onClick={() => setCategory(item)} key={item}>{item}</button>)}</div>
                {selectionError && <p className="entry-data-state is-error" role="alert">{selectionError}</p>}
                {(source === "recipe" && recipeCatalog.loading) || (source === "product" && productCatalog.status === "loading") ? <p className="entry-data-state" role="status">목록을 불러오고 있어요.</p> : filtered.length === 0 ? <p className="entry-data-state">조건에 맞는 항목이 없어요. 검색어나 카테고리를 바꿔보세요.</p> : <div className="entry-result-grid">{filtered.map((item) => <button type="button" className="entry-result" key={item.id} onClick={() => void selectLibraryItem(item)} disabled={resolvingItemId === item.id}><span>{item.category}</span><h3>{item.name}</h3><p>{item.note}</p><small>{resolvingItemId === item.id ? "영양정보를 불러오고 있어요" : item.nutritionAvailable ? `당류 ${item.sugar}g · ${item.calories}kcal` : "누르면 영양정보를 불러와요"}</small>{item.favorite && <i aria-label="즐겨찾기">♥</i>}</button>)}</div>}
              </div>
            )}
          </>
        ) : (
          <div className="mini-detail">
            <div className="mini-detail-summary">
              <div className="mini-food-art"><span>{selected.category}</span><strong>{selected.kind}</strong></div>
              <div><small>{selected.kind}</small><h3>{selected.name}</h3><p>{selected.note}</p><Link href={selected.href}>영양 정보 더 보기 →</Link></div>
            </div>
            {selected.nutritionAvailable ? <div className="projected-change">
              <p className="eyebrow">담으면 이렇게 바뀌어요</p>
              <div className="projected-row"><div><span>선택한 날 당류</span><strong>{sugarText(totals.sugar)}g → {sugarText(totals.sugar + selected.sugar)}g</strong></div><div className="projected-bar"><i style={{ clipPath: `inset(0 ${100 - percent(totals.sugar + selected.sugar, goals.sugar)}% 0 0)` }} /></div><p>{totals.sugar + selected.sugar <= goals.sugar ? `설정한 목표까지 ${sugarText(goals.sugar - totals.sugar - selected.sugar)}g 남아요.` : `설정한 목표보다 ${sugarText(totals.sugar + selected.sugar - goals.sugar)}g 높아져요.`}</p></div>
              <div className="projected-row calorie"><div><span>선택한 날 칼로리</span><strong>{totals.calories.toLocaleString()} → {(totals.calories + selected.calories).toLocaleString()}kcal</strong></div><div className="projected-bar"><i style={{ clipPath: `inset(0 ${100 - percent(totals.calories + selected.calories, goals.calories)}% 0 0)` }} /></div><p>설정한 하루 목표 {goals.calories.toLocaleString()}kcal와 함께 계산했어요.</p></div>
            </div> : <div className="projected-change"><p className="eyebrow">분석 대기 중</p><p>아직 영양 수치를 계산하지 않았어요. 완료되면 캘린더와 오늘 기록에 반영돼요.</p></div>}
            <footer className={`mini-detail-actions save-${saveState}`}><p>{saveState === "saved" ? "기록을 저장했어요." : saveState === "error" ? "저장하지 못했어요. 다시 시도해 주세요." : selected.kind === "사진 분석" && serverMealLogId ? "서버에 등록한 사진을 선택한 식사에 표시해둘게요." : <>저장한 다음에는 <b>{nextMeal}</b> 기록을 이어볼 수 있어요.</>}</p><button type="button" className="solid-button" onClick={saveItem} disabled={saveState === "saving" || saveState === "saved"}>{saveState === "saving" ? "저장하고 있어요" : saveState === "saved" ? "저장했어요" : saveState === "error" ? "다시 저장하기" : selected.kind === "사진 분석" && serverMealLogId ? "사진 등록 마치기" : `${meal}에 저장하기`}</button></footer>
          </div>
        )}
      </section>
    </div>
    {loginPrompt && <LoginPromptDialog onClose={() => setLoginPrompt(false)} />}
    </>
  );
}

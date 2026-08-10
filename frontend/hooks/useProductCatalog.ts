"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { products as mockProducts, type ProductData } from "@/data/catalog";
import { PRODUCT_CATEGORIES, SWEETENER_FILTERS, type ProductCategory } from "@/data/taxonomy";
import { useUserSettings } from "@/hooks/useUserSettings";
import {
  searchProducts,
  type ProductSearchItem,
} from "@/lib/api/zerocheck";

const PAGE_SIZE = 20;

function productCategory(value?: string | null, fallback?: ProductCategory): ProductCategory {
  const matched = PRODUCT_CATEGORIES.find((item) => item.label === value);
  return matched?.label ?? fallback ?? "가공식품";
}

function toProductCard(item: ProductSearchItem): ProductData {
  const fallback = mockProducts.find((product) => product.backendId === item.id);
  const brand = item.brand || item.desc || fallback?.brand || "";
  const nutritionAvailable = item.sugar != null && item.calories != null;
  const sweeteners = (item.tags ?? []).filter((tag) =>
    SWEETENER_FILTERS.some((filter) => tag.includes(filter) || filter.includes(tag)),
  );

  return {
    backendId: item.id,
    slug: item.id,
    foodCode: fallback?.foodCode ?? item.id.slice(0, 13).toUpperCase(),
    title: item.name || fallback?.title || "상품 이름 준비 중",
    brand,
    maker: fallback?.maker ?? brand,
    category: productCategory(item.category, fallback?.category),
    serving: item.serving ?? fallback?.serving ?? "제품 표시량",
    calories: item.calories ?? fallback?.calories ?? 0,
    sugar: item.sugar ?? fallback?.sugar ?? 0,
    protein: fallback?.protein ?? 0,
    fat: fallback?.fat ?? 0,
    carbs: fallback?.carbs ?? 0,
    ingredients: fallback?.ingredients ?? [],
    sweeteners: sweeteners.length > 0 ? sweeteners : fallback?.sweeteners ?? [],
    image: item.image || item.url || fallback?.image || "",
    summary: fallback?.summary ?? `${brand}의 영양정보와 원재료는 상세에서 확인할 수 있어요.`,
    savedDemo: fallback?.savedDemo ?? 0,
    nutritionAvailable,
  };
}

async function loadProductPage(values: { query?: string; category?: string; warning?: string; sort?: string; page: number }) {
  const timeout = new Promise<never>((_, reject) => {
    window.setTimeout(() => reject(new Error("PRODUCT_CATALOG_MOCK_FALLBACK")), 3500);
  });
  const response = await Promise.race([searchProducts(values), timeout]);
  const cards = response.items.map(toProductCard);
  return {
    cards,
    hasMore: response.hasNext ?? response.items.length === PAGE_SIZE,
    total: response.total ?? response.items.length,
  };
}

export function useProductCatalog(values: { query?: string; category?: string; sort?: string }) {
  const { profile } = useUserSettings();
  const [items, setItems] = useState<ProductData[]>([]);
  const [status, setStatus] = useState<"loading" | "api" | "mock">("loading");
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [revision, setRevision] = useState(0);
  const warning = (profile.allergenCodes ?? []).join(",") || undefined;
  const requestValues = { ...values, warning };
  const requestKey = `${values.query ?? ""}|${values.category ?? ""}|${warning ?? ""}|${values.sort ?? "rank"}|${revision}`;
  const activeKey = useRef(requestKey);

  useEffect(() => {
    let active = true;
    activeKey.current = requestKey;
    setStatus("loading");
    setPage(1);
    setHasMore(false);

    const timeout = window.setTimeout(() => {
      loadProductPage({ ...requestValues, page: 1 })
        .then(({ cards, hasMore: nextHasMore, total: nextTotal }) => {
          if (!active) return;
          setItems(cards);
          setHasMore(nextHasMore);
          setTotal(nextTotal);
          setStatus("api");
        })
        .catch(() => {
          if (!active) return;
          setItems(mockProducts);
          setTotal(mockProducts.length);
          setHasMore(false);
          setStatus("mock");
        });
    }, 220);

    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [requestKey]);

  const loadMore = useCallback(() => {
    if (!hasMore || loadingMore || status !== "api") return;
    const nextPage = page + 1;
    const keyAtStart = activeKey.current;
    setLoadingMore(true);
    loadProductPage({ ...requestValues, page: nextPage })
      .then(({ cards, hasMore: nextHasMore, total: nextTotal }) => {
        if (activeKey.current !== keyAtStart) return;
        setItems((current) => {
          const known = new Set(current.map((item) => item.backendId));
          return [...current, ...cards.filter((item) => !known.has(item.backendId))];
        });
        setPage(nextPage);
        setHasMore(nextHasMore);
        setTotal(nextTotal);
      })
      .catch(() => setHasMore(false))
      .finally(() => setLoadingMore(false));
  }, [hasMore, loadingMore, page, requestKey, status]);

  const retry = useCallback(() => setRevision((current) => current + 1), []);
  return { products: items, status, total, hasMore, loadingMore, loadMore, retry };
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { products as mockProducts, type ProductData } from "@/data/catalog";
import { PRODUCT_CATEGORIES, type ProductCategory } from "@/data/taxonomy";
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
  const brand = item.desc || fallback?.brand || "브랜드 정보 준비 중";

  return {
    backendId: item.id,
    slug: item.id,
    foodCode: fallback?.foodCode ?? item.id.slice(0, 13).toUpperCase(),
    title: item.name || fallback?.title || "상품 이름 준비 중",
    brand,
    maker: fallback?.maker ?? brand,
    category: productCategory(undefined, fallback?.category),
    serving: fallback?.serving ?? "100g",
    calories: fallback?.calories ?? 0,
    sugar: fallback?.sugar ?? 0,
    protein: fallback?.protein ?? 0,
    fat: fallback?.fat ?? 0,
    carbs: fallback?.carbs ?? 0,
    ingredients: fallback?.ingredients ?? [],
    sweeteners: fallback?.sweeteners ?? [],
    image: item.url || fallback?.image || "",
    summary: fallback?.summary ?? `${brand}의 영양정보와 원재료는 상세에서 확인할 수 있어요.`,
    savedDemo: fallback?.savedDemo ?? 0,
    nutritionAvailable: Boolean(fallback),
  };
}

async function loadProductPage(values: { query?: string; category?: string; sort?: string; page: number }) {
  const response = await searchProducts(values);
  const cards = response.items.map(toProductCard);
  return { cards, hasMore: response.items.length === PAGE_SIZE };
}

export function useProductCatalog(values: { query?: string; category?: string; sort?: string }) {
  const [items, setItems] = useState<ProductData[]>([]);
  const [status, setStatus] = useState<"loading" | "api" | "mock">("loading");
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [revision, setRevision] = useState(0);
  const requestKey = `${values.query ?? ""}|${values.category ?? ""}|${values.sort ?? "rank"}|${revision}`;
  const activeKey = useRef(requestKey);

  useEffect(() => {
    let active = true;
    activeKey.current = requestKey;
    setStatus("loading");
    setPage(1);
    setHasMore(false);

    const timeout = window.setTimeout(() => {
      loadProductPage({ ...values, page: 1 })
        .then(({ cards, hasMore: nextHasMore }) => {
          if (!active) return;
          setItems(cards);
          setHasMore(nextHasMore);
          setStatus("api");
        })
        .catch(() => {
          if (!active) return;
          setItems(mockProducts);
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
    loadProductPage({ ...values, page: nextPage })
      .then(({ cards, hasMore: nextHasMore }) => {
        if (activeKey.current !== keyAtStart) return;
        setItems((current) => {
          const known = new Set(current.map((item) => item.backendId));
          return [...current, ...cards.filter((item) => !known.has(item.backendId))];
        });
        setPage(nextPage);
        setHasMore(nextHasMore);
      })
      .catch(() => setHasMore(false))
      .finally(() => setLoadingMore(false));
  }, [hasMore, loadingMore, page, requestKey, status]);

  const retry = useCallback(() => setRevision((current) => current + 1), []);
  return { products: items, status, hasMore, loadingMore, loadMore, retry };
}

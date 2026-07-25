"use client";

import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { SafeImage } from "@/components/SafeImage";
import { useAuthSession } from "@/hooks/useAuthSession";
import { getProductFavorites, getRecipeFavorites } from "@/lib/api/zerocheck";

type SavedMenu = {
  id: string;
  title: string;
  kind: "레시피" | "저당픽";
  href: string;
  image?: string | null;
};

type SavedMenuFilter = "all" | "recipe" | "product";

const FAVORITES_CHANGED_EVENT = "dangdang:favorites-changed";

export function SavedMenuDrawer() {
  const { ready, signedIn, token } = useAuthSession();
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState<SavedMenuFilter>("all");
  const [loading, setLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [items, setItems] = useState<SavedMenu[]>([]);
  const drawerRef = useRef<HTMLElement>(null);
  const panelId = useId();

  const loadFavorites = useCallback(async () => {
    if (!signedIn || !token) {
      setItems([]);
      setLoadFailed(false);
      return;
    }

    setLoading(true);
    setLoadFailed(false);
    const [recipes, products] = await Promise.allSettled([
      getRecipeFavorites(token),
      getProductFavorites(token),
    ]);

    const nextItems: SavedMenu[] = [];
    if (recipes.status === "fulfilled") {
      nextItems.push(...recipes.value["list-receipe"].map((item) => ({
        id: `recipe-${item.id}`,
        title: item.name,
        kind: "레시피" as const,
        href: `/recipes/${item.id}`,
        image: item.image,
      })));
    }
    if (products.status === "fulfilled") {
      nextItems.push(...products.value["list-products"].map((item) => ({
        id: `product-${item.id}`,
        title: item.name,
        kind: "저당픽" as const,
        href: `/product/${item.id}`,
        image: item.image,
      })));
    }

    setItems(nextItems);
    setLoadFailed(recipes.status === "rejected" && products.status === "rejected");
    setLoading(false);
  }, [signedIn, token]);

  useEffect(() => {
    if (ready) void loadFavorites();
  }, [loadFavorites, ready]);

  useEffect(() => {
    const refresh = () => void loadFavorites();
    window.addEventListener(FAVORITES_CHANGED_EVENT, refresh);
    return () => window.removeEventListener(FAVORITES_CHANGED_EVENT, refresh);
  }, [loadFavorites]);

  useEffect(() => {
    if (!open) return;

    function closeOnOutside(event: PointerEvent) {
      if (drawerRef.current && !drawerRef.current.contains(event.target as Node)) setOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("pointerdown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const filteredItems = items.filter((item) => {
    if (filter === "all") return true;
    return filter === "recipe" ? item.kind === "레시피" : item.kind === "저당픽";
  });

  return (
    <aside ref={drawerRef} className={`saved-menu-drawer ${open ? "is-open" : ""}`} aria-label="찜한 메뉴">
      <section id={panelId} className="saved-menu-panel" aria-hidden={!open}>
        <header>
          <div><p>나의 보관함</p><h2>찜한 메뉴</h2></div>
          <button type="button" onClick={() => setOpen(false)} aria-label="찜한 메뉴 닫기">×</button>
        </header>

        <div className="saved-menu-content" aria-live="polite">
          {!ready || loading ? (
            <div className="saved-menu-state"><i /><p>찜한 메뉴를 불러오고 있어요.</p></div>
          ) : !signedIn ? (
            <div className="saved-menu-state">
              <span aria-hidden="true">♥</span>
              <h3>마음에 든 메뉴를 모아보세요</h3>
              <p>로그인하면 저장한 레시피와 저당픽을 어디서든 바로 열 수 있어요.</p>
              <Link href="/login" onClick={() => setOpen(false)}>로그인하기</Link>
            </div>
          ) : loadFailed ? (
            <div className="saved-menu-state">
              <span aria-hidden="true">↻</span>
              <h3>목록을 불러오지 못했어요</h3>
              <p>잠시 후 다시 확인해 주세요.</p>
              <button type="button" onClick={() => void loadFavorites()}>다시 불러오기</button>
            </div>
          ) : items.length === 0 ? (
            <div className="saved-menu-state">
              <span aria-hidden="true">♡</span>
              <h3>아직 찜한 메뉴가 없어요</h3>
              <p>레시피와 저당픽의 하트를 누르면 여기에 모여요.</p>
              <Link href="/recipes" onClick={() => setOpen(false)}>메뉴 둘러보기</Link>
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="saved-menu-state">
              <span aria-hidden="true">♡</span>
              <h3>찜한 {filter === "recipe" ? "레시피" : "저당픽"}이 없어요</h3>
              <button type="button" onClick={() => setFilter("all")}>전체 보기</button>
            </div>
          ) : (
            <ul className="saved-menu-list">
              {filteredItems.map((item) => (
                <li key={item.id}>
                  <Link href={item.href} onClick={() => setOpen(false)}>
                    <span className={`saved-menu-thumb is-${item.kind === "레시피" ? "recipe" : "product"}`}>
                      {item.image ? <SafeImage src={item.image} alt="" fallbackLabel={item.kind} /> : <i aria-hidden="true">{item.kind === "레시피" ? "🥗" : "🛒"}</i>}
                    </span>
                    <span><small>{item.kind}</small><strong>{item.title}</strong></span>
                    <b aria-hidden="true">›</b>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>

        {ready && signedIn && items.length > 0 && <footer aria-label="찜한 메뉴 필터">
          <button
            type="button"
            className={filter === "all" ? "is-active" : ""}
            aria-pressed={filter === "all"}
            onClick={() => setFilter("all")}
          >
            전체
          </button>
          <button
            type="button"
            className={filter === "recipe" ? "is-active" : ""}
            aria-pressed={filter === "recipe"}
            onClick={() => setFilter("recipe")}
          >
            레시피
          </button>
          <button
            type="button"
            className={filter === "product" ? "is-active" : ""}
            aria-pressed={filter === "product"}
            onClick={() => setFilter("product")}
          >
            저당픽
          </button>
        </footer>}
      </section>

      {!open && (
        <button
          type="button"
          className="saved-menu-toggle"
          aria-expanded="false"
          aria-controls={panelId}
          aria-label="찜한 메뉴 열기"
          onClick={() => {
            setFilter("all");
            setOpen(true);
          }}
        >
          <span aria-hidden="true">♥</span>
          {items.length > 0 && <b>{items.length}</b>}
        </button>
      )}
    </aside>
  );
}

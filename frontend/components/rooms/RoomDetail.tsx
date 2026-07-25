"use client";

import type { CSSProperties } from "react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { SafeImage } from "@/components/SafeImage";
import styles from "@/components/rooms/Rooms.module.css";
import { badges, mealPhotos, members, rooms } from "@/components/rooms/roomData";
import { useAuthSession } from "@/hooks/useAuthSession";

type RoomTab = "today" | "status" | "members";
type TodayView = "전체" | "아침" | "점심" | "저녁" | "간식";

const tabs: { id: RoomTab; label: string }[] = [
  { id: "today", label: "오늘" },
  { id: "status", label: "현황" },
  { id: "members", label: "멤버" },
];

const mealSlots = [
  { label: "아침", symbol: "☀" },
  { label: "점심", symbol: "◐" },
  { label: "저녁", symbol: "☾" },
  { label: "간식", symbol: "●" },
] as const;

const todayViews: TodayView[] = ["전체", "아침", "점심", "저녁", "간식"];
const galleryPhotos = [
  { image: "https://recipe1.ezmember.co.kr/cache/recipe/2026/06/16/9b85be24c05057a56f46e19079e6ca8a1.jpg", name: "아침 샐러드" },
  { image: "https://recipe1.ezmember.co.kr/cache/recipe/2026/05/26/5a04f882582fc89a3742cde65c036b5e1.jpg", name: "채소 한 접시" },
  { image: "https://recipe1.ezmember.co.kr/cache/recipe/2026/05/18/783e4c4c7ce0b194b23d638bf43d51c31.png?w=1000", name: "당근 케이크" },
  { image: "https://recipe1.ezmember.co.kr/cache/recipe/2026/04/14/55c3f4357e7622a1ac1145b0301cbc851.jpg?w=1000", name: "애호박 덮밥" },
  { image: "https://recipe1.ezmember.co.kr/cache/recipe/2026/02/14/1f4b9c5910db525344f5b7c2e04a92611.jpg", name: "현미 채소밥" },
  { image: "https://recipe1.ezmember.co.kr/cache/recipe/2025/05/06/776b468aaef45abbed920ad5e89e6c851.jpg", name: "두부 한 끼" },
  { image: "https://recipe1.ezmember.co.kr/cache/recipe/2025/05/06/1fa6acb9629d1dcec832c9257a8b013b1.jpg", name: "닭가슴살 채소구이" },
  { image: "https://recipe1.ezmember.co.kr/cache/recipe/2025/04/30/dc6835b54d468673680f18134d03db071.jpg", name: "메밀 샐러드" },
] as const;
const missingMeals: Record<Exclude<TodayView, "전체">, number[]> = {
  아침: [5],
  점심: [4],
  저녁: [3, 5],
  간식: [4, 5],
};

function isMealMissing(meal: Exclude<TodayView, "전체">, memberIndex: number) {
  return missingMeals[meal].includes(memberIndex);
}

function getGalleryRecord(meal: Exclude<TodayView, "전체">, memberIndex: number) {
  const member = members[memberIndex];
  const existing = mealPhotos.find((item) => item.member === member.name && item.meal === meal);
  if (existing) return existing;

  const mealIndex = mealSlots.findIndex((slot) => slot.label === meal);
  const recipe = galleryPhotos[(mealIndex * members.length + memberIndex) % galleryPhotos.length];
  const recipeName = recipe.name;

  return {
    id: `mock-${meal}-${member.name}`,
    member: member.name,
    avatar: member.avatar,
    meal,
    name: recipeName,
    tags: [meal, "오늘기록"],
    sugar: Number((5.4 + ((memberIndex + mealIndex) % 7) * 1.2).toFixed(1)),
    calories: 210 + ((memberIndex + mealIndex) % 6) * 48,
    image: recipe.image,
    photoCount: 1 + ((memberIndex + mealIndex) % 3),
    coverSource: "사진으로 남긴 식사",
    reactions: 2 + ((memberIndex * 2 + mealIndex) % 8),
    items: [
      { source: "사진", name: `${meal} 사진` },
      { source: "레시피", name: recipeName },
      { source: "저당픽", name: memberIndex % 2 === 0 ? "무가당 요거트" : "현미밥" },
    ],
  };
}

type GalleryMeal = ReturnType<typeof getGalleryRecord>;

function getGallerySlides(meal: GalleryMeal) {
  const startIndex = Math.max(0, galleryPhotos.findIndex((photo) => photo.image === meal.image));
  return Array.from({ length: meal.photoCount }, (_, index) => (
    index === 0
      ? { image: meal.image, name: meal.name }
      : galleryPhotos[(startIndex + index) % galleryPhotos.length]
  ));
}

function getCurrentMealView(): Exclude<TodayView, "전체"> {
  const hour = new Date().getHours();
  if (hour < 11) return "아침";
  if (hour < 15) return "점심";
  if (hour < 18) return "간식";
  return "저녁";
}

export function RoomDetail({ roomId }: { roomId: string }) {
  const { ready: authReady, signedIn } = useAuthSession();
  const room = rooms.find((item) => item.id === roomId);
  const roomMembers = room ? members.slice(0, Math.min(room.members, members.length)) : [];
  const memberColumns = Math.max(1, Math.min(3, roomMembers.length));
  const [tab, setTab] = useState<RoomTab>("today");
  const [todayView, setTodayView] = useState<TodayView>("전체");
  const [toast, setToast] = useState("");
  const [replies, setReplies] = useState<Record<string, string>>({});
  const [openReplyId, setOpenReplyId] = useState<string | null>(null);
  const [photoIndexes, setPhotoIndexes] = useState<Record<string, number>>({});
  const [reactionCounts, setReactionCounts] = useState<Record<string, number>>({});
  const [reportMeal, setReportMeal] = useState<{ id: string; member: string } | null>(null);
  const [reportReason, setReportReason] = useState("");
  const [comments, setComments] = useState<Record<string, string[]>>({
    "meal-minji": ["준호 · 색 조합부터 맛있어 보여요"],
    "meal-junho": ["민지 · 아침 챙긴 것부터 성공 👏"],
  });

  const tabsRef = useRef<HTMLElement>(null);
  const didInitialScroll = useRef(false);

  useEffect(() => {
    setTodayView(getCurrentMealView());
  }, []);

  // 방에 처음 들어오면 방 헤더를 지나 탭(오늘/현황/멤버) 지점으로 스크롤을
  // 맞춰, 셋로그처럼 식탁 피드가 바로 보이게 한다. 탭은 sticky라 상단 글로벌
  // 내비 바로 아래에 붙는다(모바일 62px / 데스크톱 72px).
  useEffect(() => {
    if (didInitialScroll.current) return;
    if (!authReady || !signedIn) return;
    const el = tabsRef.current;
    if (!el) return;
    didInitialScroll.current = true;
    const stickyNavOffset = window.matchMedia("(max-width: 700px)").matches ? 62 : 72;
    const top = el.getBoundingClientRect().top + window.scrollY - stickyNavOffset;
    window.scrollTo({ top: Math.max(0, top), behavior: "auto" });
  }, [authReady, signedIn]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (!reportMeal) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setReportMeal(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [reportMeal]);

  if (!authReady) {
    return (
      <main className={styles.page}>
        <div className={styles.wrap}>
          <section className={styles.authGate} aria-label="얌로그 확인 중">
            <span aria-hidden="true" />
          </section>
        </div>
      </main>
    );
  }

  if (!signedIn) {
    return (
      <main className={styles.page}>
        <div className={styles.wrap}>
          <section className={styles.authGate}>
            <div className={styles.authGateSymbol} aria-hidden="true">
              <svg viewBox="0 0 32 32"><circle cx="11" cy="12" r="4" /><circle cx="21" cy="12" r="4" /><path d="M5 27c.7-5.4 2.8-8.1 6-8.1s5.3 2.7 6 8.1" /><path d="M15 27c.7-5.4 2.8-8.1 6-8.1s5.3 2.7 6 8.1" /></svg>
            </div>
            <p className={styles.eyebrow}>얌로그</p>
            <h1>로그인하면<br />우리 모임 식탁을 볼 수 있어요.</h1>
            <p>친구들이 남긴 오늘의 식사와 콕 찌르기를 확인해요.</p>
            <div className={styles.authGateActions}>
              <Link className={styles.primaryButton} href="/login">로그인하기</Link>
              <Link className={styles.secondaryButton} href="/signup">회원가입하기</Link>
            </div>
          </section>
        </div>
      </main>
    );
  }

  if (!room) {
    return (
      <main className={styles.page}>
        <div className={styles.wrap}>
          <section className={styles.roomNotFound}>
            <span aria-hidden="true">🍽️</span>
            <h1>모임을 찾을 수 없어요</h1>
            <p>초대 링크가 만료됐거나 참여가 끝난 모임일 수 있어요.</p>
            <Link className={styles.primaryButton} href="/rooms">내 모임으로 돌아가기</Link>
          </section>
        </div>
      </main>
    );
  }

  const inviteCode = room.inviteCode;

  function copyInvite() {
    const inviteLink = `${window.location.origin}/rooms/join?code=${inviteCode}`;
    void navigator.clipboard.writeText(inviteLink)
      .then(() => setToast("초대 링크를 복사했어요."))
      .catch(() => setToast(`초대 코드 ${inviteCode}를 복사해주세요.`));
  }

  function sendReply(mealId: string) {
    const message = replies[mealId]?.trim();
    if (!message) return;
    setComments((current) => ({ ...current, [mealId]: [...(current[mealId] ?? []), `나 · ${message}`] }));
    setReplies((current) => ({ ...current, [mealId]: "" }));
    setOpenReplyId(null);
  }

  return (
    <main className={styles.page}>
      <div className={styles.wrap}>
        <header className={styles.roomHeader}>
          <div className={styles.roomIdentity}>
            <span className={styles.roomEmoji} aria-hidden="true">{room.emoji}</span>
            <div>
              <p className={styles.eyebrow}>함께 기록한 지 {room.days}일</p>
              <h1>{room.name}</h1>
              <p className={styles.roomHeaderMeta}>멤버 {room.members}명 · 오늘 {room.recordedToday}명 기록</p>
            </div>
          </div>
          <div className={styles.roomHeaderActions}>
            <button type="button" className={styles.secondaryButton} onClick={copyInvite}>초대 링크</button>
            <Link className={styles.secondaryButton} href={`/rooms/${room.id}/settings`}>모임 관리</Link>
            <Link className={styles.primaryButton} href="/">내 식단 기록</Link>
          </div>
        </header>

        <nav className={styles.roomTabs} aria-label="모임 메뉴" ref={tabsRef}>
          {tabs.map((item) => (
            <button
              type="button"
              role="tab"
              key={item.id}
              aria-selected={tab === item.id}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className={styles.tabContent}>
          {tab === "today" && (
            <section aria-labelledby="today-room-title">
              <nav className={styles.mealViewTabs} aria-label="오늘 식사 보기">
                {todayViews.map((view) => (
                  <button
                    type="button"
                    key={view}
                    aria-pressed={todayView === view}
                    onClick={() => setTodayView(view)}
                  >
                    {view}
                  </button>
                ))}
              </nav>

              {todayView === "전체" ? (
                <>
                  <header className={styles.todayHeading}>
                    <div>
                      <p className={styles.eyebrow}>오늘의 식탁</p>
                      <h2 id="today-room-title">멤버별 기록</h2>
                    </div>
                  </header>

                  <div className={styles.memberMealBoard} aria-label="멤버별 오늘 식사">
                    <div className={styles.boardHeader} aria-hidden="true">
                      <span>멤버</span>
                      {mealSlots.map((slot) => <span key={slot.label}>{slot.label}</span>)}
                    </div>
                    {roomMembers.map((member, memberIndex) => (
                      <article className={styles.memberMealRow} key={member.id} data-current={member.name === "나"}>
                        <div className={styles.boardMember}>
                          <span className={styles.avatar} style={{ background: member.color, color: "#18221b" }} aria-hidden="true">{member.avatar}</span>
                          <span><strong>{member.name}</strong>{member.name === "나" && <small>me</small>}</span>
                        </div>
                        {mealSlots.map((slot) => {
                          const record = getGalleryRecord(slot.label, memberIndex);
                          const isMissing = isMealMissing(slot.label, memberIndex);
                          return (
                            <button
                              type="button"
                              key={slot.label}
                              className={`${styles.boardMealCell} ${isMissing ? styles.boardMealEmpty : styles.boardMealFilled}`}
                              aria-label={isMissing ? `${member.name} ${slot.label} 아직 기록 없음` : `${member.name} ${slot.label} ${record.name} 보기`}
                              disabled={isMissing}
                              onClick={() => {
                                setTodayView(record.meal as Exclude<TodayView, "전체">);
                              }}
                            >
                              {isMissing ? (
                                <>
                                  <i aria-hidden="true">{slot.symbol}</i>
                                  <span>아직</span>
                                </>
                              ) : (
                                <>
                                  <SafeImage src={record.image} alt="" fallbackLabel={slot.label} />
                                  {record.photoCount > 1 && <span>+{record.photoCount - 1}</span>}
                                </>
                              )}
                            </button>
                          );
                        })}
                      </article>
                    ))}
                  </div>
                </>
              ) : (
                <section className={styles.mealMoment} aria-labelledby="today-room-title">
                  <header className={styles.mealMomentHeader}>
                    <div>
                      <p className={styles.eyebrow}>오늘의 {todayView}</p>
                      <h2 id="today-room-title">{todayView} 식탁</h2>
                    </div>
                    <Link href="/" className={styles.mealUploadButton}>＋ 내 {todayView} 올리기</Link>
                  </header>

                  <div
                    className={styles.setlogFeed}
                    style={{ "--member-columns": memberColumns } as CSSProperties}
                    data-members={roomMembers.length}
                  >
                    {roomMembers.map((member, memberIndex) => {
                      if (isMealMissing(todayView, memberIndex)) {
                        return (
                          <article className={`${styles.setlogCard} ${styles.setlogEmptyCard}`} key={`empty-${todayView}-${member.id}`}>
                            <div className={styles.setlogEmptyPhoto}>
                              <span className={styles.avatar} style={{ background: member.color, color: "#18221b" }} aria-hidden="true">{member.avatar}</span>
                              <p>아직 {todayView} 사진이 없어요</p>
                            </div>
                            <footer className={styles.setlogEmptyAction}>
                              <button type="button" onClick={() => setToast(`${member.name}님을 콕 찔렀어요.`)}>콕 찌르기</button>
                            </footer>
                          </article>
                        );
                      }

                      const meal = getGalleryRecord(todayView, memberIndex);
                        const recipeCount = meal.items.filter((item) => item.source === "레시피").length;
                        const foodCount = meal.items.filter((item) => item.source === "저당픽").length;
                        const mealSlides = getGallerySlides(meal);
                        const photoIndex = photoIndexes[meal.id] ?? 0;
                        const activeSlide = mealSlides[photoIndex];
                        return (
                          <article className={styles.setlogCard} key={meal.id}>
                            <div className={styles.setlogPhoto}>
                              <SafeImage src={activeSlide.image} alt={`${activeSlide.name} ${photoIndex + 1}번째 사진`} fallbackLabel="식단 사진" />
                              {mealSlides.length > 1 && (
                                <button
                                  type="button"
                                  className={styles.setlogGalleryOpen}
                                  onClick={() => setPhotoIndexes((current) => ({
                                    ...current,
                                    [meal.id]: ((current[meal.id] ?? 0) + 1) % mealSlides.length,
                                  }))}
                                  aria-label={`${meal.member}님의 다음 ${meal.meal} 사진 보기`}
                                >
                                  <span>다음 사진 보기</span>
                                </button>
                              )}
                              <div className={styles.setlogAuthor}>
                                <span className={styles.avatar} aria-hidden="true">{meal.avatar}</span>
                                <strong>{meal.member}</strong>
                              </div>
                              <div className={styles.setlogPhotoCount}>
                                <strong>{mealSlides.length > 1 ? `${photoIndex + 1} / ${mealSlides.length}` : "사진 1장"}</strong>
                              </div>
                              {mealSlides.length > 1 && (
                                <>
                                  <span className={styles.setlogNextHint} aria-hidden="true">›</span>
                                  <span className={styles.setlogDots} aria-hidden="true">
                                    {mealSlides.map((slide, index) => <i key={`${slide.image}-${index}`} data-active={photoIndex === index} />)}
                                  </span>
                                </>
                              )}
                              <div className={styles.setlogActions}>
                                <button type="button" onClick={() => setOpenReplyId((current) => current === meal.id ? null : meal.id)}>댓글</button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setReactionCounts((current) => ({ ...current, [meal.id]: (current[meal.id] ?? meal.reactions) + 1 }));
                                    setToast(`${meal.member}님의 식탁에 맛있겠다를 보냈어요.`);
                                  }}
                                >
                                  맛있겠다 {reactionCounts[meal.id] ?? meal.reactions}
                                </button>
                                {meal.member !== "나" && (
                                  <button
                                    type="button"
                                    aria-label={`${meal.member}님의 식사 더보기`}
                                    onClick={() => {
                                      setReportReason("");
                                      setReportMeal({ id: meal.id, member: meal.member });
                                    }}
                                  >
                                    ···
                                  </button>
                                )}
                              </div>
                              <div className={styles.setlogBubbles}>
                                {(comments[meal.id] ?? []).slice(-2).map((comment) => <p key={comment}>{comment}</p>)}
                              </div>
                              {openReplyId === meal.id && (
                                <form className={styles.setlogReply} onSubmit={(event) => { event.preventDefault(); sendReply(meal.id); }}>
                                  <input
                                    autoFocus
                                    value={replies[meal.id] ?? ""}
                                    onChange={(event) => setReplies((current) => ({ ...current, [meal.id]: event.target.value }))}
                                    placeholder="짧게 답글 남기기"
                                    aria-label={`${meal.member}님 식단에 댓글`}
                                    maxLength={160}
                                  />
                                  <button type="submit">보내기</button>
                                </form>
                              )}
                            </div>
                            <footer className={styles.setlogMeta}>
                              <div>
                                <strong>{activeSlide.name}</strong>
                                <span>{meal.coverSource}</span>
                              </div>
                              <div className={styles.sourceSummary} aria-label="한 끼 구성">
                                <span>사진 {meal.photoCount}</span>
                                {recipeCount > 0 && <span>레시피 {recipeCount}</span>}
                                {foodCount > 0 && <span>저당픽 {foodCount}</span>}
                              </div>
                            </footer>
                          </article>
                        );
                    })}
                  </div>
                </section>
              )}
            </section>
          )}

          {tab === "status" && (
            <section className={styles.statusPage} aria-labelledby="status-title">
              <header className={styles.statusLead}>
                <div>
                  <p className={styles.eyebrow}>이번 달 모임 기록</p>
                  <h2 id="status-title">우리의 식탁이 이만큼 쌓였어요</h2>
                </div>
                <div className={styles.statusLeadRate}>
                  <span>이번 달 기록</span>
                  <strong>{room.recordRate}%</strong>
                </div>
              </header>

              <div className={styles.statusStats}>
                <article><span aria-hidden="true">🌱</span><div><strong>{room.days}일</strong><small>함께 기록한 날</small></div></article>
                <article><span aria-hidden="true">🍚</span><div><strong>{room.recordedToday}명</strong><small>오늘 식사를 남긴 멤버</small></div></article>
                <article><span aria-hidden="true">🏅</span><div><strong>{room.rank ? `${room.rank}위` : "쉬는 중"}</strong><small>이번 주 모임 순위</small></div></article>
              </div>

              <div className={styles.statusCards}>
                <article className={styles.statusCard}>
                  <header><h3>이번 주 당류</h3><strong>평균 {room.averageSugar}g</strong></header>
                  <ol className={styles.statusBarList}>
                    {[...roomMembers].sort((a, b) => a.sugar - b.sugar).map((member) => (
                      <li key={member.id}>
                        <span>{member.name}</span>
                        <span className={styles.wideBar}><i style={{ width: `${Math.min(100, member.sugar * 2)}%` }} /></span>
                        <strong>{member.sugar}g</strong>
                      </li>
                    ))}
                  </ol>
                </article>

                <article className={`${styles.statusCard} ${styles.statusCardLime}`}>
                  <header><h3>이번 달 기록</h3><strong>가장 꾸준한 멤버</strong></header>
                  <ol className={styles.statusBarList}>
                    {[...roomMembers].sort((a, b) => b.records - a.records).map((member) => {
                      const recordedDays = Math.min(24, Math.round(member.records * .63));
                      return (
                        <li key={member.id}>
                          <span>{member.name}</span>
                          <span className={styles.wideBar}><i style={{ width: `${(recordedDays / 24) * 100}%` }} /></span>
                          <strong>{recordedDays}일</strong>
                        </li>
                      );
                    })}
                  </ol>
                </article>
              </div>

              <section className={styles.badgeSection} aria-labelledby="badge-title">
                <header><h2 id="badge-title">이번 주 우리다운 모습</h2></header>
                <div className={styles.badgeStrip}>
                  {badges.map((badge) => (
                    <article className={styles.badgePill} key={badge.name}>
                      <span aria-hidden="true">{badge.emoji}</span>
                      <div><strong>{badge.name} · {badge.owner}</strong><p>{badge.copy}</p></div>
                    </article>
                  ))}
                </div>
              </section>
            </section>
          )}

          {tab === "members" && (
            <section className={styles.memberSection} aria-labelledby="member-title">
              <h2 id="member-title">함께 기록하는 멤버</h2>
              <div className={styles.memberList}>
                {roomMembers.map((member, memberIndex) => (
                  <article className={styles.memberRow} key={member.id}>
                    <span className={styles.avatar} style={{ background: member.color, color: "#18221b" }} aria-hidden="true">{member.avatar}</span>
                    <div className={styles.memberInfo}><strong>{member.name}</strong><span>{member.joined}째 함께하는 중</span></div>
                    <div className={styles.memberStat}><strong>{member.records}회</strong><span>누적 기록</span></div>
                    <div className={styles.memberStat}><strong>{member.streak > 0 ? `${member.streak}일` : "쉬는 중"}</strong><span>연속 기록</span></div>
                    <div className={styles.miniCalendar} aria-label={`${member.name} 최근 2주 기록`}>
                      {Array.from({ length: 28 }, (_, index) => {
                        const filled = (index * 7 + memberIndex * 3) % 10 < Math.round(member.rate / 10);
                        return <i key={index} data-filled={filled} style={{ "--dot-color": member.color } as CSSProperties} />;
                      })}
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>

      {reportMeal && (
        <div className={styles.modalBackdrop} role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget) setReportMeal(null);
        }}>
          <section className={`${styles.modal} ${styles.reportModal}`} role="dialog" aria-modal="true" aria-labelledby="report-title">
            <header className={styles.modalHeader}>
              <div><h2 id="report-title">이 식사를 신고할까요?</h2><p>가장 가까운 이유를 골라주세요.</p></div>
              <button type="button" className={styles.closeButton} onClick={() => setReportMeal(null)} aria-label="닫기">×</button>
            </header>
            <div className={styles.modalBody}>
              <div className={styles.reportReasons}>
                {[
                  ["spam", "광고나 반복 게시물이에요"],
                  ["inappropriate", "불편한 사진이나 말이 있어요"],
                  ["privacy", "개인정보가 보여요"],
                  ["other", "다른 문제가 있어요"],
                ].map(([value, label]) => (
                  <button type="button" key={value} aria-pressed={reportReason === value} onClick={() => setReportReason(value)}>{label}</button>
                ))}
              </div>
              <div className={styles.modalActions}>
                <button type="button" className={styles.secondaryButton} onClick={() => setReportMeal(null)}>취소</button>
                <button
                  type="button"
                  className={styles.primaryButton}
                  disabled={!reportReason}
                  onClick={() => {
                    setReportMeal(null);
                    setToast("신고를 접수했어요.");
                  }}
                >
                  신고하기
                </button>
              </div>
            </div>
          </section>
        </div>
      )}

      {toast && <div className={styles.toast} role="status">{toast}</div>}
    </main>
  );
}

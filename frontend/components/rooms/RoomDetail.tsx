"use client";

import type { CSSProperties } from "react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { RecordMealModal } from "@/components/RecordMealModal";
import { SafeImage } from "@/components/SafeImage";
import { suppressScrollTopGuard } from "@/components/ScrollToTop";
import { mockRoomDetail } from "@/data/mockRooms";
import { useExitPresence } from "@/hooks/useDelayedClose";
import type { MealType as DietMealType } from "@/hooks/useDietRecords";
import { ConfirmDialog } from "@/components/SystemFeedback";
import styles from "@/components/rooms/Rooms.module.css";
import { useAuthSession } from "@/hooks/useAuthSession";
import { ApiError } from "@/lib/api/client";
import {
  addRoomMealComment,
  deleteRoomMealComment,
  getRoomCalendar,
  getRoomDetail,
  getRoomMealComments,
  getRoomMemberCalendar,
  nudgeRoomMember,
  reportRoomContent,
  toggleRoomMealReaction,
} from "@/lib/api/rooms";
import {
  MealType,
  MemberCalendarDay,
  MemberMealSlot,
  RoomCalendarDay,
  RoomComment,
  RoomDetailResponse,
} from "@/lib/rooms/contracts";

type RoomTab = "today" | "status" | "members";
type TodayView = "전체" | MealType;

const tabs: { id: RoomTab; label: string }[] = [
  { id: "today", label: "오늘" },
  { id: "status", label: "현황" },
  { id: "members", label: "멤버" },
];

const mealSlots: { label: MealType; symbol: string; name: string }[] = [
  { label: "breakfast", symbol: "☀", name: "아침" },
  { label: "lunch", symbol: "◐", name: "점심" },
  { label: "dinner", symbol: "☾", name: "저녁" },
  { label: "snack", symbol: "●", name: "간식" },
];

const MEAL_LABELS: Record<MealType, DietMealType> = { breakfast: "아침", lunch: "점심", dinner: "저녁", snack: "간식" };

const todayViews: TodayView[] = ["전체", "breakfast", "lunch", "dinner", "snack"];

function getCurrentMealView(): MealType {
  const hour = new Date().getHours();
  if (hour < 11) return "breakfast";
  if (hour < 15) return "lunch";
  if (hour < 18) return "snack";
  return "dinner";
}

function slotKey(memberId: string, mealType: MealType) {
  return `${memberId}:${mealType}`;
}

// toISOString()은 UTC 기준이라, KST 자정~오전 9시 사이에는 실제로는 오늘인
// 날짜가 어제로 잘려서 recordedDates(서버가 KST 날짜로 내려줌)와 하루씩
// 어긋났다(실사용 중 재현 - "지금 현재시간 기준으로 어제기록이 뜨고있어요").
// 브라우저 로컬 타임존 getter로 날짜 문자열을 만들어야 서버의 KST 날짜와 맞는다.
function toLocalDateKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseDateKey(key: string) {
  const [year, month, day] = key.split("-").map(Number);
  return new Date(year, month - 1, day);
}

const WEEKDAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

function formatDateLabel(key: string) {
  const date = parseDateKey(key);
  return `${date.getMonth() + 1}월 ${date.getDate()}일 (${WEEKDAY_LABELS[date.getDay()]})`;
}

export function RoomDetail({ roomId }: { roomId: string }) {
  const { ready: authReady, signedIn, token, isMockSession } = useAuthSession();
  const [detail, setDetail] = useState<RoomDetailResponse | null>(isMockSession && roomId === mockRoomDetail.room.id ? mockRoomDetail : null);
  const [loading, setLoading] = useState(!isMockSession);
  const [notFound, setNotFound] = useState(false);
  const room = detail?.room ?? null;
  const roomMembers = detail?.members ?? [];
  const memberColumns = Math.max(1, Math.min(3, roomMembers.length));
  const [tab, setTab] = useState<RoomTab>("today");
  const [todayView, setTodayView] = useState<TodayView>("전체");
  const [toast, setToast] = useState("");
  const [replies, setReplies] = useState<Record<string, string>>({});
  const [openReplyId, setOpenReplyId] = useState<string | null>(null);
  const [reactionState, setReactionState] = useState<Record<string, { reacted: boolean; count: number }>>({});
  const [photoIndexes, setPhotoIndexes] = useState<Record<string, number>>({});
  const [reportMeal, setReportMeal] = useState<{ id: string; member: string } | null>(null);
  const { rendered: reportMealView, closing: reportMealClosing } = useExitPresence(reportMeal);
  const [reportReason, setReportReason] = useState("");
  const [comments, setComments] = useState<Record<string, RoomComment[]>>({});
  const [nudgedSlots, setNudgedSlots] = useState<Record<string, boolean>>({});
  const [pendingNudge, setPendingNudge] = useState<{ memberId: string; memberName: string; mealType: MealType } | null>(null);
  const [nudgeSending, setNudgeSending] = useState(false);
  const [memberCalendars, setMemberCalendars] = useState<Record<string, MemberCalendarDay[]>>({});
  // 날짜 이동(2026-07-30 연장업무) - 기본은 오늘, 캘린더/화살표로 과거 조회.
  const [selectedDate, setSelectedDate] = useState(() => toLocalDateKey(new Date()));
  const [calendarOpen, setCalendarOpen] = useState(false);
  const { rendered: calendarView, closing: calendarClosing } = useExitPresence(calendarOpen ? true : null);
  const [calMonth, setCalMonth] = useState(() => {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1 };
  });
  const [roomCalendars, setRoomCalendars] = useState<Record<string, RoomCalendarDay[]>>({});
  // 방 안에서 바로 업로드(2026-07-31 요청) - 이전엔 "내 아침 올리기"류 버튼이
  // 홈으로 이동시켰는데, 그 자리에서 팝업으로 올리고 방 화면에 바로 반영되게.
  const [uploadMeal, setUploadMeal] = useState<MealType | null>(null);
  const [roomRefreshTick, setRoomRefreshTick] = useState(0);

  const tabsRef = useRef<HTMLElement>(null);
  const didInitialScroll = useRef(false);

  useEffect(() => {
    if (isMockSession) {
      setDetail(roomId === mockRoomDetail.room.id ? mockRoomDetail : null);
      setNotFound(roomId !== mockRoomDetail.room.id);
      setLoading(false);
      return;
    }
    if (!token) return;
    let active = true;
    setLoading(true);
    setNotFound(false);
    getRoomDetail(token, roomId, selectedDate)
      .then((response) => {
        if (!active) return;
        setDetail(response);
        if (response.incomingNudges.length > 0) {
          const [first, ...rest] = response.incomingNudges;
          setToast(
            rest.length > 0
              ? `${first.senderName}님 외 ${rest.length}명이 콕 찔렀어요.`
              : `${first.senderName}님이 ${MEAL_LABELS[first.mealType]} 기록을 콕 찔렀어요.`,
          );
        }
      })
      .catch(() => {
        if (active) setNotFound(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [isMockSession, token, roomId, selectedDate, roomRefreshTick]);

  // 캘린더가 열려 있는 동안 보고 있는 달의 기록 현황을 불러온다(월 단위 캐시).
  const calMonthKey = `${calMonth.year}-${String(calMonth.month).padStart(2, "0")}`;
  useEffect(() => {
    if (!calendarOpen || !token || roomCalendars[calMonthKey]) return;
    let active = true;
    getRoomCalendar(token, roomId, calMonth.year, calMonth.month)
      .then(({ days }) => {
        if (active) setRoomCalendars((current) => ({ ...current, [calMonthKey]: days }));
      })
      .catch(() => {
        if (active) setRoomCalendars((current) => ({ ...current, [calMonthKey]: [] }));
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [calendarOpen, token, roomId, calMonthKey]);

  useEffect(() => {
    setTodayView(getCurrentMealView());
  }, []);

  const memberIds = roomMembers.map((member) => member.id).join(",");
  useEffect(() => {
    if (tab !== "members" || !token || !memberIds) return;
    memberIds.split(",").forEach((memberId) => {
      void loadMemberCalendar(memberId);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, token, memberIds]);

  // 방에 처음 들어오면 방 헤더를 지나 탭(오늘/현황/멤버) 지점으로 스크롤을
  // 맞춰, 셋로그처럼 식탁 피드가 바로 보이게 한다. 탭은 sticky라 상단 글로벌
  // 내비 바로 아래에 붙는다(모바일 62px / 데스크톱 72px).
  useEffect(() => {
    if (didInitialScroll.current) return;
    if (!authReady || !signedIn) return;
    const el = tabsRef.current;
    if (!el) return;
    didInitialScroll.current = true;
    // ScrollToTop.tsx가 네비게이션 직후 잠깐 스크롤을 0으로 계속 되돌리는
    // 가드를 켜두는데, 여긴 그 직후 의도적으로 아래로 스크롤해야 하므로
    // 먼저 꺼준다 - 안 그러면 가드가 다음 프레임에 이 스크롤을 취소해버린다.
    suppressScrollTopGuard();
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

  useEffect(() => {
    if (!calendarOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setCalendarOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [calendarOpen]);

  // 첫 로드만 전체 게이트 - 날짜 이동으로 다시 불러올 땐 기존 화면을 유지한
  // 채로 갈아끼운다(화면 전체가 깜빡이지 않게).
  if (!authReady || (signedIn && token && loading && !detail)) {
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

  if (notFound || !room || !detail || (!token && !isMockSession)) {
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

  const slotsByKey = new Map<string, MemberMealSlot>(detail.todayMealSlots.map((slot) => [slotKey(slot.memberId, slot.mealType), slot]));

  const serverToday = detail.serverDate;
  const isToday = selectedDate >= serverToday;
  // 콕 찌르기는 서버가 항상 "오늘" 기준으로 기록하므로(POST /nudges에 날짜가
  // 없다), 과거 날짜를 보는 동안엔 버튼 영역 자체를 내리지 않는다.
  const dateLabel = formatDateLabel(selectedDate);

  function shiftDay(delta: number) {
    const date = parseDateKey(selectedDate);
    date.setDate(date.getDate() + delta);
    const next = toLocalDateKey(date);
    if (next > serverToday) return;
    setSelectedDate(next);
  }

  function toggleCalendar() {
    if (!calendarOpen) {
      const date = parseDateKey(selectedDate);
      setCalMonth({ year: date.getFullYear(), month: date.getMonth() + 1 });
    }
    setCalendarOpen((value) => !value);
  }

  function shiftCalMonth(delta: number) {
    const date = new Date(calMonth.year, calMonth.month - 1 + delta, 1);
    setCalMonth({ year: date.getFullYear(), month: date.getMonth() + 1 });
  }

  function copyInvite() {
    void navigator.clipboard.writeText(`${window.location.origin}/rooms/${roomId}/settings#invite`)
      .then(() => setToast("초대 링크는 모임 관리에서 복사할 수 있어요."));
  }

  async function loadComments(mealId: string) {
    if (comments[mealId] || !token) return;
    try {
      const page = await getRoomMealComments(token, roomId, mealId);
      setComments((current) => ({ ...current, [mealId]: page.items }));
    } catch {
      setComments((current) => ({ ...current, [mealId]: [] }));
    }
  }

  async function sendReply(mealId: string) {
    const message = replies[mealId]?.trim();
    if (!message || !token) return;
    try {
      const comment = await addRoomMealComment(token, roomId, mealId, message, crypto.randomUUID());
      setComments((current) => ({ ...current, [mealId]: [...(current[mealId] ?? []), comment] }));
      setReplies((current) => ({ ...current, [mealId]: "" }));
      setOpenReplyId(null);
    } catch (error) {
      setToast(error instanceof ApiError ? error.message : "댓글을 남기지 못했어요.");
    }
  }

  async function deleteComment(mealId: string, commentId: string) {
    if (!token) return;
    try {
      await deleteRoomMealComment(token, roomId, mealId, commentId);
      setComments((current) => ({ ...current, [mealId]: (current[mealId] ?? []).filter((item) => item.id !== commentId) }));
    } catch (error) {
      setToast(error instanceof ApiError ? error.message : "댓글을 지우지 못했어요.");
    }
  }

  async function toggleReaction(mealId: string, currentReacted: boolean, currentCount: number) {
    if (!token) return;
    try {
      const result = await toggleRoomMealReaction(token, roomId, mealId);
      setReactionState((current) => ({ ...current, [mealId]: { reacted: result.reacted, count: result.reactionCount } }));
      if (result.reacted) setToast("맛있겠다를 보냈어요.");
    } catch (error) {
      // 자기 자신 사진 반응 실패 재현용 - 원인 파악 전까지 임시로 남겨둔다.
      // 재현되면 status/payload로 서버가 실제로 뭘 돌려줬는지 바로 알 수 있다.
      if (error instanceof ApiError) {
        console.error("[room reaction failed]", { mealId, status: error.status, code: error.code, message: error.message, payload: error.payload });
      } else {
        console.error("[room reaction failed] non-ApiError", error);
      }
      setReactionState((current) => ({ ...current, [mealId]: { reacted: currentReacted, count: currentCount } }));
      setToast(error instanceof ApiError ? error.message : "반응을 보내지 못했어요.");
    }
  }

  async function confirmSendNudge() {
    if (!token || !pendingNudge) return;
    const { memberId, memberName, mealType } = pendingNudge;
    const key = slotKey(memberId, mealType);
    setNudgeSending(true);
    try {
      await nudgeRoomMember(token, roomId, memberId, mealType, crypto.randomUUID());
      setNudgedSlots((current) => ({ ...current, [key]: true }));
      setToast(`${memberName}님을 콕 찔렀어요.`);
    } catch (error) {
      setToast(error instanceof ApiError ? error.message : "콕 찌르지 못했어요.");
    } finally {
      setNudgeSending(false);
      setPendingNudge(null);
    }
  }

  async function loadMemberCalendar(memberId: string) {
    if (memberCalendars[memberId] || !token) return;
    const today = new Date();
    try {
      const { days } = await getRoomMemberCalendar(token, roomId, memberId, today.getFullYear(), today.getMonth() + 1);
      setMemberCalendars((current) => ({ ...current, [memberId]: days }));
    } catch {
      setMemberCalendars((current) => ({ ...current, [memberId]: [] }));
    }
  }

  return (
    <main className={styles.page}>
      <div className={styles.wrap}>
        <header className={styles.roomHeader}>
          <div className={styles.roomIdentity}>
            <span className={styles.roomEmoji} aria-hidden="true">{room.emoji}</span>
            <div>
              <p className={styles.eyebrow}>함께 기록한 지 {room.daysSinceStart}일</p>
              <h1>{room.name}</h1>
              <p className={styles.roomHeaderMeta}>멤버 {room.memberCount}명 · 오늘 {room.recordedTodayCount}명 기록</p>
            </div>
          </div>
          <div className={styles.roomHeaderActions}>
            {room.permissions.canInvite && (
              <button type="button" className={styles.secondaryButton} onClick={copyInvite}>초대 링크</button>
            )}
            <Link className={styles.secondaryButton} href={`/rooms/${room.id}/settings`}>모임 관리</Link>
            <button type="button" className={styles.primaryButton} onClick={() => setUploadMeal(getCurrentMealView())}>내 식단 기록</button>
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
              <div className={styles.dateNav}>
                <button type="button" className={styles.dateNavArrow} aria-label="이전 날" onClick={() => shiftDay(-1)}>◀</button>
                <button
                  type="button"
                  className={styles.dateNavLabel}
                  aria-expanded={calendarOpen}
                  onClick={toggleCalendar}
                >
                  {dateLabel}{isToday && <em>오늘</em>}<i aria-hidden="true">▾</i>
                </button>
                <button type="button" className={styles.dateNavArrow} aria-label="다음 날" disabled={isToday} onClick={() => shiftDay(1)}>▶</button>
                {!isToday && (
                  <button type="button" className={styles.dateNavToday} onClick={() => setSelectedDate(serverToday)}>오늘로</button>
                )}
              </div>

              {calendarView && (() => {
                const calDays = roomCalendars[calMonthKey];
                const calByDate = new Map((calDays ?? []).map((day) => [day.date, day]));
                const daysInMonth = new Date(calMonth.year, calMonth.month, 0).getDate();
                const leadingBlanks = new Date(calMonth.year, calMonth.month - 1, 1).getDay();
                const isCurrentMonth = calMonthKey >= serverToday.slice(0, 7);
                return (
                  <div
                    className={`${styles.modalBackdrop}${calendarClosing ? ` ${styles.isClosing}` : ""}`}
                    role="presentation"
                    onMouseDown={(event) => {
                      if (event.target === event.currentTarget) setCalendarOpen(false);
                    }}
                  >
                    <section className={`${styles.roomCalendar}${calendarClosing ? ` ${styles.isClosing}` : ""}`} role="dialog" aria-modal="true" aria-label="날짜 선택">
                      <button type="button" className={styles.roomCalendarClose} onClick={() => setCalendarOpen(false)} aria-label="닫기">×</button>
                      <header>
                        <button type="button" aria-label="이전 달" onClick={() => shiftCalMonth(-1)}>◀</button>
                        <strong>{calMonth.year}년 {calMonth.month}월</strong>
                        <button type="button" aria-label="다음 달" disabled={isCurrentMonth} onClick={() => shiftCalMonth(1)}>▶</button>
                      </header>
                      <div className={styles.roomCalendarWeekdays} aria-hidden="true">
                        {WEEKDAY_LABELS.map((label) => <span key={label}>{label}</span>)}
                      </div>
                      <div className={styles.roomCalendarGrid}>
                        {Array.from({ length: leadingBlanks }, (_, index) => <i key={`blank-${index}`} />)}
                        {Array.from({ length: daysInMonth }, (_, index) => {
                          const dayKey = `${calMonthKey}-${String(index + 1).padStart(2, "0")}`;
                          const info = calByDate.get(dayKey);
                          // 나도 올린 날(mine) / 남만 올린 날(others) 색 구분.
                          const state = info ? (info.myRecordCount > 0 ? "mine" : "others") : "none";
                          return (
                            <button
                              type="button"
                              key={dayKey}
                              data-state={state}
                              data-selected={dayKey === selectedDate || undefined}
                              disabled={dayKey > serverToday}
                              onClick={() => {
                                setSelectedDate(dayKey);
                                setCalendarOpen(false);
                              }}
                            >
                              {index + 1}
                            </button>
                          );
                        })}
                      </div>
                      <div className={styles.roomCalendarLegend}>
                        <span><i data-state="mine" />나도 올린 날</span>
                        <span><i data-state="others" />나만 안 올린 날</span>
                      </div>
                      {calDays === undefined && <p className={styles.roomCalendarLoading}>기록을 불러오는 중…</p>}
                    </section>
                  </div>
                );
              })()}

              <nav className={styles.mealViewTabs} aria-label="식사 보기">
                {todayViews.map((view) => (
                  <button
                    type="button"
                    key={view}
                    aria-pressed={todayView === view}
                    onClick={() => setTodayView(view)}
                  >
                    {view === "전체" ? view : MEAL_LABELS[view]}
                  </button>
                ))}
              </nav>

              {todayView === "전체" ? (
                <>
                  <header className={styles.todayHeading}>
                    <div>
                      <p className={styles.eyebrow}>{isToday ? "오늘의 식탁" : `${dateLabel}의 식탁`}</p>
                      <h2 id="today-room-title">멤버별 기록</h2>
                    </div>
                  </header>

                  <div className={styles.memberMealBoard} aria-label="멤버별 오늘 식사">
                    <div className={styles.boardHeader} aria-hidden="true">
                      <span>멤버</span>
                      {mealSlots.map((slot) => <span key={slot.label}>{slot.name}</span>)}
                    </div>
                    {roomMembers.map((member) => (
                      <article className={styles.memberMealRow} key={member.id} data-current={member.isMe}>
                        <div className={styles.boardMember}>
                          <span className={styles.avatar} style={{ background: member.color, color: "#18221b" }} aria-hidden="true">{member.avatarText}</span>
                          <span><strong>{member.name}</strong>{member.isMe && <small>me</small>}</span>
                        </div>
                        {mealSlots.map((slot) => {
                          const record = slotsByKey.get(slotKey(member.id, slot.label));
                          const isMissing = !record?.hasRecord;
                          const photos = record?.record?.orderedPhotos ?? [];
                          return (
                            <button
                              type="button"
                              key={slot.label}
                              className={`${styles.boardMealCell} ${isMissing ? styles.boardMealEmpty : styles.boardMealFilled}`}
                              aria-label={isMissing ? `${member.name} ${slot.name} 아직 기록 없음` : `${member.name} ${slot.name} ${record?.record?.title} 보기`}
                              disabled={isMissing}
                              onClick={() => setTodayView(slot.label)}
                            >
                              {isMissing ? (
                                <>
                                  <i aria-hidden="true">{slot.symbol}</i>
                                  <span>아직</span>
                                </>
                              ) : (
                                <>
                                  <SafeImage src={photos[0]?.imageUrl ?? null} alt="" fallbackLabel={slot.name} />
                                  {photos.length > 1 && <span>+{photos.length - 1}</span>}
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
                      <p className={styles.eyebrow}>{isToday ? "오늘" : dateLabel}의 {MEAL_LABELS[todayView]}</p>
                      <h2 id="today-room-title">{MEAL_LABELS[todayView]} 식탁</h2>
                    </div>
                    {isToday && (
                      <button type="button" className={styles.mealUploadButton} onClick={() => setUploadMeal(todayView)}>
                        ＋ 내 {MEAL_LABELS[todayView]} 올리기
                      </button>
                    )}
                  </header>

                  <div
                    className={styles.setlogFeed}
                    style={{ "--member-columns": memberColumns } as CSSProperties}
                    data-members={roomMembers.length}
                  >
                    {roomMembers.map((member) => {
                      const slot = slotsByKey.get(slotKey(member.id, todayView));
                      if (!slot?.hasRecord || !slot.record) {
                        const canSend = slot?.nudge.canSend ?? false;
                        const refused = slot?.nudge.refused ?? false;
                        const alreadyNudged = nudgedSlots[slotKey(member.id, todayView)] || slot?.nudge.sentByMe;
                        return (
                          <article className={`${styles.setlogCard} ${styles.setlogEmptyCard}`} key={`empty-${todayView}-${member.id}`}>
                            <div className={styles.setlogEmptyPhoto}>
                              <span className={styles.avatar} style={{ background: member.color, color: "#18221b" }} aria-hidden="true">{member.avatarText}</span>
                              <p>{isToday ? `아직 ${MEAL_LABELS[todayView]} 사진이 없어요` : `이날 ${MEAL_LABELS[todayView]} 기록이 없어요`}</p>
                            </div>
                            {isToday && member.isMe ? (
                              <footer className={styles.setlogEmptyAction}>
                                <button type="button" disabled title="본인에게는 콕 찌르기를 보낼 수 없어요.">셀프 콕 찌르기 안돼요</button>
                              </footer>
                            ) : isToday && (canSend || refused) && (
                              <footer className={styles.setlogEmptyAction}>
                                <button
                                  type="button"
                                  disabled={alreadyNudged || refused}
                                  title={refused ? "이 멤버는 콕 찌르기를 받지 않아요." : undefined}
                                  onClick={() => setPendingNudge({ memberId: member.id, memberName: member.name, mealType: todayView })}
                                >
                                  {refused ? "콕 안 받아요" : alreadyNudged ? "콕 찔렀어요" : "콕 찌르기"}
                                </button>
                              </footer>
                            )}
                          </article>
                        );
                      }

                      const meal = slot.record;
                      const recipeCount = meal.connectedItems.filter((item) => item.source === "recipe").length;
                      const foodCount = meal.connectedItems.filter((item) => item.source === "product").length;
                      // 비전(사진) → 레시피 → 저당픽 순으로 이미 정렬돼서 온다 - 여러
                      // 소스가 섞여 있어도 이 순서 그대로 다 넘겨볼 수 있다.
                      const photos = meal.orderedPhotos.map((photo) => photo.imageUrl);
                      const photoIndex = Math.min(photoIndexes[meal.id] ?? 0, Math.max(0, photos.length - 1));
                      const activeImage = photos[photoIndex] ?? null;
                      // 넘겨보는 사진마다 그 사진에 맞는 이름을 보여준다 - 예전엔
                      // meal.title 하나로 고정돼서 사진을 넘겨도 이름이 안 바뀌었다.
                      const activeName = meal.orderedPhotos[photoIndex]?.name ?? meal.title;
                      const reaction = reactionState[meal.id] ?? { reacted: meal.reactedByMe, count: meal.reactionCount };
                      const mealComments = comments[meal.id];
                      return (
                        <article className={styles.setlogCard} key={meal.id}>
                          <div className={styles.setlogPhoto}>
                            <SafeImage src={activeImage} alt={`${activeName} ${photoIndex + 1}번째 사진`} fallbackLabel="식단 사진" />
                            {photos.length > 1 && (
                              <>
                                <button
                                  type="button"
                                  className={styles.setlogGalleryPrev}
                                  onClick={() => setPhotoIndexes((current) => ({
                                    ...current,
                                    [meal.id]: ((current[meal.id] ?? 0) - 1 + photos.length) % photos.length,
                                  }))}
                                  aria-label={`${meal.memberName}님의 이전 ${MEAL_LABELS[todayView]} 사진 보기`}
                                >
                                  <span>이전 사진 보기</span>
                                </button>
                                <button
                                  type="button"
                                  className={styles.setlogGalleryNext}
                                  onClick={() => setPhotoIndexes((current) => ({
                                    ...current,
                                    [meal.id]: ((current[meal.id] ?? 0) + 1) % photos.length,
                                  }))}
                                  aria-label={`${meal.memberName}님의 다음 ${MEAL_LABELS[todayView]} 사진 보기`}
                                >
                                  <span>다음 사진 보기</span>
                                </button>
                              </>
                            )}
                            <div className={styles.setlogAuthor}>
                              <span className={styles.avatar} aria-hidden="true">{meal.memberAvatar}</span>
                              <strong>{meal.memberName}</strong>
                            </div>
                            <div className={styles.setlogPhotoCount}>
                              <strong>{photos.length > 1 ? `${photoIndex + 1} / ${photos.length}` : "사진 1장"}</strong>
                            </div>
                            {photos.length > 1 && (
                              <>
                                <span className={styles.setlogPrevHint} aria-hidden="true">‹</span>
                                <span className={styles.setlogNextHint} aria-hidden="true">›</span>
                                <span className={styles.setlogDots} aria-hidden="true">
                                  {photos.map((url, index) => <i key={`${url}-${index}`} data-active={photoIndex === index} />)}
                                </span>
                              </>
                            )}
                            <div className={styles.setlogActions}>
                              <button
                                type="button"
                                onClick={() => {
                                  setOpenReplyId((current) => current === meal.id ? null : meal.id);
                                  void loadComments(meal.id);
                                }}
                              >
                                {/* 2026-07-30 QA 리포트 - meal.commentCount는 페이지를 처음 연
                                    시점의 서버 스냅샷이라, 같은 화면에서 댓글을 남기거나
                                    지워도 안 바뀌었다("3개 남겼는데 1에서 안 올라감").
                                    댓글을 한 번이라도 불러온 뒤로는 그 실제 개수를 쓴다. */}
                                댓글 {mealComments?.length ?? meal.commentCount}
                              </button>
                              <button type="button" onClick={() => toggleReaction(meal.id, reaction.reacted, reaction.count)} aria-pressed={reaction.reacted}>
                                맛있겠다 {reaction.count}
                              </button>
                              {!member.isMe && (
                                <button
                                  type="button"
                                  aria-label={`${meal.memberName}님의 식사 더보기`}
                                  onClick={() => {
                                    setReportReason("");
                                    setReportMeal({ id: meal.id, member: meal.memberName });
                                  }}
                                >
                                  ···
                                </button>
                              )}
                            </div>
                            <div className={styles.setlogBubbles}>
                              {(mealComments ?? []).slice(-2).map((comment) => (
                                <p key={comment.id}>
                                  {comment.authorName} · {comment.message}
                                  {comment.canDelete && (
                                    <button type="button" onClick={() => deleteComment(meal.id, comment.id)} aria-label="댓글 삭제"> ×</button>
                                  )}
                                </p>
                              ))}
                            </div>
                            {openReplyId === meal.id && (
                              <form className={styles.setlogReply} onSubmit={(event) => { event.preventDefault(); void sendReply(meal.id); }}>
                                <input
                                  autoFocus
                                  value={replies[meal.id] ?? ""}
                                  onChange={(event) => setReplies((current) => ({ ...current, [meal.id]: event.target.value }))}
                                  placeholder="짧게 답글 남기기"
                                  aria-label={`${meal.memberName}님 식단에 댓글`}
                                  maxLength={160}
                                />
                                <button type="submit">보내기</button>
                              </form>
                            )}
                          </div>
                          <footer className={styles.setlogMeta}>
                            <div>
                              <strong>{activeName}</strong>
                              <span>당류 {meal.sugar}g · {meal.calories}kcal</span>
                            </div>
                            <div className={styles.sourceSummary} aria-label="한 끼 구성">
                              <span>사진 {photos.length}</span>
                              {recipeCount > 0 && <span>레시피 {recipeCount}</span>}
                              {foodCount > 0 && <span>저당 제품 {foodCount}</span>}
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
                  <p className={styles.eyebrow}>이번 주 모임 기록</p>
                  <h2 id="status-title">우리의 식탁이 이만큼 쌓였어요</h2>
                </div>
                <div className={styles.statusLeadRate}>
                  <span>이번 주 기록률</span>
                  <strong>{room.monthlyRecordRate}%</strong>
                </div>
              </header>

              <div className={styles.statusStats}>
                <article><span aria-hidden="true">🌱</span><div><strong>{room.daysSinceStart}일</strong><small>함께 기록한 날</small></div></article>
                <article><span aria-hidden="true">🍚</span><div><strong>{room.recordedTodayCount}명</strong><small>오늘 식사를 남긴 멤버</small></div></article>
                <article><span aria-hidden="true">🏅</span><div><strong>{room.rank ? `${room.rank}위` : "쉬는 중"}</strong><small>이번 주 모임 순위</small></div></article>
              </div>

              <div className={styles.statusCards}>
                <article className={styles.statusCard}>
                  <header><h3>오늘 당류</h3><strong>평균 {room.averageSugar}g</strong></header>
                  <ol className={styles.statusBarList}>
                    {[...roomMembers].sort((a, b) => a.averageSugar - b.averageSugar).map((member) => (
                      <li key={member.id}>
                        <span>{member.name}</span>
                        <span className={styles.wideBar}><i style={{ width: `${Math.min(100, member.averageSugar * 2)}%` }} /></span>
                        <strong>{member.averageSugar}g</strong>
                      </li>
                    ))}
                  </ol>
                </article>

                <article className={`${styles.statusCard} ${styles.statusCardLime}`}>
                  <header><h3>이번 주 기록</h3><strong>가장 꾸준한 멤버</strong></header>
                  <ol className={styles.statusBarList}>
                    {[...roomMembers].sort((a, b) => b.recordCount - a.recordCount).map((member) => (
                      <li key={member.id}>
                        <span>{member.name}</span>
                        <span className={styles.wideBar}><i style={{ width: `${member.recordRate}%` }} /></span>
                        <strong>{member.recordCount}회</strong>
                      </li>
                    ))}
                  </ol>
                </article>
              </div>

              {detail.badges.length > 0 && (
                <section className={styles.badgeSection} aria-labelledby="badge-title">
                  <header><h2 id="badge-title">이번 주 우리다운 모습</h2></header>
                  <div className={styles.badgeStrip}>
                    {detail.badges.map((badge) => (
                      <article className={styles.badgePill} key={badge.name}>
                        <span aria-hidden="true">{badge.emoji}</span>
                        <div><strong>{badge.name} · {badge.ownerName}</strong><p>{badge.copy}</p></div>
                      </article>
                    ))}
                  </div>
                </section>
              )}
            </section>
          )}

          {tab === "members" && (
            <section className={styles.memberSection} aria-labelledby="member-title">
              <h2 id="member-title">함께 기록하는 멤버</h2>
              <div className={styles.memberList}>
                {roomMembers.map((member) => {
                  const calendar = memberCalendars[member.id];
                  const recordedDates = new Set((calendar ?? []).filter((day) => day.recordCount > 0).map((day) => day.date));
                  return (
                    <article className={styles.memberRow} key={member.id}>
                      <span className={styles.avatar} style={{ background: member.color, color: "#18221b" }} aria-hidden="true">{member.avatarText}</span>
                      <div className={styles.memberInfo}><strong>{member.name}</strong><span>{member.joinedDays}일째 함께하는 중</span></div>
                      <div className={styles.memberStat}><strong>{member.recordCount}회</strong><span>이번 주 기록</span></div>
                      <div className={styles.memberStat}><strong>{member.streakDays > 0 ? `${member.streakDays}일` : "쉬는 중"}</strong><span>연속 기록</span></div>
                      <div className={styles.miniCalendar} aria-label={`${member.name} 이번 달 기록`}>
                        {Array.from({ length: 28 }, (_, index) => {
                          const date = new Date();
                          date.setDate(date.getDate() - (27 - index));
                          const filled = recordedDates.has(toLocalDateKey(date));
                          return <i key={index} data-filled={filled} style={{ "--dot-color": member.color } as CSSProperties} />;
                        })}
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>
          )}
        </div>
      </div>

      {reportMealView && (
        <div className={`${styles.modalBackdrop}${reportMealClosing ? ` ${styles.isClosing}` : ""}`} role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget) setReportMeal(null);
        }}>
          <section className={`${styles.modal} ${styles.reportModal}${reportMealClosing ? ` ${styles.isClosing}` : ""}`} role="dialog" aria-modal="true" aria-labelledby="report-title">
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
                  onClick={async () => {
                    if (!token || !reportMeal) return;
                    const meal = reportMeal;
                    setReportMeal(null);
                    try {
                      await reportRoomContent(token, roomId, {
                        targetType: "meal",
                        targetId: meal.id,
                        reason: reportReason as "spam" | "inappropriate" | "privacy" | "other",
                      });
                      setToast("신고를 접수했어요.");
                    } catch (error) {
                      setToast(error instanceof ApiError ? error.message : "신고를 접수하지 못했어요.");
                    }
                  }}
                >
                  신고하기
                </button>
              </div>
            </div>
          </section>
        </div>
      )}

      {pendingNudge && (
        <ConfirmDialog
          title={`${pendingNudge.memberName}님을 콕 찌를까요?`}
          description={`${MEAL_LABELS[pendingNudge.mealType]} 기록을 아직 안 남겼다고 알려줄게요.`}
          confirmLabel="콕 찌르기"
          busy={nudgeSending}
          onConfirm={confirmSendNudge}
          onClose={() => setPendingNudge(null)}
        />
      )}
      {uploadMeal && (
        <RecordMealModal
          meal={MEAL_LABELS[uploadMeal]}
          initialDate={selectedDate}
          onClose={() => setUploadMeal(null)}
          onSaved={() => {
            setUploadMeal(null);
            setRoomRefreshTick((tick) => tick + 1);
            setToast("저장했어요.");
          }}
        />
      )}
      {toast && <div className={styles.toast} role="status">{toast}</div>}
    </main>
  );
}

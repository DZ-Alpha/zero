"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { SafeImage } from "@/components/SafeImage";
import styles from "@/components/rooms/Rooms.module.css";
import { useAuthSession } from "@/hooks/useAuthSession";
import { ApiError } from "@/lib/api/client";
import { createRoom as createRoomApi, getRoomsHome } from "@/lib/api/rooms";
import { CreateRoomResponse, MAX_ROOM_COUNT, RoomsHomeResponse, TeamRankingItem } from "@/lib/rooms/contracts";

const emojiOptions = ["🌿", "🍚", "🥗", "🏃", "🌙"];

const MEAL_LABELS: Record<string, string> = { breakfast: "아침", lunch: "점심", dinner: "저녁", snack: "간식" };

// 2026-07-31 요청 - 아직 랭킹에 들어갈 팀(멤버 3명 이상·개설 7일 이상·랭킹
// 참여 동의)이 없으면 섹션이 통째로 텅 비어 보인다. 실제 데이터가 하나도
// 없을 때만 이 목업으로 대체하고, 예시 배지로 실데이터가 아님을 표시한다.
const MOCK_TEAM_RANKING: TeamRankingItem[] = [
  { id: "mock-1", name: "아침빛 식탁", emoji: "🌅", memberCount: 4, recordRate: 92, averageSugar: 8, rankMovement: 1, isMine: false },
  { id: "mock-2", name: "저당 챌린저스", emoji: "🥗", memberCount: 5, recordRate: 88, averageSugar: 10, rankMovement: 0, isMine: false },
  { id: "mock-3", name: "산책하는 사람들", emoji: "🚶", memberCount: 3, recordRate: 81, averageSugar: 12, rankMovement: -1, isMine: false },
  { id: "mock-4", name: "밤샘 금지단", emoji: "🌙", memberCount: 6, recordRate: 76, averageSugar: 14, rankMovement: 2, isMine: false },
];

export function RoomsHome() {
  const router = useRouter();
  const { ready: authReady, signedIn, token } = useAuthSession();
  const [home, setHome] = useState<RoomsHomeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const myRooms = home?.rooms ?? [];
  const roomActivity = home?.recentActivities ?? [];
  const realTeamRanking = home?.weeklyRanking ?? [];
  const isMockRanking = realTeamRanking.length === 0;
  const teamRanking = isMockRanking ? MOCK_TEAM_RANKING : realTeamRanking;
  const roomLimitReached = myRooms.length >= MAX_ROOM_COUNT;
  const [showAllRanking, setShowAllRanking] = useState(false);
  const [modal, setModal] = useState<"create" | "join" | null>(null);
  const [emoji, setEmoji] = useState("🌿");
  const [roomName, setRoomName] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [rankingOptIn, setRankingOptIn] = useState(true);
  const [created, setCreated] = useState<CreateRoomResponse | null>(null);
  const [creating, setCreating] = useState(false);
  const [toast, setToast] = useState("");

  useEffect(() => {
    if (!token) return;
    let active = true;
    setLoading(true);
    getRoomsHome(token)
      .then((response) => {
        if (active) setHome(response);
      })
      .catch(() => {
        if (active) setToast("모임 정보를 불러오지 못했어요.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (!modal) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeModal();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [modal]);

  function openModal(nextModal: "create" | "join") {
    setCreated(null);
    setRoomName("");
    setJoinCode("");
    setEmoji("🌿");
    setRankingOptIn(true);
    setModal(nextModal);
  }

  function closeModal() {
    setModal(null);
    setCreated(null);
  }

  async function createRoom() {
    if (roomLimitReached) {
      setToast("얌로그 모임은 3개까지 만들 수 있어요.");
      return;
    }
    if (!roomName.trim() || !token || creating) {
      if (!roomName.trim()) setToast("모임 이름을 먼저 적어주세요.");
      return;
    }
    setCreating(true);
    try {
      const response = await createRoomApi(token, { name: roomName.trim(), emoji, rankingOptIn }, crypto.randomUUID());
      setCreated(response);
      setHome((prev) => prev && { ...prev, rooms: [...prev.rooms, response.room] });
    } catch (error) {
      setToast(error instanceof ApiError ? error.message : "모임을 만들지 못했어요. 다시 시도해주세요.");
    } finally {
      setCreating(false);
    }
  }

  function previewJoin() {
    const code = joinCode.trim().toUpperCase();
    if (code.length !== 6) {
      setToast("초대 코드 6자리를 확인해주세요.");
      return;
    }
    closeModal();
    router.push(`/rooms/join?code=${encodeURIComponent(code)}`);
  }

  async function copyInvite() {
    if (!created) return;
    const origin = window.location.origin;
    try {
      await navigator.clipboard.writeText(`${origin}${created.invite.joinUrl}`);
      setToast("초대 링크를 복사했어요.");
    } catch {
      setToast("초대 코드를 직접 복사해주세요.");
    }
  }

  if (!authReady || (signedIn && token && loading)) {
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

  return (
    <main className={styles.page}>
      <div className={styles.wrap}>
        <section className={styles.hero}>
          <div>
            <h1>오늘의 식탁을 <em>함께 이어가요.</em></h1>
            <div className={styles.liveSignal} aria-label="얌로그 참여 현황">
              <i aria-hidden="true" />
              <strong>{myRooms.length} / {MAX_ROOM_COUNT}</strong>
              <span>내 모임 · 전체 {(home?.activeTeamCount ?? 0).toLocaleString()}팀 기록 중</span>
            </div>
          </div>
          <div className={styles.heroActions}>
            <button
              type="button"
              className={styles.primaryButton}
              onClick={() => roomLimitReached ? setToast("얌로그 모임은 3개까지 만들 수 있어요.") : openModal("create")}
              disabled={roomLimitReached}
            >
              모임 만들기
            </button>
            <button type="button" className={styles.secondaryButton} onClick={() => openModal("join")} disabled={roomLimitReached}>코드로 참여</button>
          </div>
          <p className={styles.roomLimit}>모임은 최대 {MAX_ROOM_COUNT}개까지 함께할 수 있어요.</p>
        </section>

        <section className={styles.section} aria-labelledby="my-rooms-title">
          <header className={styles.sectionHeader}>
            <div>
              <p className={styles.eyebrow}>내가 참여한 모임</p>
              <h2 id="my-rooms-title">내 모임</h2>
            </div>
          </header>

          {myRooms.length === 0 ? (
            <div className={styles.emptyRooms}>
              <span aria-hidden="true">🍽️</span>
              <div><strong>아직 참여한 모임이 없어요</strong><p>모임을 만들거나 받은 코드로 참여해보세요.</p></div>
              <button type="button" className={styles.primaryButton} onClick={() => openModal("create")}>첫 모임 만들기</button>
            </div>
          ) : (
            <div className={styles.roomGrid}>
              {myRooms.map((room) => {
              const recentMeals = roomActivity.filter((activity) => activity.roomId === room.id).slice(0, 3);
              return (
                <article className={styles.roomCard} key={room.id}>
                <div className={styles.roomCardTop}>
                  <span className={styles.roomEmoji} aria-hidden="true">{room.emoji}</span>
                  {room.rank ? (
                    <span className={styles.rankBadge}>전체 {room.rank}위</span>
                  ) : (
                    <span className={`${styles.rankBadge} ${styles.rankBadgeMuted}`}>
                      {room.rankingOptIn ? "참여 준비 중" : "랭킹 비참여"}
                    </span>
                  )}
                </div>
                <h3>{room.name}</h3>
                <p className={styles.roomMeta}>멤버 {room.memberCount}명 · 오늘 {room.recordedTodayCount}명 기록 · {room.daysSinceStart}일째</p>
                <div className={styles.roomCardPhotos} aria-label={`${room.name} 최근 식단`}>
                  {recentMeals.map((activity) => (
                    <span key={activity.id}>
                      <SafeImage src={activity.imageUrl} alt="" fallbackLabel={MEAL_LABELS[activity.mealType]} />
                      <i>{activity.memberAvatar}</i>
                    </span>
                  ))}
                </div>
                <div className={styles.roomStats}>
                  <div><small>팀 평균 당류</small><strong>{room.averageSugar}<span>g</span></strong></div>
                  <div><small>이번 달 기록률</small><strong>{room.monthlyRecordRate}<span>%</span></strong></div>
                  <div><small>내 참여일</small><strong>{room.myParticipationDays}<span>일</span></strong></div>
                </div>
                {room.rankingOptIn && !room.rank && (
                  <p className={styles.qualification}>전체 랭킹 참여까지 {room.rankingEligibility.remainingDays}일 남았어요.</p>
                )}
                <Link className={styles.roomLink} href={`/rooms/${room.id}`}>
                  <span>오늘 기록 보러가기</span><span aria-hidden="true">→</span>
                </Link>
              </article>
              );
              })}
            </div>
          )}
        </section>

        <section className={`${styles.section} ${styles.activitySection}`} aria-labelledby="recent-room-activity-title">
          <header className={styles.sectionHeader}>
            <div>
              <p className={styles.eyebrow}>방금 올라왔어요</p>
              <h2 id="recent-room-activity-title">모임의 새 식탁</h2>
            </div>
          </header>
          <div className={styles.activityRibbon}>
            {roomActivity.map((activity) => (
              <Link href={`/rooms/${activity.roomId}`} className={styles.activityItem} key={activity.id}>
                <span className={styles.activityPhoto}><SafeImage src={activity.imageUrl} alt="" fallbackLabel={MEAL_LABELS[activity.mealType]} /></span>
                <span className={styles.activityCopy}>
                  <small>{activity.roomEmoji} {activity.roomName}</small>
                  <strong>{activity.memberName}님이 {MEAL_LABELS[activity.mealType]}을 기록했어요 · {activity.message}</strong>
                </span>
                <span aria-hidden="true">→</span>
              </Link>
            ))}
          </div>
        </section>

        <section className={styles.section} aria-labelledby="team-ranking-title">
          <header className={styles.sectionHeader}>
            <div>
              <p className={styles.eyebrow}>이번 주 기록</p>
              <h2 id="team-ranking-title">이번 주 팀 랭킹</h2>
            </div>
            {isMockRanking ? <span className={styles.rankingPreviewBadge}>예시</span> : <p>평균 당류와 기록률만 공개돼요.</p>}
          </header>

          <ol className={styles.rankList}>
            {teamRanking.slice(0, showAllRanking ? teamRanking.length : 3).map((team, index) => (
              <li className={`${styles.rankRow} ${team.isMine ? styles.rankRowMine : ""}`} key={team.id}>
                <span className={styles.rankNumber}>{String(index + 1).padStart(2, "0")}</span>
                <span className={styles.teamEmoji} aria-hidden="true">{team.emoji}</span>
                <span className={styles.teamCopy}>
                  <strong>{team.name}{team.isMine && <em className={styles.mineBadge}>내 모임</em>}</strong>
                  <small>멤버 {team.memberCount}명 · {team.rankMovement === 0 ? "순위 유지" : `${Math.abs(team.rankMovement)}계단 ${team.rankMovement > 0 ? "상승" : "하락"}`}</small>
                </span>
                <span className={styles.teamRate}>
                  <span>기록률</span><strong>{team.recordRate}%</strong>
                  <span className={styles.miniBar}><i style={{ width: `${team.recordRate}%` }} /></span>
                </span>
                <span className={styles.teamSugar}><span>평균 당류</span><strong>{team.averageSugar}g</strong></span>
              </li>
            ))}
          </ol>
          <div className={styles.rankingNote}>
            <button type="button" onClick={() => setShowAllRanking((value) => !value)} aria-expanded={showAllRanking}>
              {showAllRanking ? "상위 3개만 보기 ↑" : "전체 팀 랭킹 보기 →"}
            </button>
          </div>
        </section>
      </div>

      {modal && (
        <div className={styles.modalBackdrop} role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget) closeModal();
        }}>
          <section className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="room-modal-title">
            <header className={styles.modalHeader}>
              <div>
                <h2 id="room-modal-title">{modal === "create" ? "새 모임 만들기" : "초대 코드로 참여"}</h2>
                <p>{modal === "create" ? "가볍게 시작하고, 공개 범위는 나중에도 바꿀 수 있어요." : "6자리 코드를 입력하면 참여 전에 모임을 미리 볼 수 있어요."}</p>
              </div>
              <button type="button" className={styles.closeButton} onClick={closeModal} aria-label="닫기">×</button>
            </header>

            <div className={styles.modalBody}>
              {modal === "join" ? (
                <form onSubmit={(event) => {
                  event.preventDefault();
                  previewJoin();
                }}>
                  <label className={styles.fieldLabel}>
                    <span>초대 코드</span>
                    <input
                      value={joinCode}
                      onChange={(event) => setJoinCode(event.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6))}
                      maxLength={6}
                      autoCapitalize="characters"
                      autoComplete="off"
                      placeholder="6자리 코드"
                      aria-label="초대 코드"
                      autoFocus
                    />
                  </label>
                  <div className={styles.privacyNotice}>
                    <strong>참여하면 내 식탁도 함께 보여요</strong>
                    <p>홈에 남긴 사진과 연결한 레시피·저당픽이 이 모임의 멤버에게 자동으로 공유돼요.</p>
                  </div>
                  <div className={styles.modalActions}>
                    <button type="button" className={styles.secondaryButton} onClick={closeModal}>취소</button>
                    <button className={styles.primaryButton} type="submit" disabled={joinCode.length !== 6}>모임 미리보기</button>
                  </div>
                </form>
              ) : created ? (
                <div className={styles.codeResult}>
                  <span className={styles.codeEmoji} aria-hidden="true">{created.room.emoji}</span>
                  <h3>{created.room.name}을 만들었어요</h3>
                  <p>초대 코드는 7일 동안 사용할 수 있어요.</p>
                  <div className={styles.inviteCode}>{created.invite.code}</div>
                  <div className={styles.modalActions}>
                    <button type="button" className={styles.secondaryButton} onClick={copyInvite}>링크 복사</button>
                    <Link className={styles.primaryButton} href={`/rooms/${created.room.id}`}>모임으로 가기</Link>
                  </div>
                </div>
              ) : (
                <form onSubmit={(event) => {
                  event.preventDefault();
                  createRoom();
                }}>
                  <div className={styles.emojiField}>
                    <span>모임 이모지</span>
                    <div className={styles.emojiList}>
                      {emojiOptions.map((option) => (
                        <button type="button" key={option} onClick={() => setEmoji(option)} aria-pressed={emoji === option}>{option}</button>
                      ))}
                    </div>
                  </div>
                  <label className={styles.fieldLabel}>
                    <span>모임 이름</span>
                    <input value={roomName} onChange={(event) => setRoomName(event.target.value)} placeholder="예: 우리집 건강반" maxLength={24} autoFocus />
                  </label>
                  <div className={styles.toggleRow}>
                    <div>
                      <strong>전체 팀 랭킹에 참여할래요</strong>
                      <small>팀 평균 당류와 기록률만 공개돼요.<br />멤버 이름과 식단은 공개되지 않아요.</small>
                    </div>
                    <button
                      type="button"
                      className={`${styles.switch} ${rankingOptIn ? styles.switchOn : ""}`}
                      onClick={() => setRankingOptIn((value) => !value)}
                      aria-pressed={rankingOptIn}
                      aria-label="전체 팀 랭킹 참여"
                    />
                  </div>
                  <div className={styles.modalActions}>
                    <button type="button" className={styles.secondaryButton} onClick={closeModal}>취소</button>
                    <button type="submit" className={styles.primaryButton} disabled={!roomName.trim() || creating}>
                      {creating ? "만드는 중…" : "모임 만들기"}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </section>
        </div>
      )}

      {toast && <div className={styles.toast} role="status">{toast}</div>}
    </main>
  );
}

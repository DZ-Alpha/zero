"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/SystemFeedback";
import styles from "@/components/rooms/Rooms.module.css";
import { members, rooms } from "@/components/rooms/roomData";
import { useAuthSession } from "@/hooks/useAuthSession";

const emojiOptions = ["🌿", "🍚", "🥗", "🥕", "🍋"];

type ConfirmAction =
  | { type: "regenerate" }
  | { type: "transfer"; memberId: string; memberName: string }
  | { type: "remove"; memberId: string; memberName: string }
  | { type: "leave" }
  | { type: "delete" };

function confirmCopy(action: ConfirmAction) {
  if (action.type === "regenerate") {
    return {
      title: "초대 코드를 새로 만들까요?",
      description: "지금 코드는 바로 사용할 수 없게 돼요.",
      confirmLabel: "새 코드 만들기",
      destructive: false,
    };
  }
  if (action.type === "transfer") {
    return {
      title: `${action.memberName}님에게 방장을 넘길까요?`,
      description: "넘긴 뒤에는 일반 멤버가 되며, 모임 삭제와 멤버 관리는 새 방장만 할 수 있어요.",
      confirmLabel: "방장 넘기기",
      destructive: false,
    };
  }
  if (action.type === "remove") {
    return {
      title: `${action.memberName}님을 내보낼까요?`,
      description: "이 멤버는 더 이상 모임 식탁과 기록을 볼 수 없어요.",
      confirmLabel: "내보내기",
      destructive: true,
    };
  }
  if (action.type === "leave") {
    return {
      title: "모임에서 나갈까요?",
      description: "나가면 이 모임의 식탁과 멤버 기록을 더 이상 볼 수 없어요.",
      confirmLabel: "모임 나가기",
      destructive: true,
    };
  }
  return {
    title: "모임을 삭제할까요?",
    description: "모든 멤버가 모임을 볼 수 없게 되며, 삭제한 기록은 되돌릴 수 없어요.",
    confirmLabel: "모임 삭제",
    destructive: true,
  };
}

export function RoomSettings({ roomId }: { roomId: string }) {
  const router = useRouter();
  const { ready: authReady, signedIn } = useAuthSession();
  const room = rooms.find((item) => item.id === roomId);
  const isOwner = room?.role === "owner";
  const initialMembers = useMemo(
    () => members.slice(0, Math.min(room?.members ?? 0, members.length)),
    [room?.members],
  );
  const [memberList, setMemberList] = useState(initialMembers);
  const [name, setName] = useState(room?.name ?? "");
  const [emoji, setEmoji] = useState(room?.emoji ?? "🌿");
  const [rankingOptIn, setRankingOptIn] = useState(room?.rankingOptIn ?? true);
  const [nudgeNotifications, setNudgeNotifications] = useState(true);
  const [activityNotifications, setActivityNotifications] = useState(true);
  const [inviteCode, setInviteCode] = useState(room?.inviteCode ?? "");
  const [deleteText, setDeleteText] = useState("");
  const [confirmAction, setConfirmAction] = useState<ConfirmAction | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");

  useEffect(() => {
    setMemberList(initialMembers);
  }, [initialMembers]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  if (!authReady) {
    return (
      <main className={styles.page}>
        <div className={styles.wrap}>
          <section className={styles.authGate} aria-label="얌로그 확인 중"><span aria-hidden="true" /></section>
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
            <h1>로그인하면<br />모임 설정을 볼 수 있어요.</h1>
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
            <Link className={styles.primaryButton} href="/rooms">내 모임으로 돌아가기</Link>
          </section>
        </div>
      </main>
    );
  }

  const inviteExpiryLabel = new Intl.DateTimeFormat("ko-KR", { month: "long", day: "numeric" })
    .format(new Date(room.inviteExpiresAt));

  async function copyInvite() {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/rooms/join?code=${inviteCode}`);
      setToast("초대 링크를 복사했어요.");
    } catch {
      setToast(`초대 코드 ${inviteCode}를 복사해주세요.`);
    }
  }

  function saveRoomInfo() {
    if (!name.trim()) {
      setToast("모임 이름을 적어주세요.");
      return;
    }
    setName(name.trim());
    setToast("모임 정보를 저장했어요.");
  }

  function saveMySettings() {
    setToast("알림 설정을 저장했어요.");
  }

  function runConfirmedAction() {
    if (!confirmAction) return;
    setBusy(true);
    window.setTimeout(() => {
      if (confirmAction.type === "regenerate") {
        setInviteCode("YAM" + Math.random().toString(36).slice(2, 5).toUpperCase());
        setToast("새 초대 코드를 만들었어요.");
      }
      if (confirmAction.type === "transfer") {
        setToast(`${confirmAction.memberName}님에게 방장을 넘겼어요.`);
      }
      if (confirmAction.type === "remove") {
        setMemberList((current) => current.filter((member) => member.id !== confirmAction.memberId));
        setToast(`${confirmAction.memberName}님을 모임에서 내보냈어요.`);
      }
      if (confirmAction.type === "leave" || confirmAction.type === "delete") {
        router.push("/rooms");
      }
      setBusy(false);
      setConfirmAction(null);
    }, 420);
  }

  const confirmation = confirmAction ? confirmCopy(confirmAction) : null;

  return (
    <main className={styles.page}>
      <div className={`${styles.wrap} ${styles.settingsWrap}`}>
        <header className={styles.settingsHeader}>
          <Link href={`/rooms/${room.id}`} aria-label={`${room.name}으로 돌아가기`}>←</Link>
          <div>
            <p className={styles.eyebrow}>{room.emoji} {room.name}</p>
            <h1>모임 관리</h1>
          </div>
        </header>

        <div className={styles.settingsLayout}>
          <aside className={styles.settingsAside}>
            <a href="#room-info">모임 정보</a>
            <a href="#invite">초대</a>
            <a href="#sharing">알림</a>
            {isOwner && <a href="#members">멤버 관리</a>}
            <a href="#leave">나가기</a>
          </aside>

          <div className={styles.settingsContent}>
            <section className={styles.settingsCard} id="room-info">
              <header>
                <div><p className={styles.eyebrow}>모임 정보</p><h2>{isOwner ? "이름과 랭킹" : "현재 모임"}</h2></div>
                {!isOwner && <span className={styles.roleBadge}>멤버</span>}
              </header>

              {isOwner ? (
                <>
                  <div className={styles.settingsEmojiList} aria-label="모임 이모지">
                    {emojiOptions.map((option) => (
                      <button type="button" key={option} aria-pressed={emoji === option} onClick={() => setEmoji(option)}>{option}</button>
                    ))}
                  </div>
                  <label className={styles.settingsField}>
                    <span>모임 이름</span>
                    <input value={name} maxLength={24} onChange={(event) => setName(event.target.value)} />
                    <small>{name.length} / 24</small>
                  </label>
                  <div className={styles.settingsToggle}>
                    <div><strong>전체 팀 랭킹 참여</strong><span>팀 평균 당류와 기록률만 공개돼요.</span></div>
                    <button type="button" className={`${styles.switch} ${rankingOptIn ? styles.switchOn : ""}`} aria-pressed={rankingOptIn} onClick={() => setRankingOptIn((value) => !value)} />
                  </div>
                  <div className={styles.settingsCardAction}>
                    <button type="button" className={styles.primaryButton} onClick={saveRoomInfo}>변경사항 저장</button>
                  </div>
                </>
              ) : (
                <div className={styles.roomReadOnly}>
                  <span aria-hidden="true">{room.emoji}</span>
                  <div><strong>{room.name}</strong><p>멤버 {room.members}명 · 함께한 지 {room.days}일</p></div>
                </div>
              )}
            </section>

            <section className={styles.settingsCard} id="invite">
              <header><div><p className={styles.eyebrow}>초대</p><h2>친구 초대하기</h2></div></header>
              <div className={styles.invitePanel}>
                <div>
                  <span>초대 코드</span>
                  <strong>{inviteCode}</strong>
                  <small>{inviteExpiryLabel}까지 사용</small>
                </div>
                <div>
                  <button type="button" className={styles.primaryButton} onClick={copyInvite}>링크 복사</button>
                  {isOwner && <button type="button" className={styles.secondaryButton} onClick={() => setConfirmAction({ type: "regenerate" })}>새 코드 만들기</button>}
                </div>
              </div>
            </section>

            <section className={styles.settingsCard} id="sharing">
              <header><div><p className={styles.eyebrow}>내 설정</p><h2>알림</h2></div></header>
              <div className={styles.settingsToggle}>
                <div><strong>콕 찌르기 알림</strong></div>
                <button type="button" className={`${styles.switch} ${nudgeNotifications ? styles.switchOn : ""}`} aria-label="콕 찌르기 알림" aria-pressed={nudgeNotifications} onClick={() => setNudgeNotifications((value) => !value)} />
              </div>
              <div className={styles.settingsToggle}>
                <div><strong>댓글과 반응 알림</strong></div>
                <button type="button" className={`${styles.switch} ${activityNotifications ? styles.switchOn : ""}`} aria-label="댓글과 반응 알림" aria-pressed={activityNotifications} onClick={() => setActivityNotifications((value) => !value)} />
              </div>
              <div className={styles.settingsCardAction}>
                <button type="button" className={styles.primaryButton} onClick={saveMySettings}>알림 저장</button>
              </div>
            </section>

            {isOwner && (
              <section className={styles.settingsCard} id="members">
                <header><div><p className={styles.eyebrow}>멤버</p><h2>{memberList.length}명과 함께하고 있어요</h2></div></header>
                <div className={styles.manageMemberList}>
                  {memberList.map((member, index) => (
                    <article key={member.id}>
                      <span className={styles.avatar} style={{ background: member.color, color: "#18221b" }} aria-hidden="true">{member.avatar}</span>
                      <div><strong>{member.name}</strong><small>{index === 0 ? "방장" : `${member.joined}째 참여 중`}</small></div>
                      {index > 0 && (
                        <div>
                          <button type="button" onClick={() => setConfirmAction({ type: "transfer", memberId: member.id, memberName: member.name })}>방장 넘기기</button>
                          <button type="button" className={styles.dangerTextButton} onClick={() => setConfirmAction({ type: "remove", memberId: member.id, memberName: member.name })}>내보내기</button>
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              </section>
            )}

            <section className={`${styles.settingsCard} ${styles.dangerCard}`} id="leave">
              <header><div><p className={styles.eyebrow}>모임 나가기</p><h2>{isOwner ? "방장 권한을 먼저 확인해요" : "이 모임에서 나가기"}</h2></div></header>
              <div className={styles.dangerRow}>
                <div>
                  <strong>모임 나가기</strong>
                  <p>{isOwner ? "다른 멤버에게 방장을 넘긴 뒤 나갈 수 있어요." : "나가면 이 모임의 식탁을 더 이상 볼 수 없어요."}</p>
                </div>
                <button
                  type="button"
                  onClick={() => isOwner ? setToast("먼저 다른 멤버에게 방장을 넘겨주세요.") : setConfirmAction({ type: "leave" })}
                >
                  모임 나가기
                </button>
              </div>

              {isOwner && (
                <div className={styles.deleteRoomBox}>
                  <div><strong>모임 삭제</strong><p>모임 이름을 입력하면 삭제할 수 있어요.</p></div>
                  <div>
                    <input value={deleteText} onChange={(event) => setDeleteText(event.target.value)} placeholder={room.name} aria-label="삭제할 모임 이름 확인" />
                    <button type="button" disabled={deleteText !== room.name} onClick={() => setConfirmAction({ type: "delete" })}>모임 삭제</button>
                  </div>
                </div>
              )}
            </section>
          </div>
        </div>
      </div>

      {confirmation && confirmAction && (
        <ConfirmDialog
          title={confirmation.title}
          description={confirmation.description}
          confirmLabel={confirmation.confirmLabel}
          destructive={confirmation.destructive}
          busy={busy}
          onConfirm={runConfirmedAction}
          onClose={() => setConfirmAction(null)}
        />
      )}
      {toast && <div className={styles.toast} role="status">{toast}</div>}
    </main>
  );
}

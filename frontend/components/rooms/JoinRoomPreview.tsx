"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import styles from "@/components/rooms/Rooms.module.css";
import { useAuthSession } from "@/hooks/useAuthSession";
import { ApiError } from "@/lib/api/client";
import { getJoinRoomPreview, joinRoom } from "@/lib/api/rooms";
import { JoinRoomPreviewResponse } from "@/lib/rooms/contracts";

export function JoinRoomPreview({ code }: { code: string }) {
  const router = useRouter();
  const { ready: authReady, signedIn, token } = useAuthSession();
  const normalizedCode = code.trim().toUpperCase();

  const [preview, setPreview] = useState<JoinRoomPreviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let active = true;
    setLoading(true);
    setNotFound(false);
    getJoinRoomPreview(token, normalizedCode)
      .then((response) => {
        if (active) setPreview(response);
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
  }, [token, normalizedCode]);

  async function handleJoin() {
    if (!token || joining) return;
    setJoining(true);
    setJoinError(null);
    try {
      const detail = await joinRoom(token, { code: normalizedCode }, crypto.randomUUID());
      router.push(`/rooms/${detail.room.id}`);
    } catch (error) {
      setJoinError(error instanceof ApiError ? error.message : "참여하지 못했어요. 다시 시도해주세요.");
      setJoining(false);
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
            <h1>로그인하면<br />초대받은 모임을 볼 수 있어요.</h1>
            <p>참여하기 전에 어떤 모임인지 먼저 확인해요.</p>
            <div className={styles.authGateActions}>
              <Link className={styles.primaryButton} href="/login">로그인하기</Link>
              <Link className={styles.secondaryButton} href="/signup">회원가입하기</Link>
            </div>
          </section>
        </div>
      </main>
    );
  }

  if (notFound || !preview) {
    return (
      <main className={styles.joinPage}>
        <section className={`${styles.joinCard} ${styles.invalidInvite}`}>
          <span aria-hidden="true">🔗</span>
          <p className={styles.eyebrow}>얌로그 초대</p>
          <h1>초대 코드를 확인해주세요</h1>
          <p>코드가 다르거나 7일의 초대 기간이 끝났을 수 있어요.</p>
          <Link className={styles.primaryButton} href="/rooms">내 모임으로 돌아가기</Link>
        </section>
      </main>
    );
  }

  const { room, activityInLastSevenDays, canJoin, blockedReason } = preview;

  return (
    <main className={styles.joinPage}>
      <section className={styles.joinCard}>
          <p className={styles.eyebrow}>얌로그 초대 · {normalizedCode}</p>
        <div className={styles.joinIdentity}>
          <span className={styles.roomEmoji} aria-hidden="true">{room.emoji}</span>
          <div>
            <h1>{room.name}</h1>
            <p>{room.daysSinceStart}일째 꾸준히 기록 중인 모임이에요.</p>
          </div>
        </div>

        <div className={styles.joinPreview}>
          <div><small>멤버</small><strong>{room.memberCount}명</strong></div>
          <div><small>최근 7일 활동</small><strong>{activityInLastSevenDays}회</strong></div>
          <div><small>전체 랭킹</small><strong>{room.rank ? `${room.rank}위` : "집계 전"}</strong></div>
        </div>

        <div className={styles.privacyNotice}>
          <strong>참여하면 오늘 식탁을 함께 봐요</strong>
          <p>홈에 남긴 식사와 연결한 레시피·저당픽이 이 모임에도 함께 보여요. 전체 랭킹에는 팀 평균과 기록률만 공개돼요.</p>
        </div>

        {!canJoin && (
          <div className={styles.joinLimitNotice} role="status">
            {blockedReason === "already_joined" ? (
              <>
                <strong>이미 참여 중인 모임이에요</strong>
                <p>모임 화면에서 바로 확인할 수 있어요.</p>
              </>
            ) : (
              <>
                <strong>지금은 새 모임에 참여할 수 없어요</strong>
                <p>함께하는 모임 하나를 나가면 이 모임에 참여할 수 있어요.</p>
              </>
            )}
          </div>
        )}

        {joinError && (
          <div className={styles.joinLimitNotice} role="alert">
            <strong>{joinError}</strong>
          </div>
        )}

        <div className={styles.joinActions}>
          <Link className={styles.secondaryButton} href="/rooms">돌아가기</Link>
          {blockedReason === "already_joined" ? (
            <Link className={styles.primaryButton} href={`/rooms/${room.id}`}>모임으로 가기</Link>
          ) : !canJoin ? (
            <button type="button" className={styles.primaryButton} disabled>모임 3개 사용 중</button>
          ) : (
            <button type="button" className={styles.primaryButton} disabled={joining} onClick={handleJoin}>
              {joining ? "참여하는 중…" : "모임 참여하기"}
            </button>
          )}
        </div>
      </section>
    </main>
  );
}

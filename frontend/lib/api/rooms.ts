import { apiRequest } from "@/lib/api/client";
import type {
  CreateRoomInput,
  CreateRoomResponse,
  CursorPage,
  JoinRoomInput,
  JoinRoomPreviewResponse,
  MemberCalendarDay,
  ReportRoomContentInput,
  RoomComment,
  RoomDetailResponse,
  RoomInvite,
  RoomSettingsResponse,
  RoomsHomeResponse,
  UpdateRoomInput,
  UpdateRoomNotificationsInput,
} from "@/lib/rooms/contracts";

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

function writeHeaders(token: string, idempotencyKey?: string): HeadersInit {
  return {
    ...authHeaders(token),
    ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
  };
}

export function getRoomsHome(token: string) {
  return apiRequest<RoomsHomeResponse>("/rooms", {
    headers: authHeaders(token),
  });
}

export function getMoreRoomActivities(token: string, cursor: string) {
  return apiRequest<Pick<RoomsHomeResponse, "recentActivities" | "recentActivitiesNextCursor">>(
    `/rooms/activities?cursor=${encodeURIComponent(cursor)}`,
    { headers: authHeaders(token) },
  );
}

export function getMoreTeamRanking(token: string, cursor: string) {
  return apiRequest<Pick<RoomsHomeResponse, "weeklyRanking" | "weeklyRankingNextCursor">>(
    `/rooms/ranking?cursor=${encodeURIComponent(cursor)}`,
    { headers: authHeaders(token) },
  );
}

export function getRoomDetail(token: string, roomId: string, recordDate?: string) {
  const query = recordDate ? `?date=${encodeURIComponent(recordDate)}` : "";
  return apiRequest<RoomDetailResponse>(`/rooms/${encodeURIComponent(roomId)}${query}`, {
    headers: authHeaders(token),
  });
}

export function getRoomSettings(token: string, roomId: string) {
  return apiRequest<RoomSettingsResponse>(`/rooms/${encodeURIComponent(roomId)}/settings`, {
    headers: authHeaders(token),
  });
}

export function updateRoom(token: string, roomId: string, input: UpdateRoomInput) {
  return apiRequest<RoomSettingsResponse>(`/rooms/${encodeURIComponent(roomId)}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(input),
  });
}

export function createRoom(token: string, input: CreateRoomInput, idempotencyKey?: string) {
  return apiRequest<CreateRoomResponse>("/rooms", {
    method: "POST",
    headers: writeHeaders(token, idempotencyKey),
    body: JSON.stringify(input),
  });
}

export function getJoinRoomPreview(token: string, code: string) {
  return apiRequest<JoinRoomPreviewResponse>(`/rooms/join-preview?code=${encodeURIComponent(code)}`, {
    headers: authHeaders(token),
  });
}

export function joinRoom(token: string, input: JoinRoomInput, idempotencyKey?: string) {
  return apiRequest<RoomDetailResponse>("/rooms/join", {
    method: "POST",
    headers: writeHeaders(token, idempotencyKey),
    body: JSON.stringify(input),
  });
}

export function updateRoomNotifications(token: string, roomId: string, input: UpdateRoomNotificationsInput) {
  return apiRequest<UpdateRoomNotificationsInput>(`/rooms/${encodeURIComponent(roomId)}/notifications`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(input),
  });
}

export function getRoomInvite(token: string, roomId: string) {
  return apiRequest<RoomInvite>(`/rooms/${encodeURIComponent(roomId)}/invite`, {
    headers: authHeaders(token),
  });
}

export function regenerateRoomInvite(token: string, roomId: string, idempotencyKey?: string) {
  return apiRequest<RoomInvite>(`/rooms/${encodeURIComponent(roomId)}/invite`, {
    method: "POST",
    headers: writeHeaders(token, idempotencyKey),
  });
}

export function deleteRoomInvite(token: string, roomId: string) {
  return apiRequest<{ status: "deleted" }>(`/rooms/${encodeURIComponent(roomId)}/invite`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export function nudgeRoomMember(token: string, roomId: string, memberId: string, mealType: string, idempotencyKey?: string) {
  return apiRequest<{ status: "sent"; retryAfterSeconds: number }>(`/rooms/${encodeURIComponent(roomId)}/nudges`, {
    method: "POST",
    headers: writeHeaders(token, idempotencyKey),
    body: JSON.stringify({ memberId, mealType }),
  });
}

export function getRoomMealComments(token: string, roomId: string, mealId: string, cursor?: string) {
  const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  return apiRequest<CursorPage<RoomComment>>(
    `/rooms/${encodeURIComponent(roomId)}/meals/${encodeURIComponent(mealId)}/comments${query}`,
    { headers: authHeaders(token) },
  );
}

export function addRoomMealComment(token: string, roomId: string, mealId: string, message: string, idempotencyKey?: string) {
  return apiRequest<RoomComment>(
    `/rooms/${encodeURIComponent(roomId)}/meals/${encodeURIComponent(mealId)}/comments`,
    {
      method: "POST",
      headers: writeHeaders(token, idempotencyKey),
      body: JSON.stringify({ message }),
    },
  );
}

export function deleteRoomMealComment(token: string, roomId: string, mealId: string, commentId: string) {
  return apiRequest<{ status: "deleted" }>(
    `/rooms/${encodeURIComponent(roomId)}/meals/${encodeURIComponent(mealId)}/comments/${encodeURIComponent(commentId)}`,
    {
      method: "DELETE",
      headers: authHeaders(token),
    },
  );
}

export function toggleRoomMealReaction(token: string, roomId: string, mealId: string) {
  return apiRequest<{ reacted: boolean; reactionCount: number }>(
    `/rooms/${encodeURIComponent(roomId)}/meals/${encodeURIComponent(mealId)}/reaction`,
    {
      method: "PUT",
      headers: authHeaders(token),
    },
  );
}

export function getRoomMemberCalendar(token: string, roomId: string, memberId: string, year: number, month: number) {
  const query = new URLSearchParams({ year: String(year), month: String(month) });
  return apiRequest<{ days: MemberCalendarDay[] }>(
    `/rooms/${encodeURIComponent(roomId)}/members/${encodeURIComponent(memberId)}/calendar?${query}`,
    { headers: authHeaders(token) },
  );
}

export function transferRoomOwnership(token: string, roomId: string, memberId: string) {
  return apiRequest<{ status: "transferred" }>(
    `/rooms/${encodeURIComponent(roomId)}/members/${encodeURIComponent(memberId)}/ownership`,
    {
      method: "PUT",
      headers: authHeaders(token),
    },
  );
}

export function removeRoomMember(token: string, roomId: string, memberId: string) {
  return apiRequest<{ status: "removed" }>(
    `/rooms/${encodeURIComponent(roomId)}/members/${encodeURIComponent(memberId)}`,
    {
      method: "DELETE",
      headers: authHeaders(token),
    },
  );
}

export function leaveRoom(token: string, roomId: string) {
  return apiRequest<{ status: "left" }>(`/rooms/${encodeURIComponent(roomId)}/membership`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export function deleteRoom(token: string, roomId: string) {
  return apiRequest<{ status: "deleted" }>(`/rooms/${encodeURIComponent(roomId)}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export function reportRoomContent(token: string, roomId: string, input: ReportRoomContentInput) {
  return apiRequest<{ status: "received" }>(`/rooms/${encodeURIComponent(roomId)}/reports`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
  });
}

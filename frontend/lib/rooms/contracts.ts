export const MAX_ROOM_COUNT = 3;

export const MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"] as const;

export type MealType = (typeof MEAL_TYPES)[number];
export type RoomRole = "owner" | "member";
export type MealSource = "photo" | "recipe" | "product";

export type RoomPermissions = {
  canEditRoom: boolean;
  canInvite: boolean;
  canManageMembers: boolean;
  canTransferOwnership: boolean;
  canDeleteRoom: boolean;
  canLeaveRoom: boolean;
};

export type RoomSummary = {
  id: string;
  name: string;
  emoji: string;
  role: RoomRole;
  memberCount: number;
  recordedTodayCount: number;
  daysSinceStart: number;
  averageSugar: number;
  monthlyRecordRate: number;
  myParticipationDays: number;
  rankingOptIn: boolean;
  rank: number | null;
  rankingEligibility: {
    eligible: boolean;
    missingMemberCount: number;
    remainingDays: number;
  };
  permissions: RoomPermissions;
};

export type RoomActivityItem = {
  id: string;
  roomId: string;
  roomName: string;
  roomEmoji: string;
  memberName: string;
  memberAvatar: string;
  mealType: MealType;
  imageUrl: string | null;
  message: string;
};

export type TeamRankingItem = {
  id: string;
  name: string;
  emoji: string;
  memberCount: number;
  recordRate: number;
  averageSugar: number;
  rankMovement: number;
  isMine: boolean;
};

export type RoomMember = {
  id: string;
  name: string;
  avatarText: string;
  role: RoomRole;
  isMe: boolean;
  joinedDays: number;
  recordCount: number;
  recordRate: number;
  averageSugar: number;
  streakDays: number;
  color: string;
};

export type ConnectedMealItem = {
  id: string;
  source: MealSource;
  name: string;
  imageUrl?: string | null;
};

export type OrderedPhoto = {
  source: MealSource;
  imageUrl: string;
};

export type MealRecord = {
  id: string;
  roomId: string;
  memberId: string;
  memberName: string;
  memberAvatar: string;
  mealType: MealType;
  title: string;
  sugar: number;
  calories: number;
  uploadedPhotoUrls: string[];
  connectedItems: ConnectedMealItem[];
  // 비전(사진) → 레시피 → 저당픽 순으로 이미 정렬된 통합 리스트 - 여러 소스가
  // 섞여 있을 때 이걸 그대로 순회하면 넘겨보기 캐러셀에 전부 나온다.
  orderedPhotos: OrderedPhoto[];
  recordDate: string;
  reactionCount: number;
  commentCount: number;
  reactedByMe: boolean;
};

export type MemberMealSlot = {
  memberId: string;
  mealType: MealType;
  hasRecord: boolean;
  nutrition: {
    sugar: number;
    calories: number;
  } | null;
  record: MealRecord | null;
  nudge: {
    canSend: boolean;
    sentByMe: boolean;
    retryAfterSeconds: number | null;
  };
};

export type MealCover = {
  imageUrl: string | null;
  source: MealSource | null;
};

export function resolveMealCover(record: Pick<MealRecord, "uploadedPhotoUrls" | "connectedItems">): MealCover {
  const uploadedPhoto = record.uploadedPhotoUrls.find(Boolean);
  if (uploadedPhoto) return { imageUrl: uploadedPhoto, source: "photo" };

  const recipe = record.connectedItems.find((item) => item.source === "recipe" && item.imageUrl);
  if (recipe?.imageUrl) return { imageUrl: recipe.imageUrl, source: "recipe" };

  const product = record.connectedItems.find((item) => item.source === "product" && item.imageUrl);
  if (product?.imageUrl) return { imageUrl: product.imageUrl, source: "product" };

  return { imageUrl: null, source: null };
}

export type RoomsHomeResponse = {
  rooms: RoomSummary[];
  recentActivities: RoomActivityItem[];
  weeklyRanking: TeamRankingItem[];
  activeTeamCount: number;
  maxRoomCount: number;
  recentActivitiesNextCursor: string | null;
  weeklyRankingNextCursor: string | null;
};

export type RoomBadge = {
  emoji: string;
  name: string;
  ownerId: string;
  ownerName: string;
  copy: string;
};

export type RoomDetailResponse = {
  room: RoomSummary;
  members: RoomMember[];
  serverDate: string;
  timezone: string;
  todayMealSlots: MemberMealSlot[];
  badges: RoomBadge[];
};

export type CreateRoomInput = {
  name: string;
  emoji: string;
  rankingOptIn: boolean;
};

export type CreateRoomResponse = {
  room: RoomSummary;
  invite: RoomInvite;
};

export type JoinRoomPreviewResponse = {
  room: Pick<RoomSummary, "id" | "name" | "emoji" | "memberCount" | "daysSinceStart" | "rank">;
  activityInLastSevenDays: number;
  inviteExpiresAt: string;
  canJoin: boolean;
  blockedReason: "room_limit" | "already_joined" | null;
};

export type JoinRoomInput = {
  code: string;
};

export type RoomInvite = {
  code: string;
  joinUrl: string;
  expiresAt: string;
};

export type RoomSettingsResponse = {
  room: RoomSummary;
  notifications: {
    nudges: boolean;
    commentsAndReactions: boolean;
  };
  activeInvite: RoomInvite | null;
  members: RoomMember[];
};

export type UpdateRoomInput = {
  name?: string;
  emoji?: string;
  rankingOptIn?: boolean;
};

export type UpdateRoomNotificationsInput = {
  nudges: boolean;
  commentsAndReactions: boolean;
};

export type RoomComment = {
  id: string;
  authorId: string;
  authorName: string;
  message: string;
  createdAt: string;
  canDelete: boolean;
};

export type CursorPage<T> = {
  items: T[];
  nextCursor: string | null;
};

export type MemberCalendarDay = {
  date: string;
  recordCount: number;
};

export type ReportRoomContentInput = {
  targetType: "meal" | "comment";
  targetId: string;
  reason: "spam" | "inappropriate" | "privacy" | "other";
};

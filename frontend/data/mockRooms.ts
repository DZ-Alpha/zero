import type { RoomDetailResponse, RoomsHomeResponse } from "@/lib/rooms/contracts";

const room = {
  id: "mock-dangdang-table",
  name: "당당한 한 끼",
  emoji: "🌿",
  role: "owner" as const,
  memberCount: 3,
  recordedTodayCount: 2,
  daysSinceStart: 12,
  averageSugar: 24.8,
  monthlyRecordRate: 78,
  myParticipationDays: 9,
  rankingOptIn: true,
  rank: 8,
  rankingEligibility: { eligible: true, missingMemberCount: 0, remainingDays: 0 },
  permissions: {
    canEditRoom: true,
    canInvite: true,
    canManageMembers: true,
    canTransferOwnership: true,
    canDeleteRoom: true,
    canLeaveRoom: false,
  },
};

export const mockRoomsHome: RoomsHomeResponse = {
  rooms: [room],
  recentActivities: [
    { id: "mock-activity-minji", roomId: room.id, roomName: room.name, roomEmoji: room.emoji, memberName: "민지", memberAvatar: "민", mealType: "lunch", imageUrl: "/product-data/lalasweet-caramel-popcorn.jpg", message: "점심 사진을 남겼어요" },
  ],
  todayActivities: [
    { id: "mock-activity-me", roomId: room.id, roomName: room.name, roomEmoji: room.emoji, memberName: "나", memberAvatar: "나", mealType: "breakfast", imageUrl: "/product-data/lotte-zero-popcorn.png", message: "아침 식탁을 채웠어요" },
    { id: "mock-activity-minji", roomId: room.id, roomName: room.name, roomEmoji: room.emoji, memberName: "민지", memberAvatar: "민", mealType: "lunch", imageUrl: "/product-data/lalasweet-caramel-popcorn.jpg", message: "점심 사진을 남겼어요" },
  ],
  weeklyRanking: [{ id: room.id, name: room.name, emoji: room.emoji, memberCount: 3, recordRate: 78, averageSugar: 24.8, rankMovement: 1, isMine: true }],
  activeTeamCount: 126,
  maxRoomCount: 3,
  recentActivitiesNextCursor: null,
  weeklyRankingNextCursor: null,
  incomingNudges: [],
};

const members = [
  { id: "mock-me", name: "나", avatarText: "나", role: "owner" as const, isMe: true, joinedDays: 12, recordCount: 18, recordRate: 82, averageSugar: 23.4, streakDays: 4, color: "#ddecce" },
  { id: "mock-minji", name: "민지", avatarText: "민", role: "member" as const, isMe: false, joinedDays: 12, recordCount: 16, recordRate: 76, averageSugar: 25.1, streakDays: 3, color: "#f6e5d8" },
  { id: "mock-jun", name: "준", avatarText: "준", role: "member" as const, isMe: false, joinedDays: 9, recordCount: 12, recordRate: 69, averageSugar: 26, streakDays: 1, color: "#dde9ef" },
];

export const mockRoomDetail: RoomDetailResponse = {
  room,
  members,
  serverDate: "2026-08-09",
  timezone: "Asia/Seoul",
  todayMealSlots: members.flatMap((member) => (["breakfast", "lunch", "dinner", "snack"] as const).map((mealType) => ({
    memberId: member.id,
    mealType,
    hasRecord: (member.id === "mock-me" && mealType === "breakfast") || (member.id === "mock-minji" && mealType === "lunch"),
    nutrition: (member.id === "mock-me" && mealType === "breakfast") ? { sugar: 4.2, calories: 360 } : (member.id === "mock-minji" && mealType === "lunch") ? { sugar: 8.1, calories: 510 } : null,
    record: (member.id === "mock-me" && mealType === "breakfast") ? {
      id: "mock-meal-me", roomId: room.id, memberId: member.id, memberName: member.name, memberAvatar: member.avatarText, mealType, title: "그릭요거트와 견과", sugar: 4.2, calories: 360, uploadedPhotoUrls: ["/product-data/lotte-zero-popcorn.png"], connectedItems: [], orderedPhotos: [{ source: "photo" as const, imageUrl: "/product-data/lotte-zero-popcorn.png", name: "아침 사진" }], recordDate: "2026-08-09", reactionCount: 2, commentCount: 0, reactedByMe: false,
    } : (member.id === "mock-minji" && mealType === "lunch") ? {
      id: "mock-meal-minji", roomId: room.id, memberId: member.id, memberName: member.name, memberAvatar: member.avatarText, mealType, title: "가벼운 점심", sugar: 8.1, calories: 510, uploadedPhotoUrls: ["/product-data/lalasweet-caramel-popcorn.jpg"], connectedItems: [], orderedPhotos: [{ source: "photo" as const, imageUrl: "/product-data/lalasweet-caramel-popcorn.jpg", name: "점심 사진" }], recordDate: "2026-08-09", reactionCount: 3, commentCount: 1, reactedByMe: true,
    } : null,
    nudge: { canSend: !member.isMe, refused: false, sentByMe: false, retryAfterSeconds: null },
  }))),
  badges: [{ emoji: "🌱", name: "첫 식탁", ownerId: "mock-me", ownerName: "나", copy: "함께 기록을 시작했어요" }],
  incomingNudges: [],
};

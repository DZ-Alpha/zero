export type Room = {
  id: string;
  name: string;
  emoji: string;
  members: number;
  recordedToday: number;
  days: number;
  averageSugar: number;
  recordRate: number;
  myDays: number;
  rank?: number;
  rankingOptIn: boolean;
  inviteCode: string;
  inviteExpiresAt: string;
  role: "owner" | "member";
};

export type TeamRank = {
  id: string;
  name: string;
  emoji: string;
  members: number;
  recordRate: number;
  averageSugar: number;
  movement: number;
  mine?: boolean;
};

export type RoomActivity = {
  id: string;
  roomId: string;
  roomName: string;
  roomEmoji: string;
  member: string;
  avatar: string;
  meal: "아침" | "점심" | "저녁" | "간식";
  image: string;
  copy: string;
};

export const rooms: Room[] = [
  {
    id: "green-table",
    name: "초록 식탁",
    emoji: "🌿",
    members: 6,
    recordedToday: 6,
    days: 42,
    averageSugar: 31.8,
    recordRate: 82,
    myDays: 19,
    rank: 3,
    rankingOptIn: true,
    inviteCode: "DG7K2A",
    inviteExpiresAt: "2026-08-01T23:59:59+09:00",
    role: "owner",
  },
  {
    id: "family-health",
    name: "우리집 건강반",
    emoji: "🍚",
    members: 4,
    recordedToday: 4,
    days: 18,
    averageSugar: 35.2,
    recordRate: 76,
    myDays: 14,
    rankingOptIn: false,
    inviteCode: "HOME24",
    inviteExpiresAt: "2026-07-29T23:59:59+09:00",
    role: "member",
  },
  {
    id: "lunch-club",
    name: "점심은 제대로",
    emoji: "🥗",
    members: 3,
    recordedToday: 3,
    days: 4,
    averageSugar: 28.4,
    recordRate: 67,
    myDays: 4,
    rankingOptIn: true,
    inviteCode: "LUNCH7",
    inviteExpiresAt: "2026-07-30T23:59:59+09:00",
    role: "member",
  },
];

export const teamRanking: TeamRank[] = [
  { id: "slow-sugar", name: "천천히 달게", emoji: "🐢", members: 12, recordRate: 94, averageSugar: 24.6, movement: 1 },
  { id: "salad-lab", name: "샐러드 연구소", emoji: "🥬", members: 8, recordRate: 91, averageSugar: 27.1, movement: 0 },
  { id: "green-table", name: "초록 식탁", emoji: "🌿", members: 6, recordRate: 82, averageSugar: 31.8, movement: 2, mine: true },
  { id: "morning-six", name: "아침 여섯 시", emoji: "🌤️", members: 9, recordRate: 86, averageSugar: 33.2, movement: -1 },
  { id: "steady-bite", name: "꾸준한 한입", emoji: "🥄", members: 17, recordRate: 80, averageSugar: 34.5, movement: 3 },
  { id: "office-lunch", name: "직장인 점심단", emoji: "💼", members: 24, recordRate: 78, averageSugar: 35.7, movement: 0 },
  { id: "rice-is-power", name: "밥심으로", emoji: "🍙", members: 11, recordRate: 76, averageSugar: 36.1, movement: -2 },
];

export const mealPhotos = [
  {
    id: "meal-minji",
    member: "민지",
    avatar: "민",
    meal: "점심",
    name: "애호박 당근라페 덮밥",
    tags: ["현미", "애호박", "당근"],
    sugar: 8.0,
    calories: 266,
    image: "https://recipe1.ezmember.co.kr/cache/recipe/2026/04/14/55c3f4357e7622a1ac1145b0301cbc851.jpg?w=1000",
    photoCount: 3,
    coverSource: "사진으로 남긴 식사",
    reactions: 4,
    items: [
      { source: "사진", name: "덮밥 사진" },
      { source: "레시피", name: "애호박 당근라페 덮밥" },
      { source: "저당픽", name: "현미밥 1팩" },
    ],
  },
  {
    id: "meal-junho",
    member: "준호",
    avatar: "준",
    meal: "아침",
    name: "아침 샐러드와 달걀",
    tags: ["달걀", "토마토", "채소"],
    sugar: 7.4,
    calories: 340,
    image: "https://recipe1.ezmember.co.kr/cache/recipe/2026/06/16/9b85be24c05057a56f46e19079e6ca8a1.jpg",
    photoCount: 2,
    coverSource: "사진으로 남긴 식사",
    reactions: 7,
    items: [
      { source: "사진", name: "아침 접시 사진" },
      { source: "저당픽", name: "구운 달걀 2개" },
    ],
  },
  {
    id: "meal-yuri",
    member: "유리",
    avatar: "유",
    meal: "간식",
    name: "당근 케이크 한 조각",
    tags: ["당근", "견과", "요거트"],
    sugar: 9.8,
    calories: 178,
    image: "https://recipe1.ezmember.co.kr/cache/recipe/2026/05/18/783e4c4c7ce0b194b23d638bf43d51c31.png?w=1000",
    photoCount: 1,
    coverSource: "레시피에서 가져온 사진",
    reactions: 3,
    items: [
      { source: "레시피", name: "저당 당근 케이크" },
      { source: "저당픽", name: "무가당 요거트" },
    ],
  },
] as const;

export const roomActivity: RoomActivity[] = [
  {
    id: "activity-minji",
    roomId: "green-table",
    roomName: "초록 식탁",
    roomEmoji: "🌿",
    member: "민지",
    avatar: "민",
    meal: "점심",
    image: "https://recipe1.ezmember.co.kr/cache/recipe/2026/04/14/55c3f4357e7622a1ac1145b0301cbc851.jpg?w=1000",
    copy: "점심 사진을 남겼어요",
  },
  {
    id: "activity-junho",
    roomId: "green-table",
    roomName: "초록 식탁",
    roomEmoji: "🌿",
    member: "준호",
    avatar: "준",
    meal: "아침",
    image: "https://recipe1.ezmember.co.kr/cache/recipe/2026/06/16/9b85be24c05057a56f46e19079e6ca8a1.jpg",
    copy: "아침 식탁을 채웠어요",
  },
  {
    id: "activity-yuri",
    roomId: "green-table",
    roomName: "초록 식탁",
    roomEmoji: "🌿",
    member: "유리",
    avatar: "유",
    meal: "간식",
    image: "https://recipe1.ezmember.co.kr/cache/recipe/2026/05/18/783e4c4c7ce0b194b23d638bf43d51c31.png?w=1000",
    copy: "간식 사진을 올렸어요",
  },
  {
    id: "activity-family-1",
    roomId: "family-health",
    roomName: "우리집 건강반",
    roomEmoji: "🍚",
    member: "엄마",
    avatar: "엄",
    meal: "저녁",
    image: "https://recipe1.ezmember.co.kr/cache/recipe/2026/05/26/5a04f882582fc89a3742cde65c036b5e1.jpg",
    copy: "저녁 식사를 남겼어요",
  },
  {
    id: "activity-family-2",
    roomId: "family-health",
    roomName: "우리집 건강반",
    roomEmoji: "🍚",
    member: "아빠",
    avatar: "아",
    meal: "점심",
    image: "https://recipe1.ezmember.co.kr/cache/recipe/2026/02/14/1f4b9c5910db525344f5b7c2e04a92611.jpg",
    copy: "점심 한 끼를 기록했어요",
  },
  {
    id: "activity-family-3",
    roomId: "family-health",
    roomName: "우리집 건강반",
    roomEmoji: "🍚",
    member: "지우",
    avatar: "지",
    meal: "간식",
    image: "https://recipe1.ezmember.co.kr/cache/recipe/2025/04/30/dc6835b54d468673680f18134d03db071.jpg",
    copy: "간식을 함께 나눴어요",
  },
  {
    id: "activity-lunch-1",
    roomId: "lunch-club",
    roomName: "점심은 제대로",
    roomEmoji: "🥗",
    member: "소라",
    avatar: "소",
    meal: "점심",
    image: "https://recipe1.ezmember.co.kr/cache/recipe/2025/05/06/776b468aaef45abbed920ad5e89e6c851.jpg",
    copy: "오늘 점심을 공유했어요",
  },
  {
    id: "activity-lunch-2",
    roomId: "lunch-club",
    roomName: "점심은 제대로",
    roomEmoji: "🥗",
    member: "도윤",
    avatar: "도",
    meal: "점심",
    image: "https://recipe1.ezmember.co.kr/cache/recipe/2025/05/06/1fa6acb9629d1dcec832c9257a8b013b1.jpg",
    copy: "점심 사진을 남겼어요",
  },
  {
    id: "activity-lunch-3",
    roomId: "lunch-club",
    roomName: "점심은 제대로",
    roomEmoji: "🥗",
    member: "하린",
    avatar: "하",
    meal: "점심",
    image: "https://recipe1.ezmember.co.kr/cache/recipe/2026/04/14/55c3f4357e7622a1ac1145b0301cbc851.jpg?w=1000",
    copy: "점심 식탁을 채웠어요",
  },
];

export const members = [
  { id: "member-me", name: "나", avatar: "나", joined: "42일", records: 38, rate: 90, sugar: 29.4, streak: 8, color: "#b8ee36" },
  { id: "member-minji", name: "민지", avatar: "민", joined: "42일", records: 35, rate: 83, sugar: 27.8, streak: 5, color: "#9ed8c4" },
  { id: "member-junho", name: "준호", avatar: "준", joined: "39일", records: 31, rate: 79, sugar: 33.1, streak: 3, color: "#f2ce67" },
  { id: "member-yuri", name: "유리", avatar: "유", joined: "31일", records: 24, rate: 77, sugar: 31.5, streak: 6, color: "#c9b9e8" },
  { id: "member-seoyeon", name: "서연", avatar: "서", joined: "24일", records: 18, rate: 75, sugar: 36.2, streak: 0, color: "#efb7a8" },
  { id: "member-hyunwoo", name: "현우", avatar: "현", joined: "18일", records: 11, rate: 61, sugar: 39.4, streak: 0, color: "#b9c8b3" },
] as const;

export const badges = [
  { emoji: "🌱", name: "개근왕", owner: "나", copy: "이번 주 7일 모두 기록" },
  { emoji: "🍚", name: "든든이", owner: "준호", copy: "한 끼 기록을 가장 많이 남김" },
  { emoji: "👩‍🍳", name: "레시피왕", owner: "민지", copy: "레시피로 5번 기록" },
  { emoji: "🥕", name: "채소한입", owner: "유리", copy: "채소가 들어간 식사를 6번 기록" },
] as const;

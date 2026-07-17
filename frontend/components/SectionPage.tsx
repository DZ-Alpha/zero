import { ChatPanel } from "@/components/ChatPanel";
import { ProductArt } from "@/components/ProductArt";
import { Shell } from "@/components/Shell";

type Kind = "search" | "diet" | "recipes" | "product" | "mypage" | "chat";

const copy: Record<Exclude<Kind,"chat">,{eyebrow:string;title:string;description:string}> = {
  search:{eyebrow:"ZERO FOOD FINDER",title:"건강정보에 맞는 제품 찾기",description:"제품명이나 브랜드로 찾고, 제로슈거·저당·알레르기 정보로 좁혀보세요."},
  diet:{eyebrow:"DIET LOG",title:"식단 기록과 변화",description:"사진으로 남긴 식단을 날짜별로 보고, 당류와 칼로리 흐름을 함께 확인하세요."},
  recipes:{eyebrow:"LOW SUGAR RECIPE",title:"재료 하나를 바꿔 가볍게",description:"평소 먹는 메뉴를 고르면 당류를 낮출 수 있는 재료와 차이를 보여드려요."},
  product:{eyebrow:"PRODUCT DETAIL",title:"제로슈거 다크 초코바",description:"표시 문구보다 실제 영양성분과 원재료를 기준으로 이해하기 쉽게 정리했습니다."},
  mypage:{eyebrow:"MY DANGDANG",title:"나의 선택 기준",description:"관심 카테고리, 알레르기, 활동 정보를 관리하면 추천이 더 정확해집니다."},
};

export function SectionPage({kind}:{kind:Kind}) {
  if(kind === "chat") return <Shell><main className="sub-main"><section className="sub-hero"><div className="wrap"><p className="eyebrow">DANGDANG GUIDE</p><h1>성분이 어려울 때 물어보세요</h1><p>일반 영양 질문부터 제품 사진과 성분표 검색까지 한 곳에서 이어집니다.</p></div></section><div className="sub-content wrap"><ChatPanel /></div></main></Shell>;
  const info=copy[kind];
  return <Shell><main className="sub-main"><section className="sub-hero"><div className="wrap"><p className="eyebrow">{info.eyebrow}</p><h1>{info.title}</h1><p>{info.description}</p></div></section><section className="sub-content wrap">{kind === "search" && <Search />}{kind === "diet" && <Diet />}{kind === "recipes" && <Recipes />}{kind === "product" && <Product />}{kind === "mypage" && <MyPage />}</section></main></Shell>;
}

function Search(){return <><div className="tool-row"><input placeholder="제품명, 브랜드, 성분으로 검색"/><button>당류 낮은순</button></div><div className="info-grid">{[["LIME ZERO","라임 제로 스파클링","당류 0g"],["PLAIN GREEK","플레인 그릭요거트","당류 3g"],["DARK CACAO","제로슈거 다크 초코바","당류 1g"]].map(([label,name,meta],i)=><article className="product-card" key={name}><ProductArt label={label} tone={i===0?"lime":i===1?"stone":"sand"}/><h3>{name}</h3><p>{meta} · 알레르기 기준 확인</p></article>)}</div></>}
function Diet(){return <div className="stat-layout"><div className="calendar"><b>2026년 7월</b><div className="calendar-grid">{Array.from({length:31},(_,i)=><span className={i+1===15?"active":""} key={i}>{i+1}</span>)}</div><button className="primary-button" style={{height:40,marginTop:20}}>식단 사진 기록 +</button></div><div className="stat-panel"><b>최근 7일 당류 변화</b><div className="bar-chart">{[42,55,38,64,48,72,55].map((h,i)=><i key={i} style={{height:`${h}%`}}/>)}</div><div className="info-grid" style={{marginTop:20}}><article className="info-card"><h3>평균 당류</h3><strong>24g</strong></article><article className="info-card"><h3>목표 안의 날</h3><strong>5일</strong></article><article className="info-card"><h3>가장 낮은 날</h3><strong>18g</strong></article></div></div></div>}
function Recipes(){return <div className="info-grid">{[["비빔면","설탕 대신 알룰로스 소스","당류 11g ↓"],["프렌치토스트","저당 통밀빵과 무가당 우유","당류 8g ↓"],["떡볶이","곤약떡과 저당 고추장","당류 14g ↓"]].map(([name,desc,value])=><article className="info-card" key={name}><h3>{name}</h3><p>{desc}</p><strong>{value}</strong></article>)}</div>}
function Product(){return <div className="stat-layout"><ProductArt label="DARK CACAO" tone="sand"/><div><div className="info-card"><p className="eyebrow">성분 한줄요약</p><h3>달지만, 당류 부담은 낮은 편이에요.</h3><p>1봉 기준 당류 1g, 단백질 12g입니다. 우유 알레르기가 있다면 원재료를 꼭 확인하세요.</p></div><div className="info-grid" style={{marginTop:16}}><article className="info-card"><h3>당류</h3><strong>1g</strong></article><article className="info-card"><h3>열량</h3><strong>165kcal</strong></article><article className="info-card"><h3>단백질</h3><strong>12g</strong></article></div></div></div>}
function MyPage(){return <div className="info-grid"><article className="info-card"><h3>기본 정보</h3><p>26세 · 여성 · 활동량 보통</p><strong>수정하기 ↗</strong></article><article className="info-card"><h3>관심 기준</h3><p>제로슈거 · 저당 · 고단백</p><strong>3개 선택</strong></article><article className="info-card"><h3>주의 성분</h3><p>우유 · 땅콩</p><strong>2개 등록</strong></article></div>}

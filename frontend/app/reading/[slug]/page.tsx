import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Shell } from "@/components/Shell";
import { getReadingArticle, readingArticles } from "@/data/reading";

export function generateStaticParams() {
  return readingArticles.map((article) => ({ slug: article.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const article = getReadingArticle((await params).slug);
  return {
    title: article?.title ?? "당당 읽을거리",
    description: article?.summary ?? "제품과 레시피를 고를 때 필요한 기준을 읽어보세요.",
  };
}

export default async function ReadingPage({ params }: { params: Promise<{ slug: string }> }) {
  const article = getReadingArticle((await params).slug);
  if (!article) notFound();

  return (
    <Shell>
      <main className="reading-detail page-wrap">
        <article className="reading-detail-article wrap">
          <Link className="reading-detail-back" href="/">← 오늘 화면으로</Link>

          <header className="reading-detail-hero">
            <div className="reading-detail-meta"><span>{article.category}</span><span>{article.readMinutes}분 읽기</span></div>
            <h1>{article.title}</h1>
            <p>{article.summary}</p>
            <div className="reading-detail-cover" aria-hidden="true"><strong>{article.cover}</strong><small>{article.coverCaption}</small></div>
          </header>

          <div className="reading-detail-layout">
            <div className="reading-detail-body">
              {article.sections.map((section, index) => (
                <section key={section.heading}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <h2>{section.heading}</h2>
                    {section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
                    {section.bullets && <ul>{section.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}</ul>}
                  </div>
                </section>
              ))}
            </div>

            <aside className="reading-detail-aside">
              <div className="reading-takeaway">
                <p>이 글의 핵심</p>
                <ul>{article.takeaways.map((takeaway) => <li key={takeaway}>{takeaway}</li>)}</ul>
              </div>
              <div className="reading-checklist">
                <p>다음 선택 전에</p>
                <ul>{article.checklist.map((item) => <li key={item}><i aria-hidden="true" />{item}</li>)}</ul>
              </div>
            </aside>
          </div>

          <footer className="reading-detail-footer">
            <div className="reading-sources">
              <p>근거와 참고 자료</p>
              <ul>{article.sources.map((source) => <li key={source.label}>{source.href ? <a href={source.href} target="_blank" rel="noreferrer">{source.label} ↗</a> : <span>{source.label}</span>}</li>)}</ul>
              <small>이 글은 제품 선택을 돕는 참고 정보이며 개인의 건강 상태를 진단하거나 치료를 대신하지 않습니다.</small>
            </div>
            <div className="reading-next-action"><span>읽은 기준을 바로 써보세요</span><strong>{article.coverCaption}</strong><Link href={article.cta.href}>{article.cta.label} <i aria-hidden="true">→</i></Link></div>
          </footer>
        </article>
      </main>
    </Shell>
  );
}

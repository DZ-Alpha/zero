import { mkdir, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";

// 백엔드에 아직 파일 수신/스토리지 API가 없어서(명세 RC-0101이 img={IMG_URL}만 받음)
// 임시로 프론트 서버가 파일을 보관하고 URL을 만들어준다. 스토리지 방식이 확정되면
// 이 라우트만 실제 업로드(프리사인드 URL 등)로 교체하면 된다.
const allowedTypes = new Map([
  ["image/jpeg", ".jpg"],
  ["image/png", ".png"],
  ["image/webp", ".webp"],
]);
const maxBytes = 10 * 1024 * 1024;

export async function POST(request: NextRequest) {
  const form = await request.formData();
  const file = form.get("file");

  if (!(file instanceof File) || file.size === 0) {
    return NextResponse.json({ detail: "업로드할 사진 파일이 없어요." }, { status: 422 });
  }
  const extension = allowedTypes.get(file.type);
  if (!extension) {
    return NextResponse.json({ detail: "JPG, PNG, WEBP 형식의 사진만 올릴 수 있어요." }, { status: 422 });
  }
  if (file.size > maxBytes) {
    return NextResponse.json({ detail: "사진 크기는 10MB 이하여야 해요." }, { status: 422 });
  }

  const directory = path.join(process.cwd(), "public", "uploads");
  await mkdir(directory, { recursive: true });
  const fileName = `diet-${Date.now()}-${randomUUID().slice(0, 8)}${extension}`;
  await writeFile(path.join(directory, fileName), Buffer.from(await file.arrayBuffer()));

  const publicBaseUrl = (process.env.PUBLIC_APP_URL || request.nextUrl.origin).replace(/\/$/, "");
  return NextResponse.json({ url: `${publicBaseUrl}/uploads/${fileName}` });
}

// iOS 카메라 기본 포맷 - 브라우저가 <img>/<canvas>에서 못 읽으므로 선택 즉시
// JPEG로 변환한다. 확장자도 같이 보는 이유는 사파리가 종종 file.type을
// "application/octet-stream"이나 빈 문자열로 주기 때문.
export function isHeicFile(file: File): boolean {
  const type = file.type.toLowerCase();
  if (type === "image/heic" || type === "image/heif") return true;
  return /\.hei[cf]$/i.test(file.name);
}

export async function convertHeicToJpeg(file: File): Promise<File> {
  const heic2any = (await import("heic2any")).default;
  const result = await heic2any({ blob: file, toType: "image/jpeg", quality: 0.9 });
  const blob = Array.isArray(result) ? result[0] : result;
  const newName = file.name.replace(/\.hei[cf]$/i, "") + ".jpg";
  return new File([blob], newName, { type: "image/jpeg" });
}

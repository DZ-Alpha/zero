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

const VISION_MAX_EDGE = 1600;
const VISION_JPEG_QUALITY = 0.82;
const VISION_SKIP_OPTIMIZE_BYTES = 1024 * 1024;

function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("image decode failed"));
    };
    image.src = url;
  });
}

function canvasToJpeg(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => blob ? resolve(blob) : reject(new Error("image encode failed")),
      "image/jpeg",
      VISION_JPEG_QUALITY,
    );
  });
}

/** Reduce camera photos before upload so the Vision request does not carry multi-MB base64. */
export async function optimizePhotoForVision(file: File): Promise<File> {
  const image = await loadImage(file);
  const maxEdge = Math.max(image.naturalWidth, image.naturalHeight);
  if (file.size <= VISION_SKIP_OPTIMIZE_BYTES && maxEdge <= VISION_MAX_EDGE) return file;

  const scale = Math.min(1, VISION_MAX_EDGE / maxEdge);
  const width = Math.max(1, Math.round(image.naturalWidth * scale));
  const height = Math.max(1, Math.round(image.naturalHeight * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("canvas unavailable");
  context.fillStyle = "#fff";
  context.fillRect(0, 0, width, height);
  context.drawImage(image, 0, 0, width, height);
  const blob = await canvasToJpeg(canvas);

  if (blob.size >= file.size) return file;
  const name = file.name.replace(/\.[^.]+$/, "") + ".jpg";
  return new File([blob], name, { type: "image/jpeg", lastModified: file.lastModified });
}

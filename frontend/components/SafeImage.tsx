"use client";

import { useEffect, useState } from "react";

type SafeImageProps = {
  src?: string | null;
  alt: string;
  className?: string;
  fallbackLabel?: string;
  loading?: "eager" | "lazy";
};

export function SafeImage({
  src,
  alt,
  className,
  fallbackLabel = "이미지 준비 중",
  loading = "lazy",
}: SafeImageProps) {
  const [failed, setFailed] = useState(!src);

  useEffect(() => {
    setFailed(!src);
  }, [src]);

  if (failed || !src) {
    return (
      <span className={`safe-image-fallback${className ? ` ${className}` : ""}`} role="img" aria-label={`${alt} 이미지가 준비 중이에요`}>
        <i aria-hidden="true" />
        <b>{fallbackLabel}</b>
      </span>
    );
  }

  return <img src={src} alt={alt} className={className} loading={loading} decoding="async" onError={() => setFailed(true)} />;
}

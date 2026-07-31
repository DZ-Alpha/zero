import type { Metadata } from "next";
import { SignupSuccessClient } from "@/components/SignupSuccessClient";

export const metadata: Metadata = {
  title: "회원가입 완료",
  robots: { index: false, follow: false },
};

export default function Page() {
  return <SignupSuccessClient />;
}

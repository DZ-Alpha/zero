import { AuthFrame } from "@/components/AuthFrame";
import { SignupTargetForm } from "@/components/SignupTargetForm";

export default async function Page({ searchParams }: { searchParams: Promise<{ provider?: string }> }) {
  const { provider = "google" } = await searchParams;
  return (
    <AuthFrame asideTitle="무리하지 않는 하루 목표부터 시작해요.">
      <SignupTargetForm provider={provider} />
    </AuthFrame>
  );
}

import { AuthFrame } from "@/components/AuthFrame";
import { SignupProfileForm } from "@/components/SignupProfileForm";

type ProfileSearchParams = {
  provider?: string;
  name?: string;
  nickname?: string;
  userName?: string;
  birthDate?: string;
  birth_date?: string;
  birthYear?: string;
  birthyear?: string;
  birthday?: string;
  email?: string;
};

export default async function Page({ searchParams }: { searchParams: Promise<ProfileSearchParams> }) {
  const { provider = "google", name, nickname, userName, birthDate, birth_date: birthDateSnake, birthYear, birthyear, birthday, email } = await searchParams;
  const socialBirthYear = birthYear ?? birthyear;
  const birthdayDigits = birthday?.replace(/\D/g, "") ?? "";
  const combinedBirthDate = birthDate
    ?? birthDateSnake
    ?? (birthdayDigits.length === 8 ? birthday : socialBirthYear && birthday ? `${socialBirthYear}${birthday}` : undefined);

  return (
    <AuthFrame asideTitle={'내게 맞는 기준,\n함께 만들어요.'}>
      <SignupProfileForm
        provider={provider}
        oauthProfile={{ name: name ?? nickname ?? userName, birthDate: combinedBirthDate, email }}
      />
    </AuthFrame>
  );
}

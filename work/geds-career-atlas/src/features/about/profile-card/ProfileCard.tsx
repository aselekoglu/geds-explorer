import portrait from "../assets/ata-speaking-2.png"
import { SignatureDeveloperCard, type SignatureDeveloperCardPointer, type SignatureDeveloperCardProps } from "../../../components/signature-developer-card/SignatureDeveloperCard"

export const DEVELOPER_URL = "https://aselekoglu.github.io/?utm_source=geds-career-atlas&utm_medium=profile-card&utm_campaign=about-developer"
export const DEVELOPER_NAME = "Ata Selekoglu"
export const DEVELOPER_TITLE = "Developer"
export const PROFILE_CARD_DRAG_THRESHOLD = 7
export type ProfileCardPointer = SignatureDeveloperCardPointer
export type ProfileCardProps = Omit<SignatureDeveloperCardProps, "profile">

/** GEDS content adapter for the reusable signature developer card. */
export function ProfileCard(props: ProfileCardProps) {
  return <SignatureDeveloperCard profile={{ name: DEVELOPER_NAME, title: DEVELOPER_TITLE, href: DEVELOPER_URL, portraitSrc: portrait, fallbackInitials: "AS" }} {...props} />
}

export default ProfileCard

import portrait from "../assets/ata-speaking-2.png"
import { SignatureLanyard, type SignatureLanyardProps } from "../../../components/signature-developer-card/SignatureLanyard"
import ProfileCard from "../profile-card/ProfileCard"

export type LanyardProps = Omit<SignatureLanyardProps, "renderCard" | "portraitSrc">

/** GEDS adapter that retains the existing About route API. */
export default function Lanyard(props: LanyardProps) {
  return <SignatureLanyard
    {...props}
    portraitSrc={portrait}
    renderCard={cardProps => <ProfileCard {...cardProps} />}
  />
}

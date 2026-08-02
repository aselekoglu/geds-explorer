# Signature Developer Card

Portable React/React-Bits-style developer card with an accessible DOM link and an optional physics lanyard. It is source-local by design: copy this directory into another React app instead of adding a monorepo or publishing a package.

## Dependencies

`react`, `three`, `@react-three/fiber`, `@react-three/drei`, `@react-three/rapier`, and `meshline` are required only for `SignatureLanyard`. `SignatureDeveloperCard` itself only needs React.

## Use

```tsx
import { SignatureDeveloperCard, SignatureLanyard } from "./components/signature-developer-card"
import portrait from "./assets/me.png"

const profile = { name: "Ada Lovelace", title: "Developer", href: "https://example.com", portraitSrc: portrait }

<SignatureLanyard
  portraitSrc={portrait}
  renderCard={cardProps => <SignatureDeveloperCard profile={profile} {...cardProps} />}
/>
```

`SignatureLanyard` waits for `portraitSrc` to decode before starting physics, respects reduced motion, and renders the supplied card in static mode when WebGL is unavailable. The included `assets/lanyard-card.glb` is the default model; a custom `cardModelSrc` must expose `clip`, `clamp`, and `metal` nodes/materials. `lanyardImage`, camera position, gravity, FOV, and width are configurable props.

For a different card design, keep the `renderCard` drag callbacks on the link/card root so the lanyard can preserve click-versus-drag behavior.

/* eslint-disable react/no-unknown-property */
import { useEffect, useMemo, useRef, useState } from "react"
import { Canvas, extend, useFrame, useThree, type ThreeElement } from "@react-three/fiber"
import { Environment, Html, Lightformer, useGLTF, useTexture } from "@react-three/drei"
import {
  BallCollider,
  CuboidCollider,
  Physics,
  RigidBody,
  useRopeJoint,
  useSphericalJoint,
  type RapierRigidBody,
  type RigidBodyProps,
} from "@react-three/rapier"
import { MeshLineGeometry, MeshLineMaterial } from "meshline"
import type { GLTF } from "three-stdlib"
import * as THREE from "three"
import ProfileCard, { type ProfileCardPointer } from "../profile-card/ProfileCard"
import portrait from "../assets/ata-speaking-2.png"
import cardGLB from "./card.glb"
import lanyard from "./lanyard.png"
import "./Lanyard.css"

extend({ MeshLineGeometry, MeshLineMaterial })

declare module "@react-three/fiber" {
  interface ThreeElements {
    meshLineGeometry: ThreeElement<typeof MeshLineGeometry>
    meshLineMaterial: ThreeElement<typeof MeshLineMaterial>
  }
}

const PROFILE_DISTANCE_FACTOR = 10
const PROFILE_HALF_WIDTH = 3.577
const PROFILE_HALF_HEIGHT = 4.977
const PROFILE_CENTER_Y = -3.844
const ATTACHMENT_Y = 1.5
const METAL_GROUP_Y = -1.2
const DESKTOP_ORIGIN_Y = 9.2
const MOBILE_SCALE = 0.63

export type LanyardProps = {
  position?: [number, number, number]
  gravity?: [number, number, number]
  fov?: number
  transparent?: boolean
  lanyardImage?: string | null
  lanyardWidth?: number
}

type BandProps = {
  maxSpeed?: number
  minSpeed?: number
  isMobile?: boolean
  lanyardImage?: string | null
  lanyardWidth?: number
}

type CardGLTF = GLTF & {
  nodes: {
    clip: THREE.Mesh
    clamp: THREE.Mesh
  }
  materials: {
    metal: THREE.MeshStandardMaterial
  }
}

type SmoothedRigidBody = RapierRigidBody & { lerped?: THREE.Vector3 }
type BandMesh = THREE.Mesh<MeshLineGeometry, MeshLineMaterial>
type DragBounds = { offsetX: number, offsetY: number, width: number, height: number }

function supportsWebGL() {
  if (typeof document === "undefined") return false
  try {
    const canvas = document.createElement("canvas")
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"))
  } catch {
    return false
  }
}

function useReducedMotion() {
  const [reducedMotion, setReducedMotion] = useState(() =>
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false
  )

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return
    const query = window.matchMedia("(prefers-reduced-motion: reduce)")
    const update = () => setReducedMotion(query.matches)
    query.addEventListener("change", update)
    return () => query.removeEventListener("change", update)
  }, [])

  return reducedMotion
}

function useImageReady(src: string, enabled: boolean) {
  const [ready, setReady] = useState(() => !enabled)

  useEffect(() => {
    if (!enabled) {
      setReady(true)
      return
    }

    let mounted = true
    const image = new Image()
    const complete = () => {
      const decoded = typeof image.decode === "function" ? image.decode().catch(() => undefined) : Promise.resolve()
      void decoded.finally(() => { if (mounted) setReady(true) })
    }

    setReady(false)
    image.addEventListener("load", complete, { once: true })
    image.addEventListener("error", complete, { once: true })
    image.src = src
    if (image.complete) complete()

    return () => {
      mounted = false
      image.removeEventListener("load", complete)
      image.removeEventListener("error", complete)
    }
  }, [enabled, src])

  return ready
}

function useLanyardActivity(target: React.RefObject<HTMLDivElement | null>) {
  const [intersecting, setIntersecting] = useState(true)
  const [visible, setVisible] = useState(() => typeof document === "undefined" || document.visibilityState !== "hidden")

  useEffect(() => {
    const element = target.current
    if (!element || typeof IntersectionObserver === "undefined") return
    const observer = new IntersectionObserver(entries => setIntersecting(entries[0]?.isIntersecting ?? true), { rootMargin: "80px" })
    observer.observe(element)
    return () => observer.disconnect()
  }, [target])

  useEffect(() => {
    const update = () => setVisible(document.visibilityState !== "hidden")
    document.addEventListener("visibilitychange", update)
    return () => document.removeEventListener("visibilitychange", update)
  }, [])

  return intersecting && visible
}

export default function Lanyard({
  position = [0, 0, 30],
  gravity = [0, -40, 0],
  fov = 20,
  transparent = true,
  lanyardImage = null,
  lanyardWidth = 1,
}: LanyardProps) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [isMobile, setIsMobile] = useState(() => typeof window !== "undefined" && window.innerWidth < 768)
  const [webGLAvailable] = useState(supportsWebGL)
  const reducedMotion = useReducedMotion()
  const photoReady = useImageReady(portrait, webGLAvailable && !reducedMotion)
  const isActive = useLanyardActivity(wrapperRef)

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768)
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])

  if (reducedMotion || !webGLAvailable) {
    return <div
      ref={wrapperRef}
      className="lanyard-wrapper lanyard-wrapper--static"
      data-camera-distance={position[2]}
      data-render-mode={reducedMotion ? "reduced-motion" : "webgl-fallback"}
    >
      <ProfileCard interactive={false} />
    </div>
  }

  if (!photoReady) {
    return <div
      ref={wrapperRef}
      className="lanyard-wrapper"
      data-camera-distance={position[2]}
      data-render-mode="loading-photo"
      data-photo-ready="false"
      aria-busy="true"
    />
  }

  return <div ref={wrapperRef} className="lanyard-wrapper" data-camera-distance={position[2]} data-render-mode="physics" data-photo-ready="true">
    <Canvas
      camera={{ position, fov }}
      dpr={[1, isMobile ? 1.5 : 2]}
      frameloop={isActive ? "always" : "never"}
      gl={{ alpha: transparent }}
      onCreated={({ gl }) => gl.setClearColor(new THREE.Color(0x000000), transparent ? 0 : 1)}
    >
      <ambientLight intensity={Math.PI} />
      <Physics gravity={gravity} paused={!isActive} timeStep={isMobile ? 1 / 30 : 1 / 60}>
        <Band
          isMobile={isMobile}
          lanyardImage={lanyardImage}
          lanyardWidth={lanyardWidth}
        />
      </Physics>
      <Environment blur={0.75}>
        <Lightformer intensity={2} color="white" position={[0, -1, 5]} rotation={[0, 0, Math.PI / 3]} scale={[100, 0.1, 1]} />
        <Lightformer intensity={3} color="white" position={[-1, -1, 1]} rotation={[0, 0, Math.PI / 3]} scale={[100, 0.1, 1]} />
        <Lightformer intensity={3} color="white" position={[1, 1, 1]} rotation={[0, 0, Math.PI / 3]} scale={[100, 0.1, 1]} />
        <Lightformer intensity={10} color="white" position={[-10, 0, 14]} rotation={[0, Math.PI / 2, Math.PI / 3]} scale={[100, 10, 1]} />
      </Environment>
    </Canvas>
  </div>
}

function Band({
  maxSpeed = 50,
  minSpeed = 0,
  isMobile = false,
  lanyardImage = null,
  lanyardWidth = 1,
}: BandProps) {
  const band = useRef<BandMesh>(null!)
  const fixed = useRef<RapierRigidBody>(null!)
  const j1 = useRef<SmoothedRigidBody>(null!)
  const j2 = useRef<SmoothedRigidBody>(null!)
  const j3 = useRef<RapierRigidBody>(null!)
  const card = useRef<RapierRigidBody>(null!)
  const vec = useMemo(() => new THREE.Vector3(), [])
  const ang = useMemo(() => new THREE.Vector3(), [])
  const rot = useMemo(() => new THREE.Vector3(), [])
  const dir = useMemo(() => new THREE.Vector3(), [])
  const dragPointer = useRef<ProfileCardPointer | null>(null)
  const dragBounds = useRef<DragBounds | null>(null)
  const dragPlaneZ = useRef(0)
  const segmentProps: RigidBodyProps = { type: "dynamic", canSleep: true, colliders: false, angularDamping: 4, linearDamping: 4 }
  const { nodes, materials } = useGLTF(cardGLB) as unknown as CardGLTF
  const texture = useTexture(lanyardImage || lanyard)
  const { camera, gl } = useThree()
  const cardScale = isMobile ? MOBILE_SCALE : 1
  const originX = isMobile ? 2.5 : 4.5
  const profileCenterY = ATTACHMENT_Y + (PROFILE_CENTER_Y - ATTACHMENT_Y) * cardScale
  const metalGroupY = ATTACHMENT_Y + (METAL_GROUP_Y - ATTACHMENT_Y) * cardScale

  const [curve] = useState(() => new THREE.CatmullRomCurve3([
    new THREE.Vector3(),
    new THREE.Vector3(),
    new THREE.Vector3(),
    new THREE.Vector3(),
  ]))
  const [dragged, drag] = useState<false | THREE.Vector3>(false)

  useRopeJoint(fixed, j1, [[0, 0, 0], [0, 0, 0], 1])
  useRopeJoint(j1, j2, [[0, 0, 0], [0, 0, 0], 1])
  useRopeJoint(j2, j3, [[0, 0, 0], [0, 0, 0], 1])
  useSphericalJoint(j3, card, [[0, 0, 0], [0, 1.5, 0]])

  const pointerToWorld = (pointer: ProfileCardPointer, planeZ: number) => {
    const rect = gl.domElement.getBoundingClientRect()
    if (rect.width <= 0 || rect.height <= 0) return null
    vec.set(
      ((pointer.clientX - rect.left) / rect.width) * 2 - 1,
      -((pointer.clientY - rect.top) / rect.height) * 2 + 1,
      0.5,
    ).unproject(camera)
    dir.copy(vec).sub(camera.position).normalize()
    if (Math.abs(dir.z) < 0.0001) return null
    return vec.copy(camera.position).add(dir.multiplyScalar((planeZ - camera.position.z) / dir.z))
  }

  const keepCardInWrapper = (pointer: ProfileCardPointer): ProfileCardPointer => {
    const bounds = dragBounds.current
    if (!bounds) return pointer
    const wrapper = gl.domElement.getBoundingClientRect()
    const maxLeft = Math.max(wrapper.left, wrapper.right - bounds.width)
    const maxTop = Math.max(wrapper.top, wrapper.bottom - bounds.height)
    const cardLeft = THREE.MathUtils.clamp(pointer.clientX - bounds.offsetX, wrapper.left, maxLeft)
    const cardTop = THREE.MathUtils.clamp(pointer.clientY - bounds.offsetY, wrapper.top, maxTop)
    return {
      ...pointer,
      clientX: cardLeft + bounds.offsetX,
      clientY: cardTop + bounds.offsetY,
    }
  }

  const handleDragStart = (pointer: ProfileCardPointer) => {
    const element = gl.domElement.parentElement?.querySelector<HTMLElement>(".profile-card")
    const bounds = element?.getBoundingClientRect()
    dragBounds.current = bounds
      ? { offsetX: pointer.clientX - bounds.left, offsetY: pointer.clientY - bounds.top, width: bounds.width, height: bounds.height }
      : null
    const translation = card.current.translation()
    dragPlaneZ.current = translation.z
    const boundedPointer = keepCardInWrapper(pointer)
    const worldPointer = pointerToWorld(boundedPointer, dragPlaneZ.current)
    if (!worldPointer) return
    dragPointer.current = boundedPointer
    drag(new THREE.Vector3().copy(worldPointer).sub(new THREE.Vector3(translation.x, translation.y, translation.z)))
  }

  const stopDrag = () => {
    dragPointer.current = null
    dragBounds.current = null
    drag(false)
  }

  useFrame((state, delta) => {
    if (dragged && dragPointer.current) {
      const worldPointer = pointerToWorld(dragPointer.current, dragPlaneZ.current)
      ;[card, j1, j2, j3, fixed].forEach(ref => ref.current?.wakeUp())
      if (worldPointer) {
        card.current?.setNextKinematicTranslation({
          x: worldPointer.x - dragged.x,
          y: worldPointer.y - dragged.y,
          z: worldPointer.z - dragged.z,
        })
      }
    }
    if (fixed.current) {
      ;[j1, j2].forEach(ref => {
        const current = ref.current
        const translation = current.translation()
        if (!current.lerped) current.lerped = new THREE.Vector3().copy(translation as THREE.Vector3)
        const clampedDistance = Math.max(0.1, Math.min(1, current.lerped.distanceTo(translation as THREE.Vector3)))
        current.lerped.lerp(translation as THREE.Vector3, delta * (minSpeed + clampedDistance * (maxSpeed - minSpeed)))
      })
      curve.points[0].copy(j3.current.translation() as THREE.Vector3)
      curve.points[1].copy(j2.current.lerped!)
      curve.points[2].copy(j1.current.lerped!)
      curve.points[3].copy(fixed.current.translation() as THREE.Vector3)
      band.current.geometry.setPoints(curve.getPoints(isMobile ? 16 : 32))
      const angularVelocity = card.current.angvel()
      const rotation = card.current.rotation()
      ang.set(angularVelocity.x, angularVelocity.y, angularVelocity.z)
      rot.set(rotation.x, rotation.y, rotation.z)
      card.current.setAngvel({ x: ang.x, y: ang.y - rot.y * 0.25, z: ang.z }, true)
    }
  })

  curve.curveType = "chordal"
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping

  return <>
    <group position={[originX, DESKTOP_ORIGIN_Y, 0]}>
      <RigidBody ref={fixed} {...segmentProps} type="fixed" />
      <RigidBody position={[0.5, 0, 0]} ref={j1} {...segmentProps}><BallCollider args={[0.1]} /></RigidBody>
      <RigidBody position={[1, 0, 0]} ref={j2} {...segmentProps}><BallCollider args={[0.1]} /></RigidBody>
      <RigidBody position={[1.5, 0, 0]} ref={j3} {...segmentProps}><BallCollider args={[0.1]} /></RigidBody>
      <RigidBody position={[2, 0, 0]} ref={card} {...segmentProps} type={dragged ? "kinematicPosition" : "dynamic"}>
        <CuboidCollider
          args={[PROFILE_HALF_WIDTH * cardScale, PROFILE_HALF_HEIGHT * cardScale, 0.04]}
          position={[0, profileCenterY, 0]}
        />
        <group
          scale={2.25 * cardScale}
          position={[0, metalGroupY, -0.05]}
        >
          <mesh geometry={nodes.clip.geometry} material={materials.metal} material-roughness={0.3} />
          <mesh geometry={nodes.clamp.geometry} material={materials.metal} />
        </group>
        <Html
          transform
          position={[0, profileCenterY, 0.04]}
          distanceFactor={PROFILE_DISTANCE_FACTOR * cardScale}
          pointerEvents="auto"
          wrapperClass="lanyard-profile-host"
          className="lanyard-profile-content"
          zIndexRange={[40, 1]}
        >
          <ProfileCard
            onDragStart={handleDragStart}
            onDragMove={pointer => { dragPointer.current = keepCardInWrapper(pointer) }}
            onDragEnd={stopDrag}
            onDragCancel={stopDrag}
          />
        </Html>
      </RigidBody>
    </group>
    <mesh ref={band}>
      <meshLineGeometry />
      <meshLineMaterial
        args={[{ resolution: new THREE.Vector2(1000, isMobile ? 2000 : 1000) }]}
        color="white"
        depthTest={false}
        resolution={isMobile ? [1000, 2000] : [1000, 1000]}
        useMap={1}
        map={texture}
        repeat={[-4, 1]}
        lineWidth={lanyardWidth * cardScale}
      />
    </mesh>
  </>
}

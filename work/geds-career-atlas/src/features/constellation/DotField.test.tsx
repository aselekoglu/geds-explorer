import { render } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { DotField } from "./DotField"

it("coalesces pointer updates at 60fps, then stops until the field is dirty again",()=>{
  const frames:Array<FrameRequestCallback>=[];const request=vi.fn((callback:FrameRequestCallback)=>{frames.push(callback);return frames.length})
  const intersections:Array<(entries:IntersectionObserverEntry[])=>void>=[]
  class TestIntersectionObserver { constructor(callback:(entries:IntersectionObserverEntry[])=>void){intersections.push(callback)} observe(){} disconnect(){} unobserve(){} }
  class TestResizeObserver { constructor(_:ResizeObserverCallback){} observe(){} disconnect(){} unobserve(){} }
  const context={setTransform:vi.fn(),clearRect:vi.fn(),beginPath:vi.fn(),moveTo:vi.fn(),arc:vi.fn(),fill:vi.fn()} as unknown as CanvasRenderingContext2D
  const getContext=vi.spyOn(HTMLCanvasElement.prototype,"getContext").mockReturnValue(context)
  const previousRequest=window.requestAnimationFrame,previousCancel=window.cancelAnimationFrame,previousIntersection=window.IntersectionObserver,previousResize=window.ResizeObserver
  Object.assign(window,{requestAnimationFrame:request,cancelAnimationFrame:vi.fn(),IntersectionObserver:TestIntersectionObserver,ResizeObserver:TestResizeObserver})
  const {container,unmount}=render(<div className="constellation-stage"><DotField bulgeStrength={58} dotSpacing={18} cursorRadius={600} waveAmplitude={1} glowRadius={110}/></div>)
  frames.shift()?.(100)
  expect(request).toHaveBeenCalledTimes(1)
  container.querySelector(".constellation-stage")!.dispatchEvent(new PointerEvent("pointermove",{clientX:10,clientY:10,bubbles:true}))
  expect(request).toHaveBeenCalledTimes(2)
  frames.shift()?.(110)
  expect(request).toHaveBeenCalledTimes(3)
  frames.shift()?.(120)
  expect(request).toHaveBeenCalledTimes(3)
  container.querySelector(".constellation-stage")!.dispatchEvent(new PointerEvent("pointermove",{clientX:14,clientY:14,bubbles:true}))
  expect(request).toHaveBeenCalledTimes(4)
  intersections[0]([{isIntersecting:false} as IntersectionObserverEntry])
  const pausedCalls=request.mock.calls.length
  frames.shift()?.(160)
  expect(request.mock.calls.length).toBe(pausedCalls)
  intersections[0]([{isIntersecting:true} as IntersectionObserverEntry])
  expect(request.mock.calls.length).toBeGreaterThan(pausedCalls)
  Object.defineProperty(document,"hidden",{value:true,configurable:true});document.dispatchEvent(new Event("visibilitychange"));frames.shift()?.(180)
  const hiddenCalls=request.mock.calls.length
  Object.defineProperty(document,"hidden",{value:false,configurable:true});document.dispatchEvent(new Event("visibilitychange"))
  expect(request.mock.calls.length).toBeGreaterThan(hiddenCalls)
  unmount();getContext.mockRestore();Object.assign(window,{requestAnimationFrame:previousRequest,cancelAnimationFrame:previousCancel,IntersectionObserver:previousIntersection,ResizeObserver:previousResize})
})

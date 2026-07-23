import { useEffect, useRef } from "react"

type DotFieldProps = { bulgeStrength:number; dotSpacing:number; cursorRadius:number; waveAmplitude:number; glowRadius:number }

export function DotField({bulgeStrength,dotSpacing,cursorRadius,waveAmplitude,glowRadius}:DotFieldProps){
  const canvasRef=useRef<HTMLCanvasElement>(null)
  const pointer=useRef({x:0,y:0,active:false})
  useEffect(()=>{
    const canvas=canvasRef.current, stage=canvas?.closest<HTMLElement>(".constellation-stage"), context=canvas?.getContext("2d")
    if(!canvas||!stage||!context)return
    const reduced=window.matchMedia?.("(prefers-reduced-motion: reduce)").matches??false
    let visible=true, hidden=document.hidden, disposed=false, staticPainted=false, dirty=true, raf:number|undefined
    let width=1,height=1,dpr=1,color="#3b7c80"
    const updateMetrics=()=>{const rect=stage.getBoundingClientRect();width=Math.max(1,rect.width);height=Math.max(1,rect.height);dpr=Math.min(window.devicePixelRatio||1,2);color=getComputedStyle(stage).getPropertyValue("--accent").trim()||"#3b7c80";const pixelWidth=Math.round(width*dpr),pixelHeight=Math.round(height*dpr);if(canvas.width!==pixelWidth||canvas.height!==pixelHeight){canvas.width=pixelWidth;canvas.height=pixelHeight;canvas.style.width=`${width}px`;canvas.style.height=`${height}px`};staticPainted=false;dirty=true}
    const schedule=()=>{if(!disposed&&!hidden&&visible&&raf===undefined&&dirty&&(!reduced||!staticPainted))raf=requestAnimationFrame(draw)}
    const draw=(now:number)=>{raf=undefined
      if(disposed||hidden||!visible||(reduced&&staticPainted)||!dirty)return
      dirty=false
      context.setTransform(dpr,0,0,dpr,0,0);context.clearRect(0,0,width,height);context.fillStyle=color;context.globalAlpha=.25;context.beginPath()
      const current=pointer.current,time=reduced?0:now/1000
      for(let y=dotSpacing/2;y<height;y+=dotSpacing)for(let x=dotSpacing/2;x<width;x+=dotSpacing){
        const dx=current.active?x-current.x:0,dy=current.active?y-current.y:0,distance=current.active?Math.hypot(dx,dy):Infinity
        const influence=Math.max(0,1-distance/cursorRadius), direction=distance>0?1/distance:0
        const wave=influence?Math.sin(distance*.04-time*3)*waveAmplitude*influence:0
        const push=(influence*influence*bulgeStrength)+wave
        const px=x+dx*direction*push,py=y+dy*direction*push
        context.moveTo(px+.75,py);context.arc(px,py,.75+Math.max(0,1-distance/glowRadius)*.65,0,Math.PI*2)
      }
      context.fill();context.globalAlpha=1;staticPainted=reduced
    }
    const onMove=(event:PointerEvent)=>{const rect=stage.getBoundingClientRect();pointer.current={x:event.clientX-rect.left,y:event.clientY-rect.top,active:true};dirty=true;schedule()}
    const onLeave=()=>{pointer.current.active=false;dirty=true;schedule()}
    const onVisibility=()=>{hidden=document.hidden;if(!hidden){staticPainted=false;dirty=true;schedule()}}
    const intersection=new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;if(visible){staticPainted=false;dirty=true;schedule()}},{threshold:.01})
    const resize=new ResizeObserver(()=>{updateMetrics();schedule()})
    const theme=new MutationObserver(()=>{updateMetrics();schedule()})
    updateMetrics();intersection.observe(stage);resize.observe(stage);theme.observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});stage.addEventListener("pointermove",onMove,{passive:true});stage.addEventListener("pointerleave",onLeave,{passive:true});document.addEventListener("visibilitychange",onVisibility);schedule()
    return()=>{disposed=true;if(raf!==undefined)cancelAnimationFrame(raf);intersection.disconnect();resize.disconnect();theme.disconnect();stage.removeEventListener("pointermove",onMove);stage.removeEventListener("pointerleave",onLeave);document.removeEventListener("visibilitychange",onVisibility)}
  },[bulgeStrength,cursorRadius,dotSpacing,glowRadius,waveAmplitude])
  return <div className="dot-field" data-testid="dot-field" data-bulge-strength={bulgeStrength} data-dot-spacing={dotSpacing} data-cursor-radius={cursorRadius} data-wave-amplitude={waveAmplitude} data-glow-radius={glowRadius}><canvas ref={canvasRef} aria-hidden="true" /></div>
}

export type PublicView="discover"|"explorer"|"about"

export function readPublicView(hash:string):PublicView{
  return hash==="#explorer"?"explorer":hash==="#about"?"about":"discover"
}

export const publicViewHash=(view:PublicView)=>`#${view}`

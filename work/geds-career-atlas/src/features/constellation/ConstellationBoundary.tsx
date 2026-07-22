import { Component, type ReactNode } from "react"

type Node={id:string;name:string}
type Props={nodes:Node[];label:string;focus?:string;onSelect?:(id:string)=>void;onDrill?:(id:string)=>void;children:ReactNode}

export class ConstellationBoundary extends Component<Props,{failed:boolean}>{
  state={failed:false}
  static getDerivedStateFromError(){return{failed:true}}
  componentDidUpdate(previous:Props){if(this.state.failed&&previous.nodes!==this.props.nodes)this.setState({failed:false})}
  render(){if(!this.state.failed)return this.props.children;return <div role="listbox" aria-label={this.props.label}>{this.props.nodes.map(node=><button key={node.id} role="option" aria-selected={node.id===this.props.focus} onClick={()=>this.props.onSelect?.(node.id)} onDoubleClick={()=>this.props.onDrill?.(node.id)} onKeyDown={event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();this.props.onSelect?.(node.id)}if(event.key==="ArrowRight"){event.preventDefault();this.props.onDrill?.(node.id)}}}>{node.name}</button>)}</div>}
}

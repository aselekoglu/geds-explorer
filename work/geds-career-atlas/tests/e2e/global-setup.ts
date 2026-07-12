import { spawn, type ChildProcess } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"

const here=path.dirname(fileURLToPath(import.meta.url))
const frontendDir=path.resolve(here,"../../dist")
const crawlerDir=path.resolve(here,"../../../geds-crawler")
const masterDb=process.env.GEDS_MASTER_DB??path.resolve(here,"../../../../../../outputs/master/geds-master.sqlite")
const healthUrl="http://127.0.0.1:8780/api/meta"

async function healthy(){
  try{return (await fetch(healthUrl)).ok}catch{return false}
}

async function waitForServer(server:ChildProcess){
  const deadline=Date.now()+30_000
  while(Date.now()<deadline){
    if(server.exitCode!==null)throw new Error(`Career Atlas server exited before becoming ready (${server.exitCode})`)
    if(await healthy())return
    await new Promise(resolve=>setTimeout(resolve,150))
  }
  throw new Error("Career Atlas server did not become ready within 30 seconds")
}

export default async function globalSetup(){
  if(await healthy())return
  const server=spawn(process.env.PYTHON_LAUNCHER??"py",["-m","geds_crawler.career_cli","serve","--master-db",masterDb,"--frontend-dir",frontendDir,"--host","127.0.0.1","--port","8780"],{
    cwd:crawlerDir,
    env:{...process.env,PYTHONPATH:path.join(crawlerDir,"src")},
    stdio:"inherit",
    windowsHide:true,
  })
  try{await waitForServer(server)}catch(error){server.kill();throw error}
  return async()=>{
    if(server.exitCode!==null)return
    server.kill()
    await Promise.race([
      new Promise<void>(resolve=>server.once("exit",()=>resolve())),
      new Promise<void>(resolve=>setTimeout(resolve,5_000)),
    ])
  }
}

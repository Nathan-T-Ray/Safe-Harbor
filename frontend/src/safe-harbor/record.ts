import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Artifact, Assessment, Candidate, CommitEvent, Evaluation, HarnessVersion, Run, Snapshot, Task } from '../../../shared/contracts';
import { api } from './client';
export interface RecordState { run?:Run; candidates:Candidate[]; tasks:Task[]; artifacts:Artifact[]; assessments:Assessment[]; harness_versions:HarnessVersion[]; evaluations:Evaluation[]; through_sequence:number }
export const emptyRecord = ():RecordState => ({candidates:[],tasks:[],artifacts:[],assessments:[],harness_versions:[],evaluations:[],through_sequence:0});
function upsert<T>(previous:T[], incoming:T[]|undefined, key:keyof T):T[] { const map = new Map(previous.map(value => [value[key],value])); incoming?.forEach(value => map.set(value[key],value)); return [...map.values()]; }
export function applyEvent(state:RecordState, event:CommitEvent):RecordState {
  if (event.sequence <= state.through_sequence) return state;
  if (event.sequence !== state.through_sequence + 1) throw new Error(`Event gap: expected ${state.through_sequence + 1}, received ${event.sequence}`);
  const u = event.upserts;
  return {run:u.runs?.at(-1) ?? state.run, candidates:upsert(state.candidates,u.candidates,'candidate_id'), tasks:upsert(state.tasks,u.tasks,'task_id'), artifacts:upsert(state.artifacts,u.artifacts,'artifact_id'), assessments:upsert(state.assessments,u.assessments,'assessment_id'), harness_versions:upsert(state.harness_versions,u.harness_versions,'harness_hash'),evaluations:upsert(state.evaluations,u.evaluations,'evaluation_id'),through_sequence:event.sequence};
}
export function reconstruct(events:CommitEvent[], sequence:number):RecordState { return events.filter(event=>event.sequence<=sequence).reduce(applyEvent,emptyRecord()); }
function fromSnapshot(s:Snapshot):RecordState {return {...s};}
export function useRecord(runId:string|null) {
  const [live,setLive] = useState<RecordState>(emptyRecord), [events,setEvents] = useState<CommitEvent[]>([]), [cursor,setCursor] = useState<number|null>(null), [playing,setPlaying] = useState(false), [speed,setSpeed] = useState(1), [error,setError] = useState<string|null>(null), [connected,setConnected] = useState(false), [loading,setLoading]=useState(false);
  const [generation,setGeneration]=useState(0); const eventRef=useRef<CommitEvent[]>([]);
  useEffect(()=>{
    let disposed=false, polling=false; eventRef.current=[]; setLive(emptyRecord());setEvents([]);setCursor(null);setPlaying(false);setError(null);setConnected(false);
    if (!runId) {setLoading(false);return;}
    setLoading(true);
    async function sync() {
      if(polling || disposed)return; polling=true;
      try {
        const snapshot=await api.snapshot(runId!); let collected=[...eventRef.current]; let after=collected.at(-1)?.sequence ?? 0;
        // Fetch missing history through the same watermark. Never construct replay from this snapshot.
        let more=true; let pages=0;
        while(more && pages++<100) { const page=await api.events(runId!,after); const known=new Set(collected.map(event=>event.event_id)); const fresh=page.events.filter(event=>!known.has(event.event_id)).sort((a,b)=>a.sequence-b.sequence); for(const event of fresh){if(event.sequence!==after+1)throw new Error(`Missing committed event ${after+1}`);collected.push(event);after=event.sequence;} more=page.has_more; if(!fresh.length && more)throw new Error('Event page made no progress'); }
        if(disposed)return;
        if(collected.length) reconstruct(collected,collected.at(-1)!.sequence);
        let current=fromSnapshot(snapshot); for(const event of collected.filter(event=>event.sequence>snapshot.through_sequence)) current=applyEvent(current,event);
        eventRef.current=collected;setEvents(collected);setLive(current);setError(null);setConnected(true);
      } catch(e){if(!disposed){setError(e instanceof Error?e.message:String(e));setConnected(false);}}
      finally{polling=false;if(!disposed)setLoading(false);}
    }
    void sync();const timer=window.setInterval(()=>void sync(),1000);return()=>{disposed=true;clearInterval(timer);};
  },[runId,generation]);
  const lastSequence=events.at(-1)?.sequence??0;
  useEffect(()=>{if(!playing)return;const timer=setInterval(()=>{setCursor(value=>{const next=(value??0)+1;if(next>=lastSequence){setPlaying(false);return lastSequence;}return next;});},1000/speed);return()=>clearInterval(timer);},[playing,speed,lastSequence]);
  const state=useMemo(()=>cursor===null?live:reconstruct(events,cursor),[live,events,cursor]);
  const seek=useCallback((sequence:number)=>{setPlaying(false);setCursor(Math.max(0,Math.min(sequence,lastSequence)));},[lastSequence]);
  return {state,events,cursor,lastSequence,playing,speed,setSpeed,error,connected,loading,seek,refresh:()=>setGeneration(value=>value+1),goLive:()=>{setPlaying(false);setCursor(null);},togglePlay:()=>{if(cursor===null||cursor>=lastSequence)setCursor(0);setPlaying(value=>!value);},next:()=>{const current=cursor??0;const next=events.find(event=>event.sequence>current && !['task.started','budget.reserved'].includes(event.cause));seek(next?.sequence??lastSequence);}};
}

import { useEffect, useRef } from 'react';
/** Keep keyboard focus in an open drawer and restore its actual invoking control. */
export function useDialogFocus<T extends HTMLElement>() {
 const ref=useRef<T>(null);
 useEffect(()=>{
  const previous=document.activeElement instanceof HTMLElement?document.activeElement:null;
  const controls=()=>[...(ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),summary,[tabindex="0"]')??[])].filter(node=>node.getClientRects().length>0);
  const frame=requestAnimationFrame(()=>controls()[0]?.focus());
  const trap=(event:KeyboardEvent)=>{if(event.key!=='Tab')return;const items=controls(),first=items[0],last=items.at(-1);if(!first)return;const active=document.activeElement;if(event.shiftKey&&(active===first||!ref.current?.contains(active))){event.preventDefault();last?.focus();}else if(!event.shiftKey&&(active===last||!ref.current?.contains(active))){event.preventDefault();first.focus();}};
  document.addEventListener('keydown',trap,true);
  return()=>{cancelAnimationFrame(frame);document.removeEventListener('keydown',trap,true);if(previous?.isConnected)previous.focus();};
 },[]);
 return ref;
}

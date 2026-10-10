// The field panel is modeless: the layer controls remain reachable.
export function openToolsKeyboard(panel,trigger,close,events=window){
 panel?.querySelector('button, input, select, summary, a[href]')?.focus();
 const dismiss=event=>{if(event.key==='Escape'){event.preventDefault();close()}};
 events.addEventListener('keydown',dismiss);
 return ()=>{events.removeEventListener('keydown',dismiss);trigger?.focus()};
}

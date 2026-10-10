export function queryPayload(origin,heading,question,mode,datasetId=null){
 if(mode==='none'&&!datasetId)throw new Error('Wait for satellite measurements before opening a summary.');
 return {...origin,heading,question,...(mode==='none'?{datasetId}:{})};
}
export async function sendQuery(payload,signal,fetcher=fetch,url='/query'){
 const response=await fetcher(url,{method:'POST',headers:{'Content-Type':'application/json'},signal,body:JSON.stringify(payload)});
 let data;
 try{data=await response.json()}catch{throw new Error('Data service unavailable. Please try again shortly.')}
 if(!response.ok)throw new Error(data.error?.message||'Data service unavailable. Please try again shortly.');
 if(typeof data.answer?.text!=='string'||!Array.isArray(data.answer.citations))throw new Error('Invalid answer received');
 return data.answer;
}

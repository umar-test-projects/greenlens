import {useEffect,useRef,useState} from 'react';
import {createWeatherController,sendCurrentWeather,weatherLocation} from './weather.js';
const empty={result:null,loading:false,status:'Enable GPS to load air temperature.'};
export default function useAirTemperature(enabled,location,request=sendCurrentWeather){
 const area=weatherLocation(location),[state,setState]=useState(empty),controller=useRef(null);
 useEffect(()=>{
  if(!enabled||!area){setState(empty);return}
  const client=createWeatherController({request,onUpdate:value=>setState({...value,area})});controller.current=client;client.start(area);
  return ()=>{client.stop();if(controller.current===client)controller.current=null};
 },[enabled,area?.lat,area?.lng,request]);
 const current=enabled&&area?(state.area?.lat===area.lat&&state.area?.lng===area.lng?state:{result:null,loading:true,status:'Loading current air temperature…'}):empty;
 return {...current,canRetry:Boolean(enabled&&area),retry:()=>controller.current?.retry()};
}

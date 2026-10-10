import React from 'react';
import {weatherTime,WEATHER_SOURCE_URL} from './weather.js';

export default function AirTemperatureCard({weather,reference=false,waitingForReference=false}){
 const {result,retry}=weather,loading=weather.loading||waitingForReference,status=waitingForReference?'Loading reference area…':weather.status;
 return <article className={`measurement-card air-temperature-card ${result?'weather-ready':''}`} aria-live="polite" aria-busy={loading}>
  <div className="measurement-heading"><span>Air temperature</span><small>{reference?'Aliganj preview':'Your area'}{result&&<> · <time dateTime={new Date(result.validAt*1000).toISOString()}>{weatherTime(result)}</time></>}</small></div>
  <strong>{result?<>{result.airTempC.toFixed(1)}<small> °C</small></>:loading?'Loading…':'Unavailable'}</strong>
  <p>{result?'Current weather estimate · 2 m above ground':status}</p>
  <p className="weather-source">{result?'Estimate · ':'Weather: '}<a href={WEATHER_SOURCE_URL} target="_blank" rel="noopener noreferrer">Open-Meteo</a>{weather.canRetry&&!loading&&!result&&<button onClick={retry}>Retry weather</button>}</p>
 </article>;
}

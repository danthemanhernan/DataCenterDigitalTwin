export const defaults={name:'Nominal operation',scenario:'Normal',faultAt:30,duration:120,setpoint:25,initial:24,ambient:29,mass:52,water:12,flow:2.2,capacity:42,minFan:18,maxFan:100,kp:14,ki:0.65,kd:4,baseLoad:58,peakLoad:83,gpu:32,idle:4,price:0.13,peakPrice:0.34,peakAt:55,shedPrice:0.27,shed:22,overhead:0.12,shedEnabled:false,bias:0,noise:0.12,period:1,hot:29,delay:3,stale:4,topic:'twin/lab01/telemetry',schema:1,schemaExtras:'{}'};
export const faults=['Normal','Fan failure','Chilled-water loss','Sensor dropout','Sensor drift','MQTT outage','Duplicate message'];
export const groups=[
 ['Thermal plant',[['setpoint','Inlet setpoint','°C',15,35,.1],['initial','Initial inlet','°C',12,45,.1],['ambient','Ambient temperature','°C',12,50,.1],['mass','Thermal capacitance','kWh/°C',5,250,.1],['water','Chilled-water supply','°C',3,24,.1],['flow','Water flow','L/s',0,8,.1],['capacity','Coil capacity','kW',1,120,.1]]],
 ['Fan & PID',[['minFan','Minimum fan','%',0,100,1],['maxFan','Maximum fan','%',0,100,1],['kp','Proportional gain','%/°C',0,100,.1],['ki','Integral gain','%/(°C·min)',0,30,.05],['kd','Derivative gain','%·min/°C',0,100,.1]]],
 ['Power & demand response',[['gpu','GPU capacity','kW',1,100,.1],['idle','Idle IT draw','kW',1,50,.1],['baseLoad','Initial GPU load','%',0,100,1],['peakLoad','Step GPU load','%',0,100,1],['price','Off-peak tariff','$/kWh',0,10,.01],['peakPrice','Peak tariff','$/kWh',0,10,.01],['peakAt','Tariff step time','min',0,240,1],['shedPrice','Shedding threshold','$/kWh',0,10,.01],['shed','Load reduction','percentage points',0,100,1],['overhead','Fixed overhead','fraction of IT draw',0,1,.01]]],
 ['Sensors, alerts & telemetry',[['bias','Temperature bias','°C',-10,10,.1],['noise','Temperature noise amplitude','°C',0,5,.01],['period','Sampling interval','min',1,10,1],['hot','High inlet threshold','°C',15,60,.1],['delay','High inlet delay','min',1,30,1],['stale','Stale telemetry threshold','min',1,30,1],['schema','Schema version','',1,99,1]]]
];
const clamp=(x,a,b)=>Math.min(b,Math.max(a,x));
function extraFields(text){
 if(typeof text!=='string'||text.length>4000) throw new Error('Invalid extensions');
 const obj=JSON.parse(text);
 if(!obj||typeof obj!=='object'||Array.isArray(obj)||Object.values(obj).some(v=>v!==null&&!['string','number','boolean'].includes(typeof v))) throw new Error('Invalid extensions');
 return obj;
}
export function validate(c){
 if(!c||!faults.includes(c.scenario)||typeof c.name!=='string'||!c.name.trim()||typeof c.shedEnabled!=='boolean'||typeof c.topic!=='string'||!c.topic.trim()||/[+#\s\u0000]/.test(c.topic)) return false;
 try{extraFields(c.schemaExtras??'{}')}catch{return false}
 return [...groups.flatMap(g=>g[1]),['duration','','',10,240,1],['faultAt','','',0,240,1]].every(([key,,,lo,hi,step])=>Number.isFinite(c[key])&&c[key]>=lo&&c[key]<=hi&&(step!==1||Number.isInteger(c[key])))&&c.minFan<=c.maxFan&&(c.scenario==='Normal'||c.faultAt<c.duration);
}
export function simulate(c){
 if(!validate(c)) throw new Error('Check the model inputs before running.');
 let temp=c.initial, integral=0,lastMeasurement=null,lastEvent=0,lastValid=0,highSince=null,alerts=[],points=[],energy=0,itEnergy=0,cost=0,dropped=0,duplicates=0,accepted=0;
 const active=new Map();
 const rule=(condition,type,minute)=>{
   if(condition&&!active.has(type)){const event={type,minute,cleared:null};active.set(type,event);alerts.push(event);}
   if(!condition&&active.has(type)){active.get(type).cleared=minute;active.delete(type);}
 };
 for(let minute=0;minute<c.duration;minute++){
  const fault=minute>=c.faultAt?c.scenario:'Normal';
  const requested=minute>=20?c.peakLoad:c.baseLoad;
  const price=minute>=c.peakAt?c.peakPrice:c.price;
  const shed=c.shedEnabled&&price>=c.shedPrice?Math.min(c.shed,requested):0;
  const it=c.idle+c.gpu*(requested-shed)/100;
  const sensor=fault==='Sensor dropout'?null:temp+c.bias+c.noise*Math.sin(minute*2.17)+(fault==='Sensor drift'?3:0);
  if(sensor!==null)lastValid=minute;
  const error=sensor===null?0:sensor-c.setpoint;
  const derivative=sensor===null||lastMeasurement===null?0:(sensor-lastMeasurement);
  const candidate=clamp(integral+error,-200,200);
  const raw=40+c.kp*error+c.ki*candidate+c.kd*derivative;
  if(sensor!==null&&((raw>=c.minFan&&raw<=c.maxFan)||(raw>c.maxFan&&error<0)||(raw<c.minFan&&error>0)))integral=candidate;
  lastMeasurement=sensor;
  const command=sensor===null?c.maxFan:clamp(40+c.kp*error+c.ki*integral+c.kd*derivative,c.minFan,c.maxFan);
  const fan=fault==='Fan failure'?command*.18:command;
  const flow=fault==='Chilled-water loss'?c.flow*.1:c.flow;
  const cooling=c.capacity*(fan/100)*clamp(flow/2.2,0,1.5)*clamp((temp-c.water)/13,0,1.6);
  const total=it*(1+c.overhead)+5*(fan/100)**3+cooling/4+.6*flow;
  const sample=minute%c.period===0;
  const delivered=sample&&fault!=='MQTT outage';
  const duplicate=delivered&&fault==='Duplicate message';
  if(delivered){lastEvent=minute;accepted++;} else if(sample)dropped++;
  if(duplicate)duplicates++;
  highSince=sensor!==null&&sensor>=c.hot?(highSince??minute):null;
  rule(highSince!==null&&minute-highSince+1>=c.delay,'High rack inlet',minute);
  rule(minute-lastEvent>=c.stale,'Stale telemetry',minute);
  rule(minute-lastValid>=c.stale,'Inlet sensor unavailable',minute);
  rule(fan<command-10,'Fan tracking error',minute);
  rule(c.flow>0&&flow<c.flow*.5,'Chilled-water flow low',minute);
  rule(shed>0,'Demand response active',minute);
  points.push({minute,temp,sensor,fan,command,flow,cooling,it,total,price,shed,delivered,sample,duplicate,fault,pue:total/it});
  cost+=total*price/60;energy+=total/60;itEnergy+=it/60;
  temp+=(it+.32*(c.ambient-temp)-cooling)/(c.mass*60);
 }
 return {config:{...c},points,alerts,energy,itEnergy,cost,pue:energy/itEnergy,peak:Math.max(...points.map(p=>p.temp)),dropped,duplicates,accepted};
}
export function packet(c,p){
 return {schema_version:c.schema,event_id:'lab01-'+p.minute,minute:p.minute,site_id:'lab01',inlet_c:p.sensor===null?null:+p.sensor.toFixed(3),fan_pct:+p.fan.toFixed(2),water_flow_lps:p.flow,it_kw:+p.it.toFixed(3),facility_kw:+p.total.toFixed(3),tariff_usd_kwh:p.price,shed_pct:p.shed,quality:p.sensor===null?'missing':'good',extensions:extraFields(c.schemaExtras??'{}')};
}
export const tests=[
 ['Normal run stays below the inlet limit',{},r=>r.peak<r.config.hot],
 ['Fan failure triggers command tracking alert',{scenario:'Fan failure'},r=>r.alerts.some(a=>a.type==='Fan tracking error')],
 ['Water loss trips flow alert',{scenario:'Chilled-water loss'},r=>r.alerts.some(a=>a.type==='Chilled-water flow low')],
 ['Sensor dropout drives fan to configured maximum',{scenario:'Sensor dropout'},r=>r.points.slice(r.config.faultAt).every(p=>p.sensor===null&&p.command===r.config.maxFan)],
 ['MQTT outage creates a stale alert and drops samples',{scenario:'MQTT outage'},r=>r.dropped>0&&r.alerts.some(a=>a.type==='Stale telemetry')],
 ['Duplicate events are counted and deduplicated',{scenario:'Duplicate message'},r=>r.duplicates>0&&r.accepted===r.points.filter(p=>p.sample).length],
 ['Price-triggered shedding reduces IT energy',{shedEnabled:true},r=>r.itEnergy<simulate({...r.config,shedEnabled:false}).itEnergy],
 ['Facility energy and PUE reconcile',{},r=>r.pue>=1&&Math.abs(r.pue*r.itEnergy-r.energy)<1e-8]
];

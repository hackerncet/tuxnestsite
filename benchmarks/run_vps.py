"""HTTP load generator. Runs OUTSIDE the limited server containers.
Synthetic data only. Records actual wall-clock times, response statuses and container stats.
"""
import asyncio, json, math, os, random, statistics, subprocess, time
from collections import Counter,defaultdict
from pathlib import Path
import httpx

BASE=os.getenv('NCET_BENCH_BASE','http://127.0.0.1:18787')
COOKIE_NAME='ncet_session'
CLIENT_PASSWORD='Benchmark-Password-Not-For-Production-2026!'

def token(i):return f'ncet-local-load-benchmark-session-{i:03d}-20261017'
def csrf(i):return f'synthetic-csrf-{i:03d}-only'
def pct(values,part):
    if not values:return None
    values=sorted(values)
    return round(values[min(len(values)-1,max(0,math.ceil(len(values)*part)-1))],1)
def stats_summary(values):
    return {'p50_ms':pct(values,.5),'p95_ms':pct(values,.95),'p99_ms':pct(values,.99),'max_ms':round(max(values),1) if values else None}

def docker_stats():
    result={}
    try:
        c=subprocess.run(['docker','stats','--no-stream','--format','{{json .}}',
                          'ncet-bench-web','ncet-bench-pg'],
                         capture_output=True,text=True,timeout=8,check=True)
        for line in c.stdout.splitlines():
            row=json.loads(line)
            try:mem=float(row.get('MemUsage','0').split('/')[0].strip().split()[0])
            except ValueError:mem=0
            unit=row.get('MemUsage','').split('/')[0].lower()
            if 'gib' in unit:mem*=1024
            if 'kib' in unit:mem/=1024
            cpu=float(row.get('CPUPerc','0').strip().rstrip('%') or 0)
            result[row.get('Name') or row.get('Container') or 'container']={'mem_mib':round(mem,1),'cpu_percent':round(cpu,1)}
    except Exception as error:
        result['metric_error']=str(error)[:80]
    return result

async def scenario(client,name,users,duration,think,ramp=12):
    random_seed=2317+users+int(think*10)
    results=[]
    start=time.perf_counter();stop=start+duration
    async def individual(i):
        rng=random.Random(random_seed+i)
        await asyncio.sleep(rng.uniform(0,min(ramp,duration/3)))
        while time.perf_counter()<stop:
            val=rng.random()
            if val<.11:path='/';kind='home';method='GET'
            elif val<.26:path='/api/bca/directory?limit=18&offset='+str((i%5)*18);kind='directory';method='GET'
            elif val<.34:path='/students/profile/1NC24BCA'+str(i%120).zfill(3);kind='profile';method='GET'
            elif val<.41:path='/static/ncet-brand.svg';kind='static';method='GET'
            elif val<.52:path='/api/auth/me';kind='session';method='GET'
            elif val<.65:path='/api/bca/me';kind='student';method='GET'
            elif val<.75:path='/api/bca/cases';kind='cases';method='GET'
            elif val<.88:path='/api/bca/showcase/me';kind='showcase';method='GET'
            elif val<.96:path='/students/portal';kind='portal';method='GET'
            else:path='/api/bca/cases';kind='create_case';method='POST'
            headers={'Cookie':COOKIE_NAME+'='+token(i)}
            kwargs={}
            if method=='POST':
                headers['X-CSRF-Token']=csrf(i)
                kwargs['json']={'category':'academics','subject':'Performance test academic question',
                                'description':'A synthetic academic support query for capacity testing only.'}
            requested=time.perf_counter()
            try:
                response=await client.request(method,BASE+path,headers=headers,**kwargs)
                status=response.status_code
                err='' if status in (200,201) else f'HTTP {status}'
            except Exception as e:
                status=0;err=type(e).__name__
            results.append({'latency_ms':(time.perf_counter()-requested)*1000,
                            'status':status,'kind':kind,'error':err})
            wait=rng.uniform(think*.75,think*1.25) if think else 0
            if wait:await asyncio.sleep(wait)
    async def sample_container():
        samples=[]
        while time.perf_counter()<stop:
            samples.append(await asyncio.to_thread(docker_stats))
            await asyncio.sleep(5)
        return samples
    sampler=asyncio.create_task(sample_container())
    await asyncio.gather(*(individual(i) for i in range(users)))
    samples=await sampler
    took=time.perf_counter()-start
    failed=[r for r in results if r['error']]
    per={}
    for kind in {r['kind'] for r in results}:
        ss=[r for r in results if r['kind']==kind]
        per[kind]={'n':len(ss),'errors':len([x for x in ss if x['error']]),
                   'p95_ms':pct([x['latency_ms'] for x in ss],.95)}
    maxmem={}
    maxcpu={}
    for sample in samples:
        for n,item in sample.items():
            if isinstance(item,dict):
                maxmem[n]=max(maxmem.get(n,0),item.get('mem_mib',0))
                maxcpu[n]=max(maxcpu.get(n,0),item.get('cpu_percent',0))
    record={'scenario':name,'virtual_users':users,'duration_s':round(took,1),
            'think_time_mean_s':think,'requests':len(results),
            'throughput_rps':round(len(results)/took,2),
            'errors':len(failed),'error_rate_pct':round(100*len(failed)/len(results),2) if results else 100,
            'statuses':dict(Counter(str(r['status']) for r in results)),
            **stats_summary([r['latency_ms'] for r in results]),
            'max_mem_mib':maxmem,'max_cpu_pct':maxcpu,'by_endpoint':per}
    print('SCENARIO '+json.dumps(record,sort_keys=True),flush=True)
    return record

async def login_burst(client,count):
    # Actual Argon2 verification; capped to 8 requests to avoid a single-IP rate-limit.
    start=time.perf_counter()
    async def once(i):
        t=time.perf_counter()
        try:
            result=await client.post(BASE+'/api/auth/login',
                json={'username':f'1NC24BCA{i:03d}','password':CLIENT_PASSWORD,'role':'student'})
            return {'latency_ms':(time.perf_counter()-t)*1000,'status':result.status_code}
        except Exception as err:
            return {'latency_ms':(time.perf_counter()-t)*1000,'status':0,'error':type(err).__name__}
    before=docker_stats()
    rows=await asyncio.gather(*(once(i) for i in range(count)))
    after=docker_stats()
    record={'scenario':'real_login_burst','concurrent_logins':count,
            'duration_s':round(time.perf_counter()-start,1),
            'statuses':dict(Counter(str(x['status']) for x in rows)),
            'errors':sum(x['status']!=200 for x in rows),
            **stats_summary([x['latency_ms'] for x in rows]),
            'memory_before':before,'memory_after':after}
    print('LOGIN '+json.dumps(record,sort_keys=True),flush=True)
    return record

async def main():
    async with httpx.AsyncClient(timeout=httpx.Timeout(12,connect=4),
           limits=httpx.Limits(max_connections=220,max_keepalive_connections=170)) as client:
        start=time.monotonic()
        while True:
            try:
                if (await client.get(BASE+'/healthz',timeout=3)).status_code==200:break
            except Exception:pass
            if time.monotonic()-start>40:raise RuntimeError('Application is not healthy')
            await asyncio.sleep(1)
        print('BASELINE '+json.dumps({'stats':docker_stats()}),flush=True)
        scenarios=[
            await scenario(client,'100_students_normal_8s_think',100,55,8,12),
            await scenario(client,'150_students_normal_8s_think',150,55,8,15),
            await scenario(client,'150_students_high_activity_1s_think',150,35,1,10),
        ]
        login_four=await login_burst(client,4)
        login=await login_burst(client,8)
    # More reliable than sampled RSS; records docker cgroup OOM events.
    memory_peaks={}
    for name in ('ncet-bench-web','ncet-bench-pg'):
        def read(arg):
            proc=subprocess.run(['docker','exec',name,'sh','-c',arg],
                capture_output=True,text=True,timeout=8)
            return proc.stdout.strip() if proc.returncode==0 else proc.stderr.strip()
        memory_peaks[name]={'memory_peak_bytes':read('cat /sys/fs/cgroup/memory.peak'),
                            'memory_events':read('cat /sys/fs/cgroup/memory.events')}
    report={'limitations':'CI Docker quotas, 1 vCPU across services; NOT an actual DigitalOcean Droplet. 150 seeded synthetic sessions, PostgreSQL co-resident, background worker enabled; no remote LLM or OCR document workload.','scenarios':scenarios,
            'login_burst_4':login_four,'login_burst_8':login,'cgroup':memory_peaks}
    out=Path('benchmarks/vps_result.json');out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('REPORT_FILE='+str(out),flush=True)
    print('CGROUP '+json.dumps(memory_peaks),flush=True)

if __name__=='__main__':asyncio.run(main())

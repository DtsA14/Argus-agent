import json,sys,collections
R=sys.argv[1]
rows=[json.loads(l) for l in open(R+'/times.jsonl')]
w={}
for r in rows:
    if r['nodeid'].endswith(('@sandbox_a','@sandbox_b')):
        a=w.setdefault(r['nodeid'],[1e18,0]); a[0]=min(a[0],r['start']); a[1]=max(a[1],r['stop'])
mem=[k for k in w if 'test_memory_limit_kills_the_code' in k]
last=max(r['stop'] for r in rows)+2          # the observer of an earlier run may have kept recording: cut at this run's last test
ev=[]
for l in open(R+'/events.log'):
    p=l.split()
    if len(p)>=4 and p[1] in('die','oom') and int(p[0])/1e9<=last: ev.append((int(p[0])/1e9,p[1],p[2].split('=')[1],p[4].split('=',1)[1][:14] if len(p)>4 else ''))
bad=[e for e in ev if e[1]=='oom' or e[2]=='137']
outside=[e for e in bad if not any(s-1<=e[0]<=t+1 for s,t in w.values())]
c=collections.Counter((e[1],e[3]) for e in bad)
oom=[e for e in bad if e[1]=='oom']
oom_in_mem=all(any(w[k][0]-1<=e[0]<=w[k][1]+1 for k in mem) for e in oom)
print('die137:',sum(1 for e in bad if e[1]=='die'),'oom:',len(oom),'outside windows:',len(outside),'oom inside memory test window:',oom_in_mem)
print('by image:',sorted(c.items(),key=lambda x:-x[1]))
print('other exit codes:',collections.Counter(e[2] for e in ev if e[1]=='die' and e[2]!='137'))

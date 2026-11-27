"""Strict RBXM v0 animation extractor for user-supplied R6 KeyframeSequences.

Reads raw/LZ4 chunks, class/reference arrays, names, pose CFrames, weights,
easing, timestamps, loop flags, and source Motor6D C0/C1. No Roblox execution
or network. Unrelated properties remain unparsed. Unsupported encoding fails.
"""
import argparse,hashlib,json,math,struct
from pathlib import Path

MAGIC=b"<roblox!\x89\xff\r\n\x1a\n"
EXPECTED_SHA="a05aa15bd6cc28b739c53208c69037bc547bbb731e78d200393468a26029d2d4"
PARTS=("HumanoidRootPart","Torso","Head","Left Arm","Right Arm","Left Leg","Right Leg")
NORMALS=((1,0,0),(0,1,0),(0,0,1),(-1,0,0),(0,-1,0),(0,0,-1))

def lz4_block(src,size):
    """Raw LZ4 block, not LZ4 frame; bounded output and checked offsets."""
    i=0;out=bytearray()
    def length(n):
        nonlocal i
        if n==15:
            while True:
                assert i<len(src),"truncated LZ4 length"
                v=src[i];i+=1;n+=v
                if v!=255:break
        return n
    while i<len(src):
        token=src[i];i+=1;n=length(token>>4)
        assert i+n<=len(src) and len(out)+n<=size,"invalid LZ4 literals"
        out.extend(src[i:i+n]);i+=n
        if i==len(src):break
        assert i+2<=len(src)
        offset=src[i]|src[i+1]<<8;i+=2
        assert 0<offset<=len(out),"bad LZ4 match offset"
        n=length(token&15)+4;assert len(out)+n<=size,"LZ4 output overflow"
        for _ in range(n):out.append(out[-offset])
    assert len(out)==size,(len(out),size)
    return bytes(out)

def chunks(raw):
    assert raw[:14]==MAGIC and raw[14:16]==b"\0\0","not RBXM v0"
    count,instances=struct.unpack_from("<II",raw,16)
    assert count<10000 and instances<1000000
    pos=32;end=False
    while pos<len(raw):
        assert pos+16<=len(raw)
        tag,compressed,size,reserved=struct.unpack_from("<4sIII",raw,pos);pos+=16
        assert size<=64*1024*1024 and pos+(compressed or size)<=len(raw)
        data=raw[pos:pos+(compressed or size)];pos+=compressed or size
        if compressed:data=lz4_block(data,size)
        yield tag,data
        if tag==b"END\0":end=True;break
    assert end and pos==len(raw),"missing END or trailing data"

def u32(d,i):return struct.unpack_from("<I",d,i)[0]
def string(d,i):
    n=u32(d,i);assert i+4+n<=len(d)
    return d[i+4:i+4+n].decode("utf8","replace"),i+4+n
def interleaved(d,n):
    assert len(d)==4*n,(len(d),n)
    return [int.from_bytes(d[j::n],"big") for j in range(n)]
def references(d,n):
    a=0;out=[]
    for v in interleaved(d,n):
        a+=(v>>1)^-(v&1);out.append(a)
    return out
def floats(d,n):
    # Roblox rotates the IEEE-754 sign bit to the least-significant bit.
    return [struct.unpack(">f",((v>>1)|((v&1)<<31)).to_bytes(4,"big"))[0] for v in interleaved(d,n)]
def rotation(code):
    assert 1<=code<=36,("unknown orientation",code)
    x,y=NORMALS[(code-1)//6],NORMALS[(code-1)%6]
    assert sum(a*b for a,b in zip(x,y))==0,("invalid orientation",code)
    z=(x[1]*y[2]-x[2]*y[1],x[2]*y[0]-x[0]*y[2],x[0]*y[1]-x[1]*y[0])
    return tuple(v for row in zip(x,y,z) for v in row)
def cframes(d,n):
    p=0;rot=[]
    for _ in range(n):
        code=d[p];p+=1
        if code==0:r=struct.unpack_from("<9f",d,p);p+=36
        else:r=rotation(code)
        rot.append(r)
    assert len(d)==p+12*n
    xyz=[floats(d[p+4*n*j:p+4*n*(j+1)],n) for j in range(3)]
    out=[]
    for i,r in enumerate(rot):
        assert all(math.isfinite(v) for v in r)
        orth=max(abs(sum(r[a*3+k]*r[b*3+k] for k in range(3))-(a==b)) for a in range(3) for b in range(3))
        assert orth<2e-4,orth
        out.append({"r":list(r),"t":[v[i] for v in xyz]})
    return out

def parse(raw,strict=True):
    digest=hashlib.sha256(raw).hexdigest()
    if strict:assert digest==EXPECTED_SHA,"wrong source bytes"
    cls={};props={};parent={}
    for tag,d in chunks(raw):
        if tag==b"INST":
            k=u32(d,0);name,j=string(d,4);n=u32(d,j+1)
            assert d[j] in (0,1)
            cls[k]=(name,references(d[j+5:j+5+4*n],n))
        elif tag==b"PROP":
            k=u32(d,0);name,j=string(d,4);props[k,name]=(d[j],d[j+1:])
        elif tag==b"PRNT":
            assert d[0]==0;n=u32(d,1)
            parent=dict(zip(references(d[5:5+4*n],n),references(d[5+4*n:],n)))
    assert len(cls)==u32(raw,16)
    classes={i:c for c,ids in cls.values() for i in ids}
    assert len(classes)==u32(raw,20)==len(parent)
    values={i:{} for i in classes}
    selected={"Name","DisplayName","Loop","Priority","Time","CFrame","C0","C1","Part0","Part1","Weight","EasingStyle","EasingDirection","AuthoredHipHeight"}
    for (k,name),(typ,d) in props.items():
        if name not in selected:continue
        c,ids=cls[k];n=len(ids)
        if typ==1:
            j=0;arr=[]
            for _ in ids:s,j=string(d,j);arr.append(s)
            assert j==len(d)
        elif typ==2:arr=[bool(x) for x in d];assert len(arr)==n
        elif typ==4:arr=floats(d,n)
        elif typ==0x12:arr=interleaved(d,n)
        elif typ==0x13:arr=references(d,n)
        elif typ==0x10:arr=cframes(d,n)
        else:raise ValueError((c,name,typ))
        for i,v in zip(ids,arr):values[i][name]=v
    motors={}
    for i,c in classes.items():
        if c!="Motor6D":continue
        v=values[i];a=values[v["Part0"]]["Name"];b=values[v["Part1"]]["Name"]
        motors[b]={"name":v["Name"],"parent_part":a,"child_part":b,"C0":v["C0"],"C1":v["C1"]}
    assert set(motors)==set(PARTS)-{"HumanoidRootPart"}
    clips={}
    for i,c in classes.items():
        if c!="KeyframeSequence":continue
        v=values[i];name=v["Name"]
        assert name in ("Walk","Sprint"),name
        frames=[]
        for k in sorted((j for j in classes if classes[j]=="Keyframe" and parent[j]==i),key=lambda j:values[j]["Time"]):
            poses={};todo=[j for j in classes if classes[j]=="Pose" and parent[j]==k]
            while todo:
                j=todo.pop();q=values[j];pn=q["Name"]
                assert pn not in poses and pn in PARTS
                pp=values[parent[j]]["Name"] if classes[parent[j]]=="Pose" else None
                poses[pn]={**q["CFrame"],"weight":q["Weight"],"easing_style":q["EasingStyle"],"easing_direction":q["EasingDirection"],"parent_pose":pp}
                todo.extend(x for x in classes if classes[x]=="Pose" and parent[x]==j)
            assert set(poses)==set(PARTS)
            for pn,pose in poses.items():
                assert pose["easing_style"]==0 and pose["easing_direction"]==0
                assert pose["weight"]==(0 if pn=="HumanoidRootPart" else 1)
                assert pose["parent_pose"]==(None if pn=="HumanoidRootPart" else motors[pn]["parent_part"])
            frames.append({"time":values[k]["Time"],"poses":poses})
        times=[f["time"] for f in frames];assert times[0]==0 and all(b>a for a,b in zip(times,times[1:]))
        assert all(abs((b-a)-1/60)<1e-6 for a,b in zip(times,times[1:]))
        seam={}
        for pn in PARTS:
            a,b=frames[0]["poses"][pn],frames[-1]["poses"][pn]
            tr=sum(x*y for x,y in zip(a["r"],b["r"]))
            seam[pn]={"degrees":math.degrees(math.acos(max(-1,min(1,(tr-1)/2)))),"translation_studs":math.dist(a["t"],b["t"])}
        key="walk_cycle" if name=="Walk" else "run_cycle"
        clips[key]={"source_name":name,"duration":times[-1],"loop":v["Loop"],"loop_start":0,"loop_end":times[-1],"source_priority":v["Priority"],"source_fps":60,"keyframes":frames,"seam":seam}
    assert set(clips)=={"walk_cycle","run_cycle"} and all(c["loop"] for c in clips.values())
    if strict:assert [len(clips[n]["keyframes"]) for n in ("walk_cycle","run_cycle")]==[50,35]
    return {"source_sha256":digest,"source_bytes":len(raw),"instance_count":len(classes),"class_count":len(cls),"credit":next((values[i].get("DisplayName") for i in classes if classes[i]=="Humanoid"),None),"motors":motors,"clips":clips}

def main():
    p=argparse.ArgumentParser();p.add_argument("source",default="assets/animations/run_walk_roblox.bin",nargs="?");p.add_argument("--output",default="render/animation_source.json");a=p.parse_args()
    data=parse(Path(a.source).read_bytes());out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(data,indent=2)+"\n")
    print(json.dumps({"source_sha256":data["source_sha256"],"credit":data["credit"],"clips":{n:{k:v for k,v in c.items() if k!="keyframes"}|{"keyframe_count":len(c["keyframes"])} for n,c in data["clips"].items()}},indent=2))
if __name__=="__main__":main()

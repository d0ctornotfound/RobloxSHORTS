"""Reusable, declarative advisory QC for evaluated per-frame scene metrics.
Rules specify a selector, optional row filter, transform, reducer, and limit.
Missing data is an explicit unmeasured flag, never an automatic pass.
"""
import math
def select(row,path):
    current=[row]
    for part in path.split("."):
        nxt=[]
        for value in current:
            if part=="*":
                if isinstance(value,dict):nxt.extend(value.values())
                elif isinstance(value,list):nxt.extend(value)
            elif isinstance(value,dict) and part in value:nxt.append(value[part])
            elif isinstance(value,list) and part.isdigit() and int(part)<len(value):nxt.append(value[int(part)])
        current=nxt
    return [v for v in current if v is not None]
def transform(v,t):
    if t=="abs":return abs(v)
    if t=="vertical_span":return v[3]-v[2]
    if t=="horizontal_span":return v[1]-v[0]
    if t=="safe_bounds":return v[4]>0 and .035<=v[0]<=v[1]<=.965 and .035<=v[2]<=v[3]<=.965
    return v
def compare(value,op,limit):
    return {"max":lambda:value<=limit,"min":lambda:value>=limit,"eq":lambda:value==limit}[op]()
def evaluate(rows,rules):
    result=[]
    for rule in rules:
        vals=[];matched=0
        for row in rows:
            if "when" in rule:
                w=rule["when"];v=select(row,w["selector"])
                if not v or not all(x==w["equals"] for x in v):continue
            matched+=1
            for v in select(row,rule["selector"]):
                try:vals.append(transform(v,rule.get("transform")))
                except (TypeError,IndexError,ValueError):continue
        red=rule.get("reduce","max")
        v=None
        if vals:
            if red=="max":v=max(vals)
            elif red=="min":v=min(vals)
            elif red=="all":v=all(vals)
            elif red=="sum":v=sum(vals)
            elif red=="count_false":v=sum(not x for x in vals)
            elif red=="delta":v=abs(vals[-1]-vals[0])
            elif red=="rms":v=math.sqrt(sum(x*x for x in vals)/len(vals))
        result.append({"name":rule["name"],"selector":rule["selector"],"value":v,"limit":rule["limit"],"operator":rule["op"],"samples":len(vals),"matched_frames":matched,"status":"unmeasured" if v is None else "pass" if compare(v,rule["op"],rule["limit"]) else "flag"})
    return result
if __name__=="__main__":
    rows=[{"a":{"one":{"gap":.01},"two":{"gap":-.02}},"phase":"sit"},{"a":{"one":{"gap":.03}},"phase":"stand"}]
    rules=[{"name":"gap","selector":"a.*.gap","when":{"selector":"phase","equals":"sit"},"transform":"abs","reduce":"max","op":"max","limit":.015},{"name":"missing","selector":"a.*.not_here","op":"eq","limit":True}]
    report=evaluate(rows,rules)
    assert report[0]["value"]==.02 and report[0]["status"]=="flag" and report[0]["samples"]==2
    assert report[1]["status"]=="unmeasured"
    print("declarative QC self-test PASS")

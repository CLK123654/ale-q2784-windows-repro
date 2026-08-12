from __future__ import annotations
import argparse,atexit,csv,json,shutil,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REQUIRED={'README.txt','tenant_catalog.csv','environment_values.csv','migration_policy.json','change_request.md','starter/tenant-dashboards/Chart.yaml','starter/tenant-dashboards/values.yaml','starter/tenant-dashboards/templates/configmaps.yaml'}

def rows(path):
 with path.open(encoding='utf-8-sig',newline='') as handle:return list(csv.DictReader(handle))
def run(args):
 result=subprocess.run(args,text=True,capture_output=True,timeout=180)
 if result.returncode:raise RuntimeError(result.stdout+result.stderr)
 return result.stdout
def write_values(path,environment,tenants):
 lines=['environment:',f"  label: {environment['label']}",f"  cluster: {environment['cluster']}",'tenants:']
 for tenant in tenants:
  lines.extend([f"  - tenantId: {tenant['tenant_id']}",f"    displayName: {tenant['display_name']}",f"    metricName: {tenant['metric_name']}",f"    window: {tenant['window']}"])
 path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
def write_csv(path,fieldnames,data):
 with path.open('w',encoding='utf-8',newline='') as handle:
  writer=csv.DictWriter(handle,fieldnames=fieldnames,lineterminator='\n');writer.writeheader();writer.writerows(data)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--output',required=True);parser.add_argument('--helm',required=True);args=parser.parse_args();source=Path(args.input).resolve();output=Path(args.output).resolve()
 if output.exists():shutil.rmtree(output)
 finished={'ok':False}
 def cleanup():
  if not finished['ok'] and output.exists():shutil.rmtree(output)
 atexit.register(cleanup)
 present={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
 if present!=REQUIRED:raise ValueError('仪表盘迁移材料集合发生变化')
 tenants=rows(source/'tenant_catalog.csv');environments=rows(source/'environment_values.csv');policy=json.loads((source/'migration_policy.json').read_text(encoding='utf-8'))
 if not tenants or set(tenants[0])!={'tenant_id','display_name','metric_name','window'}:raise ValueError('租户字段发生变化')
 if not environments or set(environments[0])!={'environment','release_name','namespace','label','cluster'}:raise ValueError('环境字段发生变化')
 ids=[x['tenant_id'] for x in tenants]
 if '' in ids or len(ids)!=len(set(ids)):raise ValueError('tenant_id缺失或重复')
 if any(x['metric_name'] not in policy['allowed_metrics'] or x['window'] not in policy['allowed_windows'] for x in tenants):raise ValueError('租户字段不符合迁移策略')
 if any(x in {'titleFragment','queryFragment'} for x in tenants[0]):raise ValueError('租户目录仍含可执行片段字段')
 environment_names=[x['environment'] for x in environments]
 if environment_names!=policy['rollout_order']:raise ValueError('环境顺序与上线策略不一致')
 if not isinstance(policy['observation_minutes'],int) or policy['observation_minutes']<=0:raise ValueError('观察时长无效')
 output.mkdir(parents=True);(output/'chart').mkdir();(output/'values').mkdir();(output/'renders').mkdir();(output/'reports').mkdir()
 shutil.copytree(ROOT/'chart',output/'chart/tenant-dashboards')
 inventory=[]
 for environment in environments:
  values=output/f"values/{environment['environment']}.yaml";write_values(values,environment,tenants)
  run([args.helm,'lint',str(output/'chart/tenant-dashboards'),'-f',str(values)])
  manifest=run([args.helm,'template',environment['release_name'],str(output/'chart/tenant-dashboards'),'-f',str(values),'--namespace',environment['namespace']])
  (output/f"renders/{environment['environment']}.yaml").write_text(manifest.replace('\r\n','\n'),encoding='utf-8')
  for tenant in tenants:
   title=tenant['display_name']+policy['title_separator']+environment['label']
   query=f"sum(rate({tenant['metric_name']}{{tenant_id=\"{tenant['tenant_id']}\",cluster=\"{environment['cluster']}\"}}[{tenant['window']}]))"
   inventory.append({'environment':environment['environment'],'release_name':environment['release_name'],'namespace':environment['namespace'],'tenant_id':tenant['tenant_id'],'configmap_name':tenant['tenant_id']+'-dashboard','title':title,'query':query})
 write_csv(output/'reports/dashboard_inventory.csv',['environment','release_name','namespace','tenant_id','configmap_name','title','query'],inventory)
 migration=[{'tenant_id':x['tenant_id'],'source_fields':'tenant_id,display_name,metric_name,window','destination_fields':'tenantId,displayName,metricName,window','tenant_text_executed':'false'} for x in tenants]
 write_csv(output/'reports/migration_map.csv',['tenant_id','source_fields','destination_fields','tenant_text_executed'],migration)
 (output/'RELEASE-NOTES.md').write_text(f"版本组已将租户标题和查询从tpl片段迁为结构化字段。维护窗口只影响租户仪表盘的标题和查询，值班人员先应用development候选清单，等待{policy['observation_minutes']}分钟并查看结果后再处理production。标题或查询不符时回滚到{policy['rollback_source']}。\n",encoding='utf-8')
 (output/'README.txt').write_text('chart保存不再执行租户文本的Helm Chart，values是两个环境的结构化配置，renders是候选清单。reports中的dashboard_inventory.csv列出标题和查询，migration_map.csv记录字段迁移。\n',encoding='utf-8');finished['ok']=True
if __name__=='__main__':main()

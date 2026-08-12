from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];expected=json.loads((ROOT/'qa/expected_hashes.json').read_text());actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'task/输入数据包.zip',ROOT/'task/reference.zip',ROOT/'task/关键标准答案.xlsx',ROOT/'task/任务规格转化.xlsx']}
if actual!=expected:raise AssertionError({'expected':expected,'actual':actual})
(ROOT/'evidence/attachment-hashes.json').write_text(json.dumps(actual,indent=2)+'\n',encoding='utf-8')

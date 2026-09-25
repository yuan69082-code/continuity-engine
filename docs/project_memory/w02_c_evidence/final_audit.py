"""Read-only W02-C source/protection/link/file-list audit; exclusive outputs."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

sys.dont_write_bytecode = True
from audit import collect

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pending():
    raw = subprocess.check_output(
        ['git', '-c', 'core.quotepath=false', 'status', '--porcelain=v1', '-z', '--untracked-files=all'], cwd=ROOT)
    rows = []
    for item in raw.split(b'\x00'):
        if not item:
            continue
        code, path = item[:2].decode('ascii'), item[3:].decode('utf-8')
        if code in ('R ', ' R', 'C ', ' C'):
            raise RuntimeError('RENAMED_OR_COPIED_PATH_REQUIRES_MANUAL_REVIEW')
        rows.append((code, path))
    return rows


def links(paths):
    missing=[]
    pattern=re.compile(r'(?<!!)\[[^\]]+\]\(([^)]+)\)')
    for path in paths:
        if not path.endswith('.md'):
            continue
        source=ROOT/path
        for target in pattern.findall(source.read_text(encoding='utf-8')):
            target=target.strip().strip('<>').split('#',1)[0]
            if not target or '://' in target or target.startswith(('mailto:', '#')):
                continue
            resolved=(source.parent/unquote(target)).resolve()
            if not resolved.exists():
                missing.append({'source':path,'target':target})
    return missing


def main():
    baseline=json.loads((HERE/'baseline.json').read_text(encoding='utf-8'))
    current=collect()
    rows=pending()
    excluded=set(baseline['excluded'])
    changed={path for _,path in rows}
    included=sorted(changed-excluded)
    preserved=sorted(changed&excluded)
    old_source_changes=[path for path,old_hash in baseline['source'].items()
                        if current['source'].get(path)!=old_hash]
    ast_errors=[]
    for path in sorted(current['source']):
        if path.endswith('.py'):
            try:
                ast.parse((ROOT/path).read_text(encoding='utf-8'),filename=path)
            except Exception as exc:
                ast_errors.append({'path':path,'error_type':type(exc).__name__})
    bad_links=links(included)
    result={
        'baseline_head':baseline['head'],'current_head':current['head'],'branch':current['branch'],
        'source_count':len(current['source']),'source_fingerprint':current['sourceHash'],
        'old_source_changes':old_source_changes,
        'protected_identical':baseline['protected']==current['protected'],
        'formal_identical':baseline['formal_files']==current['formal_files'],
        'formal_count':len(current['formal_files']),
        'excluded_identical':baseline['excluded']==current['excluded'],
        'excluded_count':len(preserved),'excluded_expected':len(excluded),
        'index_identical':baseline['indexHash']==current['indexHash'],
        'staged':current['staged'],'ast_errors':ast_errors,
        'markdown_missing_links':bad_links,
        'pending_count':len(included),
    }
    files={'source_fingerprint':current['sourceHash'],
           'included':{path:sha(ROOT/path) for path in included},
           'excluded':{path:sha(ROOT/path) for path in preserved},
           'statuses':{path:code for code,path in rows},
           'generated_outputs':['docs/project_memory/w02_c_evidence/final.audit.json',
                                'docs/project_memory/w02_c_evidence/final.files.json',
                                'docs/project_memory/w02_c_evidence/final.pending-files.md']}
    for name,value in (('final.audit.json',result),('final.files.json',files)):
        with (HERE/name).open('x',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2)
            stream.write('\n')
    with (HERE/'final.pending-files.md').open('x',encoding='utf-8') as stream:
        stream.write('# W02-C 精确成果与保留清单\n\n')
        stream.write('仅为本批施工工作区清单，不是暂存或提交授权。')
        stream.write('生成输出本身因自引用不能在同一清单中写自身 hash。\n\n')
        stream.write(f'本批成果 {len(included)+3} 项（审计前 {len(included)} 项，加 3 项审计输出）；')
        stream.write(f'原保留材料 {len(preserved)} 项。\n\n## 本批成果\n\n')
        for path in [*included,*files['generated_outputs']]:
            stream.write(f'- `{path}`\n')
        stream.write('\n## 原样排除的既有材料\n\n')
        for path in preserved:
            stream.write(f'- `{path}`\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    main()

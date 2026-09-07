import os, sys, json, re, urllib.request
os.chdir(r'D:\项目\个人工作台系统\backend')
sys.path.insert(0, r'D:\项目\个人工作台系统\backend')

from db.base import SessionLocal
from sqlalchemy import text

db = SessionLocal()
rows = db.execute(text(
    "SELECT id, issue_no, attachments FROM pmwb_operation_issue "
    "WHERE attachments IS NOT NULL AND attachments != '' AND attachments != '[]' LIMIT 5"
)).fetchall()
db.close()

found = []
for r in rows:
    try:
        atts = json.loads(r[2]) if r[2] else []
    except Exception:
        atts = []
    if atts:
        found.append((r[0], r[1], atts))
print("带附件运营工单:", [(f[0], f[1], [a.get('name') for a in f[2]]) for f in found])

if not found:
    print("NO attachment issue found -> 构造临时工单验证")
    sys.exit(0)

issue_id = found[0][0]
print(f"\n=== 用 issue_id={issue_id} 调 /preview (supervise_urge) ===")
URL = 'http://127.0.0.1:8000/api/v1/mail-dispatch/preview'
payload = {'scene': 'supervise_urge', 'attachmentIssueId': issue_id, 'variables': {}}
req = urllib.request.Request(URL, data=json.dumps(payload).encode(),
                             headers={'Content-Type': 'application/json'}, method='POST')
resp = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
print('envelope code:', resp.get('code'), '| msg:', resp.get('message') or resp.get('msg'))
html = resp.get('data', {}).get('html', '')
print('HTML 含「工单附件」区块:', '工单附件' in html)
print('HTML 含下载链接:', 'attachments/download' in html)
m = re.search(r'工单附件（\d+ 个）.*?</ul></div>', html, re.S)
print('--- 附件区块片段 ---')
print(m.group(0)[:900] if m else '(区块未找到)')

out = r'D:\项目\个人工作台系统\prototype\supervise-urge-preview-attach.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print('预览文件已写出:', out)

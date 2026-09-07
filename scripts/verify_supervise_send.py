import os, sys, json
os.chdir(r'D:\项目\个人工作台系统\backend')
sys.path.insert(0, r'D:\项目\个人工作台系统\backend')
from unittest import mock
from services import supervise as svc
from db.base import SessionLocal
from sqlalchemy import text

captured = {}
def fake_dispatch(to, subject, scene, variables, attachments=None, raise_on_error=False, **kw):
    captured['scene'] = scene
    captured['variables'] = variables
    captured['attachments'] = attachments
    return {'success': True, 'subject': 'x', 'rendered_body': 'y'}

db = SessionLocal()
row = db.execute(text("SELECT attachments FROM pmwb_operation_issue WHERE id=21")).fetchone()
db.close()
atts = json.loads(row[0]) if row[0] else []
print("issue 21 附件元信息:", [a.get('name') for a in atts])

ticket = {
    'issue_no': 'TASK-20260804-946', 'title': 't', 'issue_type': 'x', 'category': 'c',
    'handler': 'h', 'status': 'open', 'situation_desc': '情况描述文本', 'source': '运营',
    'issue_id': 21, 'attachments': atts,
}
with mock.patch.object(svc, 'dispatch_email', side_effect=fake_dispatch):
    res = svc.supervise_ticket('urge', ticket, ['陈大海'])

print('supervise_ticket ok:', res.get('ok'))
print('scene:', captured.get('scene'))
desc = captured.get('variables', {}).get('desc') or ''
desc2 = captured.get('variables', {}).get('description') or ''
print('desc 含「工单附件」:', '工单附件' in desc)
print('description 含「工单附件」:', '工单附件' in desc2)
print('desc/description 双写一致:', desc == desc2)
caps = captured.get('attachments') or []
print('真实 MIME 附件数:', len(caps))
if caps:
    a = caps[0]
    print('  filename:', a.get('filename'))
    print('  mimeType:', a.get('mimeType'))
    print('  base64 len:', len(a.get('contentBase64', '')))

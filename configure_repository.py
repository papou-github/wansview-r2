"""Set the real GitHub repository before publishing. No network calls."""
import argparse,json,re
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('repository',help='OWNER/REPOSITORY or https://github.com/OWNER/REPOSITORY')
a=p.parse_args()
value=a.repository.removeprefix('https://github.com/').rstrip('/').removesuffix('.git')
if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+',value):
 p.error('Expected OWNER/REPOSITORY')
owner=value.split('/')[0]
root=Path(__file__).resolve().parent
file=root/'custom_components/wansview_r2/manifest.json'
data=json.loads(file.read_text())
data.update(documentation='https://github.com/'+value,issue_tracker='https://github.com/'+value+'/issues',codeowners=['@'+owner])
file.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
print('Manifest configured for https://github.com/'+value)

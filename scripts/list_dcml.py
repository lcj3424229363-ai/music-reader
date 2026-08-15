import urllib.request, json
url = 'https://api.github.com/orgs/DCMLab/repos?per_page=100&type=public'
req = urllib.request.Request(url, headers={'User-Agent': 'MTRE-research'})
data = json.loads(urllib.request.urlopen(req, timeout=30).read())
print(f'Total repos: {len(data)}')
print()
# 过滤钢琴/奏鸣曲/chopin/haydn/schubert/bach/wtc 相关
keys = ['haydn', 'chopin', 'schubert', 'wtc', 'prelude', 'sonata', 'piano', 'beethoven', 'mozart', 'bach', 'liszt', 'ravel', 'debussy', 'brahms', 'romantic', 'classical', 'chorale']
for r in data:
    name = r['name'].lower()
    desc = (r.get('description') or '')[:80]
    if any(k in name for k in keys) or any(k in desc.lower() for k in keys):
        print('  ' + r['name'].ljust(45) + ' ' + desc)
print()
print('=== ALL repos ===')
for r in sorted(data, key=lambda x: x['name'].lower()):
    print('  ' + r['name'])

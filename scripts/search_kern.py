import urllib.request, json
# Search GitHub for humdrum/digital-scores repos
url = 'https://api.github.com/search/repositories?q=well-tempered+humdrum&per_page=10'
req = urllib.request.Request(url, headers={'User-Agent': 'MTRE-research'})
data = json.loads(urllib.request.urlopen(req, timeout=30).read())
for r in data.get('items', []):
    print('  ' + r['full_name'].ljust(50) + '  ' + (r.get('description') or '')[:80])
print()
# Mozart piano sonatas humdrum
url2 = 'https://api.github.com/search/repositories?q=mozart+piano+sonatas+kern&per_page=10'
req2 = urllib.request.Request(url2, headers={'User-Agent': 'MTRE-research'})
data2 = json.loads(urllib.request.urlopen(req2, timeout=30).read())
print('--- mozart piano sonatas kern ---')
for r in data2.get('items', []):
    print('  ' + r['full_name'].ljust(50) + '  ' + (r.get('description') or '')[:80])
print()
# Beethoven piano sonatas humdrum
url3 = 'https://api.github.com/search/repositories?q=beethoven+piano+sonatas+kern&per_page=10'
req3 = urllib.request.Request(url3, headers={'User-Agent': 'MTRE-research'})
data3 = json.loads(urllib.request.urlopen(req3, timeout=30).read())
print('--- beethoven piano sonatas kern ---')
for r in data3.get('items', []):
    print('  ' + r['full_name'].ljust(50) + '  ' + (r.get('description') or '')[:80])
print()
# Chopin / Schubert
url4 = 'https://api.github.com/search/repositories?q=chopin+nocturne+kern&per_page=10'
req4 = urllib.request.Request(url4, headers={'User-Agent': 'MTRE-research'})
data4 = json.loads(urllib.request.urlopen(req4, timeout=30).read())
print('--- chopin nocturne kern ---')
for r in data4.get('items', []):
    print('  ' + r['full_name'].ljust(50) + '  ' + (r.get('description') or '')[:80])
print()
url5 = 'https://api.github.com/search/repositories?q=schubert+impromptu+kern&per_page=10'
req5 = urllib.request.Request(url5, headers={'User-Agent': 'MTRE-research'})
data5 = json.loads(urllib.request.urlopen(req5, timeout=30).read())
print('--- schubert impromptu kern ---')
for r in data5.get('items', []):
    print('  ' + r['full_name'].ljust(50) + '  ' + (r.get('description') or '')[:80])
print()
url6 = 'https://api.github.com/search/repositories?q=haydn+piano+sonata+kern&per_page=10'
req6 = urllib.request.Request(url6, headers={'User-Agent': 'MTRE-research'})
data6 = json.loads(urllib.request.urlopen(req6, timeout=30).read())
print('--- haydn piano sonata kern ---')
for r in data6.get('items', []):
    print('  ' + r['full_name'].ljust(50) + '  ' + (r.get('description') or '')[:80])

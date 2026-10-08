#!/usr/bin/env python3
"""공개된 Notion 페이지(*.notion.site)를 내려받아 Markdown으로 저장한다.

Notion 웹이 내부적으로 쓰는 공개 API(/api/v3)를 사용한다 (공식 API 아님).
- 페이지 본문 블록, 접힌 토글 안의 블록, 동기화 블록(synced block)까지 받아온다.
- 페이지 안의 하위 페이지와 DB(collection)의 행 페이지를 재귀적으로 변환한다.
  본문이 없는 DB 행(일정 타임라인 등)은 DB 표에만 남기고 파일은 만들지 않는다.
- 이미지/첨부파일은 assets_<slug>/ 에 저장한다.

사용법:
  python3 notion2md.py                 # 아래 TARGETS 전체 갱신
  python3 notion2md.py <URL> <OUT_DIR> # 임의의 공개 페이지 1개(+하위) 변환
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
UA = 'curl/8.5.0'  # Python 기본 User-Agent는 queryCollection에서 403이 난다

# 기본 변환 대상: (페이지 URL, 출력 디렉터리, DB 제목 -> 하위 폴더 이름)
TARGETS = [
    ('https://indecisive-freedom-6e8.notion.site/Doosan-Rokey-9-29d8e215779c8060974ae4a5311b1942',
     HERE / 'tutors',
     {'DAY 1 - Setup/Development Process': 'day1-setup_development_process',
      'DAY 1 - Appendix': 'day1-setup_development_process/appendix_day1',
      'DAY 2 - AI VISION (YOLO)': 'day2-AI_vision_YOLO',
      'DAY 2 - Appendix': 'day2-AI_vision_YOLO/day2_appendix',
      'DAY 3 - SLAM & Navigation': 'day3-SLAM_navigation',
      'DAY 3 - Appendix': 'day3-SLAM_navigation/day3_appendix',
      'DAY 5 - System Monitor & Multi Robot': 'day5-SystemMonitor_MultiRobot',
      'DAY 5 - Appendix': 'day5-SystemMonitor_MultiRobot/day5_appendix'}),
    ('https://teamsparkx.notion.site/SLAM-30d563918e5981abbf74cf24d6853340',
     HERE / 'rokey', {}),
]


def uuid(s):
    """URL이나 32자리 hex에서 dashed uuid를 뽑는다."""
    m = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', s)
    if m:
        return m.group(0)
    # 'Doosan-Rokey-9-29d8...' 처럼 제목 뒤에 붙은 32자리 hex (제목의 숫자가 섞이지 않게 끝에서 자름)
    h = re.findall(r'[0-9a-f]{32}', s.split('?')[0].split('#')[0])[-1]
    return f'{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}'


def safe_name(s):
    s = re.sub(r'[\\/:*?"<>|\n\t]+', '_', s).strip().rstrip('.')
    return s or 'untitled'


def slug(s):
    return re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_')


class Notion:
    """notion.site 공개 API 래퍼 + 레코드 캐시."""

    def __init__(self, site):
        self.site = site.rstrip('/')
        self.blocks, self.collections, self.views, self.users = {}, {}, {}, {}

    def post(self, ep, body, retry=3):
        for i in range(retry):
            try:
                req = urllib.request.Request(f'{self.site}/api/v3/{ep}', data=json.dumps(body).encode(),
                                             headers={'content-type': 'application/json', 'user-agent': UA})
                time.sleep(0.2)  # 요청 간격 (Cloudflare 차단 방지)
                return json.load(urllib.request.urlopen(req, timeout=60))
            except Exception as e:
                if i == retry - 1:
                    raise
                print(f'  retry {ep}: {e}')
                time.sleep(2 * (i + 1))

    def _absorb(self, rm):
        val = lambda x: x['value'].get('value', x['value']) if isinstance(x.get('value'), dict) else None
        for table, store in (('block', self.blocks), ('collection', self.collections),
                             ('collection_view', self.views), ('notion_user', self.users)):
            for k, v in rm.get(table, {}).items():
                vv = val(v)
                if vv:
                    store[k] = vv

    def load_page(self, pid):
        cursor, chunk = {'stack': []}, 0
        while True:
            r = self.post('loadPageChunk', {'pageId': pid, 'limit': 100, 'cursor': cursor,
                                             'chunkNumber': chunk, 'verticalColumns': False})
            self._absorb(r.get('recordMap', {}))
            cursor = r.get('cursor', {'stack': []})
            chunk += 1
            if not cursor.get('stack'):
                break
        self.fill_missing(pid)

    def fetch(self, ids, table='block'):
        ids = [i for i in ids if i not in (self.blocks if table == 'block' else self.collections)]
        for i in range(0, len(ids), 50):
            reqs = [{'pointer': {'table': table, 'id': x}, 'version': -1} for x in ids[i:i + 50]]
            r = self.post('syncRecordValuesMain', {'requests': reqs})  # syncRecordValues는 403
            self._absorb(r.get('recordMap', {}))

    def fill_missing(self, root):
        """접힌 토글 등으로 아직 안 받은 하위 블록을 끝까지 받아온다 (하위 page 본문은 제외)."""
        todo = [root]
        seen = set()
        while todo:
            bid = todo.pop()
            if bid in seen:
                continue
            seen.add(bid)
            b = self.blocks.get(bid)
            if not b:
                continue
            if b.get('type') == 'page' and bid != root:
                continue
            kids = b.get('content', [])
            missing = [k for k in kids if k not in self.blocks]
            if missing:
                self.fetch(missing)
            todo += kids
            ptr = b.get('format', {}).get('transclusion_reference_pointer', {}).get('id')
            if ptr:
                if ptr not in self.blocks:
                    self.fetch([ptr])
                todo.append(ptr)

    def query(self, cv_block):
        """collection_view 블록 → (collection, view, 행 id 목록)."""
        vid = cv_block['view_ids'][0]
        if vid not in self.views:
            self.fetch([vid], 'collection_view')
        view = self.views.get(vid, {})
        cid = cv_block.get('collection_id') or view.get('format', {}).get('collection_pointer', {}).get('id')
        if not cid:
            return None, view, []
        if cid not in self.collections:
            self.fetch([cid], 'collection')
        r = self.post('queryCollection', {
            'collection': {'id': cid, 'spaceId': cv_block['space_id']},
            'collectionView': {'id': vid, 'spaceId': cv_block['space_id']},
            'loader': {'type': 'reducer', 'reducers': {'collection_group_results': {'type': 'results', 'limit': 1000}},
                       'searchQuery': '', 'userTimeZone': 'Asia/Seoul'}})
        self._absorb(r.get('recordMap', {}))
        ids = r['result']['reducerResults']['collection_group_results']['blockIds']
        return self.collections.get(cid, {}), view, ids

    def download(self, url):
        req = urllib.request.Request(url, headers={'user-agent': UA})
        return urllib.request.urlopen(req, timeout=60).read()

    def signed_url(self, src, bid, space):
        r = self.post('getSignedFileUrls', {'urls': [{'url': src, 'permissionRecord':
                                                      {'table': 'block', 'id': bid, 'spaceId': space}}]})
        return (r.get('signedUrls') or [None])[0]


class PageWriter:
    def __init__(self, nt, folder_map):
        self.nt = nt
        self.folder_map = folder_map
        self.paths = {}      # page id -> 저장될 md 경로
        self.done = set()
        self.queue = []      # (page id, md 경로)
        self.log = []
        self.img_n = {}      # assets 폴더 -> 이번 실행에서 저장한 이미지 수

    # ---------- rich text ----------
    def rt(self, arr, md_path=None):
        out = []
        for seg in arr or []:
            text = seg[0]
            anns = seg[1] if len(seg) > 1 else []
            link = None
            marks = []
            for a in anns:
                k = a[0]
                if k == 'p':  # 페이지 멘션
                    pid = a[1]
                    title = self.title(pid) or 'page'
                    text, link = title, self.link_to(pid, md_path)
                elif k == 'u':
                    u = self.nt.users.get(a[1], {})
                    text = '@' + (u.get('name') or 'user')
                elif k == 'd':
                    d = a[1]
                    text = d.get('start_date', '') + (f" ~ {d['end_date']}" if d.get('end_date') else '') + \
                        (f" {d['start_time']}" if d.get('start_time') else '')
                elif k == 'lm':  # 링크 멘션 (‣ 로 표시되는 외부 링크 카드)
                    text, link = a[1].get('title') or a[1].get('href', ''), a[1].get('href')
                elif k == 'e':
                    text = f'${a[1]}$'
                elif k == 'a':
                    link = a[1]
                    if link.startswith('/'):
                        link = self.link_to(uuid(link), md_path) if re.search(r'[0-9a-f]{32}', link.replace('-', '')) \
                            else self.nt.site + link
                elif k in ('b', 'i', 's', 'c'):
                    marks.append(k)
            if 'c' in marks and text.strip():
                text = wrap(text, '`')
            if 'b' in marks:
                text = wrap(text, '**')
            if 'i' in marks:
                text = wrap(text, '*')
            if 's' in marks:
                text = wrap(text, '~~')
            if link and text.strip():
                text = f'[{text.strip()}]({link})'
            out.append(text)
        return ''.join(out).replace('****', '')

    def title(self, pid):
        b = self.nt.blocks.get(pid)
        if not b:
            try:
                self.nt.fetch([pid])
            except Exception:
                return None
            b = self.nt.blocks.get(pid)
        if not b:
            return None
        return ''.join(s[0] for s in b.get('properties', {}).get('title', [])).strip()

    def link_to(self, pid, md_path):
        if pid in self.paths and md_path is not None:
            return rel(self.paths[pid], md_path)
        return f"{self.nt.site}/{pid.replace('-', '')}"

    # ---------- assets ----------
    def asset(self, b, md_path, kind='image'):
        src = (b.get('properties', {}).get('source') or [['']])[0][0] or b.get('format', {}).get('display_source', '')
        if not src:
            return '', ''
        space = b.get('space_id', '')
        try:
            if kind == 'image':
                if src.startswith('http') and 'amazonaws' not in src and 'notion' not in src:
                    url = src
                else:
                    url = f"{self.nt.site}/image/{urllib.parse.quote(src, safe='')}?table=block&id={b['id']}&spaceId={space}&cache=v2"
            else:
                url = self.nt.signed_url(src, b['id'], space) if not src.startswith('http') or 'amazonaws' in src else src
                if not url:
                    return src, ''
            data = self.nt.download(url)
        except Exception as e:
            self.log.append(f'asset 실패 {md_path.name}: {src[:80]} ({e})')
            return src, ''
        adir = md_path.parent / f'assets_{slug(md_path.stem) or b["id"][:8]}'
        adir.mkdir(parents=True, exist_ok=True)
        if adir not in self.img_n:
            # 이번 실행에서 처음 쓰는 폴더: 이전 변환의 이미지를 지우고 번호를 1부터 다시 센다
            # (기존 파일 수로 번호를 매기면 다시 받을 때마다 img_05, img_06 ... 으로 쌓인다)
            for f in adir.glob('img_*'):
                f.unlink()
            self.img_n[adir] = 0
        if kind == 'image':
            self.img_n[adir] += 1
        n = self.img_n[adir]
        name = urllib.parse.unquote(src.split('?')[0].split('/')[-1].split(':')[-1]) or f'file_{n}'
        if kind == 'image':
            img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
            if img is not None:
                fn = f'img_{n:02d}.png'
                cv2.imwrite(str(adir / fn), img)
            else:
                ext = Path(name).suffix or '.bin'
                fn = f'img_{n:02d}{ext}'
                (adir / fn).write_bytes(data)
        else:
            fn = safe_name(name)
            (adir / fn).write_bytes(data)
        return src, f'{adir.name}/{fn}'

    # ---------- blocks ----------
    def children(self, b, md, ind):
        out, num, start = [], 0, 1
        for cid in b.get('content', []):
            c = self.nt.blocks.get(cid)
            if not c or not c.get('alive', True):
                continue
            if c.get('type') == 'numbered_list':
                num += 1
                if num == 1:  # 시작 번호는 연속된 목록의 첫 항목 값만 사용
                    start = c.get('format', {}).get('list_start_index', 1)
            else:
                num = 0
            out.append(self.block(c, md, ind, start + num - 1 if num else 0))
        return ''.join(out)

    def block(self, b, md, ind='', num=0):
        t = b.get('type')
        p = b.get('properties', {})
        f = b.get('format', {})
        text = self.rt(p.get('title'), md)
        kids = lambda extra='': self.children(b, md, ind + extra)

        if t in ('header', 'sub_header', 'sub_sub_header', 'header_4'):
            lvl = {'header': 2, 'sub_header': 3, 'sub_sub_header': 4, 'header_4': 5}[t]
            return f"\n{ind}{'#' * lvl} {text}\n\n" + kids()
        if t == 'text':
            body = '\n'.join(ind + l for l in text.split('\n')) + '\n\n' if text.strip() else ''
            return body + kids('    ')
        if t in ('bulleted_list', 'numbered_list', 'to_do'):
            if t == 'numbered_list':
                marker = f"{num}."
            elif t == 'to_do':
                marker = '- [x]' if (p.get('checked') or [['No']])[0][0] == 'Yes' else '- [ ]'
            else:
                marker = '-'
            sub = ' ' * (len(marker) + 1)
            lines = text.split('\n')
            body = f"{ind}{marker} {lines[0]}\n" + ''.join(f"{ind}{sub}{l}\n" for l in lines[1:])
            k = kids(sub)
            return body + ('\n' + k if k else '') + '\n'
        if t == 'toggle':
            k = kids('  ')
            return f"{ind}<details><summary>{text}</summary>\n\n{k}{ind}</details>\n\n"
        if t == 'quote':
            return quote(ind, (text + '\n\n' if text else '') + self.children(b, md, ''))
        if t == 'callout':
            icon = f.get('page_icon', '')
            icon = icon if icon and not icon.startswith('http') and '/' not in icon else ''
            inner = (text + '\n\n' if text else '') + self.children(b, md, '')
            return quote(ind, (icon + ' ' if icon else '') + inner)
        if t == 'code':
            lang = (p.get('language') or [['']])[0][0].lower()
            lang = {'plain text': '', 'shell': 'bash'}.get(lang, lang)
            code = ''.join(s[0] for s in p.get('title', []))
            cap = self.rt(p.get('caption'), md)
            out = f"{ind}```{lang}\n" + ''.join(f"{ind}{l}\n" for l in code.split('\n')) + f"{ind}```\n"
            return out + (f"{ind}*{cap}*\n" if cap else '') + '\n'
        if t == 'image':
            src, ref = self.asset(b, md, 'image')
            cap = self.rt(p.get('caption'), md)
            return f"{ind}![{cap or 'image'}]({ref or src})\n" + (f"{ind}*{cap}*\n" if cap else '') + '\n'
        if t in ('file', 'pdf'):
            src, ref = self.asset(b, md, 'file')
            name = text or (src.split('/')[-1] if src else 'file')
            return f"{ind}📎 [{name}]({ref or src})\n\n"
        if t in ('video', 'embed', 'audio', 'figma', 'gist', 'maps', 'drive', 'tweet', 'codepen'):
            src = (p.get('source') or [['']])[0][0] or f.get('display_source', '')
            cap = self.rt(p.get('caption'), md)
            return f"{ind}🔗 {t}: <{src}>" + (f" — {cap}" if cap else '') + '\n\n'
        if t == 'bookmark':
            link = (p.get('link') or [['']])[0][0]
            desc = self.rt(p.get('description'), md)
            return f"{ind}🔖 [{text or link}]({link})" + (f" — {desc}" if desc else '') + '\n\n'
        if t == 'divider':
            return f"{ind}---\n\n"
        if t == 'equation':
            return f"{ind}$$\n{ind}{''.join(s[0] for s in p.get('title', []))}\n{ind}$$\n\n"
        if t == 'table':
            cols = f.get('table_block_column_order', [])
            rows = []
            for rid in b.get('content', []):
                r = self.nt.blocks.get(rid)
                if r:
                    rows.append([self.rt(r.get('properties', {}).get(c), md).replace('|', '\\|').replace('\n', '<br>')
                                 for c in cols])
            if not rows:
                return ''
            if not f.get('table_block_column_header'):
                rows.insert(0, [''] * len(cols))
            out = f"{ind}| " + ' | '.join(rows[0]) + ' |\n' + f"{ind}|" + '---|' * len(cols) + '\n'
            return out + ''.join(f"{ind}| " + ' | '.join(r) + ' |\n' for r in rows[1:]) + '\n'
        if t in ('column_list', 'column', 'transclusion_container'):
            return kids()
        if t == 'transclusion_reference':
            ptr = f.get('transclusion_reference_pointer', {}).get('id')
            src = self.nt.blocks.get(ptr)
            return self.children(src, md, ind) if src else ''
        if t in ('alias', 'link_to_page'):
            pid = f.get('alias_pointer', {}).get('id')
            return f"{ind}↗️ [{self.title(pid) or 'page'}]({self.link_to(pid, md)})\n\n" if pid else ''
        if t == 'page':
            path = self.register(b['id'], md.parent / md.stem / f"{safe_name(text)}.md")
            icon = f.get('page_icon', '')
            icon = icon + ' ' if icon and '/' not in icon else ''
            return f"{ind}📄 [{icon}{text}]({rel(path, md)})\n\n"
        if t in ('collection_view', 'collection_view_page'):
            return self.collection(b, md, ind)
        if t in ('table_of_contents', 'breadcrumb'):
            return ''
        # 모르는 블록: 텍스트와 하위 블록은 최대한 살린다
        self.log.append(f'알 수 없는 블록 {t} ({md.name})')
        return (f"{ind}{text}\n\n" if text else '') + kids()

    def collection(self, b, md, ind):
        coll, view, ids = self.nt.query(b)
        name = self.rt(coll.get('name'), md) or 'Database'
        out = f"\n{ind}#### 🗂️ {name}\n\n"
        desc = self.rt(coll.get('description'), md)
        if desc:
            out += f"{ind}{desc}\n\n"
        schema = coll.get('schema', {})
        props = [x['property'] for x in view.get('format', {}).get(f"{view.get('type', 'table')}_properties", [])
                 if x.get('visible', True) and x['property'] != 'title' and x['property'] in schema]
        rows = [self.nt.blocks[i] for i in ids if i in self.nt.blocks]
        # view에 정렬 조건이 있으면 그대로 적용 (공개 API 응답은 정렬이 안 되어 옴)
        for srt in reversed(view.get('query2', {}).get('sort', [])):
            key = srt.get('property')
            if key in schema or key == 'title':
                rows.sort(key=lambda r: natural(self.rt(r.get('properties', {}).get(key), md)),
                          reverse=srt.get('direction') == 'descending')
        sub = self.folder_map.get(re.sub(r'\s+', ' ', name).strip())
        folder = (md.parent / sub) if sub else (md.parent / md.stem / safe_name(name))
        out += f"{ind}| " + ' | '.join(['제목'] + [schema[pp]['name'] for pp in props]) + ' |\n'
        out += f"{ind}|" + '---|' * (len(props) + 1) + '\n'
        for n, r in enumerate(rows, 1):
            title = self.rt(r.get('properties', {}).get('title'), md) or 'untitled'
            cell = title
            if r.get('content'):  # 본문이 있는 행만 별도 md로 변환
                path = self.register(r['id'], folder / f"{n:02d}_{safe_name(title)}.md")
                cell = f"[{title}]({rel(path, md)})"
            vals = [self.prop(r, pp, schema[pp], md) for pp in props]
            out += f"{ind}| " + ' | '.join([cell] + vals) + ' |\n'
        return out + '\n'

    def prop(self, r, pid, sch, md):
        v = r.get('properties', {}).get(pid)
        if sch.get('type') == 'checkbox':
            return '✅' if v and v[0][0] == 'Yes' else ''
        return self.rt(v, md).replace('|', '\\|').replace('\n', ' ') if v else ''

    # ---------- page ----------
    def register(self, pid, path):
        if pid not in self.paths:
            self.paths[pid] = path
            self.queue.append(pid)
        return self.paths[pid]

    def write_page(self, pid):
        self.nt.load_page(pid)
        b = self.nt.blocks[pid]
        md = self.paths[pid]
        md.parent.mkdir(parents=True, exist_ok=True)
        title = self.title(pid) or 'untitled'
        icon = b.get('format', {}).get('page_icon', '')
        icon = icon + ' ' if icon and '/' not in icon else ''
        out = [f"# {icon}{title}\n\n> 원본: {self.nt.site}/{pid.replace('-', '')}  \n"
               f"> 최종 수정: {time.strftime('%Y-%m-%d %H:%M', time.localtime(b.get('last_edited_time', 0) / 1000))}"
               f" / 변환: {time.strftime('%Y-%m-%d %H:%M')}\n\n"]
        # DB 행이면 속성 표
        if b.get('parent_table') == 'collection':
            coll = self.nt.collections.get(b['parent_id'], {})
            rows = [(s['name'], self.prop(b, k, s, md)) for k, s in coll.get('schema', {}).items() if k != 'title']
            rows = [(k, v) for k, v in rows if v]
            if rows:
                out.append('| 속성 | 값 |\n|---|---|\n' + ''.join(f'| {k} | {v} |\n' for k, v in rows) + '\n')
        out.append(self.children(b, md, ''))
        text = re.sub(r'\n{3,}', '\n\n', ''.join(out)).strip() + '\n'
        md.write_text(text, encoding='utf-8')
        self.done.add(pid)
        print(f'  {md.relative_to(HERE) if HERE in md.parents else md}  ({len(text)} chars)')

    def run(self, root_id, root_path):
        self.register(root_id, root_path)
        while self.queue:
            pid = self.queue.pop(0)
            if pid not in self.done:
                self.write_page(pid)


def natural(s):
    """'1-2' < '1-10' 처럼 숫자를 숫자로 비교하는 정렬 key."""
    return [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', s or '')]


def wrap(s, mark):
    lead = s[:len(s) - len(s.lstrip())]
    trail = s[len(s.rstrip()):]
    return f'{lead}{mark}{s.strip()}{mark}{trail}' if s.strip() else s


def quote(ind, inner):
    return ''.join(f'{ind}> {l}\n' if l else f'{ind}>\n' for l in inner.rstrip('\n').split('\n')) + '\n'


def rel(target, md):
    import os
    return urllib.parse.quote(os.path.relpath(target, md.parent))


def convert(url, out_dir, folder_map=None):
    site = re.match(r'https?://[^/]+', url).group(0)
    nt = Notion(site)
    pid = uuid(url.split('?p=')[-1] if '?p=' in url else url.split('?')[0])
    w = PageWriter(nt, folder_map or {})
    nt.load_page(pid)
    title = w.title(pid) or 'index'
    out_dir = Path(out_dir)
    print(f'[{title}] -> {out_dir}')
    w.run(pid, out_dir / f'{safe_name(title)}.md')
    for l in w.log:
        print('  ⚠️ ', l)
    return w


def main():
    if len(sys.argv) >= 3:
        convert(sys.argv[1], sys.argv[2])
    else:
        for url, out, fmap in TARGETS:
            convert(url, out, fmap)


if __name__ == '__main__':
    main()

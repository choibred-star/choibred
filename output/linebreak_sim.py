# hwpx 본문 문단을 python-hwpx form_fit 으로 줄바꿈 시뮬레이션
import re, sys, zipfile
from dataclasses import replace
from hwpx.form_fit.measure import TextStyle, hancom_line_starts
W = 48189
def load(path):
    z = zipfile.ZipFile(path); h = z.read('Contents/header.xml').decode(); s = z.read('Contents/section0.xml').decode()
    fonts = dict(re.findall(r'<hh:font id="(\d+)" face="([^"]+)"', re.search(r'<hh:fontface lang="HANGUL".*?</hh:fontface>', h, re.S).group(0)))
    cp = {}
    for cid, b in re.findall(r'<hh:charPr id="(\d+)"(.*?)</hh:charPr>', h, re.S):
        cp[cid] = (int(re.search(r'height="(\d+)"', b).group(1)) / 100,
                   fonts[re.search(r'<hh:fontRef hangul="(\d+)"', b).group(1)],
                   int(re.search(r'<hh:spacing hangul="(-?\d+)"', b).group(1)))
    pp = {}
    for pid, b in re.findall(r'<hh:paraPr id="(\d+)"(.*?)</hh:paraPr>', h, re.S):
        case = re.search(r'<hp:case.*?</hp:case>', b, re.S)
        mi = re.search(r"<hc:intent value=\"(-?\d+)\"", case.group(0) if case else b); intent = int(mi.group(1)) if mi else 0
        pp[pid] = (intent, re.search(r'breakNonLatinWord="(\w+)"', b).group(1), re.search(r'horizontal="(\w+)"', b).group(1))
    return s, cp, pp
def paras(s):
    s = re.sub(r'<hp:tbl .*?</hp:tbl>', '', s, flags=re.S)
    for m in re.finditer(r'<hp:p [^>]*paraPrIDRef="(\d+)"[^>]*>(.*?)</hp:p>', s, re.S):
        runs = [(c, ''.join(re.findall(r'<hp:t>(.*?)</hp:t>', b, re.S))) for c, b in re.findall(r'<hp:run charPrIDRef="(\d+)"[^>]*>(.*?)</hp:run>', m.group(2), re.S)]
        yield m.group(1), runs
def lines(runs, intent, brk, cp, width=W):
    text, sizes, styles = '', [], []
    for c, t in runs:
        size, face, sp = cp[c]
        st = TextStyle(spacing=sp, hangul_face=face, glyph_face=face, break_non_latin_word=brk)
        for ch in t:
            text += ch; sizes.append(size); styles.append(st)
    if not text.strip(): return text, []
    base = replace(styles[0], indent=intent)
    ws = [width, width + min(intent, 0)]
    st = hancom_line_starts(text, ws, max(sizes), base, sizes=sizes, styles=styles)
    return text, [text[a:b] for a, b in zip(st, st[1:] + [len(text)])]
if __name__ == '__main__':
    s, cp, pp = load(sys.argv[1])
    for pid, runs in paras(s):
        intent, brk, al = pp[pid]
        text, ls = lines(runs, intent, brk, cp)
        if len(ls) > 1:
            print('|'.join(ls)); print()

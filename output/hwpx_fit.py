# -*- coding: utf-8 -*-
"""문단별 자간·줄나눔 결정 (v5.1)

   한글은 기본이 '어절 단위' 줄나눔이라, 띄어쓰기 없는 긴 덩어리
   (예: 동북아엘엔지허브터미널㈜(BS한양·GS에너지·전남도·여수시)가 줄 끝에 안 들어가면
   통째로 다음 줄로 넘어가고, 양쪽 맞춤이 남은 공간을 어절 사이에 벌려 넣는다.
   → 글자가 띄엄띄엄해지고, 심하면 첫 줄에 마커만 남는다.

   그래서 문단마다
   1) 한글과 같은 규칙으로 줄바꿈을 시뮬레이션하고(python-hwpx form_fit, 휴먼명조 실측 글자폭)
   2) 줄마다 '어절 사이에 더 벌어지는 폭'(em)을 재서
   3) 자간 BASE(-5%) 근처에서 그 값이 OK 이하가 되는 자간을 찾고(가까운 값 우선)
   4) 자간으로 안 되면 그 문단만 '글자 단위' 줄나눔으로 바꾼다.
"""

PT_MM = 0.352778          # 1pt = 0.352778mm

BASE = -5                 # 본문 기본 자간(%)
HI, LO = -2, -10          # 문단별로 허용하는 자간 범위(%)
OK = 0.25                 # 어절 사이에 더 벌어져도 되는 폭(em). 0.25em ≈ 4pt(16pt 본문)
ORPHAN = 5                # 마지막 줄에 이보다 적은 글자만 남으면 외톨이 줄로 본다
LONG = 10                 # 글자 단위로 끊어도 되는 덩어리 길이(띄어쓰기 없이 이어진 글자 수)

# 한글 paraPr breakNonLatinWord 값 — 이름과 반대로 동작한다(python-hwpx form_fit 실측).
WORD = "BREAK_WORD"       # 어절 단위(한글 기본)
CHAR = "KEEP_WORD"        # 글자 단위

try:
    from hwpx.form_fit.measure import TextStyle, hancom_line_starts, char_advance
    ENGINE = True
except ImportError:       # python-hwpx 6.8 미만 — 근사 계산으로 대체
    ENGINE = False


# ---------- 근사 글자폭 (내어쓰기 계산·엔진이 없을 때) ----------
def _em_factor(ch):
    """글자 하나가 차지하는 폭(em 배수) 추정"""
    o = ord(ch)
    if ch == " ":
        return 0.50
    if 0xAC00 <= o <= 0xD7A3 or 0x3130 <= o <= 0x318F or 0x4E00 <= o <= 0x9FFF:
        return 1.0
    if 0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF:
        return 1.0
    if ch in "㎡㎥㎞㎜㎘·—…→←↑↓□ㅇ○●▲◇「」『』％%℃①②③④⑤⑥⑦⑧⑨⑩㈜":
        return 1.0
    if ch.isdigit() or ("a" <= ch <= "z") or ("A" <= ch <= "Z"):
        return 0.55
    if ch in ".,:;'\"`!|/\\()[]{}-+=~<>&*_^’‘":
        return 0.50
    return 0.7


HU_PER_MM = 7200 / 25.4


# ---------- 줄바꿈 시뮬레이션 ----------
# chars = [(글자, 크기pt, 글꼴이름, 자간%), ...]   widths = [첫 줄 폭, 나머지 줄 폭] (HWPUNIT)

def _styles(chars, brk):
    cache, out = {}, []
    for _, _, face, sp in chars:
        key = (face, sp)
        if key not in cache:
            cache[key] = TextStyle(spacing=sp, hangul_face=face, glyph_face=face,
                                   break_non_latin_word=brk)
        out.append(cache[key])
    return out


def _advance(ch, size, st):
    if ENGINE:
        return char_advance(ch, size, st)
    return size * 100 * (_em_factor(ch) + st / 100.0)


def layout(chars, widths, brk=WORD):
    """한글과 같은 규칙으로 줄을 나눈다 → 각 줄의 (시작, 끝) 목록"""
    text = "".join(c[0] for c in chars)
    if not text.strip():
        return [(0, len(text))]
    if ENGINE:
        styles = _styles(chars, brk)
        starts = hancom_line_starts(text, widths, max(c[1] for c in chars), styles[0],
                                    sizes=[c[1] for c in chars], styles=styles)
    else:                                   # 근사: 공백에서만 끊는다
        starts, cur, start, k = [0], 0.0, 0, 0
        last_sp = None
        for i, (ch, size, _, sp) in enumerate(chars):
            w = widths[min(k, len(widths) - 1)]
            cur += _advance(ch, size, sp)
            if ch == " ":
                last_sp = i
            elif cur > w and last_sp is not None and last_sp > start:
                start = last_sp + 1
                starts.append(start)
                k += 1
                cur = sum(_advance(c[0], c[1], c[3]) for c in chars[start:i + 1])
                last_sp = None
    ends = starts[1:] + [len(text)]
    return list(zip(starts, ends))


def gaps(chars, widths, brk=WORD):
    """(줄 수, 가장 많이 벌어진 줄의 어절 사이 추가 폭 em, 외톨이 줄 여부).
       마지막 줄은 양쪽 맞춤을 안 하므로 벌어짐 계산에서 뺀다."""
    spans = layout(chars, widths, brk)
    styles = _styles(chars, brk) if ENGINE else None
    worst = 0.0
    for k, (a, b) in enumerate(spans[:-1]):
        while b > a and chars[b - 1][0] == " ":
            b -= 1
        used = 0.0
        for i in range(a, b):
            ch, size, _, sp = chars[i]
            used += _advance(ch, size, styles[i] if ENGINE else sp)
        lead = a
        while lead < b and chars[lead][0] == " ":
            lead += 1
        n_gap = sum(1 for i in range(lead, b) if chars[i][0] == " ")
        em = chars[a][1] * 100
        slack = widths[min(k, len(widths) - 1)] - used
        worst = max(worst, slack / max(n_gap, 1) / em)
    a, b = spans[-1]
    orphan = len(spans) > 1 and sum(1 for i in range(a, b) if chars[i][0] != " ") < ORPHAN
    return len(spans), worst, orphan


def clean_split(chars, widths, brk, long_=LONG):
    """글자 단위로 끊긴 곳이 모두 긴 덩어리(long_ 글자 이상) 안인지.
       '6,804|억원', '기화|송출설비' 처럼 짧은 낱말이 끊기면 False."""
    for a, _ in layout(chars, widths, brk)[1:]:
        if chars[a - 1][0] == " " or chars[a][0] == " ":
            continue
        l, r = a, a
        while l > 0 and chars[l - 1][0] != " ":
            l -= 1
        while r < len(chars) and chars[r][0] != " ":
            r += 1
        if r - l < long_:
            return False
    return True


def fit(build, widths, base=BASE, hi=HI, lo=LO, ok=OK):
    """build(자간) → chars. (자간, 줄나눔, 줄 수, 최대 벌어짐 em, 외톨이 줄) 을 돌려준다.

    1) 어절 단위에서 base 에 가까운 자간부터 시도해 벌어짐이 ok 이하이고 외톨이 줄이 없는 것 중
       줄 수가 가장 적은 것
    2) 없으면 글자 단위로 같은 방법. 단, 끊기는 곳이 긴 덩어리 안일 때만(clean_split)
    3) 그래도 없으면 벌어짐이 가장 작은 것
    """
    order = sorted(range(lo, hi + 1), key=lambda s: (abs(s - base), s > base))
    tried = []
    for brk in (WORD, CHAR):
        res = [(sp, brk) + gaps(build(sp), widths, brk) for sp in order]
        if brk == CHAR:
            res = [r for r in res if clean_split(build(r[0]), widths, CHAR)]
        tried += res
        good = [r for r in res if r[3] <= ok and not r[4]]
        if good:
            n = min(r[2] for r in good)
            return next(r for r in good if r[2] == n)      # order 순 = base 에 가까운 것
    return min(tried, key=lambda r: (r[4], round(r[3], 2), r[1] != WORD, abs(r[0] - base)))


def count_lines(chars, width, brk=WORD):
    return len(layout(chars, [width], brk))

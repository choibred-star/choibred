# -*- coding: utf-8 -*-
"""문단 끝에 글자 몇 개만 넘어가는 줄(외톨이 줄)을 없애기 위해 자간을 조인다.

   v5 원칙: 자간은 '문서 전체가 같은 값'이 기본이다.
   - 모든 본문 문단은 BASE(기본 -5%)로 통일한다.
   - 줄 수를 1줄 이상 줄일 수 있을 때만, MIN(기본 -10%)까지 1%씩 조인다.
   - 벌리는(+) 조정과 '줄 끝 빈 공간 줄이기' 조정은 하지 않는다.
     (v4 는 문단마다 +2 ~ -20% 로 널뛰어 문단끼리 글자 밀도가 달라 보였다)
"""

PT_MM = 0.352778          # 1pt = 0.352778mm

BASE = -5                 # 본문 기본 자간(%) — 문서 전체 공통
MIN = -10                 # 외톨이 줄을 없앨 때 허용하는 최대 조임(%)


# 실제 한글 렌더링과 대조해 보정한 값 (휴먼명조 기준 추정)
def _em_factor(ch):
    """글자 하나가 차지하는 폭(em 배수) 추정"""
    o = ord(ch)
    if ch == " ":
        return 0.50                    # 한글 글꼴의 공백은 반각(0.5em)
    if 0xAC00 <= o <= 0xD7A3:          # 한글 음절
        return 1.0
    if 0x3130 <= o <= 0x318F:          # 한글 자모
        return 1.0
    if 0x4E00 <= o <= 0x9FFF:          # 한자
        return 1.0
    if 0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF:   # 전각 기호·괄호
        return 1.0
    if ch in "㎡㎥㎞㎜㎘·—…→←↑↓□ㅇ○●▲◇「」『』％%℃①②③④⑤⑥⑦⑧⑨⑩㈜":
        return 1.0                     # % 는 한글 글꼴에서 전각으로 나온다
    if ch.isdigit():
        return 0.55
    if ("a" <= ch <= "z") or ("A" <= ch <= "Z"):
        return 0.55
    if ch in ".,:;'\"`!|/\\()[]{}-+=~<>&*_^’‘":
        return 0.50
    return 0.7


SAFETY = 1.03      # 추정 오차 대비 여유


def _widths(text, size_pt, spacing, locks=None):
    """글자별 진행폭(mm). locks[i] 가 True 인 글자는 항상 자간 0 으로 계산한다."""
    em = size_pt * PT_MM * SAFETY
    out = []
    for i, c in enumerate(text):
        sp = 0 if (locks and locks[i]) else spacing
        out.append(em * _em_factor(c) + em * sp / 100.0)
    return out


def count_lines(text, size_pt, spacing, first_w, rest_w, locks=None):
    """줄바꿈 시뮬레이션 -> 줄 수"""
    limit, cur, lines = first_w, 0.0, 1
    for w in _widths(text, size_pt, spacing, locks):
        if cur + w > limit + 1e-9:
            lines += 1
            limit, cur = rest_w, w
        else:
            cur += w
    return lines


def fit(text, size_pt, first_w, rest_w, base=BASE, min_spacing=MIN, locks=None):
    """자간(%)을 돌려준다. 기본은 base, 줄이 줄어들 때만 min_spacing 까지 조인다."""
    if not text.strip():
        return base
    n0 = count_lines(text, size_pt, base, first_w, rest_w, locks)
    if n0 == 1:
        return base
    for sp in range(base - 1, min_spacing - 1, -1):      # 약한 쪽부터
        if count_lines(text, size_pt, sp, first_w, rest_w, locks) < n0:
            return sp
    return base

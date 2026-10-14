# -*- coding: utf-8 -*-
"""개조식 보고서 — 한글(HWPX) 네이티브 생성 공통 모듈 (v5)
   참고 서식(HK로지텍 검토보고)의 규격을 따른다.

   v5 변경점
   - 자간: 문서 전체 BASE(-5%) 통일, 외톨이 줄을 없앨 때만 MIN(-10%)까지 조임
   - 표: 머리행 반복·셀 안쪽 여백 2mm/1mm·행 최소 높이·긴 글 열 자동 왼쪽 정렬
   - 표를 담는 문단: 줄간격 100%, 위아래 0 (표 위아래가 들쭉날쭉 벌어지는 것 방지)
   - 표 뒤 간격: 빈 문단으로 일정하게
   - 줄 배치 캐시(linesegarray) 제거 — patch() 가 처리

   사용법:  from v4_base import *   →  TITLE/H/O/D/M/N/TABLE …  →  save(path)"""
import re
from hwpx.document import HwpxDocument
from hwpx_style import char_pr, para_pr, border_fill, patch, HU_MM
import hwpx_fit
from hwpx_fit import fit, count_lines, WORD, CHAR, BASE as SPACING_BASE

# ---------- 서식 규격 (참고 문서에서 추출) ----------
FONT   = "휴먼명조"          # 본문
HFONT  = "HY헤드라인M"       # 제목·□ 항목
QFONT  = "맑은 고딕"         # 연도 앞 ’
BODY   = 16                  # 본문 pt
HEAD   = 15                  # □ 항목 pt
TSIZE  = 20                  # 제목 pt
TSPACE = -17                 # 제목 자간 %
TLINE  = 187                 # 제목 줄간격 %
LINE   = 157                 # 줄간격 %
TEXT_W = 170.0               # 본문 폭(mm) = A4 210 - 좌우 20+20
ALIGN  = "JUSTIFY"           # 양쪽 맞춤 — 오른쪽 끝을 채운다
NAVY   = "#25377C"
ORANGE = "#F39200"
LABELBG = "#263056"          # 참고자료 라벨 배경
GRAY   = "#999999"
GRAYBG = "#E5E5E5"
GAP_H, GAP_ITEM = 5.0, 1.0   # □ 위 5pt, 항목 사이 1pt
GAP_TABLE = 4                # 표 뒤 빈 문단 크기(pt)
CELL_LR, CELL_TB = 2.0, 1.0  # 표 셀 안쪽 여백(mm) 좌우 / 위아래
ROW_H = 8.0                  # 데이터 표 행 최소 높이(mm) — 내용이 길면 한글이 늘린다
HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"

d = HwpxDocument.new()
d.page.set_size(width=HU_MM(210), height=HU_MM(297), orientation="WIDELY")   # 세로
d.page.set_margins(left=HU_MM(20), right=HU_MM(20), top=HU_MM(10), bottom=HU_MM(10),
                   header=HU_MM(10), footer=HU_MM(10))

FID  = int(d.styles.ensure_font(FONT))
HFID = int(d.styles.ensure_font(HFONT))
QFID = int(d.styles.ensure_font(QFONT))
FACE = {FID: FONT, HFID: HFONT, QFID: QFONT}

_h0   = d.package.get_text("Contents/header.xml")
CBASE = len(re.findall(r'<hh:charPr id="', _h0))
PBASE = len(re.findall(r'<hh:paraPr id="', _h0))
CHAR_DEFS, PARA_DEFS = [], []
_cc, _pc = {}, {}


def cstyle(size_pt, bold=False, font_id=None, ratio=100, spacing=0, color="#000000"):
    key = (size_pt, bold, FID if font_id is None else font_id, ratio, spacing, color)
    if key not in _cc:
        cid = CBASE + len(CHAR_DEFS)
        CHAR_DEFS.append(char_pr(cid, key[2], size_pt, bold=bold, color=color,
                                 ratio=ratio, spacing=spacing))
        _cc[key] = cid
    return _cc[key]


def pstyle(align=ALIGN, hang=0.0, prev=0.0, nxt=0.0, border=None, line=LINE, brk=WORD):
    key = (align, hang, prev, nxt, border, line, brk)
    if key not in _pc:
        pid = PBASE + len(PARA_DEFS)
        PARA_DEFS.append(para_pr(pid, align, 0.0, hang, prev, nxt,
                                 line=line, border_fill_id=border, break_non_latin=brk))
        _pc[key] = pid
    return _pc[key]


EM = lambda pt: pt * 0.352778


def char_attrs(text, bold, size, spacing=0, lock=False, font=None):
    """글자마다 (글자, 크기, 굵게, 글꼴id, 자간).
       연도 앞 ’ 는 맑은 고딕, () 안은 1pt 작게. lock 이면 크기·자간 고정."""
    out, depth = [], 0
    for ch in text:
        sz = size if lock else (size - 1 if (depth > 0 or ch in "()") else size)
        out.append((ch, sz, bold, QFID if ch in "’'" else (font or FID), 0 if lock else spacing))
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
    return out


def split_runs(text, bold, size, spacing=0, lock=False, font=None):
    out, buf, cur = [], "", None
    for ch, sz, b, fid, sp in char_attrs(text, bold, size, spacing, lock, font):
        st = cstyle(sz, b, fid, 100, sp)
        if st != cur:
            if buf:
                out.append((buf, cur))
            buf, cur = "", st
        buf += ch
    if buf:
        out.append((buf, cur))
    return out


ADJUSTED = []


def para(parts, size=BODY, align=ALIGN, before=0.0, after=0.0,
         border=None, line=LINE, font=None, hang=None):
    """parts = [(text, bold, lock)] — 앞머리(마커+라벨)는 lock=True 로 준다.
       내어쓰기 폭은 앞머리 실제 폭으로 자동 계산한다."""
    parts = [(p_ + (False,))[:3] if len(p_) == 2 else p_ for p_ in parts]
    text  = "".join(t for t, _, _ in parts)

    if hang is None:
        hang = 0.0          # 내어쓰기는 HANG() 으로 따로 계산해 넘긴다

    def build(sp):
        return [(ch, sz, FACE[fid], s_)
                for txt, bold, lock in parts
                for ch, sz, _, fid, s_ in char_attrs(txt, bold, size, sp, lock, font)]

    spacing, brk = 0, WORD
    if align in ("JUSTIFY", "LEFT") and text.strip():
        widths = [HU_MM(TEXT_W), HU_MM(TEXT_W) - HU_MM(hang)]
        spacing, brk, _, worst, orphan = fit(build, widths)
        if spacing != SPACING_BASE or brk != WORD or worst > hwpx_fit.OK or orphan:
            ADJUSTED.append((spacing, brk, round(worst, 2), orphan, text.strip()[:30]))

    p = d.add_paragraph("", para_pr_id_ref=pstyle(align, hang, before, after, border, line, brk))
    for txt, bold, lock in parts:
        for chunk, cid in split_runs(txt, bold, size, spacing, lock, font):
            p.add_run(chunk, char_pr_id_ref=cid)
    return p


# ---------- 항목 사이 간격은 '빈 문단'으로 준다 ----------
# 문단 위/아래 간격만으로는 한글에서 거의 보이지 않는다. 실제 서식은
# 항목마다 1pt짜리 빈 문단을, □ 앞에는 5pt짜리 빈 문단을 끼워 넣는다.
_first_h = [True]


def SP(size_pt, font_id):
    p = d.add_paragraph("", para_pr_id_ref=pstyle("JUSTIFY", 0, 0, 0))
    p.add_run("", char_pr_id_ref=cstyle(size_pt, font_id=font_id, spacing=0))


def SP_ITEM():  SP(1, HFID)          # 항목 뒤 1pt
def SP_HEAD():  SP(5, FID)           # □ 앞 5pt


# ---------- 개조식 위계 (들여쓰기는 앞 공백 + 내어쓰기) ----------
# ---------- 내어쓰기: 마커 폭에서 계산하고 위계별 상·하한으로 묶는다 ----------
# 라벨((대상)·(재무성 확보 수준) 등) 길이는 넣지 않는다. 실제 서식 파일을 보면
# 라벨이 길든 짧든 내어쓰기가 11~13mm로 일정했고, 이는 마커 앞머리(" ㅇ ")의
# 폭과 일치한다. 라벨 폭까지 더하면 문단마다 값이 널뛰어 정렬이 무너진다.
HANG_RANGE = {          # (최소, 최대) mm — 계산값이 이 범위를 벗어나면 잘라낸다
    "H": (0.0, 0.0),
    "O": (11.0, 14.0),
    "D": (13.5, 16.5),
    "M": (16.0, 20.0),
    "N": (13.5, 16.5),
}


def HANG(level, prefix, size=BODY):
    """마커 앞머리의 실제 글자 폭을 재고 위계별 상·하한으로 묶는다."""
    from hwpx_fit import _em_factor
    lo, hi = HANG_RANGE[level]
    if hi == 0.0:
        return 0.0
    w = sum(_em_factor(c) for c in prefix) * EM(size)
    return min(max(w, lo), hi)


def H(t):
    if not _first_h[0]:
        SP_HEAD()
    _first_h[0] = False
    para([("□ " + t, False, True)], HEAD, before=GAP_H, after=GAP_ITEM,
         font=HFID, hang=HANG("H", "□ ", HEAD))
    SP_ITEM()


def O(b, r=""):
    para([(" ㅇ ", False, True), (b, True, True), (r, False, False)],
         after=GAP_ITEM, hang=HANG("O", " ㅇ "))
    SP_ITEM()


def D(b, r=""):
    para([("   - ", False, True), (b, bool(r), bool(r)), (r, False, False)],
         after=GAP_ITEM, hang=HANG("D", "   - "))
    SP_ITEM()


def M(t):
    para([("     ㆍ", False, True), (t, False, False)],
         after=GAP_ITEM, hang=HANG("M", "     ㆍ"))
    SP_ITEM()


def N(t):
    para([("    * " + t, False, False)], BODY - 3, after=GAP_ITEM,
         font=QFID, hang=HANG("N", "    * ", BODY - 3))
    SP_ITEM()


# ---------- 표 공통 ----------
def _holder():
    """표를 담는 문단 서식 — 줄간격 100%, 위아래 0. 기본 문단(함초롬 10pt·160%)을
       그대로 쓰면 표 위아래 간격이 표마다 달라 보인다."""
    return dict(para_pr_id_ref=pstyle("LEFT", 0, 0, 0, line=100),
                char_pr_id_ref=cstyle(1, font_id=FID))


def _margins(t, lr_mm, tb_mm):
    """표 안쪽 여백(inMargin)과 모든 셀 여백(cellMargin)을 같은 값으로 맞춘다."""
    v = dict(left=str(HU_MM(lr_mm)), right=str(HU_MM(lr_mm)),
             top=str(HU_MM(tb_mm)), bottom=str(HU_MM(tb_mm)))
    for e in [t.element.find(HP + "inMargin")] + list(t.element.iter(HP + "cellMargin")):
        if e is not None:
            for k, x in v.items():
                e.set(k, x)


def _row_heights(t, heights_hu):
    """행별 최소 높이를 넣고 표 전체 높이를 그 합으로 맞춘다."""
    for r, tr in enumerate(t.element.findall(HP + "tr")):
        for tc in tr.findall(HP + "tc"):
            tc.find(HP + "cellSz").set("height", str(heights_hu[r]))
    t.element.find(HP + "sz").set("height", str(sum(heights_hu)))


def GAP(pt=GAP_TABLE):
    SP(pt, FID)


# ---------- 제목 표 ----------
def TITLE(text, date):
    t = d.add_table(1, 1, width=HU_MM(TEXT_W), **_holder())
    t.set_cell_border_fill(0, 0, "__BF_TITLE__")
    c = t.cell(0, 0)
    c.text = text
    for e, k in ((t.element, "sz"), (c.element, "cellSz")):
        e.find("{http://www.hancom.co.kr/hwpml/2011/paragraph}" + k).set("height", "4800")
    for cp in c.paragraphs:
        cp.para_pr_id_ref = pstyle("CENTER", 0, 3, 3, line=TLINE)
        for run in cp.runs:
            run.char_pr_id_ref = cstyle(TSIZE, font_id=HFID, spacing=TSPACE)
    para([(date, False, True)], align="RIGHT", after=6)


# ---------- 법령 점선 박스 ----------
def LAWBOX(lines):
    t = d.add_table(1, 1, width=HU_MM(TEXT_W), **_holder())
    _margins(t, 3.0, 2.0)
    t.set_cell_border_fill(0, 0, "__BF_DASH__")
    c = t.cell(0, 0)
    c.text = lines[0]
    for extra in lines[1:]:
        c.add_paragraph(extra)
    for i, cp in enumerate(c.paragraphs):
        cp.para_pr_id_ref = pstyle("JUSTIFY", 0, 0, 0, line=140)
        for run in cp.runs:
            run.char_pr_id_ref = cstyle(BODY - 4, bold=(i == 0))
    GAP()


# ---------- 참고자료 라벨 (남색 박스 + 제목 박스) ----------
def REFLABEL(title):
    t = d.add_table(1, 3, width=HU_MM(TEXT_W), **_holder())
    t.set_column_widths([HU_MM(28), HU_MM(5), HU_MM(TEXT_W - 33)])
    t.set_cell_border_fill(0, 0, "__BF_LABEL__")
    t.set_cell_border_fill(0, 1, "__BF_GAP__")
    t.set_cell_border_fill(0, 2, "__BF_BOX__")
    for e in (t.element,):
        e.find("{http://www.hancom.co.kr/hwpml/2011/paragraph}sz").set("height", "2835")
    texts = ["참고자료", "", title]
    for i, txt in enumerate(texts):
        c = t.cell(0, i)
        c.element.find("{http://www.hancom.co.kr/hwpml/2011/paragraph}cellSz").set("height", "2835")
        c.text = txt
        for cp in c.paragraphs:
            cp.para_pr_id_ref = pstyle("CENTER", 0, 0, 0, line=120)
            for run in cp.runs:
                run.char_pr_id_ref = cstyle(HEAD + 2 if i == 0 else HEAD, font_id=HFID,
                                            color="#FFFFFF" if i == 0 else "#000000")
    GAP()


# ---------- 데이터 표 (회색 실선 + 머리행 음영) ----------
TSIZE_CELL = BODY - 4        # 표 글자 12pt


def _col_align(rows, widths_mm, header_rows):
    """열마다 정렬을 정한다. 본문 칸 글이 한 줄에 들어가면 가운데, 넘치면 왼쪽(양쪽).
       긴 글을 가운데 정렬하면 줄마다 시작 위치가 달라 표가 지저분해 보인다."""
    out = []
    for c_, w in enumerate(widths_mm):
        inner = w - 2 * CELL_LR
        long_ = any(count_lines([(ch, TSIZE_CELL, FONT, SPACING_BASE) for ch in row[c_]],
                                HU_MM(inner)) > 1
                    for row in rows[header_rows:])
        out.append("JUSTIFY" if long_ else "CENTER")
    return out


def TABLE(rows, widths_mm, aligns=None, header_rows=1, row_h=ROW_H, gap=GAP_TABLE):
    """회색 실선 표. 바깥 좌우 테두리는 넣지 않는다(열린 표).

    aligns   열별 정렬 리스트("CENTER"/"JUSTIFY"/"LEFT"). None 이면 자동.
    widths_mm 합이 본문 폭(TEXT_W)을 넘지 않게 한다. 넘으면 오류.
    """
    assert sum(widths_mm) <= TEXT_W + 0.01, f"표 폭 {sum(widths_mm)}mm > 본문 폭 {TEXT_W}mm"
    assert all(len(r) == len(widths_mm) for r in rows), "행마다 칸 수가 열 너비 수와 달라요"
    aligns = aligns or _col_align(rows, widths_mm, header_rows)
    t = d.add_table(len(rows), len(rows[0]), width=HU_MM(sum(widths_mm)), **_holder())
    t.set_column_widths([HU_MM(w) for w in widths_mm])
    last = len(rows[0]) - 1
    for r, row in enumerate(rows):
        is_head = r < header_rows
        for c_, val in enumerate(row):
            side = "_L" if c_ == 0 else ("_R" if c_ == last else "")
            t.set_cell_border_fill(r, c_, f"__BF_{'HEAD' if is_head else 'CELL'}{side}__")
            cell = t.cell(r, c_)
            cell.text = val
            al = "CENTER" if is_head else aligns[c_]
            for cp in cell.paragraphs:
                cp.para_pr_id_ref = pstyle(al, 0, 0, 0, line=130)
                for run in cp.runs:
                    run.char_pr_id_ref = cstyle(TSIZE_CELL, bold=is_head,
                                                spacing=SPACING_BASE)
    # 머리행: 쪽이 넘어가면 다음 쪽에 반복
    t.element.set("repeatHeader", "1" if header_rows else "0")
    for r, tr in enumerate(t.element.findall(HP + "tr")):
        for tc in tr.findall(HP + "tc"):
            tc.set("header", "1" if r < header_rows else "0")
    _margins(t, CELL_LR, CELL_TB)
    _row_heights(t, [HU_MM(row_h + (1.0 if r < header_rows else 0.0))
                     for r in range(len(rows))])
    if gap:
        GAP(gap)
    return t


BORDER_SPECS = [
    ("__BF_TITLE__", dict(top=("1.5 mm", NAVY), bottom=("1.0 mm", ORANGE))),
    ("__BF_DASH__",  dict(top=("0.12 mm", "#000000", "DASH"),
                          bottom=("0.12 mm", "#000000", "DASH"),
                          left=("0.12 mm", "#000000", "DASH"),
                          right=("0.12 mm", "#000000", "DASH"))),
    ("__BF_LABEL__", dict(top=("0.12 mm", "#000000"), bottom=("0.12 mm", "#000000"),
                          left=("0.12 mm", "#000000"), right=("0.12 mm", "#000000"),
                          fill=LABELBG)),
    ("__BF_GAP__",   dict()),
    ("__BF_BOX__",   dict(top=("0.12 mm", "#000000"), bottom=("0.12 mm", "#000000"),
                          left=("0.12 mm", "#000000"), right=("0.12 mm", "#000000"))),
    # 표 셀 — 머리행(HEAD)/본문(CELL) × 첫 열(_L)·끝 열(_R)·가운데
    ("__BF_HEAD__",   dict(top=("0.4 mm", GRAY), bottom=("0.4 mm", GRAY),
                           left=("0.12 mm", GRAY), right=("0.12 mm", GRAY), fill=GRAYBG)),
    ("__BF_HEAD_L__", dict(top=("0.4 mm", GRAY), bottom=("0.4 mm", GRAY),
                           right=("0.12 mm", GRAY), fill=GRAYBG)),
    ("__BF_HEAD_R__", dict(top=("0.4 mm", GRAY), bottom=("0.4 mm", GRAY),
                           left=("0.12 mm", GRAY), fill=GRAYBG)),
    ("__BF_CELL__",   dict(top=("0.12 mm", GRAY), bottom=("0.12 mm", GRAY),
                           left=("0.12 mm", GRAY), right=("0.12 mm", GRAY))),
    ("__BF_CELL_L__", dict(top=("0.12 mm", GRAY), bottom=("0.12 mm", GRAY),
                           right=("0.12 mm", GRAY))),
    ("__BF_CELL_R__", dict(top=("0.12 mm", GRAY), bottom=("0.12 mm", GRAY),
                           left=("0.12 mm", GRAY))),
]


def save(path):
    d.save_to_path(path, mode="rebuild")
    patch(path, CHAR_DEFS, PARA_DEFS, BORDER_SPECS)
    print("saved", path, f"| 자간 기본 {SPACING_BASE}%, 조정 문단 {len(ADJUSTED)}개"
          + ("" if hwpx_fit.ENGINE else "  (python-hwpx<6.8: 근사 계산)"))
    for sp, brk, worst, orphan, head in ADJUSTED:
        note = "글자 단위" if brk == CHAR else "어절 단위"
        warn = ("  ← 외톨이 줄. 문구를 줄이거나 늘릴 것" if orphan else
                "  ← 아직 벌어짐. 문구를 다듬을 것" if worst > hwpx_fit.OK else "")
        print(f"   자간 {sp:+d}% {note} 벌어짐 {worst:.2f}em | {head}{warn}")

# -*- coding: utf-8 -*-
"""python-hwpx 6.3.0은 새로 만든 charPr/paraPr을 header.xml에 기록하지 못한다.
   그래서 스타일 ID를 직접 지정해 문서를 만들고, 저장 후 header.xml에 정의를 주입한다."""
import re, zipfile, shutil, os

HU_MM = lambda mm: int(round(mm / 25.4 * 7200))   # mm  -> HWPUNIT(1/7200 inch)
HU_PT = lambda p_: int(round(p_ * 100))           # pt  -> HWPUNIT
SZ    = lambda p_: int(round(p_ * 100))           # pt  -> charPr height


def char_pr(cid, font_id, size_pt, bold=False, color="#000000", ratio=100, spacing=0):
    b = "<hh:bold/>" if bold else ""
    f = lambda a: f'{a}="{font_id}"'
    return (
        f'<hh:charPr id="{cid}" height="{SZ(size_pt)}" textColor="{color}" shadeColor="none" '
        f'useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="2">'
        f'<hh:fontRef {f("hangul")} {f("latin")} {f("hanja")} {f("japanese")} {f("other")} '
        f'{f("symbol")} {f("user")}/>'
        f'<hh:ratio hangul="{ratio}" latin="{ratio}" hanja="{ratio}" japanese="{ratio}" '
        f'other="{ratio}" symbol="{ratio}" user="{ratio}"/>'
        f'<hh:spacing hangul="{spacing}" latin="{spacing}" hanja="{spacing}" japanese="{spacing}" '
        f'other="{spacing}" symbol="{spacing}" user="{spacing}"/>'
        '<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        '<hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        f'{b}'
        '<hh:underline type="NONE" shape="SOLID" color="#000000"/>'
        '<hh:strikeout shape="NONE" color="#000000"/>'
        '<hh:outline type="NONE"/>'
        '<hh:shadow type="NONE" color="#C0C0C0" offsetX="10" offsetY="10"/>'
        '</hh:charPr>')


def para_pr(pid, align="LEFT", left_mm=0.0, hang_mm=0.0,
            prev_pt=0.0, next_pt=0.0, line=162, border_fill_id=None,
            break_non_latin="BREAK_WORD"):
    """hang_mm > 0 이면 내어쓰기(둘째 줄부터 그만큼 들여쓴다).

    주의) hp:switch 의 hp:case(HwpUnitChar) 분기는 한글이 우선해서 읽는데,
    이 분기의 값은 hp:default 의 '절반'으로 적어야 한다. 한글이 만든 파일을
    뜯어보면 intent 가 default -6878 / case -3439 처럼 정확히 2배 차이가 난다.
    두 분기에 같은 값을 넣으면 들여쓰기가 두 배로 적용되어 레이아웃이 무너진다.

    break_non_latin: 한글 줄나눔. 이름과 반대로 "BREAK_WORD" = 어절 단위(기본),
    "KEEP_WORD" = 글자 단위다(hwpx_fit.WORD / hwpx_fit.CHAR).
    """
    # 한글이 실제로 적용하는 값은 hp:case 쪽이다. 따라서 요청한 치수를 case 에 넣고
    # hp:default 에는 그 2배를 넣는다(한글이 만든 파일의 관례).
    half = {"intent": -HU_MM(hang_mm), "left": HU_MM(left_mm),
            "prev": HU_PT(prev_pt), "next": HU_PT(next_pt)}

    def margin(mul):
        v = {k: int(x) * mul for k, x in half.items()}
        return (f'<hh:margin>'
                f'<hc:intent value="{v["intent"]}" unit="HWPUNIT"/>'
                f'<hc:left value="{v["left"]}" unit="HWPUNIT"/>'
                f'<hc:right value="0" unit="HWPUNIT"/>'
                f'<hc:prev value="{v["prev"]}" unit="HWPUNIT"/>'
                f'<hc:next value="{v["next"]}" unit="HWPUNIT"/></hh:margin>'
                f'<hh:lineSpacing type="PERCENT" value="{line}" unit="HWPUNIT"/>')
    return (
        f'<hh:paraPr id="{pid}" tabPrIDRef="0" condense="0" fontLineHeight="0" '
        f'snapToGrid="0" suppressLineNumbers="0" checked="0" textDir="LTR">'
        f'<hh:align horizontal="{align}" vertical="BASELINE"/>'
        '<hh:heading type="NONE" idRef="0" level="0"/>'
        f'<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="{break_non_latin}" widowOrphan="0" '
        'keepWithNext="0" keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>'
        '<hh:autoSpacing eAsianEng="0" eAsianNum="0"/>'
        '<hp:switch><hp:case hp:required-namespace="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">'
        + margin(1) + '</hp:case><hp:default>' + margin(2) + '</hp:default></hp:switch>'
        f'<hh:border borderFillIDRef="{border_fill_id or 2}" offsetLeft="0" offsetRight="0" '
        f'offsetTop="{280 if border_fill_id else 0}" offsetBottom="{280 if border_fill_id else 0}" '
        'connect="0" ignoreMargin="0"/></hh:paraPr>')


def border_fill(bid, top=None, bottom=None, left=None, right=None, fill=None):
    """각 변은 ("0.5 mm", "#1F3864") 또는 ("0.12 mm", "#000000", "DASH") 형태.
       None 이면 선 없음. fill 은 셀 배경색(예 "#263056")."""
    def b(tag, v):
        if v is None:
            return f'<hh:{tag} type="NONE" width="0.12 mm" color="#000000"/>'
        typ = v[2] if len(v) > 2 else "SOLID"
        return f'<hh:{tag} type="{typ}" width="{v[0]}" color="{v[1]}"/>'
    br = ""
    if fill:
        br = ('<hc:fillBrush><hc:winBrush faceColor="%s" hatchColor="#FF000000" '
              'alpha="0"/></hc:fillBrush>' % fill)
    return (f'<hh:borderFill id="{bid}" threeD="0" shadow="0" centerLine="NONE" '
            'breakCellSeparateLine="0">'
            '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
            '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
            + b("leftBorder", left) + b("rightBorder", right)
            + b("topBorder", top) + b("bottomBorder", bottom)
            + '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
            + br + '</hh:borderFill>')


def patch(path, char_defs, para_defs, border_specs=()):
    """저장된 hwpx의 header.xml에 스타일 정의를 주입하고 itemCnt를 실제 개수로 맞춘다.
    section 의 줄 배치 캐시(hp:linesegarray)도 지워 한글이 새로 계산하게 한다.

    border_specs = [(자리표시자, {top:(폭,색), bottom:(폭,색), left:…, right:…}), ...]
    borderFill 번호는 파일을 열어 실제 최대값 다음으로 확정하고,
    header(문단 테두리)와 section(표 셀 테두리)의 자리표시자를 모두 치환한다.
    """
    tmp = path + ".tmp"
    # borderFill 실제 번호를 먼저 확정한다 (header 를 한 번 읽어서)
    with zipfile.ZipFile(path) as zin:
        _h = zin.read("Contents/header.xml").decode("utf-8")
    nxt0 = max(int(x) for x in re.findall(r'<hh:borderFill id="(\d+)"', _h)) + 1
    ph_map, bdefs, nxt = {}, [], nxt0
    for ph, spec in border_specs:
        ph_map[ph] = str(nxt)
        bdefs.append(border_fill(nxt, **spec))
        nxt += 1
    for ph, real in ph_map.items():
        para_defs = [q.replace(ph, real) for q in para_defs]

    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            data = zin.read(it.filename)
            # 본문(section) 안의 자리표시자도 실제 번호로 치환 (제목 표 셀 테두리 등)
            if it.filename.startswith("Contents/section"):
                t = data.decode("utf-8")
                for ph, real in ph_map.items():
                    t = t.replace(ph, real)
                # 줄 배치 캐시(linesegarray)를 지운다. 빈 문서 템플릿에 남은 값(폭 150mm 등)이
                # 실제 본문 폭과 달라 한글이 첫 화면을 그 값으로 그리는 일을 막는다.
                # 지우면 한글이 열 때 줄 배치를 새로 계산한다.
                t = re.sub(r"<hp:linesegarray>.*?</hp:linesegarray>", "", t, flags=re.S)
                data = t.encode("utf-8")
            if it.filename == "Contents/header.xml":
                h = data.decode("utf-8")
                if bdefs:
                    h = h.replace("</hh:borderFills>", "".join(bdefs) + "</hh:borderFills>")
                    n = len(re.findall(r'<hh:borderFill id="', h))
                    h = re.sub(r'<hh:borderFills itemCnt="\d+">',
                               f'<hh:borderFills itemCnt="{n}">', h)
                h = h.replace("</hh:charProperties>", "".join(char_defs) + "</hh:charProperties>")
                h = h.replace("</hh:paraProperties>", "".join(para_defs) + "</hh:paraProperties>")
                for tag in ("charProperties", "paraProperties"):
                    body = re.search(rf'<hh:{tag} itemCnt="\d+">(.*?)</hh:{tag}>', h, re.S).group(1)
                    n = len(re.findall(rf'<hh:{tag[:-10]}Pr id="', body))
                    h = re.sub(rf'<hh:{tag} itemCnt="\d+">', f'<hh:{tag} itemCnt="{n}">', h)
                data = h.encode("utf-8")
            zi = zipfile.ZipInfo(it.filename, date_time=it.date_time)
            zi.compress_type = (zipfile.ZIP_STORED if it.filename == "mimetype"
                                else zipfile.ZIP_DEFLATED)
            zout.writestr(zi, data)
    os.replace(tmp, path)

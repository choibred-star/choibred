---
name: "korean-hwpx-report"
description: 한국 행정기관식 개조식(□·ㅇ·-·ㆍ·*) 보고서를 한글 파일(.hwpx)로 직접 생성한다. Word 변환 없이 네이티브로 만들어 서식 손실이 없다. 본문 휴먼명조 16pt 양쪽맞춤·A4 세로·제목은 HY헤드라인M 20pt를 1행 1열 표에 넣고 위 남색 아래 주황 줄·연도 앞 '는 맑은 고딕·괄호 안 1pt 축소·자간 문서 전체 -5% 통일(외톨이 줄만 -10%까지)·머리행 반복 데이터 표·참고자료 라벨 박스와 법령 점선 박스를 적용한다. 사용자가 '한글 파일로', 'hwp/hwpx로', '아래아한글로', '한글 보고서', 'HWP 공문', '개조식 보고서를 한글로', 'docx를 한글로' 같은 요청을 하거나, 공공기관 보고자료를 한글 형식으로 원하면 명시적으로 'hwpx'라 말하지 않아도 반드시 이 스킬을 사용할 것. Word(.docx) 결과물을 원하면 korean-gov-report 스킬을 대신 쓴다.
---

# 한글(HWPX) 개조식 보고서 생성

DOCX를 만들어 한글에서 변환하지 말 것. 변환하면 탭·내어쓰기·표 폭이 반드시 틀어진다.
`python-hwpx`로 HWPX(OWPML)를 직접 만든다.

## 0. 준비

```bash
pip install python-hwpx --break-system-packages
```

`scripts/` 의 파이썬 파일 네 개(`hwpx_style.py`, `hwpx_fit.py`, `v4_base.py`, `example_build.py`)를
작업 폴더로 복사한다. 서식은 모두 `v4_base.py` 에 있으므로 보고서 스크립트는 본문만 쓴다.

```python
from v4_base import *        # TITLE · H · O · D · M · N · TABLE · REFLABEL · LAWBOX · GAP · save
```

## 1. 반드시 지켜야 할 함정 여섯 가지

이 라이브러리와 한글 포맷에는 모르면 반드시 걸리는 함정이 있다.

### (1) 라이브러리가 새 스타일을 저장하지 못한다

`styles.ensure_run()` / `apply_paragraph_format()` 은 `itemCnt` 만 올리고 정의를 header.xml에
쓰지 않는다(6.3.0 확인). 그래서 **스타일 ID를 직접 배정하고, 저장 후 `patch()` 로 주입**한다.
`scripts/hwpx_style.py` 가 이 일을 한다.

### (2) 스타일 ID는 반드시 연속이어야 한다

한글은 charPr/paraPr을 id가 아니라 **순번**으로 참조한다. 0~6 다음에 100번을 쓰면 문서 전체가
기본 서식으로 초기화된다. 빈 문서의 기존 개수를 세어 그 다음 번호부터 연속 배정할 것.

```python
_h0   = d.package.get_text("Contents/header.xml")
CBASE = len(re.findall(r'<hh:charPr id="', _h0))
PBASE = len(re.findall(r'<hh:paraPr id="', _h0))
```

borderFill은 표를 만들 때 한글이 하나 더 추가하므로 **저장이 끝난 뒤** 최대값+1로 확정한다
(`patch()` 가 자리표시자를 치환해 준다).

### (3) 세로 용지는 `landscape="WIDELY"` 다

이름과 반대다. `NARROWLY` 를 넣으면 가로로 나온다.

```python
d.page.set_size(width=HU_MM(210), height=HU_MM(297), orientation="WIDELY")
```

### (4) 실제로 적용되는 값은 hp:case 쪽이다

문단 여백은 `hp:switch` 안에 두 번 기록된다. **한글이 화면에 적용하는 값은
`hp:case`(HwpUnitChar) 분기이고, `hp:default` 에는 그 2배를 적어야 한다.**

```
한글이 만든 파일:  case: intent -3439(≈12mm, 실제 적용)   default: intent -6878
```

그래서 `hwpx_style.para_pr(hang_mm=...)` 에 넘기는 값은 **실제로 적용되기를 원하는
치수**이며, 함수가 case 에 그 값을, default 에 2배를 넣는다. 반대로 넣으면
들여쓰기가 절반만 먹어서 둘째 줄이 왼쪽으로 튀어나온다.

두 분기에 같은 값을 넣어도 안 된다(두 배로 적용된다).
가운데·오른쪽 정렬 문단에는 내어쓰기를 넣지 말 것(0으로 둘 것).

### (5) 표 셀 테두리 번호는 section 에도 들어간다

제목 표처럼 셀 테두리를 지정하면 `borderFillIDRef` 가 **section0.xml** 에 기록된다.
`patch()` 는 header 와 section 양쪽의 자리표시자를 모두 치환하므로, 셀 지정도
자리표시자로 넘긴다.

```python
t = d.add_table(1, 1, width=HU_MM(180))
t.set_cell_border_fill(0, 0, "__TITLE_BF__")   # patch 에서 실제 번호로
```

### (6) 그림·표는 라이브러리 API로

`add_picture(data, "jpg", width_mm=, height_mm=, align="CENTER")`,
`add_table(rows, cols, width=HU_MM(180))` 은 정상 동작한다. 표 셀은 텍스트를 넣은 뒤
셀 문단의 `para_pr_id_ref` 와 run의 `char_pr_id_ref` 를 직접 지정한다.

## 2. 서식 규격

| 항목 | 값 |
|---|---|
| 용지 | A4 세로, 좌우 여백 20mm, 상하 10mm (본문 폭 170mm) |
| 본문 | 휴먼명조 16pt, **줄간격 157%**, **양쪽 맞춤(JUSTIFY)** |
| 위계 | □ HY헤드라인M 15pt / ㅇ·-·ㆍ 휴먼명조 16pt / * 각주 맑은 고딕 13pt |
| 들여쓰기 | 앞 공백으로 준다 — □ 없음, `　ㅇ `, `　　- `, `　　　ㆍ`, `　　* ` |
| 내어쓰기 | **마커 앞머리 폭에서 계산하고 위계별 상·하한으로 묶는다** — ㅇ 11~14mm, - 13.5~16.5mm, ㆍ 16~20mm, * 13.5~16.5mm, □ 0. 라벨((대상)·(재무성 확보 수준) 등) 폭은 더하지 않는다. 실제 서식에서 라벨 길이와 무관하게 11~13mm로 일정했고, 이는 앞머리 " ㅇ " 폭과 일치한다 |
| **문단 간격** | **빈 문단으로 준다.** 항목마다 뒤에 1pt(HY헤드라인M) 빈 문단, □ 앞에 5pt(휴먼명조) 빈 문단. 문단 위/아래 간격(5pt·1pt)도 함께 준다 |
| 제목 | 1행 1열 표. HY헤드라인M **20pt 자간 -17, 줄간격 187%** 가운데, 셀 위 남색 1.5mm(#25377C) / 아래 주황 1.0mm(#F39200), 좌우 선 없음, 셀 높이 4800 |
| 연도 앞 ’ | 맑은 고딕 |
| 괄호 안 글자 | 본문보다 1pt 작게 (단, ㅇ 옆 라벨은 예외 — 본문과 같은 크기) |
| 장평·자간 | **장평 100% 고정. 자간은 문서 전체 -5%로 통일**(`hwpx_fit.BASE`). 문단 끝에 몇 글자만 넘어가 줄이 하나 더 생길 때만 **-10%까지**(`hwpx_fit.MIN`) 1%씩 조여 그 줄을 끌어올린다. 벌리는(+) 조정은 하지 않는다 |
| 예외 | 마커와 (라벨) 은 크기·자간 고정(100%/0%) |

## 3. 자간 — 통일이 먼저, 조정은 최소로

**문단마다 자간이 다르면 문단끼리 글자 밀도가 달라 보여 지저분해진다.** (v4 는 +2 ~ -20% 를
문단마다 다르게 써서, 같은 쪽 안에 -2%·-11%·-16%·-20% 문단이 섞였다.) 그래서 v5 는

- 모든 본문 문단(표 안 글자 포함)을 **BASE = -5%** 로 통일한다
- 줄 수를 **실제로 1줄 줄일 수 있을 때만** -6, -7 … **MIN = -10%** 까지 약한 쪽부터 시도한다
- 줄 끝 빈 공간을 줄이려는 조정, 벌리는(+) 조정은 하지 않는다 — 양쪽 맞춤이 처리한다
- 한 줄짜리 문단은 손대지 않는다. 장평은 건드리지 않는다

```python
spacing = fit(text, size_pt,
              first_w=TEXT_W,                 # 본문 폭 170mm (A4 210 - 좌우 20+20)
              rest_w =TEXT_W - hang_mm,
              locks=locks)                    # locks: 글자별 고정 여부 → int(%) 반환
```

`save()` 가 끝에 "자간 기본 -5%, 조정 문단 N개 [값들]" 을 출력한다. 조정 문단이 많거나
값이 MIN 에 몰리면 문장을 다듬는 게 낫다(자간으로 억지로 맞추지 말 것).
BASE·MIN 은 `hwpx_fit.py` 맨 위에서 바꾼다.

`locks` 는 글자 수와 길이가 같은 bool 리스트다. True인 글자는 조정 대상에서 빠지고
항상 100%/0%로 계산·출력되며, 괄호 안이어도 크기를 줄이지 않는다. 마커와 (라벨) 에 쓴다.

폭 계수는 실제 한글 렌더링과 대조해 보정한 값이다(공백 0.5em, `%`·`·`·`→`·`㎡` 전각 1.0em,
숫자·영문 0.55em). 결과가 예상과 다르면 `hwpx_fit._em_factor()` 의 계수를 조정한다.

## 4. 참고자료(붙임) 양식

세 가지를 `scripts/v4_base.py` 가 제공한다.

- `REFLABEL(제목)` — 1행 3열. 남색(#263056) 배경 + 흰 글자 17pt 「참고자료」 박스,
  간격 셀, 제목 박스(실선). 붙임 페이지마다 맨 위에 놓는다.
- `LAWBOX([줄, 줄, …])` — 사방 점선(0.12mm) 박스. 근거 법령 조문을 넣는다.
- `TABLE(rows, widths_mm, aligns=None, header_rows=1, row_h=8.0, gap=4)` — 회색(#999999) 실선,
  머리행은 회색 배경(#E5E5E5)에 위아래 0.4mm 굵은 선. 글자 12pt·줄간격 130%·자간 -5%.
  **바깥 좌·우 테두리는 넣지 않는다**(열린 표). 첫 열은 왼쪽 선을, 끝 열은 오른쪽 선을
  빼야 하므로 셀 서식이 머리/본문 × 첫열/끝열/가운데 = 6종으로 나뉜다.
  v5 에서 표가 깔끔해지도록 다음을 자동으로 한다.
  - **정렬**: 머리행은 가운데. 본문 칸은 열 단위로, 한 줄에 들어가면 가운데·넘치면 양쪽 정렬
    (긴 글을 가운데 정렬하면 줄마다 시작 위치가 달라 지저분하다). `aligns` 로 직접 지정 가능
  - **셀 안쪽 여백** 좌우 2mm·위아래 1mm(v4 는 위아래 0.5mm라 글자가 선에 붙었다)
  - **행 최소 높이** 8mm(머리행 9mm) — 행 높이가 들쭉날쭉하지 않다. 글이 길면 한글이 늘린다
  - **머리행 반복**(`repeatHeader`) — 쪽이 넘어가도 다음 쪽에 머리행이 나온다
  - 표를 담는 문단은 줄간격 100%·위아래 0, 표 뒤에는 4pt 빈 문단 → 표 위아래 간격이 일정
  - 열 너비 합이 본문 폭(170mm)을 넘거나 칸 수가 안 맞으면 오류를 낸다

  열 너비는 **글이 가장 긴 열에 가장 넓게** 준다. 짧은 열(시간·구분)은 25~35mm 가 무난하다.

## 5. 작성 순서

`scripts/v4_base.py` 가 서식 전체(용지·글꼴·스타일 캐시·위계 함수·표)를 정의한다.
`scripts/example_build.py` 를 복사해 본문만 갈아끼운다.

```python
from v4_base import *
TITLE("제목", "(’26. 10. 29.(목), 담당부서)")
H("점검 개요")                         # □
O("(일시) ", "’26. 10. 29.(목) …")     # ㅇ (라벨, 본문)
D("(개요) ", "…")                      # -
M("…")                                 # ㆍ
N("…")                                 # * 각주
TABLE(rows, [32, 55, 83])              # 데이터 표
save("report.hwpx")                    # 저장 + patch() + 자간 요약 출력
```

`save()` 안에서 `patch()` 가 스타일 주입, borderFill 번호 확정, **줄 배치 캐시(linesegarray) 제거**를
한다. linesegarray 는 한글이 마지막으로 계산한 줄 배치인데, 빈 문서 템플릿 값(폭 150mm)이 남아
있으면 한글이 첫 화면을 틀린 값으로 그린다. 지우면 한글이 열 때 새로 계산한다.

## 6. 만든 뒤 반드시 자체 점검

한글이 없는 환경에서는 눈으로 볼 수 없으므로 XML을 직접 검사한다.

```python
import zipfile, re
h = zipfile.ZipFile(path).read('Contents/header.xml').decode()
s = zipfile.ZipFile(path).read('Contents/section0.xml').decode()

for tag in ('charPr', 'paraPr', 'borderFill'):
    v = [int(x) for x in re.findall(rf'<hh:{tag} id="(\d+)"', h)]
    assert v == list(range(v[0], v[0] + len(v))), f"{tag} ID가 끊김"

assert max(int(x) for x in re.findall(r'charPrIDRef="(\d+)"', s)) \
       < len(re.findall(r'<hh:charPr id="', h)), "정의 안 된 charPr 참조"
assert 'landscape="WIDELY"' in s, "용지가 가로"

# hp:case 는 hp:default 의 절반이어야 한다
for m in re.finditer(r'<hh:paraPr id="\d+"(?:(?!</hh:paraPr>).)*?</hh:paraPr>', h, re.S):
    v = re.findall(r'<hc:intent value="(-?\d+)"', m.group(0))
    if len(v) == 2:
        assert int(v[1]) == int(v[0]) * 2, "case/default 배율 오류"
```

assert '<hp:linesegarray' not in s, "줄 배치 캐시가 남음"
assert '__BF' not in s, "borderFill 자리표시자가 남음"

# 자간은 BASE(-5)·제목(-17)·고정(0) 외에는 MIN(-10)까지 몇 개만 있어야 한다
sp = {c: int(re.search(r'<hh:spacing hangul="(-?\d+)"', b).group(1))
      for c, b in re.findall(r'<hh:charPr id="(\d+)"(.*?)</hh:charPr>', h, re.S)}
used = sorted({sp[c] for c in set(re.findall(r'charPrIDRef="(\d+)"', s))})
assert min(used) >= -17 and max(used) <= 0, used
```

`itemCnt` 가 실제 개수와 맞는지도 확인한다(`patch()` 가 맞춰주지만 검증할 것).

## 7. 사용자에게 알릴 것

한글이 설치된 환경이 아니면 **실제 렌더링을 확인할 수 없다.** 파일을 건네면서 이 점을
분명히 말하고, 깨지면 화면 캡처를 요청한다. 증상별 원인은 다음과 같다.

- 글꼴·크기가 전부 기본값 → 스타일 ID 불연속
- 들여쓰기만 이상 → paraPr margin 단위
- 용지가 가로 → `landscape` 값
- 표·그림만 깨짐 → 개체 구조
- 문단마다 글자 간격이 달라 보임 → 자간이 BASE 로 통일됐는지(6장 점검), 조정 문단 수
- 표 행 높이·여백이 들쭉날쭉 → `TABLE()` 대신 `d.add_table()` 을 직접 쓰지 않았는지
- 둘째 줄 들여쓰기가 마커 뒤 글자와 안 맞음 → `HANG_RANGE`(v4_base.py) 값을 1mm 단위로 조정

한글이 설치된 Windows에서 확실하게 만들어야 하면 `pyhwpx`(한글 COM 자동화)가 대안이다.

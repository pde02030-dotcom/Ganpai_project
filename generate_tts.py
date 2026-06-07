#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
faq_cache.json 의 모든 대본(FAQ·에스컬레이션·내레이션·케그이벤트)을
4개 언어 음성파일로 자동 생성한다. → audio/ 폴더에 저장 (1단 캐시 완성).

★ 이 스크립트는 '네 맥'에서 실행해라 (샌드박스는 TTS 네트워크가 막혀 있음).

백엔드 2가지:
  1) edge-tts  : 고품질 뉴럴 음성, .mp3 출력. 설치: pip install edge-tts
                 python3 generate_tts.py --backend edge
  2) say(macOS): 설치 불필요, 오프라인, .aiff 출력 (내장 TTS)
                 python3 generate_tts.py --backend say
  3) dryrun    : 음성 안 굽고 작업 목록만 확인 (로직 점검용)
                 python3 generate_tts.py --backend dryrun

빈칸([TOILET_CODE] 등 대문자 placeholder)이 남은 대본은 자동 SKIP.
→ faq_cache.json 의 화장실 비번/와이파이 값을 채운 뒤 다시 돌리면 그 파일도 생성됨.
"""

import json
import re
import sys
import subprocess
import asyncio
from pathlib import Path

ROOT = Path(__file__).parent
CACHE = ROOT / "faq_cache.json"
OUT = ROOT / "audio"

# [BEER] 변수 치환용 (케그 안내 sapporo/yebisu 2버전)
BEER_MAP = {
    "sapporo": {"ko": "삿포로", "en": "Sapporo", "ja": "サッポロ", "zh": "札幌"},
    "yebisu":  {"ko": "에비스", "en": "Yebisu", "ja": "エビス", "zh": "惠比寿"},
}

# edge-tts 뉴럴 음성
EDGE_VOICE = {
    "ko": "ko-KR-SunHiNeural",
    "en": "en-US-AriaNeural",
    "ja": "ja-JP-NanamiNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
}
# macOS say 음성
SAY_VOICE = {"ko": "Yuna", "en": "Samantha", "ja": "Kyoko", "zh": "Tingting"}

PLACEHOLDER = re.compile(r"\[[^\]]+\]")   # 미입력 변수: [TOILET_CODE], [화장실 비밀번호] 등 (모든 대괄호)


def collect_jobs(cache):
    """(text, out_filename) 작업 목록을 모은다."""
    jobs = []

    # 1) FAQ 9개
    for faq in cache["faqs"]:
        for lang, text in faq["answers"].items():
            jobs.append((text, faq["audio"][lang]))

    # 2) 에스컬레이션 (직원 호출 안내)
    for lang, text in cache["escalation"]["responses"].items():
        jobs.append((text, f"escalation_{lang}.mp3"))

    # 3) 맥주 설명 내레이션
    nb = cache["narration_beer"]
    for lang, text in nb["scripts"].items():
        jobs.append((text, nb["audio"][lang]))

    # 4) 케그 이벤트 ① 종 안내 (sapporo/yebisu 2버전, [BEER] 치환)
    ann = cache["narration_keg"]["step1_announce"]
    for variant, audios in ann["audio_variants"].items():
        for lang, text in ann["scripts"].items():
            filled = text.replace("[BEER]", BEER_MAP[variant][lang])
            jobs.append((filled, audios[lang]))

    # 5) 케그 이벤트 ② 가위바위보
    rps = cache["narration_keg"]["step2_event_rps"]
    for lang, text in rps["scripts"].items():
        jobs.append((text, rps["audio"][lang]))

    return jobs


def lang_of(filename):
    """파일명에서 언어코드 추출 (..._ko.mp3 → ko)."""
    stem = Path(filename).stem
    return stem.split("_")[-1]


async def gen_edge(jobs):
    import edge_tts
    for text, fname in jobs:
        lang = lang_of(fname)
        out = OUT / (Path(fname).stem + ".mp3")
        await edge_tts.Communicate(text, EDGE_VOICE[lang]).save(str(out))
        print(f"  ✅ {out.name}")


def gen_say(jobs):
    for text, fname in jobs:
        lang = lang_of(fname)
        out = OUT / (Path(fname).stem + ".aiff")   # say 는 aiff 출력
        subprocess.run(["say", "-v", SAY_VOICE[lang], "-o", str(out), text], check=True)
        print(f"  ✅ {out.name}")


def gen_dryrun(jobs):
    for text, fname in jobs:
        print(f"  · {fname:32s} ({lang_of(fname)}) {text[:40]}...")


def main():
    backend = "dryrun"
    if "--backend" in sys.argv:
        backend = sys.argv[sys.argv.index("--backend") + 1]

    cache = json.load(open(CACHE, encoding="utf-8"))
    all_jobs = collect_jobs(cache)

    # 빈칸 남은 대본 SKIP
    jobs, skipped = [], []
    for text, fname in all_jobs:
        (skipped if PLACEHOLDER.search(text) else jobs).append((text, fname))

    print(f"총 {len(all_jobs)}개 / 생성 {len(jobs)}개 / 보류(빈칸) {len(skipped)}개  [backend={backend}]")
    if skipped:
        print("  ⏸️ 빈칸으로 SKIP:", ", ".join(sorted({f for _, f in skipped})))
    print()

    OUT.mkdir(exist_ok=True)
    if backend == "edge":
        asyncio.run(gen_edge(jobs))
    elif backend == "say":
        gen_say(jobs)
    else:
        gen_dryrun(jobs)

    print(f"\n완료 → {OUT}/")


if __name__ == "__main__":
    main()

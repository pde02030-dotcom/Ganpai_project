#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
faq_cache.json 의 모든 대본(FAQ·에스컬레이션·내레이션·환영·케그)을
음성파일로 생성한다. → audio/<프로필>/ 폴더에 저장.

★ 이 스크립트는 '네 맥'에서 실행해라 (샌드박스는 TTS 네트워크가 막혀 있음).

음성 프로필 2종 (손님이 화면에서 선택):
  bold_f : 힘차고 당찬 여성 (기본)
  bold_m : 힘차고 당찬 남성 (같은 어조)
→ 프로필마다 같은 파일명으로 audio/<프로필>/ 에 저장. 프론트가 선택 재생.

백엔드:
  edge   : 3개 프로필 전부 생성, .mp3  (권장)  → pip install edge-tts
           python3 generate_tts.py --backend edge
  say    : 기본 프로필(bold_f)만, 오프라인 .aiff (macOS 내장)
           python3 generate_tts.py --backend say
  dryrun : 음성 안 굽고 목록만
           python3 generate_tts.py --backend dryrun

빈칸([CODE] 등 대괄호 placeholder) 남은 대본은 자동 SKIP.
콘텐츠 톤: calm(FAQ·내레이션·환영) / lively(케그) → 프로필 base 위에 가산.
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

# [BEER] 변수 치환 (케그 안내 sapporo/yebisu 2버전)
BEER_MAP = {
    "sapporo": {"ko": "삿포로", "en": "Sapporo", "ja": "サッポロ", "zh": "札幌"},
    "yebisu":  {"ko": "에비스", "en": "Yebisu", "ja": "エビス", "zh": "惠比寿"},
}

# ── 음성 프로필 (voice persona) ──
#   rate/pitch = 프로필 고유 기조(힘참). 콘텐츠 톤(TONE)이 여기에 가산된다.
VOICE_PROFILES = {
    "bold_f": {  # 힘차고 당찬 여성 (기본)
        "edge": {"ko": "ko-KR-SunHiNeural", "en": "en-US-JennyNeural",
                 "ja": "ja-JP-NanamiNeural", "zh": "zh-CN-XiaoyiNeural"},
        "say":  {"ko": "Yuna", "en": "Samantha", "ja": "Kyoko", "zh": "Tingting"},
        "rate": 8, "pitch": 8,
    },
    "bold_m": {  # 힘차고 당찬 남성 (같은 어조)
        "edge": {"ko": "ko-KR-InJoonNeural", "en": "en-US-GuyNeural",
                 "ja": "ja-JP-KeitaNeural", "zh": "zh-CN-YunjianNeural"},
        "say":  {"ko": "Yuna", "en": "Daniel", "ja": "Otoya", "zh": "Tingting"},
        "rate": 8, "pitch": 0,
    },
}
DEFAULT_PROFILE = "bold_f"

# ── 콘텐츠 톤(상황별) — 프로필 위에 가산 ──
TONE = {
    "calm":   {"rate": -8, "pitch": 0,  "say_wpm": 165},
    "lively": {"rate": 12, "pitch": 10, "say_wpm": 205},
}

PLACEHOLDER = re.compile(r"\[[^\]]+\]")   # 미입력 변수: [CODE] 등 (모든 대괄호)


def collect_jobs(cache):
    """(text, out_filename, tone) 작업 목록을 모은다. tone = 'calm' | 'lively'."""
    jobs = []

    # 1) FAQ 9개 (calm)
    for faq in cache["faqs"]:
        for lang, text in faq["answers"].items():
            jobs.append((text, faq["audio"][lang], "calm"))

    # 2) 에스컬레이션 (calm)
    for lang, text in cache["escalation"]["responses"].items():
        jobs.append((text, f"escalation_{lang}.mp3", "calm"))

    # 3) 맥주 설명 내레이션 (calm)
    nb = cache["narration_beer"]
    for lang, text in nb["scripts"].items():
        jobs.append((text, nb["audio"][lang], "calm"))

    # 4) 진입 환영 멘트 (calm)
    wc = cache.get("welcome")
    if wc:
        for lang, text in wc["scripts"].items():
            jobs.append((text, wc["audio"][lang], "calm"))

    # 5) 케그 이벤트 ① 종 안내 (sapporo/yebisu 2버전, [BEER] 치환) — lively
    ann = cache["narration_keg"]["step1_announce"]
    for variant, audios in ann["audio_variants"].items():
        for lang, text in ann["scripts"].items():
            filled = text.replace("[BEER]", BEER_MAP[variant][lang])
            jobs.append((filled, audios[lang], "lively"))

    # 6) 케그 이벤트 ② 가위바위보 (lively)
    rps = cache["narration_keg"]["step2_event_rps"]
    for lang, text in rps["scripts"].items():
        jobs.append((text, rps["audio"][lang], "lively"))

    return jobs


def lang_of(filename):
    """파일명에서 언어코드 추출 (..._ko.mp3 → ko)."""
    return Path(filename).stem.split("_")[-1]


async def gen_edge(jobs):
    import edge_tts
    for prof_name, prof in VOICE_PROFILES.items():
        outdir = OUT / prof_name
        outdir.mkdir(parents=True, exist_ok=True)
        print(f"\n▶ 프로필: {prof_name}")
        for text, fname, tone in jobs:
            lang = lang_of(fname)
            rate = prof["rate"] + TONE[tone]["rate"]
            pitch = prof["pitch"] + TONE[tone]["pitch"]
            out = outdir / (Path(fname).stem + ".mp3")
            await edge_tts.Communicate(
                text, prof["edge"][lang],
                rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz"
            ).save(str(out))
            print(f"  ✅ {prof_name}/{out.name}  [{tone} {rate:+d}% {pitch:+d}Hz]")


def gen_say(jobs):
    prof_name = DEFAULT_PROFILE
    prof = VOICE_PROFILES[prof_name]
    outdir = OUT / prof_name
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"\n▶ say 백엔드는 기본 프로필({prof_name})만 생성합니다 (.aiff, 오프라인).")
    for text, fname, tone in jobs:
        lang = lang_of(fname)
        wpm = TONE[tone]["say_wpm"]
        out = outdir / (Path(fname).stem + ".aiff")
        subprocess.run(["say", "-v", prof["say"][lang], "-r", str(wpm), "-o", str(out), text], check=True)
        print(f"  ✅ {prof_name}/{out.name}  [{tone}]")


def gen_dryrun(jobs):
    for prof_name in VOICE_PROFILES:
        for text, fname, tone in jobs:
            print(f"  · {prof_name}/{Path(fname).name:28s} ({lang_of(fname)}/{tone}) {text[:28]}...")


def main():
    backend = "dryrun"
    if "--backend" in sys.argv:
        backend = sys.argv[sys.argv.index("--backend") + 1]

    cache = json.load(open(CACHE, encoding="utf-8"))
    all_jobs = collect_jobs(cache)

    # 빈칸 남은 대본 SKIP
    jobs, skipped = [], []
    for text, fname, tone in all_jobs:
        (skipped if PLACEHOLDER.search(text) else jobs).append((text, fname, tone))

    nprof = 1 if backend == "say" else len(VOICE_PROFILES)
    print(f"대본 {len(jobs)}개 × 프로필 {nprof} = 총 {len(jobs) * nprof}개  [backend={backend}]")
    if skipped:
        print("  ⏸️ 빈칸으로 SKIP:", ", ".join(sorted({Path(f).name for _, f, _ in skipped})))
    print()

    OUT.mkdir(exist_ok=True)
    if backend == "edge":
        asyncio.run(gen_edge(jobs))
    elif backend == "say":
        gen_say(jobs)
    else:
        gen_dryrun(jobs)

    print(f"\n완료 → {OUT}/<프로필>/  (bold_f / bold_m)")


if __name__ == "__main__":
    main()

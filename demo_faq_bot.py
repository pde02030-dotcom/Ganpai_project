#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ganpai 광안2호점 — AI 음성 응대 데모 골격 (MVP 1단계 로직 검증용)
================================================================

이 스크립트가 보여주는 것 = 설계서 4장의 응답 파이프라인:

    [손님 음성] → ① STT → ② FAQ 매칭 → ┬─ 매칭 O → [1단] 즉답 (캐시 mp3)
                                        ├─ 곤란질문 → [직원 호출] 안내
                                        └─ 매칭 X → [2단] RAG+LLM (자리만)

★ 핵심: 이 데모는 API 키 없이 바로 돌아간다.
  STT / 임베딩 / LLM / TTS 가 들어갈 자리는 주석 [PLUG-IN] 으로 표시.
  지금은 그 자리에 '키 없이 되는 임시 구현'을 넣어 로직 흐름을 눈으로 확인한다.

실행:
    python3 demo_faq_bot.py                  # 예시 질문 + 내레이션 + 케그 이벤트 자동 시연
    python3 demo_faq_bot.py --chat           # 직접 타이핑 대화 (STT 결과를 타이핑으로 대체)
    python3 demo_faq_bot.py --narration ja   # 맥주 설명 내레이션 (지정 언어) 재생
    python3 demo_faq_bot.py --keg yebisu --lang zh   # 케그 이벤트(종+가위바위보) 재생

audio/ 폴더에 mp3가 있으면 실제로 소리가 재생된다(맥: afplay 내장). 없으면 텍스트만.
"""

import json
import sys
import shutil
import difflib
import subprocess
from pathlib import Path

CACHE_PATH = Path(__file__).parent / "faq_cache.json"
AUDIO_DIR = Path(__file__).parent / "audio"   # generate_tts.py 가 굽는 폴더


# ─────────────────────────────────────────────────────────────
# 0. 캐시 로드
# ─────────────────────────────────────────────────────────────
def load_cache():
    with open(CACHE_PATH, encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────
# ① STT (음성 → 텍스트)   [PLUG-IN]
# ─────────────────────────────────────────────────────────────
def speech_to_text(audio_input):
    """
    [PLUG-IN] 실서비스: 마이크 녹음(wav) → Whisper / Google STT 호출 → (텍스트, 언어코드) 반환.
    데모: 이미 텍스트로 받았다고 가정하고 그대로 돌려준다.
    """
    return audio_input


def detect_language(text):
    """
    아주 단순한 언어 감지 (데모용). 실서비스는 STT가 언어코드를 함께 반환하거나
    fasttext/langdetect 사용. 여기선 유니코드 범위로 ko/ja/zh/en 대충 구분.
    """
    for ch in text:
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3:            # 한글
            return "ko"
        if 0x3040 <= o <= 0x30FF:            # 히라가나/가타카나 → 일본어
            return "ja"
    # 한자만 있으면 중국어로(일본어는 위에서 가나로 먼저 잡힘)
    if any(0x4E00 <= ord(ch) <= 0x9FFF for ch in text):
        return "zh"
    return "en"


# ─────────────────────────────────────────────────────────────
# ② 매칭 (질문 → FAQ)   [PLUG-IN: 임베딩으로 교체 예정]
# ─────────────────────────────────────────────────────────────
def _keyword_hits(text, triggers):
    t = text.lower()
    return sum(1 for kw in triggers if kw.lower() in t)


def match_faq(text, lang, cache):
    """
    데모 매칭 = 트리거 키워드 포함 수 + 문장 유사도(difflib).
    [PLUG-IN] 실서비스: 질문 임베딩 ↔ FAQ 임베딩 코사인 유사도(pgvector)로 교체.
    반환: (faq dict 또는 None, score)
    """
    best, best_score = None, 0.0
    for faq in cache["faqs"]:
        triggers = faq["triggers"].get(lang, [])
        kw = _keyword_hits(text, triggers)
        # 키워드 히트가 강한 신호: 1개=0.5, 2개+=0.8. 문장 유사도는 보조(가중 0.3).
        # (짧은 질문 vs 긴 답변은 유사도가 낮게 나오므로 키워드를 주신호로 둔다.)
        kw_score = 0.8 if kw >= 2 else (0.5 if kw == 1 else 0.0)
        sim = difflib.SequenceMatcher(None, text.lower(),
                                      faq["answers"].get(lang, "").lower()).ratio()
        score = kw_score + 0.3 * sim
        if score > best_score:
            best, best_score = faq, score
    return best, best_score


def is_escalation(text, lang, cache):
    triggers = cache["escalation"]["triggers"].get(lang, [])
    return _keyword_hits(text, triggers) > 0


# ─────────────────────────────────────────────────────────────
# ③ TTS / 재생   [PLUG-IN]
# ─────────────────────────────────────────────────────────────
def play_audio(mp3_name):
    """
    1단 캐시 재생. audio/ 폴더에 해당 파일(.mp3 또는 say가 만든 .aiff)이 있으면 실제 재생.
    없으면 파일명만 출력(아직 TTS 안 구운 상태).
    [PLUG-IN] 실서비스: 앱/스피커 재생 SDK로 교체.
    """
    stem = Path(mp3_name).stem
    cand = None
    for ext in (".mp3", ".aiff", ".m4a", ".wav"):
        p = AUDIO_DIR / (stem + ext)
        if p.exists():
            cand = p
            break
    if not cand:
        print(f"   🔊 [재생예정] {mp3_name}  (audio/ 에 파일 없음 → generate_tts.py 먼저 실행)")
        return
    print(f"   🔊 [재생] {cand.name}")
    player = (shutil.which("afplay") or shutil.which("ffplay")
              or shutil.which("aplay") or shutil.which("mpg123"))
    if player:
        args = [player, str(cand)]
        if player.endswith("ffplay"):
            args = [player, "-nodisp", "-autoexit", "-loglevel", "quiet", str(cand)]
        try:
            subprocess.run(args, check=False)
        except Exception as e:
            print(f"      (재생 실패: {e})")
    else:
        print("      (재생기 없음: 맥은 afplay 기본 내장 / 리눅스는 mpg123 설치)")


# ─────────────────────────────────────────────────────────────
# ④ 2단 생성 (RAG + LLM)   [PLUG-IN]
# ─────────────────────────────────────────────────────────────
def generate_with_llm(text, lang, cache):
    """
    [PLUG-IN] 실서비스: RAG로 메뉴·가게정보 검색 → LLM(가게 페르소나) 생성 → TTS.
    반드시 '검색된 사실 안에서만' 답하게 하고, 모르면 직원 호출로 폴백(할루시네이션 차단).
    데모: 실제 호출 대신 폴백 메시지 출력.
    """
    fallback = {
        "ko": "(2단 생성 자리) 지금은 LLM 미연결 → 안전하게 직원 호출로 폴백합니다.",
        "en": "(LLM stage placeholder) LLM not connected — safely falling back to staff call.",
        "ja": "(LLM生成の箇所) 未接続のため、安全のためスタッフ呼び出しにフォールバックします。",
        "zh": "(LLM生成处) 未连接，为安全起见转为呼叫店员。",
    }
    return fallback.get(lang, fallback["en"])


# ─────────────────────────────────────────────────────────────
# 메인 응답 흐름 (설계서 4.1)
# ─────────────────────────────────────────────────────────────
def handle(audio_input, cache):
    text = speech_to_text(audio_input)          # ①
    lang = detect_language(text)
    print(f"🗣️  손님({lang}): {text}")

    # 곤란질문 우선 차단 → 직원 호출 (아날로그)
    if is_escalation(text, lang, cache):
        msg = cache["escalation"]["responses"].get(lang, cache["escalation"]["responses"]["en"])
        print(f"🙋 [직원 호출] {msg}")
        return

    faq, score = match_faq(text, lang, cache)     # ②
    threshold = cache["config"]["match_threshold"]

    if faq and score >= threshold:                # [1단] 즉답
        answer = faq["answers"].get(lang, faq["answers"]["en"])
        mp3 = faq["audio"].get(lang, faq["audio"]["en"])
        print(f"⚡ [1단·즉답 / {faq['id']} / score={score:.2f}]")
        print(f"   🤖 {answer}")
        play_audio(mp3)                           # ③
    else:                                         # [2단] 생성
        print(f"🐢 [2단·생성 / 매칭실패 score={score:.2f}]")
        print(f"   🤖 {generate_with_llm(text, lang, cache)}")   # ④
    print()


# ─────────────────────────────────────────────────────────────
# 확장 기능: 내레이션 / 케그 이벤트 재생 (탭 트리거 시뮬레이션)
# ─────────────────────────────────────────────────────────────
def play_narration(cache, lang="en"):
    """맥주 설명 내레이션 (버튼 탭 → 해당 언어 재생)."""
    nb = cache["narration_beer"]
    print(f"🍺 [맥주 설명 내레이션 / {lang}]")
    print(f"   🤖 {nb['scripts'].get(lang, nb['scripts']['en'])}")
    play_audio(nb["audio"].get(lang, nb["audio"]["en"]))
    print()


def play_keg(cache, beer="sapporo", lang="en"):
    """케그 교체 이벤트: ① 종 안내(맥주 변종) → ② 가위바위보."""
    keg = cache["narration_keg"]
    beer_word = {"sapporo": {"ko": "삿포로", "en": "Sapporo", "ja": "サッポロ", "zh": "札幌"},
                 "yebisu": {"ko": "에비스", "en": "Yebisu", "ja": "エビス", "zh": "惠比寿"}}[beer]

    ann = keg["step1_announce"]
    text1 = ann["scripts"].get(lang, ann["scripts"]["en"]).replace("[BEER]", beer_word[lang])
    print(f"🔔 [케그 교체 ① 종 안내 / {beer} / {lang}]")
    print(f"   🤖 {text1}")
    play_audio(ann["audio_variants"][beer].get(lang, ann["audio_variants"][beer]["en"]))

    rps = keg["step2_event_rps"]
    print(f"✊ [케그 교체 ② 가위바위보 / {lang}]")
    print(f"   🤖 {rps['scripts'].get(lang, rps['scripts']['en'])}")
    play_audio(rps["audio"].get(lang, rps["audio"]["en"]))
    print()


# ─────────────────────────────────────────────────────────────
# 실행부
# ─────────────────────────────────────────────────────────────
DEMO_QUESTIONS = [
    "추천 메뉴가 뭐예요?",            # ko / 1단 hit (recommend)
    "What time do you close?",        # en / 1단 hit (hours)
    "カードで払えますか？",            # ja / 1단 hit (payment)
    "这个辣吗？",                      # zh / 1단 hit (spicy)
    "땅콩 알레르기가 있는데 괜찮나요?",  # ko / 직원 호출 (escalation)
    "주차장 있어요?",                  # ko / 2단 폴백 (매칭 실패)
]


def _arg_after(flag, default=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
            return sys.argv[i + 1]
    return default


def main():
    cache = load_cache()
    print(f"=== {cache['store']['name_ko']} · AI 응대 데모 ===\n")

    # 확장 기능: 내레이션 / 케그 이벤트
    if "--narration" in sys.argv:
        play_narration(cache, _arg_after("--narration", "en"))
        return
    if "--keg" in sys.argv:
        play_keg(cache, _arg_after("--keg", "sapporo"), _arg_after("--lang", "en"))
        return

    if "--chat" in sys.argv:
        print("질문을 입력하세요 (종료: 빈 줄 / quit)\n")
        while True:
            try:
                q = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not q or q.lower() == "quit":
                break
            handle(q, cache)
    else:
        for q in DEMO_QUESTIONS:
            handle(q, cache)
        # 확장 기능 데모도 한 번씩 보여준다
        print("─" * 50)
        play_narration(cache, "en")
        play_keg(cache, "sapporo", "en")


if __name__ == "__main__":
    main()

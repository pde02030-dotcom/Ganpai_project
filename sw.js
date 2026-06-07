/* ganpai 키오스크 PWA 서비스워커 — 오프라인 캐싱
   콘텐츠/음성이 바뀌면 CACHE 버전을 올려라 (예: v5 → v6) → 자동 갱신.
   프리캐시: 기본 음성 프로필(bold_f) + 공용(종소리·아이콘·코어).
   다른 프로필(bold_m)은 재생 시 런타임 캐시(cache-first)로 자동 저장. */
const CACHE = "ganpai-v6";

const ASSETS = [
  "./","index.html","faq_cache.json","manifest.webmanifest",
  "icon-192.png","icon-512.png","apple-touch-icon.png",
  "audio/bell.mp3?v=6",
  "audio/bold_f/escalation_en.mp3","audio/bold_f/escalation_ja.mp3","audio/bold_f/escalation_ko.mp3","audio/bold_f/escalation_zh.mp3",
  "audio/bold_f/hours_en.mp3","audio/bold_f/hours_ja.mp3","audio/bold_f/hours_ko.mp3","audio/bold_f/hours_zh.mp3",
  "audio/bold_f/keg_announce_sapporo_en.mp3","audio/bold_f/keg_announce_sapporo_ja.mp3","audio/bold_f/keg_announce_sapporo_ko.mp3","audio/bold_f/keg_announce_sapporo_zh.mp3",
  "audio/bold_f/keg_announce_yebisu_en.mp3","audio/bold_f/keg_announce_yebisu_ja.mp3","audio/bold_f/keg_announce_yebisu_ko.mp3","audio/bold_f/keg_announce_yebisu_zh.mp3",
  "audio/bold_f/keg_rps_en.mp3","audio/bold_f/keg_rps_ja.mp3","audio/bold_f/keg_rps_ko.mp3","audio/bold_f/keg_rps_zh.mp3",
  "audio/bold_f/narration_en.mp3","audio/bold_f/narration_ja.mp3","audio/bold_f/narration_ko.mp3","audio/bold_f/narration_zh.mp3",
  "audio/bold_f/non_alcohol_en.mp3","audio/bold_f/non_alcohol_ja.mp3","audio/bold_f/non_alcohol_ko.mp3","audio/bold_f/non_alcohol_zh.mp3",
  "audio/bold_f/order_en.mp3","audio/bold_f/order_ja.mp3","audio/bold_f/order_ko.mp3","audio/bold_f/order_zh.mp3",
  "audio/bold_f/payment_en.mp3","audio/bold_f/payment_ja.mp3","audio/bold_f/payment_ko.mp3","audio/bold_f/payment_zh.mp3",
  "audio/bold_f/recommend_en.mp3","audio/bold_f/recommend_ja.mp3","audio/bold_f/recommend_ko.mp3","audio/bold_f/recommend_zh.mp3",
  "audio/bold_f/seat_charge_en.mp3","audio/bold_f/seat_charge_ja.mp3","audio/bold_f/seat_charge_ko.mp3","audio/bold_f/seat_charge_zh.mp3",
  "audio/bold_f/smoking_age_en.mp3","audio/bold_f/smoking_age_ja.mp3","audio/bold_f/smoking_age_ko.mp3","audio/bold_f/smoking_age_zh.mp3",
  "audio/bold_f/spicy_en.mp3","audio/bold_f/spicy_ja.mp3","audio/bold_f/spicy_ko.mp3","audio/bold_f/spicy_zh.mp3",
  "audio/bold_f/toilet_wifi_en.mp3","audio/bold_f/toilet_wifi_ja.mp3","audio/bold_f/toilet_wifi_ko.mp3","audio/bold_f/toilet_wifi_zh.mp3",
  "audio/bold_f/welcome_en.mp3","audio/bold_f/welcome_ja.mp3","audio/bold_f/welcome_ko.mp3","audio/bold_f/welcome_zh.mp3"
];

self.addEventListener("install", e=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting()));
});

self.addEventListener("activate", e=>{
  e.waitUntil(
    caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))))
      .then(()=>self.clients.claim())
  );
});

// cache-first: 한 번 캐시되면 오프라인에서도 즉시 재생 (다른 프로필도 재생 즉시 캐시됨)
self.addEventListener("fetch", e=>{
  if(e.request.method!=="GET") return;
  e.respondWith(
    caches.match(e.request).then(hit=> hit || fetch(e.request).then(res=>{
      const copy=res.clone();
      caches.open(CACHE).then(c=>c.put(e.request, copy)).catch(()=>{});
      return res;
    }).catch(()=>hit))
  );
});

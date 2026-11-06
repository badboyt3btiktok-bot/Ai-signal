# Agent City: شركة ايجنت مستقلة

أنت بتحكي مع **المدير (CEO)** بس. بتقله "بدي كذا"، وهو بيخطط، وبيوزع، والفريق بينفذ، وبيرجعلك تقرير.
بعد فترة بتجيبله طلب ثاني، فبيشتغل عليه والمدينة بتتذكر اللي تعلمته.

## شو بيميّزها
- **أي مشروع:** مش مربوطة بمجال. مؤشر الذهب هو مجرد أول مشروع (`examples/gold_indicator.txt`).
- **توظيف تلقائي (HR):** إذا المهمة بتحتاج دور مش موجود (مثلاً Data Scientist)، بتنخلق ايجنت جديد بصلاحيات أقل ما يمكن.
- **تعلّم:** أي ايجنت بيكتشف طريقة مفيدة بيحفظها كـ Skill (`save_skill`) وكل المدينة بتستفيد بالمشاريع الجاية. وبعد كل مشروع المدير بيسجّل دروس.
- **مراجعة مستقلة:** ايجنت QA بيفتح الملفات وبيشغّل الكود قبل ما تتحسب أي مهمة منتهية. إذا فشلت: إعادة، ثم المدير بيعيد صياغتها، ثم فشل معلن.
- **أمان:** صلاحيات لكل ايجنت حسب دوره، `shell` وأي فعل خارجي بحتاج موافقتك (بدون ما توقف باقي المدينة)، سقف توكنز لكل مشروع، سجل تدقيق `audit.jsonl`، وزر إيقاف طوارئ.

## التشغيل
```
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
python agentcity.py add --file examples/gold_indicator.txt
python agentcity.py run          # أو: serve  (المدينة بتضل شغالة وبتستنى طلباتك)
python agentcity.py status
python agentcity.py approvals    # أي شي استنى موافقتك
python agentcity.py approve a1   # ثم run
python agentcity.py stop         # إيقاف طوارئ فوري (resume للاستئناف)
python agentcity.py sandbox      # ابني صورة Docker لعزل كود الايجنت (مرة وحدة)
python agentcity.py data         # نزّل بيانات الذهب وجمّدها (الـ sandbox بدون إنترنت)
python agentcity.py web          # واجهة مراقبة وموافقات للموبايل (بيطبع رابط فيه توكن)، وفيها /city
python agentcity.py view         # صفحة HTML بتوريك المدينة: أفق الايجنت، هيكل الشركة، الفريق، المشاريع، الخط الزمني
python tests/test_city.py        # اختبار منطق المدينة بدون API
python tests/test_improvements.py # sandbox، قواعد المخاطر، البروتوكول، الطابور، الويب
python tests/test_api_contract.py # اختبار توافق مع قواعد Claude API (thinking, max_tokens, refusal, JSON, سقف التوكنز)
```
كل شغل الايجنت بمجلد `city_home/workspace/<project>/`، والمهارات بـ `city_home/skills/`.

## بدون API: `CITY_BACKEND=file`
المدينة بتكتب كل طلب LLM بـ `city_home/llm/inbox/N.json` وبتستنى الرد بـ `llm/outbox/N.json`.
اللي بيرد ممكن يكون Claude Code بجلسة تفاعلية (أو إنسان):
```
CITY_BACKEND=file python agentcity.py run &      # المدينة بتشتغل وبتستنى
python agentcity.py llm show                      # اعرض أول طلب معلّق
python agentcity.py llm reply --file reply.json   # {"content":[{"type":"text",..}|{"type":"tool_use","name":..,"input":{..}}]}
```
التوكنز بهالوضع تقدير (≈4 حروف/توكن) وما في فاتورة API. QA "المستقل" هون نفس العقل اللي اشتغل، فاستقلاليته أضعف.

## متغيرات
`CITY_MODEL` (الافتراضي claude-sonnet-5-5)، `CITY_TOKEN_BUDGET` (600000 لكل مشروع، بينفرض حتى جوا المهمة)، `CITY_OWNER_LANG`،
`CITY_EFFORT` (medium)، `CITY_MAX_TOKENS` (16000)، `CITY_FALLBACKS` (1 = تحويل تلقائي لنموذج ثاني عند الرفض، 0 لإيقافه)، `CITY_RUN_TIMEOUT` (300 ثانية).

التوكنز المحسوبة = input + cache write + cache read + output (يعني السقف محافظ). `status` بيعرض كمان تقدير الكلفة بالدولار.

## تنبيهات صريحة
- **Sandbox:** `run_python` و`shell` بيشتغلوا بحاوية Docker: بدون شبكة، rootfs للقراءة، بدون capabilities، حدود ذاكرة/CPU/عمليات،
  مجلد المشروع بس قابل للكتابة و`shared/` (فيه risk.py) للقراءة فقط. `CITY_SANDBOX=auto|docker|local`
  (auto بيرجع لتشغيل محلي مع تحذير إذا الصورة مش مبنية؛ docker = إجباري). `fetch_url` لسا بيشتغل من المدينة نفسها.
- **قواعد المخاطر:** لازم الاستراتيجية تتفوق على الشراء والاحتفاظ (Sharpe)، وحد أدنى صفقات على train/validation/test.
  `gold_toolkit.protocol` بيفتح الاختبار النهائي مرة وحدة وبس لاستراتيجية نجحت، والمدينة بتراقب `final_test.lock`
  (حذف/تعديل = تحذير نزاهة بالتقرير وبالويب).
- **الويب:** كل شي بتوكن (`CITY_WEB_TOKEN` أو `city_home/web_token`)، كوكي HttpOnly/SameSite=Strict + فحص CSRF.
  الافتراضي 127.0.0.1؛ للموبايل من برّا استعمل نفق آمن (Tailscale/WireGuard)، مش port مفتوح. القرارات بتروح لطابور
  وبيطبّقها المشغّل الشغال، فما في تضارب على state.json.
- لحد هلأ ما اختبرتها مع Claude الحقيقي، فقط منطق المدينة بنموذج وهمي. أول تشغيل راقب `status` و`audit.jsonl`.
- ملفات `shared/gold_toolkit` الأصلية (risk.py, backtest.py...) محمية: write_file بيرفضها، وقبل كل مهمة بتنفحص وبترجع من seed إذا انعدّلت (`tamper_restored` بالتدقيق). الايجنت بيقدروا يضيفوا ملفات جديدة.
- بيانات الذهب: `data.from_yahoo()` (يحتاج `pip install yfinance`) بينزّل GC=F مرة وبيجمّدها بـ `shared/data/gold_GCF_daily.csv`. GC=F عقود آجلة، مش سبوت XAUUSD بالظبط.
- مشروع الذهب: إشارات فقط، وليس نصيحة مالية.

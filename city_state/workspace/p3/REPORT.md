# [RESEARCH DAY] #1: continuous gold (GC=F daily) strategy research in the Strategy Lab. Signals only, no trading.
Goal: find edges that beat buy & hold on risk-adjusted terms AND survive the live forward test.
Plan at most 3 tasks: (1) review lab_board + company lessons and write ideas.md with 2-3 NEW, economically motivated hypotheses that differ from what was already tried (not parameter tweaks of rejected ideas); (2) implement each as a strategy module (HYPOTHESIS, small PARAMS grid <= 60 combos, causal signal(close, **p) -> 0/1) and submit with lab_submit (each idea ONE submission; never resubmit tweaks to chase validation); (3) write research_log.md: what was tried, lab verdicts, forward-test status of active strategies, honest conclusion.
Rules: never evaluate the validation period yourself to tune; the lab does that once. Quality over quantity.

CURRENT LAB STATE:
Total trials so far: 0 (today 0/12). More trials => higher chance of lucky validation results; forward test is the real judge.

FORWARD TEST (0/10 active):

RECENT REJECTIONS (learn from these):

جولة البحث الأولى خلصت. الفريق اخترع 3 أفكار جديدة وقدّمها للمختبر مرة وحدة لكل فكرة. فكرة 'شراء النزلة بالترند الصاعد' عدّت فحص المخاطر (Sharpe تحقق 0.88 مقابل 0.77 للشراء والاحتفاظ، 18 صفقة) ودخلت اختبار المستقبل؛ التانيتين انرفضوا. هاد مش دليل ربح لسا: الحكم الحقيقي على الأيام الجاية، وبدنا شي 60 يوم. السجل: city_home/workspace/p3/research_log.md

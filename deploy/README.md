# تشغيل Agent City على سيرفر 24 ساعة

المدينة بتضل شغالة لحالها: بتستلم الطلبات، بتشتغل عليها، وبتستنى موافقتك بس على الأفعال الخطرة.
بتحتاج: سيرفر Ubuntu/Debian صغير (2 CPU / 4GB RAM كافي)، ومفتاح Anthropic API فيه رصيد، وTailscale لتوصل من الموبايل.

## 1. التثبيت (مرة وحدة)
```bash
ssh root@SERVER
git clone https://github.com/badboyt3btiktok-bot/Ai-signal.git /root/ai-signal
cd /root/ai-signal
BRANCH=main bash deploy/install.sh        # قبل دمج الـ PR: BRANCH=claude/agent-city-gold-project-x4nxgt
```
السكربت بينصّب Docker وPython، بيعمل مستخدم خاص `agentcity`، بيبني صورة الـ sandbox، بينزّل بيانات الذهب،
وبيركّب خدمتين: `agent-city` (المدينة) و`agent-city-web` (الواجهة).

## 2. المفتاح
```bash
nano /etc/agent-city.env      # حط ANTHROPIC_API_KEY=...
systemctl restart agent-city
```
الملف مقروء بس من root ومن مستخدم المدينة. المفتاح ما بيدخل حاوية الايجنت أبداً.

## 3. الموبايل (بدون ما تفتح أي port على الإنترنت)
```bash
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up                  # سجّل دخول بنفس حساب Tailscale اللي على موبايلك
tailscale serve --bg 8787     # بيعطيك رابط HTTPS جوا شبكتك الخاصة
grep CITY_WEB_TOKEN /etc/agent-city.env
```
افتح على الموبايل (مع تطبيق Tailscale شغال): `https://<server>.<tailnet>.ts.net/?t=<التوكن>`
ومن هناك: المشاريع، الموافقات، زر الطوارئ، طلب جديد، و"🏙️ شوف المدينة".

## الاستعمال اليومي
| بدك | الأمر |
|---|---|
| طلب جديد | من الواجهة، أو: `sudo -u agentcity /opt/agent-city/.venv/bin/python /opt/agent-city/agentcity.py add "..."` |
| شو صاير | `journalctl -u agent-city -f` أو الواجهة |
| إيقاف طوارئ | زر الواجهة، أو `systemctl stop agent-city` |
| تحديث الكود | `BRANCH=main bash /opt/agent-city/deploy/install.sh` (بيحافظ على city_home والمفتاح) |
| نسخة احتياطية | `tar czf city_backup.tgz -C /opt/agent-city city_home` |

## تنبيهات
- **الكلفة:** كل مشروع إله سقف (`CITY_TOKEN_BUDGET`، افتراضياً 600 ألف توكن ≈ دولارين لـ 6 دولار مع Sonnet). مشروع وصل السقف بيوقف وبيستناك.
- **مجموعة docker:** مستخدم المدينة فيها عشان يشغّل الـ sandbox، وهاي صلاحية قوية على السيرفر. خلي السيرفر مخصص للمدينة.
- **الموافقات:** أي `shell` أو فعل خارجي بيوقف المهمة لحد ما توافق من الواجهة. الباقي بيكمل.

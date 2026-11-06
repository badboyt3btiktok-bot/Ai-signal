#!/usr/bin/env bash
# تثبيت Agent City على سيرفر Ubuntu/Debian ليشتغل 24 ساعة.
# الاستعمال (كـ root):  bash deploy/install.sh
# بعدها حط مفتاحك بـ /etc/agent-city.env وشغّل: systemctl restart agent-city
set -euo pipefail
REPO="${REPO:-https://github.com/badboyt3btiktok-bot/Ai-signal.git}"
BRANCH="${BRANCH:-main}"
DIR=/opt/agent-city
ENVF=/etc/agent-city.env

[ "$(id -u)" -eq 0 ] || { echo "شغّله كـ root (sudo)"; exit 1; }

echo "== 1/7 الحزم"
apt-get update -y
apt-get install -y git python3 python3-venv python3-pip ca-certificates curl
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

echo "== 2/7 مستخدم خاص للمدينة"
id agentcity >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/agentcity --shell /usr/sbin/nologin agentcity
# ملاحظة: مجموعة docker بتعطي صلاحيات قوية؛ لازمة عشان المدينة تشغّل الـ sandbox.
usermod -aG docker agentcity

echo "== 3/7 الكود"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch origin "$BRANCH" && git -C "$DIR" checkout "$BRANCH" && git -C "$DIR" pull --ff-only origin "$BRANCH"
else
  git clone --branch "$BRANCH" "$REPO" "$DIR"
fi
mkdir -p "$DIR/city_home"
chown -R agentcity:agentcity "$DIR"

echo "== 4/7 بيئة Python"
sudo -u agentcity python3 -m venv "$DIR/.venv"
sudo -u agentcity "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt" yfinance

echo "== 5/7 إعدادات وأسرار (/etc/agent-city.env)"
if [ ! -f "$ENVF" ]; then
  umask 077
  cat > "$ENVF" <<CONF
# حط مفتاح Anthropic هون (حساب فيه رصيد):
ANTHROPIC_API_KEY=
CITY_HOME=$DIR/city_home
CITY_SANDBOX=docker
CITY_TOKEN_BUDGET=600000
CITY_MODEL=claude-sonnet-5-5
CITY_EFFORT=medium
CITY_WEB_TOKEN=$(head -c 24 /dev/urandom | base64 | tr -d '/+=' )
CONF
  chown root:agentcity "$ENVF"; chmod 640 "$ENVF"
fi

echo "== 6/7 صورة الـ sandbox + بيانات الذهب"
cd "$DIR"
sudo -u agentcity env CITY_HOME="$DIR/city_home" "$DIR/.venv/bin/python" agentcity.py sandbox | tail -1
sudo -u agentcity env CITY_HOME="$DIR/city_home" "$DIR/.venv/bin/python" agentcity.py data || echo "تحذير: ما نزلت بيانات الذهب (بتقدر تعيدها بعدين)"

echo "== 7/7 خدمات systemd"
cp "$DIR/deploy/agent-city.service" "$DIR/deploy/agent-city-web.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable agent-city-web && systemctl restart agent-city-web
if grep -q '^ANTHROPIC_API_KEY=.\+' "$ENVF"; then
  systemctl enable agent-city && systemctl restart agent-city
  echo "المدينة شغالة."
else
  systemctl enable agent-city
  echo "باقي خطوة: حط ANTHROPIC_API_KEY بـ $ENVF وبعدين: systemctl restart agent-city"
fi
echo
echo "رابط الواجهة (عبر Tailscale): بعد 'tailscale up' شغّل: tailscale serve --bg 8787"
echo "وافتح: https://<اسم-السيرفر>.<tailnet>.ts.net/?t=$(grep CITY_WEB_TOKEN "$ENVF" | cut -d= -f2)"

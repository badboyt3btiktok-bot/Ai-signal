# صورة تشغيل كود الايجنت: Python + pandas/numpy فقط. وقت التشغيل بدون شبكة (--network none).
# بيئات خلف proxy بشهادة خاصة: الشهادة بتنمرر كـ BuildKit secret (ما بتنحفظ بالصورة).
FROM python:3.13-slim
RUN --mount=type=secret,id=ca \
    if [ -s /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca; fi; \
    pip install --no-cache-dir "pandas>=2.2" "numpy>=2.0" && useradd -m -u 10001 agent
WORKDIR /work

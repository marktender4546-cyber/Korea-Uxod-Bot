# Korea Uhod — Telegram do‘kon bot + Mini App

Botda:
- O‘zbekcha va ruscha interfeys
- Mahsulot katalogi, rasmlar, kategoriya va qidiruv
- Savatcha va buyurtmani rasmiylashtirish (to‘lov yo‘q)
- Buyurtmalar adminlarga Telegram orqali yuboriladi
- Telegram Mini App, mobilga mos dizayn
- SQLite bazasi va `/orders` admin buyrug‘i

## 1. Kompyuterda ishga tushirish (Windows)

1. Python 3.11 yoki 3.12 o‘rnating: https://www.python.org/downloads/
2. ZIP faylni oching va shu papkada terminal/CMD oching.
3. Quyidagilarni bajaring:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. BotFather'dan olgan tokenni kiriting. CMD'da:

   ```bat
   set BOT_TOKEN=123456:YOUR_TOKEN
   set WEBAPP_URL=https://example.com
   set ADMIN_IDS=123456789
   python bot.py
   ```

   `WEBAPP_URL` mini app uchun HTTPS manzil bo‘lishi kerak. Mahalliy sinovda vaqtincha `https://example.com` mini app ochilishi mumkin, ammo u sizning do‘koningiz emas. Mini App'ni to‘liq sinash uchun Render'dagi HTTPS manzilni ishlating. Mahalliy katalog/API'ni tekshirish uchun brauzerda `http://127.0.0.1:10000` ni oching.

   `ADMIN_IDS` — administrator Telegram raqami (raqamli user ID). Uni olish uchun Telegram'dagi ID ko‘rsatuvchi botdan foydalaning. Bir nechta admin bo‘lsa vergul bilan yozing.

5. Botga Telegram'da `/start` yuboring. Mini App tugmasi uchun `WEBAPP_URL` to‘g‘ri va ommaviy HTTPS URL bo‘lishi shart.

## 2. GitHub + Render orqali joylash

1. GitHub'da yangi repository yarating.
2. `bot.py`, `requirements.txt`, `render.yaml` va `README.md` fayllarini repository'ga yuklang.
3. Render.com'ga kiring → **New +** → **Blueprint** → GitHub repository'ni tanlang.
4. Render `render.yaml` faylini o‘qib web service yaratadi.
5. Render service → **Environment** bo‘limida quyidagilarni kiriting:
   - `BOT_TOKEN`: BotFather tokeni
   - `WEBAPP_URL`: Render bergan manzil, masalan `https://korea-uhod-bot.onrender.com` (o‘zingizdagi aniq manzilni kiriting)
   - `ADMIN_IDS`: admin Telegram user ID(lar)i, masalan `123456789`
6. Save changes / redeploy qiling. Service'ning `/health` manzili `{"ok":true,...}` qaytarsa, server ishlayapti.
7. Telegram'da botga `/start` yuboring va Mini App'ni ochib ko‘ring.

## Muhim eslatmalar

- Tokenni GitHub'ga hech qachon joylamang. Uni faqat environment variables orqali bering.
- `WEBAPP_URL` qiymati Render bergan haqiqiy HTTPS domeni bo‘lishi kerak. Shu sababli URL'ni bir marta Environment'ga kiritish shart; Telegram Mini App ommaviy HTTPS talab qiladi.
- Render bepul servislar vaqtincha uxlab qolishi mumkin. Birinchi ochilish sekinroq bo‘lishi mumkin.
- Render free disk doimiy saqlashni kafolatlamaydi; SQLite ma’lumotlari deploy yoki restart paytida yo‘qolishi mumkin. Doimiy buyurtma tarixi uchun Render persistent disk yoki tashqi PostgreSQL kerak bo‘ladi.
- Hozir katalogda namunaviy mahsulotlar bor. Mahsulot nomlari, narxlari, tavsifi va rasm URL'larini `bot.py` ichidagi `SEED_PRODUCTS` ro‘yxatida o‘zgartiring. Birinchi ishga tushishda ular bazaga qo‘shiladi.
- Bu o‘quv/demo do‘kon. To‘lov integratsiyasi kiritilmagan.

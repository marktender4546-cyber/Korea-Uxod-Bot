import os
import json
import asyncio
import logging
import sqlite3
import threading
from datetime import datetime
from urllib.parse import quote

from flask import Flask, jsonify, request, render_template_string
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, MenuButtonWebApp
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# =========================
# CONFIGURATION
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
PORT = int(os.getenv("PORT", "10000"))
DB_PATH = os.getenv("DB_PATH", "store.db")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("korea-uhod")
app = Flask(__name__)
router = Router()
dp = Dispatcher()
dp.include_router(router)
bot = Bot(BOT_TOKEN) if BOT_TOKEN else None

# Simple bilingual store catalog. Edit these examples or add products through SQLite.
SEED_PRODUCTS = [
    ("Centella calming serum", "Сыворотка с центеллой", "Сarum", "Serum", "Сыворотка для успокоения кожи и поддержания увлажнения.", "Успокаивающая сыворотка для увлажнения кожи.", 89000, "https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?w=900"),
    ("Rice brightening toner", "Тонер с рисом", "Tonik", "Тонер", "Yuzni namlash va teri ko‘rinishini yaxshilash uchun tonik.", "Тонер для увлажнения и улучшения внешнего вида кожи.", 115000, "https://images.unsplash.com/photo-1601049541289-9b1b7bbbfe19?w=900"),
    ("Hyaluronic cream", "Крем с гиалуроновой кислотой", "Krem", "Крем", "Kundalik parvarish uchun namlovchi krem.", "Увлажняющий крем для ежедневного ухода.", 99000, "https://images.unsplash.com/photo-1556229010-6c3f2c9ca5f8?w=900"),
    ("Gentle cleansing foam", "Мягкая пенка для умывания", "Tozalash", "Очищение", "Yuzni muloyim tozalash uchun ko‘pik.", "Пенка для мягкого очищения лица.", 75000, "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=900"),
    ("Daily sunscreen SPF50", "Солнцезащитный крем SPF50", "SPF", "SPF", "Har kungi quyoshdan himoya kremi.", "Солнцезащитный крем на каждый день.", 125000, "https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=900"),
    ("Sheet mask set", "Набор тканевых масок", "Niqob", "Маски", "Teri parvarishi uchun niqoblar to‘plami.", "Набор тканевых масок для ухода за кожей.", 45000, "https://images.unsplash.com/photo-1596755389378-c31d21fd1273?w=900"),
]

def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_uz TEXT NOT NULL, name_ru TEXT NOT NULL,
            category_uz TEXT NOT NULL, category_ru TEXT NOT NULL,
            description_uz TEXT NOT NULL, description_ru TEXT NOT NULL,
            price INTEGER NOT NULL, image TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, username TEXT, customer_name TEXT,
            phone TEXT, address TEXT, items TEXT NOT NULL, total INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Yangi',
            created_at TEXT NOT NULL
        )""")
        count = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            c.executemany("""INSERT INTO products
                (name_uz,name_ru,category_uz,category_ru,description_uz,description_ru,price,image)
                VALUES(?,?,?,?,?,?,?,?)""", SEED_PRODUCTS)

init_db()

UZ = {
    "welcome": "🌸 <b>Korea Uhod — koreys parvarishi</b>\\nSevimli mahsulotlaringizni toping va buyurtma bering.",
    "catalog": "🛍 Katalog", "cart": "🧺 Savatcha", "orders": "📦 Buyurtmalarim",
    "language": "🌐 Tilni o‘zgartirish", "help": "ℹ️ Yordam", "open": "✨ Do‘konni ochish",
    "choose_lang": "Tilni tanlang:", "lang_saved": "Til saqlandi!",
    "empty_cart": "Savatchangiz hozircha bo‘sh.", "webapp_hint": "Mahsulotlarni ko‘rish va buyurtma berish uchun do‘konni oching.",
    "admin": "Admin buyruqlari: /orders — so‘nggi buyurtmalar", "no_orders": "Hozircha buyurtmalar yo‘q."
}
RU = {
    "welcome": "🌸 <b>Korea Uhod — корейский уход</b>\\nНаходите любимые товары и оформляйте заказ.",
    "catalog": "🛍 Каталог", "cart": "🧺 Корзина", "orders": "📦 Мои заказы",
    "language": "🌐 Изменить язык", "help": "ℹ️ Помощь", "open": "✨ Открыть магазин",
    "choose_lang": "Выберите язык:", "lang_saved": "Язык сохранён!",
    "empty_cart": "Ваша корзина пока пуста.", "webapp_hint": "Откройте магазин, чтобы посмотреть товары и оформить заказ.",
    "admin": "Команды администратора: /orders — последние заказы", "no_orders": "Заказов пока нет."
}
USER_LANG = {}

def tr(user_id, key):
    return (RU if USER_LANG.get(user_id, "uz") == "ru" else UZ).get(key, key)

def main_keyboard(user_id):
    lang = USER_LANG.get(user_id, "uz")
    open_text = (RU if lang == "ru" else UZ)["open"]
    if WEBAPP_URL:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=open_text, web_app=WebAppInfo(url=WEBAPP_URL))],
            [InlineKeyboardButton(text=(RU if lang == "ru" else UZ)["language"], callback_data="language")],
            [InlineKeyboardButton(text=(RU if lang == "ru" else UZ)["help"], callback_data="help")]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Til / Язык", callback_data="language")],
        [InlineKeyboardButton(text="ℹ️ Yordam / Помощь", callback_data="help")]
    ])

@router.message(CommandStart())
async def start(message: Message):
    USER_LANG.setdefault(message.from_user.id, "uz")
    if WEBAPP_URL:
        try:
            await bot.set_chat_menu_button(
                chat_id=message.chat.id,
                menu_button=MenuButtonWebApp(text="Korea Uhod", web_app=WebAppInfo(url=WEBAPP_URL))
            )
        except Exception as e:
            log.info("Menu button setup skipped: %s", e)
    await message.answer(tr(message.from_user.id, "welcome"), reply_markup=main_keyboard(message.from_user.id), parse_mode="HTML")

@router.callback_query(F.data == "language")
async def language_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="lang_uz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")
    ]])
    await call.message.answer(tr(call.from_user.id, "choose_lang"), reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.in_({"lang_uz", "lang_ru"}))
async def set_language(call: CallbackQuery):
    USER_LANG[call.from_user.id] = call.data.split("_")[1]
    await call.message.answer(tr(call.from_user.id, "lang_saved"), reply_markup=main_keyboard(call.from_user.id))
    await call.answer()

@router.callback_query(F.data == "help")
async def help_callback(call: CallbackQuery):
    text = ("Savol va buyurtmalar bo‘yicha administratorga yozing." if USER_LANG.get(call.from_user.id, "uz") == "uz"
            else "По вопросам и заказам напишите администратору.")
    await call.message.answer(text)
    await call.answer()

@router.message(Command("orders"))
async def admin_orders(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Bu buyruq faqat administrator uchun.")
        return
    with db() as c:
        rows = c.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 10").fetchall()
    if not rows:
        await message.answer(tr(message.from_user.id, "no_orders"))
        return
    for r in rows:
        await message.answer(
            f"🧾 <b>Buyurtma #{r['id']}</b>\\n"
            f"👤 {r['customer_name']} (@{r['username'] or '—'})\\n"
            f"📞 {r['phone']}\\n📍 {r['address']}\\n"
            f"💰 {r['total']:,} so‘m\\n📦 {r['items']}\\n🕒 {r['created_at']}\\nStatus: {r['status']}",
            parse_mode="HTML"
        )

# =========================
# MINI APP
# =========================
HTML = r"""<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="theme-color" content="#f8edf0"><title>Korea Uhod</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root{--pink:#e98ba5;--deep:#7b344b;--bg:#fff8fa;--card:#fff;--text:#33262b;--muted:#927e85}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header{padding:22px 18px 15px;background:linear-gradient(135deg,#fbe3eb,#fff4f7);border-radius:0 0 25px 25px}
.brand{display:flex;align-items:center;gap:10px}.logo{width:43px;height:43px;border-radius:15px;background:#fff;display:grid;place-items:center;font-size:24px;box-shadow:0 5px 20px #dca6b344}
h1{font-size:21px;margin:0;color:var(--deep)}.sub{font-size:12px;color:var(--muted);margin-top:4px}
.search{margin-top:18px;display:flex;gap:8px}.search input{width:100%;border:0;background:#fff;border-radius:14px;padding:13px 15px;font-size:14px;outline:none}
.langs{display:flex;gap:6px;margin-top:12px}.lang{border:1px solid #f0d4dd;border-radius:20px;padding:6px 11px;background:#fff;color:var(--deep);font-size:12px}
main{padding:17px 14px 100px}.section{display:flex;align-items:center;justify-content:space-between;margin:5px 3px 13px}.section h2{font-size:17px;margin:0}.count{font-size:12px;color:var(--muted)}
.categories{display:flex;gap:8px;overflow:auto;padding-bottom:14px}.cat{white-space:nowrap;border:0;border-radius:22px;padding:9px 14px;background:#fff;color:#795764;box-shadow:0 2px 12px #8e45510b}.cat.active{background:var(--deep);color:white}
.products{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.product{background:#fff;border-radius:18px;overflow:hidden;box-shadow:0 5px 20px #8e45510b;position:relative}.product img{width:100%;height:145px;object-fit:cover;background:#f5e9ed}.pbody{padding:11px}.pname{font-size:13px;font-weight:700;line-height:1.35;min-height:35px}.desc{font-size:11px;color:var(--muted);line-height:1.4;height:30px;overflow:hidden;margin-top:4px}.pfoot{display:flex;align-items:center;justify-content:space-between;gap:4px;margin-top:10px}.price{font-size:13px;font-weight:800;color:var(--deep)}.add{border:0;border-radius:11px;background:#f7dce5;color:var(--deep);font-size:18px;width:33px;height:33px}
.bottom{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid #f2e3e8;padding:10px 14px calc(10px + env(safe-area-inset-bottom));display:flex;gap:9px;z-index:5}.bottom button{flex:1;border:0;border-radius:14px;padding:12px;background:#f8e8ee;color:var(--deep);font-weight:700}.bottom button.primary{background:var(--deep);color:white}
.overlay{display:none;position:fixed;inset:0;background:#24151bb0;z-index:10;align-items:flex-end}.sheet{background:#fff;width:100%;max-height:90vh;overflow:auto;border-radius:25px 25px 0 0;padding:22px 18px calc(22px + env(safe-area-inset-bottom))}.sheet h2{margin:0 0 15px}.field{width:100%;padding:13px;border:1px solid #eedde3;border-radius:12px;margin:6px 0 10px;font:inherit}.line{display:flex;justify-content:space-between;gap:10px;padding:10px 0;border-bottom:1px solid #f5e9ed;font-size:13px}.submit{width:100%;border:0;background:var(--deep);color:white;padding:14px;border-radius:14px;font-weight:700;margin-top:12px}.empty{text-align:center;color:var(--muted);padding:35px 5px;grid-column:1/-1}.toast{position:fixed;top:15px;left:50%;transform:translateX(-50%);background:#35242b;color:white;padding:10px 15px;border-radius:12px;z-index:30;font-size:13px;display:none}
@media(min-width:650px){main,header{max-width:900px;margin:auto}.products{grid-template-columns:repeat(3,minmax(0,1fr))}.product img{height:200px}}
</style></head><body>
<header><div class="brand"><div class="logo">🌸</div><div><h1>Korea Uhod</h1><div class="sub" id="subtitle">Koreys parvarishi — teringizga mehr</div></div></div>
<div class="search"><input id="search" placeholder="Mahsulot qidirish..." oninput="render()"></div>
<div class="langs"><button class="lang" onclick="setLang('uz')">🇺🇿 O‘zbekcha</button><button class="lang" onclick="setLang('ru')">🇷🇺 Русский</button></div></header>
<main><div class="section"><h2 id="catalogTitle">Mashhur mahsulotlar</h2><span class="count" id="productCount"></span></div>
<div class="categories" id="categories"></div><div class="products" id="products"></div></main>
<div class="bottom"><button onclick="openCart()" id="cartBtn">🧺 Savatcha (0)</button><button class="primary" onclick="openCheckout()" id="checkoutBtn">Buyurtma berish</button></div>
<div class="overlay" id="overlay" onclick="if(event.target===this)closeSheet()"><div class="sheet"><h2 id="sheetTitle">Savatcha</h2><div id="sheetContent"></div><button class="submit" id="sheetAction" onclick="sheetSubmit()">Davom etish</button><button class="field" onclick="closeSheet()" style="background:#fff">Yopish / Закрыть</button></div></div>
<div class="toast" id="toast"></div>
<script>
const tg=window.Telegram?.WebApp; tg?.ready(); tg?.expand();
let lang='uz', allProducts=[], category='all', cart={}, sheetMode='cart', cats=[];
const words={
 uz:{subtitle:'Koreys parvarishi — teringizga mehr',catalog:'Mashhur mahsulotlar',search:'Mahsulot qidirish...',all:'Hammasi',add:'Qo‘shish',cart:'Savatcha',order:'Buyurtma berish',empty:'Savatchangiz bo‘sh',continue:'Rasmiylashtirish',name:'Ismingiz',phone:'Telefon raqamingiz',address:'Yetkazib berish manzili',send:'Buyurtmani yuborish',close:'Yopish',success:'Buyurtmangiz qabul qilindi! Tez orada siz bilan bog‘lanamiz.',remove:'O‘chirish',total:'Jami',noProducts:'Mahsulot topilmadi',category:'Kategoriya',added:'Savatchaga qo‘shildi',need:'Barcha maydonlarni to‘ldiring',error:'Xatolik yuz berdi. Qayta urinib ko‘ring.',orderInfo:'Buyurtma uchun aloqa ma’lumotlarini kiriting.'},
 ru:{subtitle:'Корейский уход — забота о вашей коже',catalog:'Популярные товары',search:'Поиск товаров...',all:'Все',add:'Добавить',cart:'Корзина',order:'Оформить заказ',empty:'Корзина пуста',continue:'Продолжить',name:'Ваше имя',phone:'Номер телефона',address:'Адрес доставки',send:'Отправить заказ',close:'Закрыть',success:'Заказ принят! Скоро мы с вами свяжемся.',remove:'Удалить',total:'Итого',noProducts:'Товары не найдены',category:'Категория',added:'Добавлено в корзину',need:'Заполните все поля',error:'Произошла ошибка. Попробуйте ещё раз.',orderInfo:'Введите контактные данные для заказа.'}
};
function t(k){return words[lang][k]||k}
function money(n){return Number(n).toLocaleString('ru-RU')+' сум'}
function setLang(v){lang=v;document.documentElement.lang=v;document.getElementById('subtitle').textContent=t('subtitle');document.getElementById('catalogTitle').textContent=t('catalog');document.getElementById('search').placeholder=t('search');document.getElementById('checkoutBtn').textContent=t('order');renderCats();render();updateCartButton()}
async function load(){try{let r=await fetch('/api/products');allProducts=await r.json();cats=[...new Set(allProducts.map(p=>lang==='uz'?p.category_uz:p.category_ru))];renderCats();render()}catch(e){document.getElementById('products').innerHTML='<div class="empty">Server bilan aloqa yo‘q</div>'}}
function renderCats(){let values=[...new Set(allProducts.map(p=>lang==='uz'?p.category_uz:p.category_ru))];document.getElementById('categories').innerHTML=`<button class="cat ${category==='all'?'active':''}" onclick="chooseCat('all')">${t('all')}</button>`+values.map(c=>`<button class="cat ${category===c?'active':''}" onclick="chooseCat(${JSON.stringify(c)})">${c}</button>`).join('')}
function chooseCat(c){category=c;renderCats();render()}
function render(){let q=document.getElementById('search').value.toLowerCase();let list=allProducts.filter(p=>(category==='all'||(lang==='uz'?p.category_uz:p.category_ru)===category)&&((lang==='uz'?p.name_uz+' '+p.description_uz:p.name_ru+' '+p.description_ru).toLowerCase().includes(q)));document.getElementById('productCount').textContent=list.length;document.getElementById('products').innerHTML=list.map(p=>`<article class="product"><img src="${esc(p.image)}" loading="lazy" onerror="this.src='https://placehold.co/500x400/f8e8ee/7b344b?text=Korea+Uhod'"><div class="pbody"><div class="pname">${esc(lang==='uz'?p.name_uz:p.name_ru)}</div><div class="desc">${esc(lang==='uz'?p.description_uz:p.description_ru)}</div><div class="pfoot"><span class="price">${money(p.price)}</span><button class="add" onclick="add(${p.id})" aria-label="${t('add')}">+</button></div></div></article>`).join('')||`<div class="empty">${t('noProducts')}</div>`}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function add(id){cart[id]=(cart[id]||0)+1;updateCartButton();toast(t('added'));tg?.HapticFeedback?.impactOccurred('light')}
function updateCartButton(){let n=Object.values(cart).reduce((a,b)=>a+b,0);document.getElementById('cartBtn').textContent='🧺 '+t('cart')+' ('+n+')'}
function total(){return allProducts.reduce((s,p)=>s+p.price*(cart[p.id]||0),0)}
function openCart(){sheetMode='cart';document.getElementById('sheetTitle').textContent=t('cart');document.getElementById('sheetAction').textContent=t('continue');let items=allProducts.filter(p=>cart[p.id]);document.getElementById('sheetContent').innerHTML=items.length?items.map(p=>`<div class="line"><span>${esc(lang==='uz'?p.name_uz:p.name_ru)} × ${cart[p.id]}</span><b>${money(p.price*cart[p.id])}</b><button onclick="del(${p.id})">−</button></div>`).join('')+`<div class="line"><b>${t('total')}</b><b>${money(total())}</b></div>`:`<div class="empty">${t('empty')}</div>`;document.getElementById('sheetAction').style.display=items.length?'block':'none';showSheet()}
function del(id){delete cart[id];openCart();updateCartButton()}
function openCheckout(){if(!Object.keys(cart).length){openCart();return}sheetMode='checkout';document.getElementById('sheetTitle').textContent=t('order');document.getElementById('sheetContent').innerHTML=`<p style="color:var(--muted);font-size:13px">${t('orderInfo')}</p><input class="field" id="customerName" placeholder="${t('name')}"><input class="field" id="phone" type="tel" placeholder="${t('phone')}"><textarea class="field" id="address" placeholder="${t('address')}" rows="2"></textarea><div class="line"><b>${t('total')}</b><b>${money(total())}</b></div>`;document.getElementById('sheetAction').style.display='block';document.getElementById('sheetAction').textContent=t('send');showSheet()}
function showSheet(){document.getElementById('overlay').style.display='flex'}
function closeSheet(){document.getElementById('overlay').style.display='none'}
function sheetSubmit(){if(sheetMode==='cart'){closeSheet();openCheckout();return}let name=document.getElementById('customerName').value.trim(),phone=document.getElementById('phone').value.trim(),address=document.getElementById('address').value.trim();if(!name||!phone||!address){toast(t('need'));return}sendOrder({name,phone,address,lang,items:allProducts.filter(p=>cart[p.id]).map(p=>({id:p.id,qty:cart[p.id]})),total:total(),telegram_user:tg?.initDataUnsafe?.user||null}).then(r=>{if(!r.ok)throw Error('bad');cart={};updateCartButton();closeSheet();toast(t('success'));tg?.HapticFeedback?.notificationOccurred('success');setTimeout(()=>tg?.close?.(),1800)}).catch(()=>toast(t('error')))}
async function sendOrder(data){let r=await fetch('/api/orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});return r.json()}
function toast(msg){let el=document.getElementById('toast');el.textContent=msg;el.style.display='block';setTimeout(()=>el.style.display='none',2300)}
load();updateCartButton();
</script></body></html>"""

@app.get("/")
def mini_app():
    return render_template_string(HTML)

@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "korea-uhod"})

@app.get("/api/products")
def api_products():
    with db() as c:
        rows = c.execute("SELECT * FROM products WHERE active=1 ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.post("/api/orders")
def api_orders():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()[:100]
    phone = str(data.get("phone", "")).strip()[:50]
    address = str(data.get("address", "")).strip()[:300]
    items = data.get("items", [])
    if not name or not phone or not address or not isinstance(items, list) or not items:
        return jsonify({"ok": False, "error": "invalid_order"}), 400
    clean, total = [], 0
    with db() as c:
        for item in items:
            try:
                pid, qty = int(item["id"]), max(1, min(99, int(item["qty"])))
            except (KeyError, TypeError, ValueError):
                continue
            product = c.execute("SELECT id,name_uz,price FROM products WHERE id=? AND active=1", (pid,)).fetchone()
            if product:
                clean.append(f"{product['name_uz']} × {qty}")
                total += product["price"] * qty
        if not clean:
            return jsonify({"ok": False, "error": "empty_order"}), 400
        tg_user = data.get("telegram_user") or {}
        user_id = tg_user.get("id")
        username = str(tg_user.get("username", ""))[:100]
        c.execute("""INSERT INTO orders(user_id,username,customer_name,phone,address,items,total,status,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (int(user_id or 0), username, name, phone, address, "; ".join(clean), total, "Yangi", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")))
        order_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    # Notify configured admins without exposing bot token in the frontend.
    if bot and ADMIN_IDS:
        async def notify():
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(admin_id,
                        f"🛍 <b>Yangi buyurtma #{order_id}</b>\\n"
                        f"👤 {name}\\n📞 {phone}\\n📍 {address}\\n"
                        f"📦 {'; '.join(clean)}\\n💰 {total:,} so‘m",
                        parse_mode="HTML")
                except Exception as e:
                    log.warning("Admin notification failed: %s", e)
        try:
            asyncio.run_coroutine_threadsafe(notify(), bot_loop)
        except Exception:
            log.exception("Could not schedule admin notification")
    return jsonify({"ok": True, "order_id": order_id})

bot_loop = None

def run_flask():
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)

async def run_bot():
    global bot_loop
    bot_loop = asyncio.get_running_loop()
    if not BOT_TOKEN:
        log.error("BOT_TOKEN is missing. Set it in your environment.")
        return
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    if BOT_TOKEN:
        asyncio.run(run_bot())
    else:
        log.warning("Web app is running without Telegram polling. Set BOT_TOKEN to enable the bot.")
        threading.Event().wait()

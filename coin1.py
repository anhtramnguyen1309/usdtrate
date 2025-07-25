# update_giacoin_cache
import aiohttp
import asyncio
import json
import time
import re
from playwright.async_api import async_playwright
from telegram import Update
from telegram.ext import ContextTypes
import aiohttp

coins = ["BTC", "ETH", "XRP", "TRX", "DOGE"]

async def fetch_usdt_vnd_binance_p2p():
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    headers = {"Content-Type": "application/json"}
    payload = {
        "asset": "USDT",
        "fiat": "VND",
        "merchantCheck": False,
        "page": 1,
        "payTypes": ["BANK"],
        "publisherType": None,
        "rows": 10,
        "tradeType": "BUY",
        "TRANSAMOUNT":"500000000",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()
            prices = [float(ad['adv']['price']) for ad in data['data'] if float(ad['adv']['price']) > 0]
            return min(prices) if prices else None

async def fetch_binance_usdt_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            return float(data['price']) if 'price' in data else None

async def fetch_bithumb_price(symbol):
    url = f"https://api.bithumb.com/public/ticker/{symbol}_KRW"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            return float(data['data']['closing_price']) if 'data' in data else None

async def get_naver_rate(page):
    try:
        await page.goto("https://finance.naver.com/marketindex/exchangeDetail.nhn?marketindexCd=FX_VNDKRW")
        await page.wait_for_timeout(3000)

        content = await page.content()

        # Tìm tỷ giá cho option 100 VND
        match = re.search(r'<option value="([\d.]+)" label="100">.*?VND</option>', content)
        if match:
            krw_for_100_vnd = float(match.group(1))
            vnd_per_krw = 1 / krw_for_100_vnd
            return round(vnd_per_krw, 2)

        else:
            print("❌ Không tìm thấy tỷ giá từ NAVER")
            return None

    except Exception as e:
        print("⚠️ Lỗi NAVER:", e)
        return None  
    


from datetime import datetime

async def update_cache():
    print(datetime.now())

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        naver_rate = await get_naver_rate(page)
        await browser.close()

    usdt_vnd = await fetch_usdt_vnd_binance_p2p()
    usdt_krw = await fetch_bithumb_price("USDT")

    coins_data = {}
    for coin in coins:
        binance = await fetch_binance_usdt_price(coin)
        bithumb = await fetch_bithumb_price(coin)
        coins_data[coin] = {"binance": binance, "bithumb": bithumb}

    result = {
        "updated_at": time.time(),
        "usdt_vnd": usdt_vnd,
        "usdt_krw": usdt_krw,
        "naver_rate": naver_rate,
        "coins": coins_data
    }

    with open("giacoin_cache.json", "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        print("✅ NAVER RATE:", naver_rate, type(naver_rate))
        print("💾 Ghi JSON với naver_rate =", result["naver_rate"], type(result["naver_rate"]))
if __name__ == "__main__":
    import asyncio

    async def test():
        print("▶️ Bắt đầu cập nhật dữ liệu test...")
        await update_cache()
        print("✅ Đã chạy xong update_cache()")

    asyncio.run(test())

async def check_giacoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Đang lấy tỷ giá, vui lòng chờ trong giây lát...")

    msg = ""

    # Lấy NAVER rate qua Playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        naver_rate = await get_naver_rate(page)
        await browser.close()

    msg += f"🌐 Tỷ giá NAVER (VND/KRW): {naver_rate}\n\n" if naver_rate else "🌐 NAVER: Không lấy được dữ liệu\n\n"
    msg += "💱 TỶ GIÁ COIN\n\n"

    # Lấy USDT từ Binance P2P và Bithumb
    usdt_vnd = await fetch_usdt_vnd_binance_p2p()
    usdt_krw = await fetch_bithumb_price("USDT")
    krw_rate = (usdt_vnd / usdt_krw) if usdt_vnd and usdt_krw else None

    msg += "USDT:\n"
    msg += f"  Binance P2P: {usdt_vnd:,.0f} VND\n" if usdt_vnd else "  Binance P2P: Không có dữ liệu\n"
    msg += f"  Bithumb: {usdt_krw:,.0f} KRW\n" if usdt_krw else "  Bithumb: Không có dữ liệu\n"
    msg += f"  KRW Rate: {krw_rate:.2f}\n\n" if krw_rate else "  KRW Rate: Không tính được\n\n"

    # Các coin khác
    coins = ["XRP", "TRX", "DOGE", "BTC", "ETH"]
    for coin in coins:
        binance_price = await fetch_binance_usdt_price(coin)
        bithumb_price = await fetch_bithumb_price(coin)

        msg += f"{coin}:\n"
        if coin in ("BTC", "ETH"):
            msg += f"  Binance: {binance_price:,.0f} USDT\n" if binance_price else "  Binance: Không có dữ liệu\n"
        else:
            msg += f"  Binance: {binance_price:.5f} USDT\n" if binance_price else "  Binance: Không có dữ liệu\n"

        msg += f"  Bithumb: {bithumb_price:,.0f} KRW\n" if bithumb_price else "  Bithumb: Không có dữ liệu\n"

        if binance_price and bithumb_price and usdt_vnd:
            calculated_rate = (binance_price * usdt_vnd) / bithumb_price
            msg += f"  KRW Rate: {calculated_rate:.2f}\n\n"
        else:
            msg += "  KRW Rate: Không tính được\n\n"

    await update.message.reply_text(msg.strip())
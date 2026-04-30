async def check_all_sites(diagnostic, subject, grade, date):
    if not MOS_LOGIN or not MOS_PASSWORD:
        print("❌ Нет MOS_LOGIN или MOS_PASSWORD")
        return {"found": False, "site": "", "snippet": ""}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="ru-RU",
        )

        page = await context.new_page()

        try:
            # 1. Сначала ОК МЦКО, потому что через него есть вход через МЭШ
            ok_login = await login_through_okmcko(page)

            if not ok_login:
                print("❌ Вход через ОК МЦКО / МЭШ не выполнен")
                await browser.close()
                return {"found": False, "site": "", "snippet": ""}

            # 2. Проверяем ОК МЦКО
            okmcko_result = await check_okmcko(page, diagnostic)
            if okmcko_result["found"]:
                await browser.close()
                return okmcko_result

            # 3. Проверяем портфолио МЭШ
            portfolio_result = await check_portfolio(page, diagnostic)
            if portfolio_result["found"]:
                await browser.close()
                return portfolio_result

            await browser.close()
            return {"found": False, "site": "", "snippet": ""}

        except Exception as e:
            print("❌ Общая ошибка проверки:", e)
            await browser.close()
            return {"found": False, "site": "", "snippet": ""}

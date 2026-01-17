import streamlit as st
import pandas as pd
import asyncio
import nest_asyncio
import os
import time
import logging
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

nest_asyncio.apply()

# Set asyncio policy for Windows
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# --- إعداد الصفحة ---
st.set_page_config(page_title="ICP Unified Search", layout="wide")
st.title("HAMADA ICP UNIFIED SEARCH TEST")

# --- إدارة جلسة العمل (Session State) ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
if 'run_state' not in st.session_state:
    st.session_state['run_state'] = 'stopped'
if 'batch_results' not in st.session_state:
    st.session_state['batch_results'] = []
if 'browser_page' not in st.session_state:
    st.session_state['browser_page'] = None
if 'browser' not in st.session_state:
    st.session_state['browser'] = None

# قائمة الجنسيات
countries_list = ["Select Nationality", "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia", "Cameroon", "Canada", "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros", "Congo (Congo-Brazzaville)", "Costa Rica", "Côte d'Ivoire", "Croatia", "Cuba", "Cyprus", "Czechia (Czech Republic)", "Democratic Republic of the Congo", "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Holy See", "Honduras", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Palestine State", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Korea", "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States of America", "Uruguay", "Uzbekistan", "Vanuatu", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe"]

# --- تسجيل الدخول ---
if not st.session_state['authenticated']:
    with st.form("login_form"):
        st.subheader("Protected Access")
        pwd_input = st.text_input("Enter Password", type="password")
        if st.form_submit_button("Login"):
            if pwd_input == "Bilkish":
                st.session_state['authenticated'] = True
                st.rerun()
            else: st.error("Incorrect Password.")
    st.stop()

# --- إعدادات أساسية ---
TARGET_URL = "https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false"
LOGIN_URL_PART = "client/default.html#/login"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def setup_browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # غيره إلى False لو عايز تشوف الـ browser local للـ debug
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            locale='en-US',  # فرض اللغة الإنجليزية عشان الـ labels تكون "Passport Type"
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        async def handle_route(route):
            if LOGIN_URL_PART in route.request.url:
                logger.warning(f"Prevented redirect to login: {route.request.url}")
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", handle_route)
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_load_state('networkidle', timeout=60000)  # انتظار تحميل كامل
        await asyncio.sleep(5)

        # انتظار حقل Passport Number عشان نتأكد إن الـ form loaded
        try:
            await page.wait_for_selector("input#passportNo", timeout=60000)
            logger.info("Form loaded successfully (passportNo field found)")
        except:
            logger.error("Passport Number field not found - page may not have loaded correctly")

        # إغلاق popup إذا موجود
        try:
            await page.click("button:has-text('I Got It')", timeout=10000)
        except:
            pass

        # اختيار نوع الطلب (radio button)
        await page.evaluate("""
            const el = document.querySelector("input[value='4']");
            if (el) {
                el.click();
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        """)
        await asyncio.sleep(2)

        # محاولة اختيار Passport Type مع try/except و timeout أكبر + selector محسن
        try:
            # selector محسن يدعم إنجليزي أو عربي
            passport_type_container = page.locator(
                "//label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'passport type') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'نوع جواز')]/following::div[contains(@class,'ui-select-container')][1]"
            )
            await passport_type_container.wait_for(state="visible", timeout=60000)
            await passport_type_container.click(force=True, timeout=60000)
            await asyncio.sleep(1)

            # كتابة ORDINARY PASSPORT (أو عادي لو عربي)
            await page.keyboard.type("ORDINARY PASSPORT", delay=100)
            await asyncio.sleep(2)  # انتظار الـ suggestions
            await page.keyboard.press("Enter")
            await asyncio.sleep(1)
            await page.keyboard.press("Escape")
            logger.info("Passport Type set successfully")
        except Exception as e:
            logger.warning(f"Failed to set Passport Type (may be optional or default): {str(e)}")
            # نستمر بدون ما نفشل الـ setup كامل

        return page, browser

async def process_row(page, passport_no, nationality, previous_passport, previous_unified):
    # الكود زي ما هو (مع await لكل حاجة)
    try:
        passport_input = page.locator("input#passportNo")
        await passport_input.fill("")
        await asyncio.sleep(0.5)

        try:
            clear_btn = page.locator('div[name="currentNationality"] button[ng-if="showClear"]')
            if await clear_btn.is_visible(timeout=2000):
                await clear_btn.click(force=True)
                await asyncio.sleep(0.5)
        except:
            pass

        await passport_input.fill(passport_no)
        await asyncio.sleep(1.0)
        await page.keyboard.press("Tab")
        await asyncio.sleep(0.5)

        unified_number = "Not Found"
        async with page.expect_response("**/checkValidateLeavePermitRequest**", timeout=30000) as response_info:
            await page.keyboard.type(nationality, delay=100)
            await asyncio.sleep(2.0)
            await page.keyboard.press("Enter")
            await asyncio.sleep(1.0)
            await page.keyboard.press("Escape")

            response = await response_info.value
            if response.status == 200:
                json_data = await response.json()
                if json_data.get("message") == "Invalid data" or json_data.get("unifiedNumber") == "Invalid data":
                    return "Invalid Data"
                raw_unified = json_data.get("unifiedNumber")
                if raw_unified is not None:
                    unified_str = str(raw_unified).strip()
                    if unified_str and unified_str not in ["Invalid data", "null", "None", ""]:
                        if previous_unified is not None and unified_str == previous_unified:
                            if passport_no == previous_passport:
                                unified_number = unified_str
                            else:
                                unified_number = "Not Found"
                        else:
                            unified_number = unified_str

        return unified_number
    except PlaywrightTimeoutError:
        return "Not Found"
    except Exception as e:
        logger.error(f"Error processing {passport_no}: {str(e)}")
        return "ERROR"

def color_status(val):
    color = '#90EE90' if val == 'Found' else '#FFCCCB'
    return f'background-color: {color}'

# --- واجهة المستخدم ---
tab1, tab2 = st.tabs(["Single Search", "Upload Excel File"])

with tab1:
    st.subheader("Single Person Search")
    c1, c2 = st.columns(2)
    p_in = c1.text_input("Passport Number", key="s_p")
    n_in = c2.selectbox("Nationality", countries_list, key="s_n")

    if st.button("Search Now"):
        if p_in and n_in != "Select Nationality":
            with st.spinner("Searching..."):
                try:
                    if st.session_state['browser_page'] is None:
                        page, browser = asyncio.run(setup_browser())
                        st.session_state['browser_page'] = page
                        st.session_state['browser'] = browser
                    page = st.session_state['browser_page']
                    unified = asyncio.run(process_row(page, p_in, n_in.upper(), None, None))
                    status = "Found" if unified not in ["Not Found", "ERROR", "Invalid Data"] else "Not Found"
                    res = {"Passport Number": p_in, "Nationality": n_in, "Unified Number": unified, "Status": status}
                    df_res = pd.DataFrame([res])
                    styled_df = df_res.style.applymap(color_status, subset=['Status'])
                    st.dataframe(styled_df)
                except Exception as e:
                    st.error(f"Error: {str(e)}")

with tab2:
    st.subheader("Batch Processing Control")
    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx"])

    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        st.write(f"Total records: {len(df)}")
        st.dataframe(df, height=200)

        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns(3)
        if col_ctrl1.button("▶️ Start / Resume"):
            st.session_state.run_state = 'running'
        if col_ctrl2.button("⏸️ Pause"):
            st.session_state.run_state = 'paused'
        if col_ctrl3.button("⏹️ Stop & Reset"):
            st.session_state.run_state = 'stopped'
            st.session_state.batch_results = []
            if st.session_state.get('browser'):
                asyncio.run(st.session_state['browser'].close())
                st.session_state['browser_page'] = None
                st.session_state['browser'] = None
            st.rerun()

        if st.session_state.run_state in ['running', 'paused']:
            progress_bar = st.progress(0)
            status_text = st.empty()
            stats_area = st.empty()
            live_table_area = st.empty()

            try:
                if st.session_state['browser_page'] is None:
                    page, browser = asyncio.run(setup_browser())
                    st.session_state['browser_page'] = page
                    st.session_state['browser'] = browser

                page = st.session_state['browser_page']

                start_time = time.time()
                actual_success = 0
                previous_passport = None
                previous_unified = None

                for i, row in df.iterrows():
                    while st.session_state.run_state == 'paused':
                        status_text.warning("Paused... click Resume to continue.")
                        time.sleep(1)

                    if st.session_state.run_state == 'stopped':
                        break

                    if i < len(st.session_state.batch_results):
                        if st.session_state.batch_results[i].get("Status") == "Found":
                            actual_success += 1
                        continue

                    p_num = str(row.get('Passport Number', '')).strip()
                    nat = str(row.get('Nationality', '')).strip().upper()

                    status_text.info(f"Processing {i+1}/{len(df)}: {p_num}")
                    unified = asyncio.run(process_row(page, p_num, nat, previous_passport, previous_unified))

                    status = "Found" if unified not in ["Not Found", "ERROR", "Invalid Data"] else "Not Found"
                    res = {"Passport Number": p_num, "Nationality": nat, "Unified Number": unified, "Status": status}

                    if status == "Found":
                        actual_success += 1
                        previous_unified = unified
                        previous_passport = p_num

                    st.session_state.batch_results.append(res)

                    elapsed = round(time.time() - start_time, 1)
                    progress_bar.progress((i + 1) / len(df))
                    stats_area.markdown(f"✅ **Actual Success (Found):** {actual_success} | ⏱️ **Timer:** {elapsed}s")

                    current_df = pd.DataFrame(st.session_state.batch_results)
                    styled_df = current_df.style.applymap(color_status, subset=['Status'])
                    live_table_area.dataframe(styled_df, use_container_width=True)
                    time.sleep(2)

                if st.session_state.run_state == 'running':
                    st.success("Batch Completed!")
                    final_df = pd.DataFrame(st.session_state.batch_results)
                    st.download_button("Download Full Report (CSV)", final_df.to_csv(index=False).encode('utf-8'), "full_results.csv")
            except Exception as e:
                st.error(f"Batch Error: {str(e)}")
import os
import sys
import time
import json
import pandas as pd
from .progress import Progress
from .scroller import Scroller
from .tweet import Tweet
from urllib.parse import quote

from datetime import datetime
from time import sleep
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.safari.service import Service as SafariService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.chrome import ChromeDriverManager


TWITTER_LOGIN_URL = "https://x.com/i/flow/login"


class Twitter_Scraper:
    def __init__(
        self,
        mail,
        username,
        password,
        headlessState,
        max_tweets=50,
        scrape_username=None,
        scrape_hashtag=None,
        scrape_query=None,
        scrape_bookmarks=False,
        scrape_poster_details=False,
        scrape_latest=True,
        scrape_top=False,
        proxy=None,
        cookie_file="x_cookie.json",
        browser="chrome",
    ):
        print("Initializing Twitter Scraper...")
        self.mail = mail
        self.username = username
        self.password = password
        self.headlessState = headlessState
        self.interrupted = False
        self.cookie_file = cookie_file
        self.browser = browser.lower()
        self.tweet_ids = set()
        self.data = []
        self.tweet_cards = []
        self.scraper_details = {
            "type": None,
            "username": None,
            "hashtag": None,
            "bookmarks": False,
            "query": None,
            "tab": None,
            "poster_details": False,
        }
        self.max_tweets = max_tweets
        self.progress = Progress(0, max_tweets)
        self.router = self.go_to_home
        self.driver = self._get_driver(proxy)
        self.actions = ActionChains(self.driver)
        self.scroller = Scroller(self.driver)
        self._config_scraper(
            max_tweets=max_tweets,
            scrape_username=scrape_username,
            scrape_hashtag=scrape_hashtag,
            scrape_bookmarks=scrape_bookmarks,
            scrape_query=scrape_query,
            scrape_latest=scrape_latest,
            scrape_top=scrape_top,
            scrape_poster_details=scrape_poster_details,
        )

    def _config_scraper(
        self,
        max_tweets=50,
        scrape_username=None,
        scrape_hashtag=None,
        scrape_bookmarks=False,
        scrape_query=None,
        scrape_list=None,
        scrape_latest=True,
        scrape_top=False,
        scrape_poster_details=False,
    ):
        self.tweet_ids = set()
        self.data = []
        self.tweet_cards = []
        self.max_tweets = max_tweets
        self.progress = Progress(0, max_tweets)
        self.scraper_details = {
            "type": None,
            "username": scrape_username,
            "hashtag": str(scrape_hashtag).replace("#", "")
            if scrape_hashtag is not None
            else None,
            "bookmarks": scrape_bookmarks,
            "query": scrape_query,
            "list": scrape_list,
            "tab": "Latest" if scrape_latest else "Top" if scrape_top else "Latest",
            "poster_details": scrape_poster_details,
        }
        self.router = self.go_to_home
        self.scroller = Scroller(self.driver)

        if scrape_username:
            self.scraper_details["type"] = "Username"
            self.router = self.go_to_profile
        elif scrape_hashtag:
            self.scraper_details["type"] = "Hashtag"
            self.router = self.go_to_hashtag
        elif scrape_bookmarks:
            self.scraper_details["type"] = "Bookmarks"
            self.router = self.go_to_bookmarks
        elif scrape_query:
            self.scraper_details["type"] = "Query"
            self.router = self.go_to_search
        elif scrape_list:
            self.scraper_details["type"] = "List"
            self.router = self.go_to_list
        else:
            self.scraper_details["type"] = "Home"
            self.router = self.go_to_home
        pass

    def _safe_get(self, url, retries=3, wait_sec=3):
        last_error = None
        for i in range(retries):
            try:
                self.driver.get(url)
                return
            except Exception as e:
                last_error = e
                print(f"Open {url} failed, retry {i+1}/{retries}: {e}")
                sleep(wait_sec)
        raise last_error

    def _dismiss_overlays(self):
        try:
            # 处理 cookie 横幅 / 弹窗
            candidates = self.driver.find_elements(
                By.XPATH,
                "//span[text()='Refuse non-essential cookies']/../../.."
                " | //span[text()='Accept all cookies']/../../.."
                " | //button[@aria-label='Close']"
                " | //div[@role='button' and @aria-label='Close']"
            )

            for el in candidates:
                try:
                    self.driver.execute_script("arguments[0].click();", el)
                    sleep(1)
                except Exception:
                    pass
        except Exception:
            pass

    def _get_driver(self, proxy=None):
        print("Setup WebDriver...")

        if self.browser == "chrome":
            browser_option = ChromeOptions()
            
            # 反检测配置
            browser_option.add_argument("--disable-blink-features=AutomationControlled")
            browser_option.add_argument("--disable-infobars")
            browser_option.add_argument("--disable-extensions")
            browser_option.add_argument("--disable-dev-shm-usage")
            browser_option.add_argument("--no-sandbox")
            browser_option.add_argument("--start-maximized")
            browser_option.add_argument("--disable-gpu")
            browser_option.add_argument("--disable-setuid-sandbox")
            browser_option.add_argument("--disable-web-security")
            browser_option.add_argument("--allow-running-insecure-content")
            browser_option.add_argument("--disable-features=VizDisplayCompositor")
            browser_option.add_argument("--ignore-certificate-errors")
            
            # 禁用自动化提示
            browser_option.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            browser_option.add_experimental_option("useAutomationExtension", False)
            
            # 设置用户代理
            browser_option.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # 启用无头模式的特殊配置
            if self.headlessState == "yes":
                browser_option.add_argument("--headless=new")
                browser_option.add_argument("--window-size=1920,1080")
                browser_option.add_argument("--hide-scrollbars")
            
            try:
                print("Initializing ChromeDriver...")
                driver = webdriver.Chrome(options=browser_option)
            except WebDriverException:
                print("Downloading ChromeDriver...")
                chrome_path = ChromeDriverManager().install()
                chrome_service = ChromeService(executable_path=chrome_path)
                driver = webdriver.Chrome(service=chrome_service, options=browser_option)
            
            # 进一步隐藏自动化特征
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            driver.execute_script("window.chrome = {runtime: {}}")
            driver.execute_script("window.navigator.chrome = {runtime: {}}")

        elif self.browser == "safari":
            browser_option = SafariOptions()
            if self.headlessState == "yes":
                browser_option.add_argument("--headless")
            print("Initializing SafariDriver...")
            driver = webdriver.Safari(options=browser_option)

        else:  # firefox
            header = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"
            browser_option = FirefoxOptions()
            browser_option.set_preference("general.useragent.override", header)
            browser_option.set_preference("security.enterprise_roots.enabled", True)
            browser_option.set_preference("network.http.http3.enable", False)
            browser_option.set_preference("dom.webnotifications.enabled", False)
            browser_option.set_preference("permissions.default.desktop-notification", 2)
            browser_option.accept_insecure_certs = True
            if self.headlessState == "yes":
                browser_option.add_argument("--headless")

            try:
                print("Initializing FirefoxDriver...")
                driver = webdriver.Firefox(options=browser_option)
            except WebDriverException:
                print("Downloading FirefoxDriver...")
                firefoxdriver_path = GeckoDriverManager().install()
                firefox_service = FirefoxService(executable_path=firefoxdriver_path)
                print("Initializing FirefoxDriver...")
                driver = webdriver.Firefox(
                    service=firefox_service,
                    options=browser_option,
                )

        driver.set_page_load_timeout(60)
        print("WebDriver Setup Complete")
        return driver

    def _wait(self, timeout=20):
        return WebDriverWait(self.driver, timeout)

    def _has_auth_token(self):
        try:
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                if cookie.get("name") == "auth_token" and cookie.get("value"):
                    return True
        except Exception:
            pass
        return False


    def _load_cookies_from_json(self, max_retries=3):
        if not os.path.exists(self.cookie_file):
            raise FileNotFoundError(f"Cookie file not found: {self.cookie_file}")

        with open(self.cookie_file, "r", encoding="utf-8") as f:
            cookies = json.load(f)

        # 过滤掉无效的 cookie（只保留 x.com 相关的）
        valid_cookies = []
        for cookie in cookies:
            domain = cookie.get("domain", "")
            if ".x.com" in domain or ".twitter.com" in domain or not domain:
                valid_cookies.append(cookie)
        
        print(f"  加载 {len(valid_cookies)} 个有效 cookies")

        last_error = None
        for attempt in range(max_retries):
            try:
                print(f"  尝试加载 cookies ({attempt+1}/{max_retries})...")
                
                # 先访问一个简单的页面
                self.driver.get("https://x.com/robots.txt")
                sleep(2)

                # 清除现有 cookies
                self.driver.delete_all_cookies()

                for cookie in valid_cookies:
                    cookie_dict = {
                        "name": cookie["name"],
                        "value": cookie["value"],
                    }

                    if cookie.get("domain"):
                        # 确保 domain 以点开头
                        domain = cookie["domain"]
                        if not domain.startswith("."):
                            domain = "." + domain
                        cookie_dict["domain"] = domain
                    if cookie.get("path"):
                        cookie_dict["path"] = cookie["path"]
                    if "secure" in cookie:
                        cookie_dict["secure"] = cookie["secure"]
                    if "httpOnly" in cookie:
                        cookie_dict["httpOnly"] = cookie["httpOnly"]

                    # 处理过期时间
                    if cookie.get("expirationDate") is not None:
                        try:
                            cookie_dict["expiry"] = int(cookie["expirationDate"])
                        except Exception:
                            pass

                    # 移除 selenium 不支持的字段
                    for bad_key in [
                        "sameSite",
                        "hostOnly",
                        "session",
                        "storeId",
                        "firstPartyDomain",
                        "partitionKey",
                        "priority",
                        "sourceScheme",
                    ]:
                        cookie_dict.pop(bad_key, None)

                    try:
                        self.driver.add_cookie(cookie_dict)
                    except Exception as e:
                        pass  # 跳过失败的 cookie，继续处理其他的

                # 重新加载主页
                self.driver.get("https://x.com/home")
                sleep(3)
                
                # 等待页面加载
                self._wait_for_page_load()
                
                return
                
            except Exception as e:
                last_error = e
                print(f"  加载 cookies 失败 (尝试 {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    sleep(3)
        
        raise last_error

    def _wait_for_page_load(self, timeout=30):
        """等待页面完全加载"""
        try:
            # 等待页面标题出现
            self._wait(timeout).until(
                lambda d: "X" in d.title or "Twitter" in d.title
            )
            print("  页面标题加载完成")
            
            # 等待页面元素
            self._wait(timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            sleep(2)
        except TimeoutException:
            print("  页面加载超时，但继续尝试...")

    def _is_logged_in(self):
        try:
            # 先看 auth_token 是否已经进浏览器
            for cookie in self.driver.get_cookies():
                if cookie.get("name") == "auth_token" and cookie.get("value"):
                    return True

            current_url = self.driver.current_url.lower()
            if "x.com/home" in current_url:
                return True

            elements = self.driver.find_elements(
                By.XPATH,
                "//*[contains(@data-testid,'SideNav_NewTweet_Button')] | //a[@href='/home']"
            )
            return len(elements) > 0
        except Exception:
            return False

    

    def login(self):
        print("\nLoading X cookies...")

        try:
            # 设置更大的超时时间
            self.driver.set_page_load_timeout(120)
            
            # 窗口最大化
            try:
                self.driver.maximize_window()
            except Exception:
                pass  # 某些环境不支持最大化
            
            # 加载 cookies
            self._load_cookies_from_json()

            # 检查是否登录成功
            if not self._is_logged_in():
                # 尝试刷新页面后再次检查
                print("  登录状态检查失败，尝试刷新页面...")
                self.driver.refresh()
                sleep(5)
                
                if not self._is_logged_in():
                    raise RuntimeError(
                        "Cookie login failed. Please export fresh cookies from your normal browser.\n"
                        "提示：请确保 Cookie 未过期，并且是从已登录的浏览器导出的。"
                    )

            print("  ✓ Cookie login successful\n")

        except TimeoutException as e:
            print(f"\nLogin Failed: 页面加载超时 ({e})")
            print("  建议：检查网络连接，或尝试使用其他浏览器（safari/firefox）")
            self._safe_quit()
            raise
        except WebDriverException as e:
            print(f"\nLogin Failed: WebDriver 错误 ({e})")
            print("  建议：更新 Chrome/Firefox 浏览器和对应的 WebDriver")
            self._safe_quit()
            raise
        except Exception as e:
            print(f"\nLogin Failed: {e}")
            self._safe_quit()
            raise

    def _safe_quit(self):
        """安全退出浏览器"""
        try:
            print("  正在关闭浏览器...")
            self.driver.quit()
        except Exception:
            pass

    

    def go_to_home(self):
        self.driver.get("https://x.com/home")
        sleep(3)

    def go_to_profile(self):
        if (
            self.scraper_details["username"] is None
            or self.scraper_details["username"] == ""
        ):
            print("Username is not set.")
            sys.exit(1)
        else:
            self.driver.get(f"https://x.com/{self.scraper_details['username']}")
            sleep(3)

    def go_to_hashtag(self):
        if (
            self.scraper_details["hashtag"] is None
            or self.scraper_details["hashtag"] == ""
        ):
            print("Hashtag is not set.")
            sys.exit(1)
        else:
            url = f"https://x.com/hashtag/{self.scraper_details['hashtag']}?src=hashtag_click"
            if self.scraper_details["tab"] == "Latest":
                url += "&f=live"

            self.driver.get(url)
            sleep(3)

    def go_to_bookmarks(self):
        if (
            self.scraper_details["bookmarks"] is False
            or self.scraper_details["bookmarks"] == ""
        ):
            print("Bookmarks is not set.")
            sys.exit(1)
        else:
            url = "https://x.com/i/bookmarks"
            self.driver.get(url)
            sleep(3)

    def go_to_search(self):
        if self.scraper_details["query"] is None or self.scraper_details["query"] == "":
            print("Query is not set.")
            sys.exit(1)
        else:
            encoded_query = quote(self.scraper_details["query"], safe="")
            url = f"https://x.com/search?q={encoded_query}&src=typed_query"

            if self.scraper_details["tab"] == "Latest":
                url += "&f=live"

            self.driver.get(url)
            sleep(3)

    def go_to_list(self):
        if not self.scraper_details["list"]:
            raise ValueError("List is not set.")
        self.driver.get(f"https://x.com/i/lists/{self.scraper_details['list']}")
        sleep(3)

    def get_tweet_cards(self):
        self.tweet_cards = self.driver.find_elements(
            "xpath", '//article[@data-testid="tweet" and not(@disabled)]'
        )
        pass

    def remove_hidden_cards(self):
        try:
            hidden_cards = self.driver.find_elements(
                "xpath", '//article[@data-testid="tweet" and @disabled]'
            )

            for card in hidden_cards[1:-2]:
                self.driver.execute_script(
                    "arguments[0].parentNode.parentNode.parentNode.remove();", card
                )
        except Exception as e:
            return
        pass

    def scrape_tweets(
        self,
        max_tweets=50,
        no_tweets_limit=False,
        scrape_username=None,
        scrape_hashtag=None,
        scrape_bookmarks=False,
        scrape_query=None,
        scrape_list=None,
        scrape_latest=True,
        scrape_top=False,
        scrape_poster_details=False,
        router=None,
    ):
        self._config_scraper(
            max_tweets=max_tweets,
            scrape_username=scrape_username,
            scrape_hashtag=scrape_hashtag,
            scrape_bookmarks=scrape_bookmarks,
            scrape_query=scrape_query,
            scrape_list=scrape_list,
            scrape_latest=scrape_latest,
            scrape_top=scrape_top,
            scrape_poster_details=scrape_poster_details,
        )

        router = router or self.router
        router()
        self._dismiss_overlays()
        self.progress.print_progress(0, False, 0, no_tweets_limit)

        idle_rounds = 0

        while True:
            try:
                self.get_tweet_cards()
                self.remove_hidden_cards()
                added_tweets = 0

                for card in self.tweet_cards[-20:]:
                    try:
                        tweet = Tweet(
                            card=card,
                            driver=self.driver,
                            actions=self.actions,
                            scrape_poster_details=self.scraper_details["poster_details"],
                        )

                        if not tweet or tweet.error or tweet.tweet is None or tweet.is_ad:
                            continue

                        unique_id = tweet.tweet_id or tweet.tweet_link or str(card)
                        if unique_id in self.tweet_ids:
                            continue

                        self.tweet_ids.add(unique_id)
                        self.data.append(tweet.tweet)
                        added_tweets += 1
                        self.progress.print_progress(len(self.data), False, 0, no_tweets_limit)

                        if len(self.data) >= self.max_tweets and not no_tweets_limit:
                            print("\nScraping Complete")
                            print(f"Tweets: {len(self.data)} out of {self.max_tweets}\n")
                            return

                    except (NoSuchElementException, StaleElementReferenceException):
                        continue

                if added_tweets == 0:
                    idle_rounds += 1
                else:
                    idle_rounds = 0

                # 如果页面给 Retry，就点一下，但不要睡 600 秒
                try:
                    retry_btn = self.driver.find_element(By.XPATH, "//span[text()='Retry']/../../..")
                    self.driver.execute_script("arguments[0].click();", retry_btn)
                    sleep(5)
                except NoSuchElementException:
                    pass

                moved = self.scroller.scroll_once()

                if not moved:
                    idle_rounds += 1

                if idle_rounds == 2:
                    self.driver.refresh()
                    sleep(3)
                    self._dismiss_overlays()

                if idle_rounds >= 4:
                    print("\nNo more tweets to scrape")
                    break

            except KeyboardInterrupt:
                print("\nKeyboard Interrupt")
                self.interrupted = True
                break
            except Exception as e:
                print(f"\nError scraping tweets: {e}")
                break

        print("")
        if len(self.data) >= self.max_tweets or no_tweets_limit:
            print("Scraping Complete")
        else:
            print("Scraping Incomplete")

        if not no_tweets_limit:
            print(f"Tweets: {len(self.data)} out of {self.max_tweets}\n")

    def save_to_csv(self):
        print("Saving Tweets to CSV...")
        now = datetime.now()
        folder_path = "./抓取的信息/"

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print("Created Folder: {}".format(folder_path))

        data = {
            "Name": [tweet[0] for tweet in self.data],
            "Handle": [tweet[1] for tweet in self.data],
            "Timestamp": [tweet[2] for tweet in self.data],
            "Verified": [tweet[3] for tweet in self.data],
            "Content": [tweet[4] for tweet in self.data],
            "Comments": [tweet[5] for tweet in self.data],
            "Retweets": [tweet[6] for tweet in self.data],
            "Likes": [tweet[7] for tweet in self.data],
            "Analytics": [tweet[8] for tweet in self.data],
            "Tags": [tweet[9] for tweet in self.data],
            "Mentions": [tweet[10] for tweet in self.data],
            "Emojis": [tweet[11] for tweet in self.data],
            "Profile Image": [tweet[12] for tweet in self.data],
            "Tweet Link": [tweet[13] for tweet in self.data],
            "Tweet ID": [f"tweet_id:{tweet[14]}" for tweet in self.data],
        }

        if self.scraper_details["poster_details"]:
            data["Tweeter ID"] = [f"user_id:{tweet[15]}" for tweet in self.data]
            data["Following"] = [tweet[16] for tweet in self.data]
            data["Followers"] = [tweet[17] for tweet in self.data]

        df = pd.DataFrame(data)

        current_time = now.strftime("%Y-%m-%d_%H-%M-%S")
        file_path = f"{folder_path}{current_time}_tweets_1-{len(self.data)}.csv"
        pd.set_option("display.max_colwidth", None)
        df.to_csv(file_path, index=False, encoding="utf-8")

        print("CSV Saved: {}".format(file_path))

        try:
            from graph_engine import generate_graph_data

            generate_graph_data(
                output_file="./graph_data/关系图谱.json",
                query=self.scraper_details.get("query") or self.scraper_details.get("username") or "",
                input_dir=folder_path,
            )
        except Exception as e:
            print("Graph generation failed: {}".format(e))

        pass

    def get_tweets(self):
        return self.data

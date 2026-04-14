import os
import sys
import time
import json
import pandas as pd
from progress import Progress
from scroller import Scroller
from tweet import Tweet
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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from webdriver_manager.firefox import GeckoDriverManager


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
    ):
        print("Initializing Twitter Scraper...")
        self.mail = mail
        self.username = username
        self.password = password
        self.headlessState = headlessState
        self.interrupted = False
        self.cookie_file = cookie_file
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

        header = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"

        browser_option = FirefoxOptions()
        browser_option.set_preference("general.useragent.override", header)

        # 关键：让 Firefox 识别系统/企业根证书
        browser_option.set_preference("security.enterprise_roots.enabled", True)

        # 关键：先关掉 HTTP/3，避免部分环境下 x.com 握手异常
        browser_option.set_preference("network.http.http3.enable", False)

        # 不要弹通知
        browser_option.set_preference("dom.webnotifications.enabled", False)
        browser_option.set_preference("permissions.default.desktop-notification", 2)

        # 关键：允许不安全证书
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


    def _load_cookies_from_json(self):
        if not os.path.exists(self.cookie_file):
            raise FileNotFoundError(f"Cookie file not found: {self.cookie_file}")

        with open(self.cookie_file, "r", encoding="utf-8") as f:
            cookies = json.load(f)

        self.driver.get("https://x.com/")
        sleep(3)

        for cookie in cookies:
            cookie_dict = {
                "name": cookie["name"],
                "value": cookie["value"],
            }

            if cookie.get("domain"):
                cookie_dict["domain"] = cookie["domain"]
            if cookie.get("path"):
                cookie_dict["path"] = cookie["path"]
            if "secure" in cookie:
                cookie_dict["secure"] = cookie["secure"]
            if "httpOnly" in cookie:
                cookie_dict["httpOnly"] = cookie["httpOnly"]

            # 你的导出文件用的是 expirationDate
            if cookie.get("expirationDate") is not None:
                try:
                    cookie_dict["expiry"] = int(cookie["expirationDate"])
                except Exception:
                    pass

            # 浏览器扩展导出的这些字段，selenium 往往不认
            # 不要传给 add_cookie
            for bad_key in [
                "sameSite",
                "hostOnly",
                "session",
                "storeId",
                "firstPartyDomain",
                "partitionKey",
            ]:
                cookie_dict.pop(bad_key, None)

            try:
                self.driver.add_cookie(cookie_dict)
            except Exception as e:
                print(f"Skip cookie {cookie.get('name')}: {e}")

        self.driver.get("https://x.com/home")
        sleep(5)

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
            self.driver.maximize_window()
            self._load_cookies_from_json()

            if not self._is_logged_in():
                raise RuntimeError(
                    "Cookie login failed. Please export fresh cookies from your normal browser."
                )

            print("\nCookie login successful\n")

        except Exception as e:
            print(f"\nLogin Failed: {e}")
            self.driver.quit()
            sys.exit(1)

    

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
        folder_path = "./tweets/"

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

        pass

    def get_tweets(self):
        return self.data

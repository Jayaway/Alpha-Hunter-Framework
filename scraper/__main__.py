import os
import sys
import argparse
import getpass
from .twitter_scraper import Twitter_Scraper

try:
    from dotenv import load_dotenv

    print("Loading .env file")
    load_dotenv()
    print("Loaded .env file\n")
except Exception as e:
    print(f"Error loading .env file: {e}")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        add_help=True,
        usage="python scraper [option] ... [arg] ...",
        description="Twitter/X Scraper without official API.",
    )

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    parser.add_argument("--mail", type=str, default=os.getenv("TWITTER_MAIL"))
    parser.add_argument("--user", type=str, default=os.getenv("TWITTER_USERNAME"))
    parser.add_argument("--password", type=str, default=os.getenv("TWITTER_PASSWORD"))
    parser.add_argument("--headlessState", type=str, default=os.getenv("HEADLESS", "no"))

    parser.add_argument("-t", "--tweets", type=int, default=50)
    parser.add_argument("-u", "--username", type=str, default=None)
    parser.add_argument("-ht", "--hashtag", type=str, default=None)
    parser.add_argument("--bookmarks", action="store_true")
    parser.add_argument("-ntl", "--no_tweets_limit", action="store_true")
    parser.add_argument("-l", "--list", type=str, default=None)
    parser.add_argument("-q", "--query", type=str, default=None)
    parser.add_argument("-a", "--add", type=str, default="")
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--top", action="store_true")
    parser.add_argument(
        "-b", "--browser",
        type=str,
        default="chrome",
        choices=["firefox", "chrome", "safari"],
        help="Browser to use (default: chrome)",
    )

    parser.add_argument(
        "--cookie-file",
        type=str,
        default="cookies/browser/x_cookie.json",
        help="Cookie file path.",
    )

    args = parser.parse_args()

    user_mail = args.mail
    user_name = args.user or "cookie_login"
    user_password = args.password or "cookie_login"
    headless_mode = str(args.headlessState or "no").strip().lower()

    if headless_mode not in {"yes", "no"}:
        headless_mode = "no"

    tweet_type_args = []
    if args.username:
        tweet_type_args.append("username")
    if args.hashtag:
        tweet_type_args.append("hashtag")
    if args.list:
        tweet_type_args.append("list")
    if args.query:
        tweet_type_args.append("query")
    if args.bookmarks:
        tweet_type_args.append("bookmarks")

    if len(tweet_type_args) > 1:
        print("Please specify only one of --username, --hashtag, --bookmarks, --list, or --query.")
        sys.exit(1)

    if args.latest and args.top:
        print("Please specify either --latest or --top, not both.")
        sys.exit(1)

    additional_data = [x.strip() for x in args.add.split(",") if x.strip()]

    scraper = Twitter_Scraper(
        mail=user_mail,
        username=user_name,
        password=user_password,
        headlessState=headless_mode,
        max_tweets=args.tweets,
        cookie_file=args.cookie_file,
        browser=args.browser,
    )

    try:
        scraper.login()
        scraper.scrape_tweets(
            max_tweets=args.tweets,
            no_tweets_limit=args.no_tweets_limit,
            scrape_username=args.username,
            scrape_hashtag=args.hashtag,
            scrape_bookmarks=args.bookmarks,
            scrape_query=args.query,
            scrape_list=args.list,
            scrape_latest=args.latest if (args.latest or args.top) else True,
            scrape_top=args.top,
            scrape_poster_details=("pd" in additional_data),
        )
        scraper.save_to_csv()
    finally:
        try:
            scraper.driver.quit()
        except Exception:
            pass

    sys.exit(0)


if __name__ == "__main__":
    main()

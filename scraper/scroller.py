import time
import random


class Scroller:
    def __init__(self, driver) -> None:
        self.driver = driver
        self.current_position = 0
        self.last_position = driver.execute_script("return window.pageYOffset;")
        self.scrolling = True
        self.scroll_count = 0

    def reset(self) -> None:
        self.current_position = 0
        self.last_position = self.driver.execute_script("return window.pageYOffset;")
        self.scroll_count = 0
        self.scrolling = True

    def scroll_to_top(self) -> None:
        self.driver.execute_script("window.scrollTo(0, 0);")

    def scroll_to_bottom(self) -> None:
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    def scroll_once(self, min_px=900, max_px=1600, min_wait=1.2, max_wait=2.0) -> bool:
        self.last_position = self.driver.execute_script("return window.pageYOffset;")
        delta = random.randint(min_px, max_px)
        self.driver.execute_script("window.scrollBy(0, arguments[0]);", delta)
        time.sleep(random.uniform(min_wait, max_wait))
        self.current_position = self.driver.execute_script("return window.pageYOffset;")
        self.scroll_count += 1

        if self.current_position <= self.last_position:
            self.scrolling = False
            return False
        return True
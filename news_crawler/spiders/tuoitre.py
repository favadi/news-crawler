"""
TuoiTre crawler.
"""
from datetime import datetime
from scrapy import Request

from .crawler import BaseCrawler
from news_crawler.items import TuoiTreArticle
from news_crawler.helper.comment_counter import TuoiTreCounter

class TuoiTreSpider(BaseCrawler):
    name = "tuoitre"
    allowed_domains = ["tuoitre.vn"]
    comment_counter = TuoiTreCounter()

    custom_settings = {
        'ITEM_PIPELINES': {
            'news_crawler.pipelines.scorer.TuoiTreScorer': 100
        }
    }

    def __init__(self, *args, days_ago: int = 30, **kwargs):
        super().__init__(*args, days_ago=days_ago, **kwargs)
        self.article_index = 1
        self.video_index = 1

    @property
    def article_url(self):
        return f"https://tuoitre.vn/timeline/0/trang-{self.article_index}.htm"

    @property
    def video_url(self):
        return f"https://tuoitre.vn/timeline/search.htm?pageindex={self.video_index}"

    def start_requests(self):
        yield Request(url=self.article_url)
        yield Request(url=self.video_url)

    def populate_comment_count(self, response, articles: list):
        """
        Override super's populate comment count to also decide if go onto next page.
        Decide by comparing the last article's published time and compare it with our date range.
        """
        last_article = yield from super().populate_comment_count(response, articles)
        next_page_url = self.next_page_decider(last_article)
        if next_page_url:
            yield Request(url=next_page_url, callback=self.parse_start_url)
        else:
            self.logger.debug(
                "Stopped going to next page for %s. Article index: %s. Video index: %s",
                last_article.item_type, self.article_index, self.video_index
            )

    def next_page_decider(self, article):
        """
        Decide if continue to next page by checking article time against self.from_timestamp.
        Return next page url.
        """
        published_time = article.published_time
        item_type = article.item_type
        self.logger.debug("Comparing published time %d vs query time %d", published_time, self.from_timestamp)
        if published_time > self.from_timestamp:
            if item_type == "video":
                self.video_index += 1
                url = self.video_url
            else:
                self.article_index += 1
                url = self.article_url
            return url

    def get_article_list(self, response):
        """
        Get list of articles from response.

        Return:
            list of Article objects.
        """
        article_block_selector = ".box-category-item"
        articles = []

        item_type = "video"
        if response.url.endswith(".htm"):
            item_type = "article"

        for article_block in response.css(article_block_selector):
            link_title = article_block.css(".box-category-link-title")
            url = link_title.attrib["href"]
            title = link_title.attrib["title"]
            identifier = link_title.attrib["data-id"]
            category = article_block.css(".box-category-category::text").get()

            # Published time format and selector for videos
            published_time_selector = "span.time::text"
            published_time_format = "%d/%m/%Y%z"
            if item_type == "article":
                # Published time selector and format for articles
                published_time_selector = ".time-ago-last-news::attr(title)"
                published_time_format = "%Y-%m-%dT%H:%M:%S%z"
            published_time = article_block.css(published_time_selector).get()
            # Convert published time from string GMT+7 to UTC timestamp
            published_time = datetime.strptime(published_time+"+0700", published_time_format).timestamp()
            articles.append(TuoiTreArticle(
                url=url,
                title=title,
                identifier=identifier,
                category=category,
                item_type=item_type,
                published_time=published_time
            ))
        return articles
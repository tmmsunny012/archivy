import datetime
from urllib.parse import urljoin

import validators
import requests
import html2text
import frontmatter
from bs4 import BeautifulSoup

from archivy import extensions
from archivy.search import add_to_index
from archivy.data import create
from archivy.config import Config


class DataObj:
    __searchable__ = ["title", "content", "desc", "tags"]

    def process_bookmark_url(self):
        try:
            url_request = requests.get(self.url).text
            parsed_html = BeautifulSoup(url_request)
            self.content = self.extract_content(parsed_html)
            self.title = parsed_html.title.string
        except BaseException:
            self.wipe()

    def wipe(self):
        self.title = None
        self.desc = None
        self.content = None

    def extract_content(self, beautsoup):
        stripped_tags = ["footer", "nav"]
        url = self.url.rstrip("/")

        for tag in stripped_tags:
            if getattr(beautsoup, tag):
                getattr(beautsoup, tag).extract()
        resources = beautsoup.find_all(["a", "img"])
        for external in resources:
            if external.name == "a" and \
                    "href" in external and \
                    external["href"].startswith("/"):
                external["href"] = urljoin(url, external["href"])
            elif external.name == "img" and \
                    "src" in external and \
                    external["src"].startswith("/"):
                external["src"] = urljoin(url, external["src"])

        return html2text.html2text(str(beautsoup))

    def __init__(self, **kwargs):

        # data has already been processed
        if kwargs["type"] == "processed-dataobj":
            for key, value in kwargs.items():
                setattr(self, key, value)
        else:
            # still needs processing
            if "path" in kwargs and kwargs["path"] != "not classified":
                self.path = kwargs["path"]
            else:
                self.path = ""
            self.desc = kwargs["desc"]
            self.tags = kwargs["tags"].split()
            self.type = kwargs["type"]
            self.content = ""
            self.id = -1

            if "date" in kwargs:
                self.date = kwargs["date"]
            else:
                self.date = datetime.datetime.now()
            if self.type == "bookmarks" or self.type == "pocket_bookmarks":
                self.url = kwargs["url"]
                if validators.url(self.url):
                    self.process_bookmark_url()
            else:
                self.title = kwargs["title"]

    def validate(self):
        valid_url = (
            self.type != "bookmarks" or self.type != "pocket_bookmarks") or (
            isinstance(
                self.url,
                str) and validators.url(
                self.url))
        valid_title = isinstance(self.title, str)
        valid_content = (self.type != "bookmark" and
                         self.type != "pocket_bookmarks") or \
            isinstance(self.content, str)
        return valid_url and valid_title and valid_content

    def insert(self):
        if self.validate():
            self.id = extensions.get_max_id()
            data = {
                "type": self.type,
                "desc": self.desc,
                "title": str(self.title),
                "date": self.date.strftime("%x").replace("/", "-"),
                "tags": self.tags,
                "id": self.id,
                "path": self.path
            }
            if self.type == "bookmarks" or self.type == "pocket_bookmarks":
                data["url"] = self.url

            extensions.set_max_id(self.id + 1)

            # convert to markdown
            dataobj = frontmatter.Post(self.content)
            dataobj.metadata = data
            create(frontmatter.dumps(dataobj), str(self.id) + "-" +
                   dataobj["date"] + "-" + dataobj["title"], path=self.path)
            add_to_index(Config.INDEX_NAME, self)
            return self.id
        return False

    @classmethod
    def from_file(cls, filename):
        data = frontmatter.load(filename)
        dataobj = {}
        dataobj["content"] = data.content
        for pair in ["tags", "desc", "id", "title", "path"]:
            dataobj[pair] = data[pair]

        dataobj["type"] = "processed-dataobj"
        return cls(**dataobj)

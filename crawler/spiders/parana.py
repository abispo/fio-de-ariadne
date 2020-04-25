from datetime import datetime
from typing import Iterator, Union

from scrapy import Request, Spider
from scrapy.http import Response

from crawler.clients.ibge import APIClientIBGE
from crawler.items import Case
from crawler.text import PARSERS


class ParanaSpider(Spider):
    name = "parana"
    allowed_domains = ["desaparecidosdobrasil.org"]
    api_client = APIClientIBGE("Paraná")

    def request_offset(self, offset: int) -> Request:
        base_url = "http://www.desaparecidosdobrasil.org/criancas-desaparecidas/parana/"
        url = f"{base_url}?offset={offset}"
        return Request(url, meta={"offset": offset})

    def start_requests(self) -> Iterator[Request]:
        yield self.request_offset(0)

    def parse(self, response: Response) -> Iterator[Union[Case, Request]]:
        for case in response.css("div.announcement"):

            # if we have cases, this is not the last page
            offset = response.meta.get("offset", 0)
            yield self.request_offset(offset + 1)

            # get main data from the case
            title = case.css("h4 a")
            href = title.attrib["href"]
            name = title.css("::text").get()
            if not name:
                continue

            # parse textual data from the case
            contents = tuple(
                line.strip() for line in case.css("::text").getall() if line.strip()
            )

            kwargs = {name: parser(contents) for name, parser in PARSERS.items()}

            if (
                kwargs["age_at_occurrence"] is None
                and kwargs["dob"] is not None
                and kwargs["missing_since"] is not None
            ):
                dob = datetime.strptime(str(kwargs["dob"]), "%Y-%m-%d")
                missing_since = datetime.strptime(
                    str(kwargs["missing_since"]), "%Y-%m-%d"
                )
                kwargs["age_at_occurrence"] = missing_since.year - dob.year

            kwargs = self.clean_city(kwargs)

            yield Case(
                name=name,
                url=response.urljoin(href),
                full_text="\n".join(contents),
                **kwargs,
            )

    def clean_city(self, kwargs):
        if kwargs.get("last_seen_at"):
            sigla = self.api_client.states["sigla"]
            city = self.api_client.search_city(kwargs["last_seen_at"])

            if city:
                name_city = city["nome"]
                kwargs["last_seen_at"] = f"{name_city} - {sigla}"
        return kwargs

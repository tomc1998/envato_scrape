from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Rating:
    rating: float
    count: int

    def serialize(self) -> dict:
        return {"rating": self.rating, "count": self.count}

    @classmethod
    def from_dict(cls, data: dict) -> "Rating":
        return cls(rating=data.get("rating", 0.0), count=data.get("count", 0))


@dataclass
class Length:
    hours: int
    minutes: int
    seconds: int

    def serialize(self) -> dict:
        return {"hours": self.hours, "minutes": self.minutes, "seconds": self.seconds}

    @classmethod
    def from_dict(cls, data: dict) -> "Length":
        return cls(
            hours=data.get("hours", 0),
            minutes=data.get("minutes", 0),
            seconds=data.get("seconds", 0),
        )


@dataclass
class Preview:
    icon_url: str
    mp3_url: str
    mp3_preview_waveform_url: str
    mp3_preview_download_url: str
    mp3_id: int
    length: Length

    def serialize(self) -> dict:
        return {
            "icon_url": self.icon_url,
            "mp3_url": self.mp3_url,
            "mp3_preview_waveform_url": self.mp3_preview_waveform_url,
            "mp3_preview_download_url": self.mp3_preview_download_url,
            "mp3_id": self.mp3_id,
            "length": self.length.serialize(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Preview":
        return cls(
            icon_url=data.get("icon_url", ""),
            mp3_url=data.get("mp3_url", ""),
            mp3_preview_waveform_url=data.get("mp3_preview_waveform_url", ""),
            mp3_preview_download_url=data.get("mp3_preview_download_url", ""),
            mp3_id=data.get("mp3_id", 0),
            length=Length.from_dict(data.get("length", {})),
        )


@dataclass
class Product:
    id: int
    name: str
    description: str
    description_html: str
    site: str
    classification: str
    classification_url: str
    price_cents: int
    number_of_sales: int
    author_username: str
    author_url: str
    author_image: str
    url: str
    summary: str
    rating: Rating
    updated_at: str
    published_at: str
    trending: bool
    previews: Preview
    attributes: list[dict]
    photo_attributes: list[dict]
    key_features: list[str]
    image_urls: list[str]
    tags: list[str]
    discounts: list[dict]

    def get_attribute(self, name: str) -> Optional[Any]:
        for attrib in self.attributes:
            if attrib['name'] == name:
                return attrib['value']
        return None

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "description_html": self.description_html,
            "site": self.site,
            "classification": self.classification,
            "classification_url": self.classification_url,
            "price_cents": self.price_cents,
            "number_of_sales": self.number_of_sales,
            "author_username": self.author_username,
            "author_url": self.author_url,
            "author_image": self.author_image,
            "url": self.url,
            "summary": self.summary,
            "rating": self.rating.serialize(),
            "updated_at": self.updated_at,
            "published_at": self.published_at,
            "trending": self.trending,
            "previews": self.previews.serialize(),
            "attributes": self.attributes,
            "photo_attributes": self.photo_attributes,
            "key_features": self.key_features,
            "image_urls": self.image_urls,
            "tags": self.tags,
            "discounts": self.discounts,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            description=data.get("description", ""),
            description_html=data.get("description_html", ""),
            site=data.get("site", ""),
            classification=data.get("classification", ""),
            classification_url=data.get("classification_url", ""),
            price_cents=data.get("price_cents", 0),
            number_of_sales=data.get("number_of_sales", 0),
            author_username=data.get("author_username", ""),
            author_url=data.get("author_url", ""),
            author_image=data.get("author_image", ""),
            url=data.get("url", ""),
            summary=data.get("summary", ""),
            rating=Rating.from_dict(data.get("rating", {})),
            updated_at=data.get("updated_at", ""),
            published_at=data.get("published_at", ""),
            trending=data.get("trending", False),
            previews=Preview.from_dict(
                data.get("previews", {}).get("icon_with_audio_preview", {})
            ),
            attributes=data.get("attributes", []),
            photo_attributes=data.get("photo_attributes", []),
            key_features=data.get("key_features", []),
            image_urls=data.get("image_urls", []),
            tags=data.get("tags", []),
            discounts=data.get("discounts", []),
        )


class Category:
    def __init__(self, name: str, path: str, total_products: Optional[int] = None):
        self.name = name
        self.path = path
        self.total_products = total_products

    def serialize(self) -> dict:
        result: dict[str, Any] = {"name": self.name, "path": self.path}
        if self.total_products is not None:
            result["total_products"] = self.total_products
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Category":
        return cls(
            data["name"], data["path"], total_products=data.get("total_products")
        )

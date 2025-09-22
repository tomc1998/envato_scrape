import atexit
import os
from typing import Optional

import click
from larch.pickle import pickle  # type: ignore[import-untyped]

from .product import Category, Product


class Cache:
    categories: dict[str, dict[str, Category]]
    products: dict[int, Product]
    cache_file: str
    dirty: bool

    def __init__(self) -> None:
        self.categories = {}
        self.products = {}
        self.cache_file = ".envato_scrape_cache.pickle"
        self.dirty = False
        self.load()
        atexit.register(self.maybe_save)

    def add_category(self, site: str, category: Category) -> None:
        self.dirty = True
        if site not in self.categories:
            self.categories[site] = {}
        self.categories[site][category.path] = category

    def add_product(self, product: Product) -> None:
        self.dirty = True
        self.products[product.id] = product

    def serialize(self) -> dict:
        serialized: dict = {"categories": {}, "products": {}}
        for site, categories in self.categories.items():
            serialized["categories"][site] = {
                name: category.serialize() for name, category in categories.items()
            }
        for product_id, product in self.products.items():
            serialized["products"][str(product_id)] = product.serialize()
        return serialized

    def maybe_save(self) -> None:
        if self.dirty:
            self.save()
            self.dirty = False

    def save(self) -> None:
        try:
            with open(self.cache_file, "wb") as f:
                pickle.dump(self.serialize(), f)
        except Exception as e:
            click.echo(f"Failed to save cache: {e}", err=True)

    def load(self) -> None:
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "rb") as f:
                    data = pickle.load(f)
                    # Load categories
                    for site, categories in data.get("categories", {}).items():
                        self.categories[site] = {}
                        for name, category_data in categories.items():
                            self.categories[site][name] = Category.from_dict(
                                category_data
                            )
                    # Load products
                    for product_id, product_data in data.get("products", {}).items():
                        self.products[int(product_id)] = Product.from_dict(product_data)
        except Exception as e:
            click.echo(f"Failed to load cache: {e}", err=True)


# Global cache instance
_cache_singleton_instance: Optional[Cache] = None


def _get_cache() -> Cache:
    global _cache_singleton_instance
    if not _cache_singleton_instance:
        _cache_singleton_instance = Cache()
    return _cache_singleton_instance


def add_product(product: Product) -> None:
    _get_cache().add_product(product)


def add_category(site: str, category: Category) -> None:
    _get_cache().add_category(site, category)


def serialize() -> dict:
    return _get_cache().serialize()


def get_products() -> dict[int, Product]:
    return _get_cache().products


def get_categories() -> dict[str, dict[str, Category]]:
    return _get_cache().categories

import atexit
import json
import os
import sys
import time
import typing
from dataclasses import dataclass
from enum import Enum


class SortBy(Enum):
    RELEVANCE = "relevance"
    RATING = "rating"
    SALES = "sales"
    PRICE = "price"
    DATE = "date"
    UPDATED = "updated"
    CATEGORY = "category"
    NAME = "name"
    TRENDING = "trending"
    FEATURED_UNTIL = "featured_until"
from typing import List, Optional

import click
import requests
from larch.pickle import pickle  # type: ignore[import-untyped]


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
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path

    def serialize(self) -> dict[str, str]:
        return {"name": self.name, "path": self.path}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "Category":
        return cls(data["name"], data["path"])


class Cache:
    categories: dict[str, dict[str, Category]]
    products: dict[int, Product]
    cache_file: str

    def __init__(self) -> None:
        self.categories = {}
        self.products = {}
        self.cache_file = ".envato_scrape_cache.pickle"
        self.load()
        atexit.register(self.save)

    def add_category(self, site: str, category: Category) -> None:
        if site not in self.categories:
            self.categories[site] = {}
        self.categories[site][category.path] = category

    def add_product(self, product: Product) -> None:
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
cache = Cache()


class EnvatoSite(Enum):
    AUDIOJUNGLE = "audiojungle"
    THEMEFOREST = "themeforest"
    PHOTODUNE = "photodune"
    CODECANYON = "codecanyon"
    VIDEOHIVE = "videohive"
    GRAPHICRIVER = "graphicriver"
    THREE_D_OCEAN = "3docean"


def check_api_key() -> str:
    """Check if the Envato API key is present in environment variables"""
    api_key = os.environ.get("ENVATO_MARKET_API_KEY")
    if not api_key:
        click.echo(
            "Error: ENVATO_MARKET_API_KEY environment variable is not set", err=True
        )
        click.echo(
            "Please set it using: export ENVATO_MARKET_API_KEY='your_api_key'", err=True
        )
        sys.exit(1)
    return api_key


def make_envato_api_call(
    api_key: str, endpoint: str, params: Optional[dict] = None
) -> typing.Any:
    """Make an API call to the Envato API with 429 retry handling"""
    base_url = "https://api.envato.com/v1/"
    url = base_url + endpoint
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "envato-scrape/0.1.0",
    }

    while True:
        try:
            response = requests.get(url, headers=headers, params=params)

            # Handle 429 status code
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait_time = int(retry_after)
                        click.echo(
                            f"Rate limited. Retrying after {wait_time} seconds...",
                            err=True,
                        )
                        time.sleep(wait_time)
                        continue  # Retry the request
                    except ValueError:
                        click.echo(
                            "Invalid Retry-After header received. "
                            + "Waiting 60 seconds...",
                            err=True,
                        )
                        time.sleep(60)
                        continue
                else:
                    click.echo(
                        "Rate limited but no Retry-After header. "
                        + "Waiting 60 seconds...",
                        err=True,
                    )
                    time.sleep(60)
                    continue

            # For other status codes, raise an exception
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # If it's not a 429 error, exit
            if (
                e.response is not None
                and hasattr(e.response, "status_code")
                and e.response.status_code == 429
            ):
                # This shouldn't happen as we handle 429 above, but just in case
                click.echo(
                    "Rate limited (from exception). Waiting 60 seconds...", err=True
                )
                time.sleep(60)
                continue
            click.echo(f"API request failed: {e}", err=True)
            sys.exit(1)
        except json.JSONDecodeError as e:
            click.echo(f"Failed to parse JSON response: {e}", err=True)
            sys.exit(1)


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Envato Scrape - A CLI tool for scraping Envato"""
    # If no command is provided, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def search_products(
    api_key: str,
    site: str,
    category: Optional[str] = None,
    term: Optional[str] = None,
    page: int = 1,
    sort_by: Optional[str] = None,
    sort_direction: Optional[str] = None,
) -> List[Product]:
    """Search for products on Envato"""
    endpoint = "discovery/search/search/item"
    params = {"site": f"{site}.net", "page": page}

    if category:
        params["category"] = category
    if term:
        params["term"] = term
    if sort_by:
        params["sort_by"] = sort_by
    if sort_direction:
        params["sort_direction"] = sort_direction

    data = make_envato_api_call(api_key, endpoint, params)

    products = []
    if "matches" in data:
        for product_data in data["matches"]:
            product = Product.from_dict(product_data)
            products.append(product)
            # Add to cache
            cache.add_product(product)

    return products


@cli.group()
def categories() -> None:
    """Manage categories"""
    pass


@categories.command("list")
@click.option(
    "--site",
    type=click.Choice([site.value for site in EnvatoSite], case_sensitive=False),
    required=True,
    help="Envato site to list categories from",
)
def _list(site: str) -> None:
    """List categories from a specific Envato site"""
    api_key = check_api_key()
    endpoint = f"market/categories:{site}.json"
    data = make_envato_api_call(api_key, endpoint)

    # Display the categories in a formatted way
    if "categories" in data:
        for category_data in data["categories"]:
            # Create Category instance
            category = Category(category_data["name"], category_data["path"])
            # Add to cache
            cache.add_category(site, category)
            click.echo(f"{category.name} (path: {category.path})")
    else:
        click.echo("No categories found or unexpected response format")


@cli.group()
def fetch() -> None:
    """Add products to the cache"""
    pass


@cli.group()
def inspect() -> None:
    """Inspect cached data"""
    pass


@inspect.command("category-sale-count")
@click.option(
    "--site",
    type=click.Choice([site.value for site in EnvatoSite], case_sensitive=False),
    required=True,
    help="Envato site to analyze",
)
def _inspect_category_sale_count(site: str) -> None:
    """Show sales statistics per category"""
    # Group products by category
    category_stats = {}
    
    # Process each product in the cache
    for product in cache.products.values():
        # Check if the product belongs to the specified site
        if product.site == f"{site}.net":
            # Get the classification which should be the category
            category = product.classification
            if category not in category_stats:
                category_stats[category] = {
                    'product_count': 0,
                    'total_sales': 0,
                    'total_revenue': 0
                }
            category_stats[category]['product_count'] += 1
            category_stats[category]['total_sales'] += product.number_of_sales
            category_stats[category]['total_revenue'] += product.number_of_sales * (float(product.price_cents) / 100.0)
    
    # Calculate average sales per product and prepare for sorting
    results = []
    for category, stats in category_stats.items():
        product_count = stats['product_count']
        total_sales = stats['total_sales']
        total_revenue = stats['total_revenue']
        average_sales = total_sales / product_count if product_count > 0 else 0
        average_revenue = float(total_revenue) / float(product_count) if product_count > 0 else 0
        results.append({
            'category': category,
            'product_count': product_count,
            'total_sales': total_sales,
            'average_sales': average_sales,
            'average_revenue': average_revenue
        })
    
    # Sort by average sales in descending order
    results.sort(key=lambda x: x['average_revenue'], reverse=True)
    
    # Output as CSV with headers
    # Use quotes to handle categories that may contain commas
    click.echo("Category,Products,Total Sales,Average Sales,Average Revenue")
    for result in results:
        # Escape quotes in category names by doubling them
        category = result['category'].replace('"', '""')
        click.echo(f'"{category}",'
                  f'{result["product_count"]},'
                  f'{result["total_sales"]},'
                  f'{result["average_sales"]:.2f},'
                  f'{result["average_revenue"]:.2f}')


@inspect.command("category-head")
@click.option(
    "--site",
    type=click.Choice([site.value for site in EnvatoSite], case_sensitive=False),
    required=True,
    help="Envato site to analyze",
)
@click.option(
    "--category",
    required=True,
    help="Category to analyze",
)
@click.option(
    "-n",
    "--number",
    type=int,
    default=10,
    help="Number of top products to show",
)
def _inspect_category_head(site: str, category: str, number: int) -> None:
    """Show top products in a category sorted by sales"""
    # Filter products by site and category
    filtered_products = []
    for product in cache.products.values():
        if (product.site == f"{site}.net" and 
            product.classification == category):
            filtered_products.append(product)
    
    # Sort by number of sales in descending order
    filtered_products.sort(key=lambda x: x.number_of_sales, reverse=True)
    
    # Take the top n products
    top_products = filtered_products[:number]
    
    # Output as CSV with headers
    click.echo("URL,Title,Sales,Price,Total Revenue,Author Username")
    for product in top_products:
        # Calculate total revenue
        price_dollars = product.price_cents / 100
        total_revenue = product.number_of_sales * price_dollars
        
        # Escape quotes in fields that may contain commas
        title = product.name.replace('"', '""')
        url = product.url.replace('"', '""')
        author_username = product.author_username.replace('"', '""')
        
        click.echo(f'"{url}",'
                  f'"{title}",'
                  f'{product.number_of_sales},'
                  f'{price_dollars:.2f},'
                  f'{total_revenue:.2f},'
                  f'"{author_username}"')


@fetch.command("search-crawl")
@click.option(
    "--site",
    type=click.Choice([site.value for site in EnvatoSite], case_sensitive=False),
    required=True,
    help="Envato site to search on",
)
@click.option(
    "--category",
    help="Category path to filter by (e.g., 'music/ambient')",
)
@click.option(
    "--page",
    help="Search result page",
)
@click.option(
    "--term",
    help="Search term",
)
@click.option(
    "--all-categories",
    is_flag=True,
    help="Crawl all categories in the cache for the specified site",
)
@click.option(
    "--all-pages",
    is_flag=True,
    help="Crawl all pages",
)
@click.option(
    "--sort-by",
    type=click.Choice([sort.value for sort in SortBy], case_sensitive=False),
    help="Sort results by the specified field",
)
@click.option(
    "--sort-direction",
    type=click.Choice(['asc', 'desc'], case_sensitive=False),
    default='desc',
    help="Sort direction (asc or desc)",
)
def _crawl(
    site: str,
    category: Optional[str],
    term: Optional[str],
    all_categories: bool,
    page: Optional[int],
    all_pages: bool,
    sort_by: Optional[str],
    sort_direction: str,
) -> None:
    """Crawl pages from search and add products to cache"""
    click.echo(f"Crawling products on site: {site}")
    if all_categories:
        if category is not None:
            click.echo(
                "Error: Cannot specify both --category and --all-categories", err=True
            )
            sys.exit(1)

        # Get categories from cache
        if site not in cache.categories:
            click.echo(
                f"Error: No categories found in cache for site '{site}'", err=True
            )
            click.echo(
                "Please run 'envato-scrape categories list --site <site>' first "
                + "to populate categories",
                err=True,
            )
            sys.exit(1)
    elif category is None:
        click.echo(
            "Error: Must specify either --category or --all-categories", err=True
        )
        sys.exit(1)

    if all_pages and page is not None:
        click.echo("Error: Cannot specify both --page and --all-pages", err=True)
        sys.exit(1)
    if not all_pages and page is None:
        click.echo("Error: Must specify either --page or --all-pages", err=True)
        sys.exit(1)

    categories_to_crawl: List[Category] = []

    if all_categories:
        # Print category paths
        print(list(cache.categories[site].values()))
        categories_to_crawl = list(cache.categories[site].values())
        category_paths = [cat.path for cat in cache.categories[site].values()]
        click.echo(f"Found categories: {', '.join(category_paths)}")
    else:
        category_obj_list = [
            cat for cat in cache.categories[site].values() if cat.path == category
        ]
        if len(category_obj_list) == 0:
            click.echo(
                f"Error: Category '{category}' not found in cache for site '{site}'",
                err=True,
            )
            sys.exit(1)
        categories_to_crawl = [category_obj_list[0]]

    pages_to_crawl: List[int] = []
    if all_pages:
        pages_to_crawl = list(range(1, 61))
    else:
        assert page is not None
        pages_to_crawl = [page]

    api_key = check_api_key()
    total_products = 0

    click.echo(
        f"Starting crawl on site '{site}' with "
        + (f"category '{category}'" if category else "all categories")
        + f" and term '{term}'"
    )

    # Crawl each category
    for category_obj in categories_to_crawl:
        click.echo(f"Crawling category: {category_obj.path}")
        for page in pages_to_crawl:
            click.echo(f"  Scraping page {page}...")
            products = search_products(
                api_key, 
                site, 
                category_obj.path, 
                term, 
                page,
                sort_by,
                sort_direction
            )
            total_products += len(products)

            if not products:
                click.echo(
                    f"  No more products found on page {page}, moving to next category."
                )
                break

    click.echo(f"Added {total_products} products to cache")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()

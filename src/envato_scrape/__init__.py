import json
import os
import sys
import time
import typing
from enum import Enum
from typing import Any, Callable, Iterable, List, Optional

import click
import requests

from . import cache
from .product import Category, Product


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


class ProductGroupStats:
    product_count: int
    total_sales: int
    total_revenue: float

    def __init__(self) -> None:
        self.product_count = 0
        self.total_sales = 0
        self.total_revenue = 0.0

    def add_product(self, product: Product) -> None:
        self.product_count += 1
        self.total_sales += product.number_of_sales
        self.total_revenue += (product.price_cents / 100.0) * product.number_of_sales


def product_group_stats_group_by(
    group_key: Callable[[Product], str], products: Iterable[Product]
) -> dict[str, ProductGroupStats]:
    stats: dict[str, ProductGroupStats] = {}
    for product in products:
        key = group_key(product)
        if key not in stats:
            stats[key] = ProductGroupStats()
        stats[key].add_product(product)
    return stats


def make_csv(
    data: Iterable[Any], row_callback: Callable[[Any], dict[str, Any]], *, sort_by: str
) -> str:
    """Convert a list of data to CSV format using a row callback to extract fields"""
    rows: List[dict[str, Any]] = [row_callback(item) for item in data]
    if not rows:
        return ""
    # Sort rows by the specified field in descending order
    rows.sort(key=lambda x: x.get(sort_by, 0), reverse=True)
    # Create CSV header
    headers = rows[0].keys()
    csv_lines = [",".join(headers)]
    # Create CSV rows
    for row in rows:
        csv_lines.append(
            ",".join(('"' + str(row[h]).replace('"', '""') + '"') for h in headers)
        )
    return "\n".join(csv_lines)


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
    category_stats = product_group_stats_group_by(
        lambda p: p.classification,
        filter(lambda x: x.site == f"{site}.net", cache.get_products().values()),
    )
    csv: str = make_csv(
        category_stats.items(),
        lambda item: (
            {
                "category": item[0],
                "product_count": item[1].product_count,
                "total_sales": item[1].total_sales,
                "average_sales": (
                    item[1].total_sales / item[1].product_count
                    if item[1].product_count > 0
                    else 0
                ),
                "average_revenue": (
                    item[1].total_revenue / item[1].product_count
                    if item[1].product_count > 0
                    else 0
                ),
                "total_products": cache.get_categories()[site][item[0]].total_products
                or 0,
                "sales_products_ratio": (
                    item[1].total_sales
                    / (cache.get_categories()[site][item[0]].total_products or 1)
                ),
            }
        ),
        sort_by="average_revenue",
    )
    click.echo(csv)


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
    for product in cache.get_products().values():
        if product.site == f"{site}.net" and product.classification == category:
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

        click.echo(
            f'"{url}",'
            f'"{title}",'
            f"{product.number_of_sales},"
            f"{price_dollars:.2f},"
            f"{total_revenue:.2f},"
            f'"{author_username}"'
        )


@fetch.command("category-products")
@click.option(
    "--site",
    type=click.Choice([site.value for site in EnvatoSite], case_sensitive=False),
    required=True,
    help="Envato site to fetch category products for",
)
def fetch_category_sales(site: str) -> None:
    """Fetch total products for each category in the cache"""
    # Check if categories exist in cache
    if site not in cache.get_categories() or not cache.get_categories()[site]:
        click.echo(f"Error: No categories found in cache for site '{site}'", err=True)
        click.echo(
            "Please run 'envato-scrape categories list --site <site>' first "
            + "to populate categories",
            err=True,
        )
        sys.exit(1)

    api_key = check_api_key()

    # Process each category
    for category in cache.get_categories()[site].values():
        click.echo(f"Fetching products for category: {category.path}")

        # Make API call to search endpoint to get total_hits
        endpoint = "discovery/search/search/item"
        params = {
            "site": f"{site}.net",
            "category": category.path,
            "page": 1,
        }

        data = make_envato_api_call(api_key, endpoint, params)

        # Extract total_hits which represents total products
        total_products = data.get("total_hits")
        if total_products is not None:
            # Update the category's total_products field
            category.total_products = total_products
            click.echo(f"  Total products: {total_products}")
        else:
            click.echo("  Could not find total products information", err=True)


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
    type=click.Choice(["asc", "desc"], case_sensitive=False),
    default="desc",
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
        if site not in cache.get_categories():
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
        print(list(cache.get_categories()[site].values()))
        categories_to_crawl = list(cache.get_categories()[site].values())
        category_paths = [cat.path for cat in cache.get_categories()[site].values()]
        click.echo(f"Found categories: {', '.join(category_paths)}")
    else:
        category_obj_list = [
            cat for cat in cache.get_categories()[site].values() if cat.path == category
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
                api_key, site, category_obj.path, term, page, sort_by, sort_direction
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

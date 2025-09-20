import atexit
import json
import os
import sys
import typing
from enum import Enum

import click
import requests


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
    cache_file: str

    def __init__(self) -> None:
        self.categories = {}
        self.cache_file = ".envato_scrape_cache.json"
        self.load()
        atexit.register(self.save)

    def add_category(self, site: str, category: Category) -> None:
        if site not in self.categories:
            self.categories[site] = {}
        self.categories[site][category.name] = category

    def serialize(self) -> dict:
        serialized = {}
        for site, categories in self.categories.items():
            serialized[site] = {
                name: category.serialize() for name, category in categories.items()
            }
        return serialized

    def save(self) -> None:
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.serialize(), f)
        except Exception as e:
            click.echo(f"Failed to save cache: {e}", err=True)

    def load(self) -> None:
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r") as f:
                    data = json.load(f)
                    for site, categories in data.items():
                        self.categories[site] = {}
                        for name, category_data in categories.items():
                            self.categories[site][name] = Category.from_dict(
                                category_data
                            )
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


def make_envato_api_call(api_key: str, endpoint: str) -> typing.Any:
    """Make an API call to the Envato API"""
    base_url = "https://api.envato.com/v1/"
    url = base_url + endpoint
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "envato-scrape/0.1.0",
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
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


@cli.command()
def hello() -> None:
    """Simple greeting command"""
    api_key = check_api_key()
    click.echo("Hello from envato-scrape!")
    # For demonstration, show that we have the API key (masked)
    masked_key = (
        api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]
        if len(api_key) > 8
        else "***"
    )
    click.echo(f"Using API key: {masked_key}")

    # Make a test API call to get username
    data = make_envato_api_call(api_key, "market/private/user/username.json")
    if "username" in data:
        click.echo(f"Connected as user: {data['username']}")
    else:
        click.echo("Could not fetch user information")


@cli.group()
def categories() -> None:
    """Manage categories"""
    pass


@categories.command()
@click.option(
    "--site",
    type=click.Choice([site.value for site in EnvatoSite], case_sensitive=False),
    required=True,
    help="Envato site to list categories from",
)
def list(site: str) -> None:
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


def main() -> None:
    cli()


if __name__ == "__main__":
    main()

from dataclasses import dataclass
from playwright.async_api import Page

@dataclass
class HarnessContext:
    page: Page
    repo_url: str
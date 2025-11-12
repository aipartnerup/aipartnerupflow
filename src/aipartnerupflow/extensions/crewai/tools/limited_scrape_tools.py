"""
Limited Website Scraping Tool for CrewAI
"""
from typing import Dict, Any, Type, List, Optional
from crewai.tools.base_tool import BaseTool
from pydantic import BaseModel, Field
import requests
from bs4 import BeautifulSoup
import re

from aipartnerupflow.core.utils.logger import get_logger
from aipartnerupflow.extensions.crewai.decorators import crew_tool

logger = get_logger(__name__)

class LimitedScrapeWebsiteInputSchema(BaseModel):
    website_url: str = Field(..., description="The URL of the website to scrape")
    max_chars: int = Field(default=5000, description="Maximum characters to extract from the website")
    focus_sections: List[str] = Field(default_factory=list, description="Specific sections to focus on (e.g., ['summary', 'overview', 'about'])")
    exclude_sections: List[str] = Field(default_factory=list, description="Sections to exclude (e.g., ['references', 'external links', 'navigation'])")
    extract_metadata: bool = Field(default=True, description="Whether to extract metadata like title, description, etc.")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Headers to use for the request")


@crew_tool()
class LimitedScrapeWebsiteTool(BaseTool):
    """Tool for scraping website content with character limits to prevent token overflow"""
    name: str = "Limited Website Scraper"
    description: str = "Scrape website content with configurable character limits to prevent token overflow"
    args_schema: Type[BaseModel] = LimitedScrapeWebsiteInputSchema

    def _run(self, website_url: str, max_chars: int = 5000, focus_sections: Optional[List[str]] = None, 
             exclude_sections: Optional[List[str]] = None, extract_metadata: bool = True, headers: Optional[Dict[str, str]] = None) -> str:
        """
        Scrape website content with character limits
        
        Args:
            website_url: URL to scrape
            max_chars: Maximum characters to extract
            focus_sections: Specific sections to focus on
            exclude_sections: Sections to exclude
            extract_metadata: Whether to extract metadata
            
        Returns:
            Limited website content as string
        """
        try:
            if focus_sections is None:
                focus_sections = []
            if exclude_sections is None:
                exclude_sections = ['references', 'external links', 'navigation', 'footer', 'sidebar']
            
            # Set headers to mimic a real browser
            request_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            if headers:
                request_headers.update(headers)

            # Make request
            response = requests.get(website_url, headers=request_headers, timeout=10)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract metadata if requested
            metadata = ""
            if extract_metadata:
                title = soup.find('title')
                if title:
                    metadata += f"Title: {title.get_text().strip()}\n"
                
                description = soup.find('meta', attrs={'name': 'description'})
                if description and hasattr(description, 'get'):
                    content = description.get('content', '')  # type: ignore
                    if content and hasattr(content, 'strip'):
                        metadata += f"Description: {content.strip()}\n"  # type: ignore
                
                metadata += f"URL: {website_url}\n\n"
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'footer', 'aside', 'header']):
                element.decompose()
            
            # Remove sections that should be excluded
            for section_text in exclude_sections:
                # Remove elements with specific text content
                for element in soup.find_all(text=re.compile(section_text, re.IGNORECASE)):
                    if element.parent:
                        element.parent.decompose()
                
                # Remove elements with specific class names or IDs
                for element in soup.find_all(class_=re.compile(section_text, re.IGNORECASE)):
                    element.decompose()
                for element in soup.find_all(id=re.compile(section_text, re.IGNORECASE)):
                    element.decompose()
            
            # Extract main content
            content = ""
            
            # Try to find main content area
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|main|body', re.I))
            
            if main_content:
                content = main_content.get_text(separator=' ', strip=True)
            else:
                # Fallback to body content
                body = soup.find('body')
                if body:
                    content = body.get_text(separator=' ', strip=True)
                else:
                    content = soup.get_text(separator=' ', strip=True)
            
            # Clean up content
            content = re.sub(r'\s+', ' ', content)  # Replace multiple whitespace with single space
            content = content.strip()
            
            # Focus on specific sections if requested
            if focus_sections:
                focused_content = ""
                for section in focus_sections:
                    # Look for headings or paragraphs containing the section keyword
                    for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p']):
                        if re.search(section, element.get_text(), re.IGNORECASE):
                            focused_content += element.get_text() + " "
                            # Include next few paragraphs
                            for sibling in element.find_next_siblings(['p', 'div'])[:3]:
                                focused_content += sibling.get_text() + " "
                
                if focused_content:
                    content = focused_content.strip()
            
            # Combine metadata and content
            full_content = metadata + content
            
            # Limit content length
            if len(full_content) > max_chars:
                full_content = full_content[:max_chars]
                # Try to end at a complete sentence
                last_period = full_content.rfind('.')
                if last_period > max_chars * 0.8:  # If we can find a period in the last 20%
                    full_content = full_content[:last_period + 1]
                else:
                    full_content += "..."
            
            logger.info(f"Scraped {len(full_content)} characters from {website_url}")
            return full_content
            
        except requests.RequestException as e:
            logger.error(f"Request error scraping {website_url}: {str(e)}")
            return f"Error: Could not access {website_url} - {str(e)}"
        except Exception as e:
            logger.error(f"Error scraping {website_url}: {str(e)}")
            return f"Error: Failed to scrape {website_url} - {str(e)}"

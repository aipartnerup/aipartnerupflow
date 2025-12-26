"""
Limited Website Scraping Tool
"""
from typing import Dict, Type, List, Optional
from aipartnerupflow.core.tools import BaseTool, tool_register
from pydantic import BaseModel, Field
import requests
from bs4 import BeautifulSoup

from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

class LimitedScrapeWebsiteInputSchema(BaseModel):
    website_url: str = Field(..., description="The URL of the website to scrape")
    max_chars: int = Field(default=5000, description="Maximum characters to extract from the website")
    focus_sections: List[str] = Field(default_factory=list, description="Specific sections to focus on (e.g., ['summary', 'overview', 'about'])")
    exclude_sections: List[str] = Field(default_factory=list, description="Sections to exclude (e.g., ['references', 'external links', 'navigation'])")
    extract_metadata: bool = Field(default=True, description="Whether to extract metadata like title, description, etc.")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Headers to use for the request")


@tool_register()
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
                exclude_sections = []
            
            # Default headers if not provided
            if headers is None:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            
            # Fetch the webpage
            response = requests.get(website_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract metadata if requested
            result_parts = []
            if extract_metadata:
                title = soup.find('title')
                if title:
                    result_parts.append(f"Title: {title.get_text().strip()}")
                
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc and meta_desc.get('content'):
                    result_parts.append(f"Description: {meta_desc.get('content').strip()}")
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Extract text content
            text_content = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text_content.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text_content = ' '.join(chunk for chunk in chunks if chunk)
            
            # Apply focus/exclude sections if provided
            if focus_sections or exclude_sections:
                # Simple keyword-based filtering
                text_content.lower()
                filtered_content = []
                
                for line in text_content.split('\n'):
                    line_lower = line.lower()
                    should_include = True
                    
                    # Check exclude sections
                    for exclude in exclude_sections:
                        if exclude.lower() in line_lower:
                            should_include = False
                            break
                    
                    # Check focus sections
                    if focus_sections and should_include:
                        should_include = any(focus.lower() in line_lower for focus in focus_sections)
                    
                    if should_include and line.strip():
                        filtered_content.append(line)
                
                text_content = '\n'.join(filtered_content)
            
            # Limit character count
            if len(text_content) > max_chars:
                text_content = text_content[:max_chars]
                text_content += f"\n\n[Content truncated to {max_chars} characters]"
            
            # Combine metadata and content
            if result_parts:
                result = '\n\n'.join(result_parts) + '\n\n' + text_content
            else:
                result = text_content
            
            logger.debug(f"Scraped {len(result)} characters from {website_url}")
            return result
            
        except requests.RequestException as e:
            error_msg = f"Error fetching website {website_url}: {str(e)}"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Error scraping website {website_url}: {str(e)}"
            logger.error(error_msg)
            return error_msg


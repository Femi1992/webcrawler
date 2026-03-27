from typing import List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


class Parser:

    def extract_links(self, html: str, base_url: str) -> List[str]:
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        for tag in soup.find_all('a', href=True):
            href = tag.get('href', '').strip()
            
            if not href:
                continue
            
            # Turn relative links into absolute links
            absolute_url = urljoin(base_url, href)
            
            # Strip fragments — /page#section becomes /page
            parsed = urlparse(absolute_url)
            clean_url = parsed._replace(fragment='').geturl()
            
            # Skip non http links like mailto: and tel:
            if not clean_url.startswith(('http://', 'https://')):
                continue
            
            links.append(clean_url)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_links = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
        
        return unique_links
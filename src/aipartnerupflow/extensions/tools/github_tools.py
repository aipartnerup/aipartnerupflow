"""
GitHub API Tool for Repository Analysis
"""
import aiohttp
import asyncio
import json
from typing import Dict, Any, Optional, Type
from aipartnerupflow.core.tools import BaseTool, tool_register
from pydantic import BaseModel, Field
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class GitHubAnalysisInputSchema(BaseModel):
    """Input schema for GitHub analysis"""
    project: str = Field(description="Project name or organization name to analyze")
    include_repos: bool = Field(default=True, description="Whether to include repository analysis")


@tool_register()
class GitHubAnalysisTool(BaseTool):
    """Tool for analyzing GitHub presence and repositories"""
    name: str = "GitHub Analysis Tool"
    description: str = "Analyze GitHub presence, repositories, and metrics for a project or organization"
    session: Optional[aiohttp.ClientSession] = None
    args_schema: Type[BaseModel] = GitHubAnalysisInputSchema
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    async def _ensure_session(self):
        """Ensure aiohttp session is available"""
        if self.session is None or self.session.closed:
            headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers=headers
            )
    
    async def _close_session(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _run(self, project: str, include_repos: bool = True) -> Dict[str, Any]:
        """Synchronous wrapper for async analysis"""
        return asyncio.run(self._arun(project, include_repos))
    
    async def _arun(self, project: str, include_repos: bool = True) -> Dict[str, Any]:
        """Analyze GitHub presence for a project or organization"""
        try:
            await self._ensure_session()
            
            # Try to find GitHub organization/user
            github_url = f"https://api.github.com/users/{project}"
            
            if not self.session:
                await self._ensure_session()
            
            async with self.session.get(github_url) as response:
                if response.status == 200:
                    user_data = await response.json()
                    
                    result = {
                        "github_project": project,
                        "github_presence_score": 100,
                        "github_repo_count": 0,
                        "github_stars_count": 0,
                        "github_followers_count": user_data.get('followers', 0),
                        "github_following_count": user_data.get('following', 0),
                        "github_public_repos": user_data.get('public_repos', 0),
                        "github_created_at": user_data.get('created_at', ''),
                        "github_type": user_data.get('type', ''),
                        "github_company": user_data.get('company', ''),
                        "github_location": user_data.get('location', ''),
                        "github_bio": user_data.get('bio', ''),
                        "github_blog": user_data.get('blog', ''),
                        "github_twitter_username": user_data.get('twitter_username', ''),
                        "github_hireable": user_data.get('hireable', False)
                    }
                    
                    if include_repos:
                        # Get repositories
                        repos_url = f"https://api.github.com/users/{project}/repos"
                        if self.session:
                            async with self.session.get(repos_url) as repos_response:
                                if repos_response.status == 200:
                                    repos_data = await repos_response.json()
                                
                                # Calculate metrics
                                repo_count = len(repos_data)
                                total_stars = sum(repo.get('stargazers_count', 0) for repo in repos_data)
                                total_forks = sum(repo.get('forks_count', 0) for repo in repos_data)
                                total_watchers = sum(repo.get('watchers_count', 0) for repo in repos_data)
                                
                                # Find most popular repo
                                most_popular_repo = max(repos_data, key=lambda x: x.get('stargazers_count', 0)) if repos_data else None
                                
                                result.update({
                                    "github_repo_count": repo_count,
                                    "github_stars_count": total_stars,
                                    "github_forks_count": total_forks,
                                    "github_watchers_count": total_watchers,
                                    "most_popular_repo": {
                                        "name": most_popular_repo.get('name', '') if most_popular_repo else '',
                                        "stars": most_popular_repo.get('stargazers_count', 0) if most_popular_repo else 0,
                                        "language": most_popular_repo.get('language', '') if most_popular_repo else ''
                                    } if most_popular_repo else None
                                })

                    logger.debug(f"GitHub analysis results: {json.dumps(result)}")
                    return result
                
                elif response.status == 404:
                    # User not found, try organization search
                    return await self._search_organization(project)
                else:
                    return {
                        "github_project": project,
                        "github_presence_score": 0,
                        "github_repo_count": 0,
                        "github_stars_count": 0,
                        "github_followers_count": 0,
                        "error": f"GitHub API request failed with status {response.status}"
                    }
            
        except Exception as e:
            logger.error(f"Error in GitHub analysis: {str(e)}")
            return {
                "github_presence_score": 0,
                "github_repo_count": 0,
                "github_stars_count": 0,
                "github_followers_count": 0,
                "error": str(e)
            }
        finally:
            await self._close_session()
    
    async def _search_organization(self, project: str) -> Dict[str, Any]:
        """Search for organization if user not found"""
        try:
            search_url = f"https://api.github.com/search/users?q={project}+type:org"
            if self.session:
                async with self.session.get(search_url) as response:
                    if response.status == 200:
                        search_data = await response.json()
                        items = search_data.get('items', [])
                        
                        if items:
                            # Found organization, give partial score
                            return {
                                "github_project": project,
                                "github_presence_score": 50,
                                "github_repo_count": 0,
                                "github_stars_count": 0,
                                "github_followers_count": 0,
                                "github_organization_found": True,
                                "github_organization_name": items[0].get('login', ''),
                                "github_organization_url": items[0].get('html_url', '')
                            }
            
            return {
                "github_project": project,
                "github_presence_score": 0,
                "github_repo_count": 0,
                "github_stars_count": 0,
                "github_followers_count": 0,
                "github_organization_found": False
            }
            
        except Exception as e:
            logger.error(f"Error searching GitHub organization: {str(e)}")
            return {
                "github_project": project,
                "github_presence_score": 0,
                "github_repo_count": 0,
                "github_stars_count": 0,
                "github_followers_count": 0,
                "error": str(e)
            }


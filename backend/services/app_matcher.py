"""
Application Matcher Service

This service provides fuzzy and semantic matching for application names,
allowing users to query applications using variations and typos.

Example:
    - "gmail" matches "Gmail API"
    - "smtp mail" matches "SMTP Email Service"
    - "google sheets" matches "Google Sheets Integration"
"""

from typing import List, Dict, Any, Tuple, Optional
from rapidfuzz import fuzz, process
import logging

logger = logging.getLogger(__name__)


class ApplicationMatcher:
    """
    Matches user queries against application names using fuzzy matching.

    Supports multiple matching strategies:
    1. Exact match - Case-insensitive substring matching
    2. Fuzzy match - Handles typos and variations using rapidfuzz
    """

    def __init__(self, fuzzy_threshold: int = 70):
        """
        Initialize the matcher.

        Args:
            fuzzy_threshold: Minimum score (0-100) for fuzzy matches. Default 70.
        """
        self.fuzzy_threshold = fuzzy_threshold

    def exact_match(self, query: str, app_name: str) -> bool:
        """
        Check if query exactly matches app name (case-insensitive substring).

        Args:
            query: User's search query
            app_name: Application name to match against

        Returns:
            True if query is found in app_name
        """
        return query.lower() in app_name.lower()

    def fuzzy_match(
        self,
        query: str,
        app_names: List[str],
        limit: int = 5
    ) -> List[Tuple[str, float, int]]:
        """
        Perform fuzzy matching using rapidfuzz.

        Args:
            query: User's search query
            app_names: List of application names to search
            limit: Maximum number of results to return

        Returns:
            List of tuples: (app_name, score, index)
        """
        if not app_names:
            return []

        # Use token_sort_ratio for better matching of multi-word queries
        # e.g., "smtp mail" matches "Mail SMTP Service"
        results = process.extract(
            query,
            app_names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=self.fuzzy_threshold,
            limit=limit
        )

        return results

    def match_applications(
        self,
        query_names: List[str],
        available_apps: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Match multiple query names against available applications.

        This is the main method that combines exact and fuzzy matching strategies.

        Args:
            query_names: List of application names from user query
            available_apps: List of application dictionaries with at least 'app_name' field

        Returns:
            List of matched application dictionaries (deduplicated)

        Example:
            >>> matcher = ApplicationMatcher()
            >>> apps = [
            ...     {"app_id": "1", "app_name": "Gmail API"},
            ...     {"app_id": "2", "app_name": "SMTP Email Service"}
            ... ]
            >>> results = matcher.match_applications(["gmail", "email"], apps)
            >>> len(results)
            2
        """
        if not query_names or not available_apps:
            return []

        matched_apps = {}  # Use dict to deduplicate by app_id

        for query in query_names:
            query = query.strip()
            if not query:
                continue

            logger.info(f"Matching query: '{query}' against {len(available_apps)} apps")

            # Strategy 1: Exact match (case-insensitive substring)
            exact_matches = []
            for app in available_apps:
                app_name = app.get("app_name", "")
                if self.exact_match(query, app_name):
                    exact_matches.append(app)
                    app_id = app.get("app_id")
                    if app_id:
                        matched_apps[app_id] = app

            if exact_matches:
                logger.info(f"  Found {len(exact_matches)} exact matches for '{query}'")
                continue

            # Strategy 2: Fuzzy match
            app_names = [app.get("app_name", "") for app in available_apps]
            fuzzy_results = self.fuzzy_match(query, app_names, limit=5)

            if fuzzy_results:
                logger.info(f"  Found {len(fuzzy_results)} fuzzy matches for '{query}':")
                for app_name, score, idx in fuzzy_results:
                    logger.info(f"    - {app_name} (score: {score:.1f})")
                    app = available_apps[idx]
                    app_id = app.get("app_id")
                    if app_id:
                        matched_apps[app_id] = app
            else:
                logger.warning(f"  No matches found for '{query}'")

        # Return deduplicated list
        result = list(matched_apps.values())
        logger.info(f"Total matched applications: {len(result)}")
        return result

    def get_best_match(
        self,
        query: str,
        available_apps: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Get the single best match for a query.

        Args:
            query: User's search query
            available_apps: List of application dictionaries

        Returns:
            Best matching application or None
        """
        matches = self.match_applications([query], available_apps)
        return matches[0] if matches else None


# Singleton instance for reuse
_matcher_instance: Optional[ApplicationMatcher] = None


def get_matcher(fuzzy_threshold: int = 70) -> ApplicationMatcher:
    """
    Get or create a singleton ApplicationMatcher instance.

    Args:
        fuzzy_threshold: Minimum score for fuzzy matches

    Returns:
        ApplicationMatcher instance
    """
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = ApplicationMatcher(fuzzy_threshold=fuzzy_threshold)
    return _matcher_instance

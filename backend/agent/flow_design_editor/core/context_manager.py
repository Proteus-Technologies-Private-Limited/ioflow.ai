"""
Context Manager for Flow Designer V2

Manages conversation context and token optimization through intelligent
summarization, reference management, and context windowing.
"""

import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass, field, asdict
from collections import deque, defaultdict
import tiktoken

logger = logging.getLogger(__name__)


@dataclass
class ContextItem:
    """Represents an item in the context"""
    id: str
    type: str  # 'app', 'service', 'parameter', 'validation', 'example'
    content: Any
    token_count: int
    importance: int  # 1-10, higher is more important
    accessed_count: int = 0
    last_accessed: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    expires_at: Optional[str] = None

    def touch(self):
        """Mark item as accessed"""
        self.accessed_count += 1
        self.last_accessed = datetime.utcnow().isoformat()


@dataclass
class ContextWindow:
    """Manages a sliding window of context"""
    max_tokens: int
    current_tokens: int = 0
    items: List[ContextItem] = field(default_factory=list)
    eviction_queue: deque = field(default_factory=deque)


class ContextManager:
    """
    Manages context for flow design conversations to optimize token usage.
    Uses intelligent caching, summarization, and reference management.
    """

    def __init__(self, max_context_tokens: int = 8000,
                 summary_threshold: int = 4000):
        """
        Initialize context manager.

        Args:
            max_context_tokens: Maximum tokens allowed in context
            summary_threshold: Token count that triggers summarization
        """
        self.max_context_tokens = max_context_tokens
        self.summary_threshold = summary_threshold

        # Token encoder
        try:
            self.encoder = tiktoken.get_encoding("cl100k_base")
        except:
            logger.warning("tiktoken not available, using character count estimation")
            self.encoder = None

        # Context storage
        self.context_items: Dict[str, ContextItem] = {}
        self.context_window = ContextWindow(max_tokens=max_context_tokens)

        # Reference management
        self.references: Dict[str, str] = {}  # ref_id -> full_id mapping
        self.ref_counter = 0

        # Summaries
        self.summaries: Dict[str, str] = {}

        # Cache for frequently accessed items
        self.access_frequency: defaultdict = defaultdict(int)

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Args:
            text: Text to count

        Returns:
            Token count
        """
        if self.encoder:
            return len(self.encoder.encode(text))
        else:
            # Rough estimation: 1 token ≈ 4 characters
            return len(text) // 4

    def add_context(self, item_type: str, content: Any,
                   importance: int = 5, ttl_minutes: int = 30) -> str:
        """
        Add an item to context.

        Args:
            item_type: Type of context item
            content: Content to add
            importance: Importance level (1-10)
            ttl_minutes: Time-to-live in minutes

        Returns:
            Context item ID
        """
        # Generate ID
        content_str = json.dumps(content) if isinstance(content, dict) else str(content)
        item_id = hashlib.md5(f"{item_type}:{content_str}".encode()).hexdigest()[:12]

        # Check if already exists
        if item_id in self.context_items:
            self.context_items[item_id].touch()
            return item_id

        # Count tokens
        token_count = self.count_tokens(content_str)

        # Create context item
        expires_at = (datetime.utcnow() + timedelta(minutes=ttl_minutes)).isoformat()
        item = ContextItem(
            id=item_id,
            type=item_type,
            content=content,
            token_count=token_count,
            importance=importance,
            expires_at=expires_at
        )

        # Store item
        self.context_items[item_id] = item

        # Add to window if space available
        self._add_to_window(item)

        # Create reference if large
        if token_count > 500:
            ref_id = self._create_reference(item_id)
            logger.info(f"Created reference {ref_id} for large item {item_id}")

        logger.debug(f"Added context item {item_id} ({item_type}, {token_count} tokens)")
        return item_id

    def get_context(self, item_id: str) -> Optional[Any]:
        """
        Get a context item by ID.

        Args:
            item_id: Item ID or reference ID

        Returns:
            Context content or None
        """
        # Check if it's a reference
        if item_id.startswith("ref_"):
            item_id = self.references.get(item_id, item_id)

        item = self.context_items.get(item_id)
        if item:
            item.touch()
            self.access_frequency[item_id] += 1
            return item.content

        return None

    def get_relevant_context(self, query: str, max_tokens: int = 2000) -> List[Dict[str, Any]]:
        """
        Get relevant context for a query.

        Args:
            query: Query string
            max_tokens: Maximum tokens to return

        Returns:
            List of relevant context items
        """
        relevant_items = []
        total_tokens = 0
        query_lower = query.lower()

        # Score items by relevance
        scored_items = []
        for item in self.context_window.items:
            score = self._calculate_relevance(item, query_lower)
            if score > 0:
                scored_items.append((score, item))

        # Sort by score and importance
        scored_items.sort(key=lambda x: (x[0], x[1].importance), reverse=True)

        # Add items up to token limit
        for score, item in scored_items:
            if total_tokens + item.token_count <= max_tokens:
                relevant_items.append({
                    "id": item.id,
                    "type": item.type,
                    "content": self._get_compressed_content(item),
                    "score": score
                })
                total_tokens += item.token_count

        logger.debug(f"Retrieved {len(relevant_items)} relevant items ({total_tokens} tokens)")
        return relevant_items

    def summarize_context(self, context_type: Optional[str] = None) -> str:
        """
        Create a summary of current context.

        Args:
            context_type: Optional type filter

        Returns:
            Context summary
        """
        items_by_type = defaultdict(list)

        for item in self.context_window.items:
            if context_type is None or item.type == context_type:
                items_by_type[item.type].append(item)

        summary_parts = []

        for item_type, items in items_by_type.items():
            if item_type == "app":
                apps = [item.content.get("name", "unknown") for item in items[:5]]
                summary_parts.append(f"Applications: {', '.join(apps)}")

            elif item_type == "service":
                services = [item.content.get("name", "unknown") for item in items[:5]]
                summary_parts.append(f"Services: {', '.join(services)}")

            elif item_type == "parameter":
                params = [item.content.get("name", "unknown") for item in items[:5]]
                summary_parts.append(f"Parameters: {', '.join(params)}")

            elif item_type == "validation":
                errors = sum(1 for item in items if item.content.get("has_errors"))
                summary_parts.append(f"Validations: {len(items)} ({errors} with errors)")

        summary = " | ".join(summary_parts)

        # Store summary
        summary_id = hashlib.md5(summary.encode()).hexdigest()[:8]
        self.summaries[summary_id] = summary

        logger.info(f"Generated summary: {summary[:100]}...")
        return summary

    def create_reference_map(self) -> Dict[str, str]:
        """
        Create a map of references for frequently accessed items.

        Returns:
            Reference map
        """
        ref_map = {}

        # Sort by access frequency
        frequent_items = sorted(
            self.access_frequency.items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]  # Top 20 most accessed

        for item_id, freq in frequent_items:
            if item_id not in self.references.values():
                ref_id = self._create_reference(item_id)
                ref_map[ref_id] = item_id

        return ref_map

    def optimize_context(self) -> Tuple[int, int]:
        """
        Optimize context by removing expired items and summarizing.

        Returns:
            Tuple of (items_removed, tokens_freed)
        """
        items_removed = 0
        tokens_freed = 0

        # Remove expired items
        expired = []
        now = datetime.utcnow()

        for item_id, item in self.context_items.items():
            if item.expires_at and datetime.fromisoformat(item.expires_at) < now:
                expired.append(item_id)
                tokens_freed += item.token_count

        for item_id in expired:
            del self.context_items[item_id]
            items_removed += 1

        # Remove from window
        self.context_window.items = [
            item for item in self.context_window.items
            if item.id not in expired
        ]
        self.context_window.current_tokens -= tokens_freed

        # Trigger summarization if needed
        if self.context_window.current_tokens > self.summary_threshold:
            self._trigger_summarization()

        logger.info(f"Optimized context: removed {items_removed} items, freed {tokens_freed} tokens")
        return items_removed, tokens_freed

    def get_context_stats(self) -> Dict[str, Any]:
        """
        Get statistics about current context.

        Returns:
            Context statistics
        """
        type_counts = defaultdict(int)
        type_tokens = defaultdict(int)

        for item in self.context_window.items:
            type_counts[item.type] += 1
            type_tokens[item.type] += item.token_count

        return {
            "total_items": len(self.context_items),
            "window_items": len(self.context_window.items),
            "current_tokens": self.context_window.current_tokens,
            "max_tokens": self.max_context_tokens,
            "utilization": f"{(self.context_window.current_tokens / self.max_context_tokens * 100):.1f}%",
            "items_by_type": dict(type_counts),
            "tokens_by_type": dict(type_tokens),
            "references_count": len(self.references),
            "summaries_count": len(self.summaries)
        }

    def _add_to_window(self, item: ContextItem):
        """Add item to context window with eviction if needed."""
        # Check if we need to evict
        while (self.context_window.current_tokens + item.token_count >
               self.context_window.max_tokens and
               self.context_window.items):

            # Find least important, least accessed item
            victim = min(
                self.context_window.items,
                key=lambda x: (x.importance, x.accessed_count, x.last_accessed)
            )

            self.context_window.items.remove(victim)
            self.context_window.current_tokens -= victim.token_count
            logger.debug(f"Evicted item {victim.id} from context window")

        # Add new item
        self.context_window.items.append(item)
        self.context_window.current_tokens += item.token_count

    def _create_reference(self, item_id: str) -> str:
        """Create a short reference for an item."""
        ref_id = f"ref_{self.ref_counter:04d}"
        self.references[ref_id] = item_id
        self.ref_counter += 1
        return ref_id

    def _calculate_relevance(self, item: ContextItem, query: str) -> float:
        """Calculate relevance score for an item."""
        score = 0.0
        content_str = json.dumps(item.content) if isinstance(item.content, dict) else str(item.content)
        content_lower = content_str.lower()

        # Direct match
        if query in content_lower:
            score += 10.0

        # Word matches
        query_words = query.split()
        for word in query_words:
            if len(word) > 3 and word in content_lower:
                score += 2.0

        # Type relevance
        type_keywords = {
            "app": ["application", "app", "service"],
            "service": ["service", "api", "endpoint"],
            "parameter": ["param", "arg", "input", "field"],
            "validation": ["error", "valid", "check", "issue"]
        }

        for keyword in type_keywords.get(item.type, []):
            if keyword in query:
                score += 3.0

        # Boost for recent access
        if item.accessed_count > 0:
            score += min(item.accessed_count, 5)

        # Importance factor
        score *= (item.importance / 10.0)

        return score

    def _get_compressed_content(self, item: ContextItem) -> Any:
        """Get compressed version of content for large items."""
        if item.token_count < 200:
            return item.content

        if isinstance(item.content, dict):
            # Return only essential fields
            compressed = {}
            essential_fields = ["id", "name", "type", "description", "required"]

            for field in essential_fields:
                if field in item.content:
                    compressed[field] = item.content[field]

            # Add field count indicator
            compressed["_fields_total"] = len(item.content)
            compressed["_compressed"] = True

            return compressed
        else:
            # Truncate string content
            content_str = str(item.content)
            if len(content_str) > 500:
                return content_str[:500] + "... [truncated]"
            return content_str

    def _trigger_summarization(self):
        """Trigger automatic summarization of old context."""
        # Find items to summarize (old, low importance)
        candidates = sorted(
            self.context_window.items,
            key=lambda x: (x.last_accessed, x.importance)
        )[:10]  # Bottom 10

        if len(candidates) < 3:
            return

        # Group by type and summarize
        by_type = defaultdict(list)
        for item in candidates:
            by_type[item.type].append(item)

        for item_type, items in by_type.items():
            summary = self._create_type_summary(item_type, items)

            # Replace items with summary
            summary_item = ContextItem(
                id=f"summary_{item_type}_{len(self.summaries)}",
                type="summary",
                content=summary,
                token_count=self.count_tokens(summary),
                importance=3,
                expires_at=items[0].expires_at
            )

            # Remove original items
            for item in items:
                self.context_window.items.remove(item)
                self.context_window.current_tokens -= item.token_count

            # Add summary
            self._add_to_window(summary_item)

        logger.info(f"Summarized {len(candidates)} items into {len(by_type)} summaries")

    def _create_type_summary(self, item_type: str, items: List[ContextItem]) -> str:
        """Create a summary for items of the same type."""
        if item_type == "app":
            names = [item.content.get("name", "?") for item in items]
            return f"Previously discussed applications: {', '.join(names)}"

        elif item_type == "service":
            names = [item.content.get("name", "?") for item in items]
            return f"Previously used services: {', '.join(names)}"

        elif item_type == "parameter":
            return f"Configured {len(items)} parameters previously"

        elif item_type == "validation":
            errors = sum(1 for item in items if item.content.get("has_errors"))
            return f"Performed {len(items)} validations ({errors} had issues)"

        else:
            return f"Processed {len(items)} {item_type} items"


# Singleton instance
_context_manager: Optional[ContextManager] = None

def get_context_manager() -> ContextManager:
    """Get or create the global context manager instance."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
"""
Text processing tools for Flow Agent System
"""
import re
from typing import List, Dict, Any


def word_count(text: str) -> dict:
    """
    Count words, characters, and lines in a text.

    Args:
        text: The text to analyze

    Returns:
        A dictionary with word count, character count, and line count
    """
    words = text.split()
    lines = text.split('\n')
    characters = len(text)
    characters_no_spaces = len(text.replace(' ', '').replace('\n', '').replace('\t', ''))

    return {
        "success": True,
        "word_count": len(words),
        "character_count": characters,
        "character_count_no_spaces": characters_no_spaces,
        "line_count": len(lines),
        "average_word_length": sum(len(word) for word in words) / len(words) if words else 0
    }


def extract_emails(text: str) -> dict:
    """
    Extract email addresses from text.

    Args:
        text: The text to search for email addresses

    Returns:
        A dictionary with found email addresses
    """
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)

    return {
        "success": True,
        "emails": emails,
        "count": len(emails)
    }


def extract_urls(text: str) -> dict:
    """
    Extract URLs from text.

    Args:
        text: The text to search for URLs

    Returns:
        A dictionary with found URLs
    """
    url_pattern = r'https?://(?:[-\w.])+(?::\d+)?(?:[/\w\s\-._~:/?#[\]@!$&\'()*+,;=]*)?'
    urls = re.findall(url_pattern, text)

    return {
        "success": True,
        "urls": urls,
        "count": len(urls)
    }


def text_summary(text: str, max_length: int = 100) -> dict:
    """
    Create a simple summary of text by extracting the beginning.

    Args:
        text: The text to summarize
        max_length: Maximum length of the summary

    Returns:
        A dictionary with the text summary
    """
    if len(text) <= max_length:
        summary = text
    else:
        summary = text[:max_length].rsplit(' ', 1)[0] + '...'

    return {
        "success": True,
        "original_length": len(text),
        "summary": summary,
        "summary_length": len(summary)
    }


def replace_text(text: str, find: str, replace: str) -> dict:
    """
    Replace all occurrences of a string in text.

    Args:
        text: The text to process
        find: The string to find
        replace: The string to replace with

    Returns:
        A dictionary with the modified text
    """
    modified_text = text.replace(find, replace)
    count = text.count(find)

    return {
        "success": True,
        "original_text": text,
        "modified_text": modified_text,
        "replacements_made": count
    }


def text_to_list(text: str, delimiter: str = ',') -> dict:
    """
    Convert text to a list by splitting on a delimiter.

    Args:
        text: The text to split
        delimiter: The delimiter to split on (default: comma)

    Returns:
        A dictionary with the resulting list
    """
    items = [item.strip() for item in text.split(delimiter)]

    return {
        "success": True,
        "items": items,
        "count": len(items)
    }
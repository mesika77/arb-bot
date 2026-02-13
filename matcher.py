from typing import List, Dict, Tuple
from datetime import timedelta
from difflib import SequenceMatcher


def calculate_title_similarity(title1: str, title2: str) -> float:
    """
    Calculate similarity between two titles using SequenceMatcher.
    
    Returns:
        Similarity score between 0.0 and 1.0
    """
    return SequenceMatcher(None, title1.lower(), title2.lower()).ratio()


def match_events(
    polymarket_events: List[Dict],
    kalshi_events: List[Dict],
    title_similarity_threshold: float = 0.7,
    date_tolerance_days: int = 1,
    debug: bool = False
) -> List[Tuple[Dict, Dict]]:
    """
    Match events between Polymarket and another platform (e.g., Manifold) based on resolution date and title similarity.
    
    Args:
        polymarket_events: List of normalized Polymarket events
        kalshi_events: List of normalized events from the other platform (generic parameter name)
        title_similarity_threshold: Minimum similarity score (0.0-1.0) to consider a match
        date_tolerance_days: Maximum days difference in resolution dates to consider
        debug: If True, print debug information about matching attempts
        
    Returns:
        List of matched event pairs: [(pm_event, other_platform_event), ...]
    """
    matched_pairs = []
    
    if debug:
        print(f"  [DEBUG] Matching {len(polymarket_events)} PM events against {len(kalshi_events)} Manifold events")
        print(f"  [DEBUG] Threshold: {title_similarity_threshold:.2f}, Date tolerance: {date_tolerance_days} days")
    
    top_similarities = []  # Track top similarities for debugging
    
    for pm_event in polymarket_events:
        pm_end_date = pm_event['end_date']
        pm_title = pm_event['title']
        
        best_match = None
        best_similarity = 0.0
        date_filtered_count = 0
        similarity_filtered_count = 0
        
        for kalshi_event in kalshi_events:
            kalshi_end_date = kalshi_event['end_date']
            kalshi_title = kalshi_event['title']
            
            # Check date match (within tolerance)
            date_diff_seconds = abs((pm_end_date - kalshi_end_date).total_seconds())
            date_diff_days = date_diff_seconds / 86400
            max_diff_seconds = date_tolerance_days * 24 * 60 * 60
            
            if date_diff_seconds > max_diff_seconds:
                date_filtered_count += 1
                continue
            
            # Calculate title similarity
            similarity = calculate_title_similarity(pm_title, kalshi_title)
            
            # Track top similarities for debugging
            if debug and similarity > 0.3:  # Only track reasonable similarities
                top_similarities.append({
                    'pm_title': pm_title[:50],
                    'manifold_title': kalshi_title[:50],
                    'similarity': similarity,
                    'date_diff_days': date_diff_days
                })
            
            if similarity >= title_similarity_threshold and similarity > best_similarity:
                best_match = kalshi_event
                best_similarity = similarity
            elif similarity < title_similarity_threshold:
                similarity_filtered_count += 1
        
        if best_match is not None:
            matched_pairs.append((pm_event, best_match))
            if debug:
                date_diff = abs((pm_end_date - best_match['end_date']).total_seconds() / 86400)
                print(f"    ✓ MATCH: '{pm_title[:45]}' <-> '{best_match['title'][:45]}'")
                print(f"      Similarity: {best_similarity:.3f}, Date diff: {date_diff:.1f} days")
        elif debug and len(polymarket_events) <= 5:  # Only show details for small sets
            print(f"    ✗ No match for: '{pm_title[:50]}'")
            print(f"      Date filtered: {date_filtered_count}, Similarity filtered: {similarity_filtered_count}")
    
    if debug and top_similarities:
        # Show top 5 similarities that didn't match
        top_similarities.sort(key=lambda x: x['similarity'], reverse=True)
        print(f"  [DEBUG] Top similarities (below threshold):")
        for i, item in enumerate(top_similarities[:5], 1):
            print(f"    {i}. {item['similarity']:.3f} | Date diff: {item['date_diff_days']:.1f}d")
            print(f"       PM: '{item['pm_title']}'")
            print(f"       MF: '{item['manifold_title']}'")
    
    return matched_pairs
